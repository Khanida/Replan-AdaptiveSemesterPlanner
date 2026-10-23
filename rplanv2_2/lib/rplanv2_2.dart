import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'planner.dart';

class ReplanApp extends StatelessWidget {
  const ReplanApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Replan 2.2',
    debugShowCheckedModeBanner: false,
    themeMode: ThemeMode.system,
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xffff985a),
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: const Color(0xfffff8f5),
    ),
    darkTheme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xffff985a),
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xff141114),
    ),
    home: const PlannerPage(),
  );
}

class PlannerPage extends StatefulWidget {
  const PlannerPage({super.key, this.readPlan, this.writePlan});
  final Future<String?> Function()? readPlan;
  final Future<void> Function(String)? writePlan;
  @override
  State<PlannerPage> createState() => _PlannerPageState();
}

class _PlannerPageState extends State<PlannerPage> {
  late final _storage = SharedPreferencesAsync();
  List<Course> _courses = [];
  List<Session> _sessions = [];
  DateTime _start = day(DateTime.now());
  int _daily = 150, _hours = 12, _unscheduled = 0, _tab = 0;
  bool _loading = true, _restoreFailed = false;
  String? _unreadable;
  String _planId = newPlanIdentity();
  Map<String, Map<String, int>> _availability = {'weekdays': {}, 'dates': {}};
  String _filter = 'All', _search = '';
  Future<void> _writes = Future.value();

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _message(String text) {
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _load() async {
    try {
      final raw =
          await (widget.readPlan?.call() ?? _storage.getString('rplanv2_2'));
      _unreadable = raw;
      if (raw != null) {
        final snapshot = PlanSnapshot.fromJson(
          jsonDecode(raw) as Map<String, dynamic>,
        );
        if (!mounted) return;
        setState(() => _apply(snapshot));
      }
    } catch (_) {
      _restoreFailed = true;
      _message(
        'Saved plan needs recovery. Export the original data or import a valid backup. Autosave is paused.',
      );
    }
    if (mounted) setState(() => _loading = false);
  }

  void _save() {
    if (_restoreFailed) return;
    final snapshot = jsonEncode(_snapshot().toJson());
    _writes = _writes
        .then(
          (_) =>
              widget.writePlan?.call(snapshot) ??
              _storage.setString('rplanv2_2', snapshot),
        )
        .catchError((Object e) {
          _message(
            'Could not save this change. Keep the app open and try again.',
          );
        });
  }

  PlanSnapshot _snapshot() => PlanSnapshot(
    _courses,
    _sessions,
    _start,
    _daily,
    _hours,
    _unscheduled,
    _availability,
    planId: _planId,
  );

  void _apply(PlanSnapshot snapshot) {
    _courses = snapshot.courses;
    _sessions = snapshot.sessions;
    _start = snapshot.start;
    _daily = snapshot.daily;
    _hours = snapshot.hours;
    _unscheduled = snapshot.unscheduled;
    _availability = snapshot.availability;
    _planId = snapshot.planId;
  }

  Future<void> _exportBackup({bool original = false}) async {
    try {
      final text = original
          ? _unreadable!
          : const JsonEncoder.withIndent('  ').convert(_snapshot().toJson());
      final name = original ? 'replan-recovery.json' : 'replan-flutter.json';
      if (!kIsWeb &&
          (defaultTargetPlatform == TargetPlatform.android ||
              defaultTargetPlatform == TargetPlatform.iOS)) {
        await Clipboard.setData(ClipboardData(text: text));
        _message(
          'Backup copied. Paste it into a file outside this app to keep a recoverable copy.',
        );
        return;
      }
      final file = XFile.fromData(
        Uint8List.fromList(utf8.encode(text)),
        mimeType: 'application/json',
        name: name,
      );
      if (kIsWeb) {
        await file.saveTo(name);
      } else {
        final destination = await getSaveLocation(suggestedName: name);
        if (destination == null) return;
        await file.saveTo(destination.path);
      }
      _message('Backup exported. Keep it outside the app.');
    } catch (_) {
      _message('Could not export backup. Your saved plan is unchanged.');
    }
  }

  Future<void> _importBackup() async {
    try {
      final file = await openFile(
        acceptedTypeGroups: [
          const XTypeGroup(
            label: 'Replan JSON backup',
            extensions: ['json'],
            uniformTypeIdentifiers: ['public.json'],
          ),
        ],
      );
      if (file == null) return;
      if (await file.length() > 20000000)
        throw const FormatException('Backup exceeds 20 MB');
      final snapshot = PlanSnapshot.fromJson(
        jsonDecode(await file.readAsString()) as Map<String, dynamic>,
      );
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Restore this backup?'),
          content: Text(
            '${snapshot.courses.length} courses and ${snapshot.sessions.length} sessions will replace the current plan. Export a backup first if you need the current plan. Browser backups are converted to whole minutes; missed history is omitted.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Restore'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      // Retain the unreadable original before allowing any replacement write.
      await _writes;
      if (_restoreFailed && _unreadable != null)
        await _storage.setString('rplanv2_2_recovery', _unreadable!);
      await _storage.setString('rplanv2_2', jsonEncode(snapshot.toJson()));
      if (!mounted) return;
      setState(() {
        _apply(snapshot);
        _restoreFailed = false;
      });
      _message('Backup restored.');
    } catch (_) {
      _message('Could not import this backup. The existing plan is unchanged.');
    }
  }

  Future<void> _availabilityDialog() async {
    final weekdays = List.generate(
      7,
      (i) => TextEditingController(
        text: _availability['weekdays']?['$i']?.toString() ?? '',
      ),
    );
    final exceptions = TextEditingController(
      text: (_availability['dates'] ?? {}).entries
          .map((e) => '${e.key} = ${e.value}')
          .join('\n'),
    );
    const names = [
      'Sunday',
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
    ];
    String? error;
    final value = await showDialog<Map<String, Map<String, int>>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Study availability'),
          content: SizedBox(
            width: 440,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Optional minutes per weekday. Blank uses daily capacity; 0 is a day off. Date exceptions override weekdays.',
                  ),
                  for (var i = 0; i < 7; i++)
                    TextField(
                      controller: weekdays[i],
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: names[i],
                        hintText: 'Daily capacity',
                      ),
                    ),
                  TextField(
                    controller: exceptions,
                    minLines: 2,
                    maxLines: 6,
                    decoration: const InputDecoration(
                      labelText: 'Date exceptions',
                      hintText: '2026-12-01 = 0\n2026-12-02 = 90',
                    ),
                  ),
                  if (error != null) Text(error!),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                try {
                  final availability = <String, Map<String, int>>{
                    'weekdays': {},
                    'dates': {},
                  };
                  for (var i = 0; i < 7; i++) {
                    if (weekdays[i].text.trim().isNotEmpty)
                      availability['weekdays']!['$i'] = int.parse(
                        weekdays[i].text.trim(),
                      );
                  }
                  for (final line
                      in exceptions.text
                          .split('\n')
                          .where((t) => t.trim().isNotEmpty)) {
                    final parts = line.split('=');
                    if (parts.length != 2) throw const FormatException();
                    final date = dateLabel(checkedDate(parts[0].trim()));
                    availability['dates']![date] = int.parse(parts[1].trim());
                  }
                  final candidate = _snapshot().toJson();
                  candidate['availability'] = availability;
                  Navigator.pop(
                    context,
                    PlanSnapshot.fromJson(candidate).availability,
                  );
                } catch (_) {
                  update(
                    () => error =
                        'Use 0–1440 minutes and date exceptions as YYYY-MM-DD = minutes.',
                  );
                }
              },
              child: const Text('Apply'),
            ),
          ],
        ),
      ),
    );
    await Future<void>.delayed(const Duration(milliseconds: 300));
    for (final controller in weekdays) {
      controller.dispose();
    }
    exceptions.dispose();
    if (value != null && mounted) {
      setState(() => _availability = value);
      _rebuild(notify: false);
    }
  }

  void _rebuild({bool notify = true}) {
    final today = day(DateTime.now());
    final result = schedule(
      _courses,
      _sessions,
      _start.isAfter(today) ? _start : today,
      _daily,
      _hours,
      availability: _availability,
    );
    setState(() {
      _sessions = result.sessions;
      _unscheduled = result.unscheduled;
    });
    _save();
    if (notify) _message('Roadmap rebuilt. Completed work is preserved.');
  }

  void _demo() {
    final now = day(DateTime.now());
    setState(() {
      _start = now;
      _courses = [
        Course(
          'demo-code',
          'Programming',
          4,
          DateTime(now.year, now.month, now.day + 45),
          [
            'Functions & parameters',
            'Objects & classes',
            'Data structures',
            'Practice problems',
          ],
        ),
        Course(
          'demo-math',
          'Calculus',
          3,
          DateTime(now.year, now.month, now.day + 35),
          ['Limits', 'Derivatives', 'Integration', 'Past papers'],
        ),
        Course(
          'demo-net',
          'Networks',
          3,
          DateTime(now.year, now.month, now.day + 50),
          ['OSI model', 'Routing', 'Transport protocols', 'Revision'],
        ),
      ];
      _sessions = [];
    });
    _rebuild(notify: false);
  }

  Future<void> _courseDialog() async {
    final name = TextEditingController(),
        credits = TextEditingController(text: '3'),
        outline = TextEditingController(),
        estimates = TextEditingController();
    final form = GlobalKey<FormState>();
    var exam = DateTime(_start.year, _start.month, _start.day + 60);
    final course = await showDialog<Course>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Add a course'),
          content: SizedBox(
            width: 440,
            child: Form(
              key: form,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextFormField(
                      controller: name,
                      decoration: const InputDecoration(
                        labelText: 'Course name',
                      ),
                      validator: (v) =>
                          v == null || v.trim().isEmpty || v.trim().length > 100
                          ? 'Enter 1–100 characters'
                          : _courses.any(
                              (c) =>
                                  c.name.toLowerCase() ==
                                  v.trim().toLowerCase(),
                            )
                          ? 'Course name already exists'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: credits,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Credit hours',
                      ),
                      validator: (v) {
                        final n = int.tryParse(v ?? '');
                        return n == null || n < 1 || n > 12
                            ? 'Use 1–12 credits'
                            : null;
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: outline,
                      minLines: 4,
                      maxLines: 8,
                      decoration: const InputDecoration(
                        labelText: 'Topics (one per line)',
                        alignLabelWithHint: true,
                      ),
                      validator: (v) {
                        final topics = (v ?? '')
                            .split('\n')
                            .map((t) => t.trim())
                            .where((t) => t.isNotEmpty)
                            .toList();
                        return topics.isEmpty ||
                                topics.length > 150 ||
                                topics.any((t) => t.length > 300) ||
                                topics
                                        .map((t) => t.toLowerCase())
                                        .toSet()
                                        .length !=
                                    topics.length
                            ? 'Enter 1–150 unique topics, up to 300 characters each'
                            : null;
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: estimates,
                      minLines: 2,
                      maxLines: 6,
                      decoration: const InputDecoration(
                        labelText: 'Minutes per topic (optional, one per line)',
                      ),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) return null;
                        final values = v.trim().split('\n');
                        final topics = outline.text
                            .split('\n')
                            .map((t) => t.trim())
                            .where((t) => t.isNotEmpty)
                            .toSet()
                            .toList();
                        return values.length != topics.length ||
                                values.any(
                                  (t) =>
                                      int.tryParse(t.trim()) == null ||
                                      int.parse(t.trim()) < 1 ||
                                      int.parse(t.trim()) > 600000,
                                )
                            ? 'Enter 1–600000 minutes for each topic'
                            : null;
                      },
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.event),
                      label: Text('Exam: ${dateLabel(exam)}'),
                      onPressed: () async {
                        final selected = await showDatePicker(
                          context: context,
                          initialDate: exam,
                          firstDate: day(DateTime.now()),
                          lastDate: DateTime(DateTime.now().year + 5),
                        );
                        if (selected != null) update(() => exam = selected);
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                if (!form.currentState!.validate()) return;
                if (!exam.isAfter(_start) ||
                    !exam.isAfter(day(DateTime.now()))) {
                  _message('Choose an exam after today and the plan start.');
                  return;
                }
                final topics = outline.text
                    .split('\n')
                    .map((s) => s.trim())
                    .where((s) => s.isNotEmpty)
                    .toSet()
                    .toList();
                final minutes = estimates.text.trim().isEmpty
                    ? <String, int>{}
                    : Map<String, int>.fromIterables(
                        topics,
                        estimates.text
                            .trim()
                            .split('\n')
                            .map((v) => int.parse(v.trim())),
                      );
                Navigator.pop(
                  context,
                  Course(
                    DateTime.now().microsecondsSinceEpoch.toString(),
                    name.text.trim(),
                    int.parse(credits.text),
                    exam,
                    topics,
                    topicMinutes: minutes,
                  ),
                );
              },
              child: const Text('Add course'),
            ),
          ],
        ),
      ),
    );
    // Controllers may still be referenced during the dialog's closing animation.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    name.dispose();
    credits.dispose();
    outline.dispose();
    estimates.dispose();
    if (course != null && mounted) {
      setState(() => _courses.add(course));
      _rebuild(notify: false);
    }
  }

  Future<void> _remove(Course c) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Remove ${c.name}?'),
        content: const Text('This removes the course and its study progress.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      setState(() {
        _courses.remove(c);
        _sessions.removeWhere((s) => s.courseId == c.id);
      });
      _rebuild(notify: false);
    }
  }

  Course _course(Session s) => _courses.firstWhere((c) => c.id == s.courseId);
  Widget _panel(Widget child) => Card(
    child: Padding(padding: const EdgeInsets.all(20), child: child),
  );
  Widget _heading(String title, String subtitle) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(
            context,
          ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          subtitle,
          style: TextStyle(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    ),
  );

  Widget _session(Session s) => Card(
    child: CheckboxListTile(
      value: s.done,
      onChanged: (v) {
        setState(() => s.done = v!);
        _save();
      },
      title: Text(
        s.topic,
        style: TextStyle(
          decoration: s.done ? TextDecoration.lineThrough : null,
        ),
      ),
      subtitle: Text(
        '${_course(s).name} · ${dateLabel(s.date)} · ${s.minutes} min',
      ),
      secondary: Icon(s.done ? Icons.task_alt : Icons.menu_book_outlined),
      controlAffinity: ListTileControlAffinity.trailing,
    ),
  );

  Widget _dashboard() {
    final today = day(DateTime.now());
    final todayWork = _sessions.where((s) => s.date == today).toList();
    final total = _sessions.fold(0, (int n, s) => n + s.minutes) + _unscheduled;
    final done = _sessions
        .where((s) => s.done)
        .fold(0, (int n, s) => n + s.minutes);
    final overdue = _sessions
        .where((s) => !s.done && s.date.isBefore(today))
        .length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _heading(
          'Your semester. Replanned.',
          'Small steps today. A calmer exam season.',
        ),
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'MAKE ROOM FOR PROGRESS',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.primary,
                  letterSpacing: 2,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                '${total == 0 ? 0 : (100 * done / total).round()}% of your study journey complete',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              LinearProgressIndicator(
                value: total == 0 ? 0 : done / total,
                minHeight: 8,
              ),
              const SizedBox(height: 16),
              Text(
                '${_courses.length} courses  ·  ${(done / 60).toStringAsFixed(1)} hours done  ·  ${((total - done) / 60).toStringAsFixed(1)} hours left',
              ),
            ],
          ),
        ),
        if (_unscheduled > 0)
          _panel(
            Text(
              '${(_unscheduled / 60).toStringAsFixed(1)} hours cannot fit before exams. Increase daily capacity, reduce workload, or review deadlines.',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (overdue > 0)
          _panel(
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$overdue unfinished sessions are overdue.'),
                TextButton.icon(
                  onPressed: _rebuild,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Replan from today'),
                ),
              ],
            ),
          ),
        const SizedBox(height: 24),
        Text('Today’s study', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        if (todayWork.isEmpty)
          _panel(
            const Text(
              'No sessions today. Add a course or check your roadmap.',
            ),
          ),
        ...todayWork.map(_session),
        if (_courses.isEmpty && !_restoreFailed)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: FilledButton.tonalIcon(
              onPressed: _demo,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Try the 3-course demo'),
            ),
          ),
      ],
    );
  }

  Widget _courseList() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _heading(
        'Your courses',
        'Use topic estimates or divide the credit-based estimate equally. Replanning moves unfinished work; it does not predict learning performance.',
      ),
      for (final c in _courses)
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.school_outlined,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      c.name,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  IconButton(
                    onPressed: () => _remove(c),
                    tooltip: 'Remove course',
                    icon: const Icon(Icons.delete_outline),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '${c.credits} credits · Exam ${dateLabel(c.exam)} · ${(c.topics.fold(0, (int n, t) => n + (c.topicMinutes[t] ?? (c.credits * _hours * 60 ~/ c.topics.length))) / 60).toStringAsFixed(1)} study hours',
              ),
              const SizedBox(height: 12),
              ...c.topics.map(
                (t) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text('• $t'),
                ),
              ),
            ],
          ),
        ),
      if (_courses.isEmpty)
        _panel(
          const Text('Add your first course and paste its topic outline.'),
        ),
      const SizedBox(height: 16),
      FilledButton.icon(
        onPressed: _restoreFailed ? null : _courseDialog,
        icon: const Icon(Icons.add),
        label: const Text('Add course'),
      ),
    ],
  );

  Widget _roadmap() {
    final rows = _sessions.where((s) {
      final matches = '${_course(s).name} ${s.topic}'.toLowerCase().contains(
        _search.toLowerCase(),
      );
      return matches &&
          (_filter == 'All' ||
              (_filter == 'Done' && s.done) ||
              (_filter == 'Pending' && !s.done) ||
              (_filter == 'Today' && s.date == day(DateTime.now())));
    }).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _heading(
          'Study roadmap',
          'Check off completed sessions. Replan unfinished work when life happens.',
        ),
        OutlinedButton.icon(
          onPressed: _rebuild,
          icon: const Icon(Icons.refresh),
          label: const Text('Replan from today'),
        ),
        const SizedBox(height: 16),
        TextField(
          onChanged: (v) => setState(() => _search = v),
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: 'Find a course or topic',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          children: ['All', 'Today', 'Pending', 'Done']
              .map(
                (f) => ChoiceChip(
                  label: Text(f),
                  selected: _filter == f,
                  onSelected: (_) => setState(() => _filter = f),
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 16),
        Text('${rows.length} sessions'),
        const SizedBox(height: 8),
        if (rows.isEmpty) _panel(const Text('No sessions match this view.')),
        ...rows.map(_session),
      ],
    );
  }

  Widget _settings() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _heading(
        'Plan your pace',
        'Changes rebuild pending sessions and preserve completed work.',
      ),
      _panel(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Daily study capacity: ${(_daily / 60).toStringAsFixed(1)} hours',
            ),
            Slider(
              value: _daily.toDouble(),
              min: 0,
              max: 1440,
              divisions: 48,
              label: '${(_daily / 60).toStringAsFixed(1)} h',
              onChanged: (v) => setState(() => _daily = v.round()),
              onChangeEnd: (_) => _rebuild(notify: false),
            ),
            const SizedBox(height: 16),
            Text('Study hours per credit: $_hours'),
            Slider(
              value: _hours.toDouble(),
              min: 1,
              max: 100,
              divisions: 99,
              label: '$_hours h',
              onChanged: (v) => setState(() => _hours = v.round()),
              onChangeEnd: (_) => _rebuild(notify: false),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              icon: const Icon(Icons.event),
              label: Text('Start: ${dateLabel(_start)}'),
              onPressed: () async {
                final now = day(DateTime.now());
                final selected = await showDatePicker(
                  context: context,
                  initialDate: _start.isBefore(now) ? now : _start,
                  firstDate: now,
                  lastDate: DateTime(now.year + 5),
                );
                if (selected != null && mounted) {
                  setState(() => _start = selected);
                  _rebuild(notify: false);
                }
              },
            ),
          ],
        ),
      ),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          OutlinedButton(
            onPressed: () => _exportBackup(original: _restoreFailed),
            child: Text(
              _restoreFailed ? 'Export original data' : 'Export JSON backup',
            ),
          ),
          OutlinedButton(
            onPressed: _importBackup,
            child: const Text('Import JSON backup'),
          ),
          OutlinedButton(
            onPressed: _availabilityDialog,
            child: const Text('Availability overrides'),
          ),
        ],
      ),
      if (_restoreFailed)
        const Text(
          'Recovery mode: autosave is paused. Export the original data, then import a valid backup.',
        ),
      _panel(
        const Text(
          'Plans save locally on this device. Sessions are allocated before each course’s exam, within your daily capacity. Replanning starts today or your future start date.',
        ),
      ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 800;
    const destinations = [
      NavigationDestination(
        icon: Icon(Icons.dashboard_outlined),
        label: 'Today',
      ),
      NavigationDestination(
        icon: Icon(Icons.school_outlined),
        label: 'Courses',
      ),
      NavigationDestination(icon: Icon(Icons.route_outlined), label: 'Roadmap'),
      NavigationDestination(icon: Icon(Icons.tune), label: 'Settings'),
    ];
    final body = _loading
        ? const Center(child: CircularProgressIndicator())
        : SingleChildScrollView(
            padding: EdgeInsets.all(wide ? 32 : 16),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 960),
                child: switch (_tab) {
                  0 => _dashboard(),
                  1 => _courseList(),
                  2 => _roadmap(),
                  _ => _settings(),
                },
              ),
            ),
          );
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'replan / 2.2',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: [
          if (!_loading)
            IconButton(
              onPressed: _importBackup,
              tooltip: 'Import JSON backup',
              icon: const Icon(Icons.file_open_outlined),
            ),
          if (_restoreFailed)
            IconButton(
              onPressed: () => _exportBackup(original: true),
              tooltip: 'Export original data',
              icon: const Icon(Icons.save_alt),
            ),
          if (!_loading && !_restoreFailed)
            IconButton(
              onPressed: _courseDialog,
              tooltip: 'Add course',
              icon: const Icon(Icons.add),
            ),
        ],
      ),
      body: wide
          ? Row(
              children: [
                NavigationRail(
                  selectedIndex: _tab,
                  onDestinationSelected: (i) => setState(() => _tab = i),
                  labelType: NavigationRailLabelType.all,
                  destinations: destinations
                      .map(
                        (d) => NavigationRailDestination(
                          icon: d.icon,
                          label: Text(d.label),
                        ),
                      )
                      .toList(),
                ),
                const VerticalDivider(width: 1),
                Expanded(child: body),
              ],
            )
          : body,
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: _tab,
              onDestinationSelected: (i) => setState(() => _tab = i),
              destinations: destinations,
            ),
    );
  }
}
