import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'planner.dart';

class ReplanApp extends StatelessWidget {
  const ReplanApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Replan 2.2', debugShowCheckedModeBanner: false,
    themeMode: ThemeMode.system,
    theme: ThemeData(useMaterial3: true, brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xffff985a), brightness: Brightness.light),
      scaffoldBackgroundColor: const Color(0xfffff8f5)),
    darkTheme: ThemeData(useMaterial3: true, brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xffff985a), brightness: Brightness.dark),
      scaffoldBackgroundColor: const Color(0xff141114)),
    home: const PlannerPage(),
  );
}

class PlannerPage extends StatefulWidget {
  const PlannerPage({super.key});
  @override
  State<PlannerPage> createState() => _PlannerPageState();
}

class _PlannerPageState extends State<PlannerPage> {
  final _storage = SharedPreferencesAsync();
  List<Course> _courses = [];
  List<Session> _sessions = [];
  DateTime _start = day(DateTime.now());
  int _daily = 150, _hours = 12, _unscheduled = 0, _tab = 0;
  bool _loading = true;
  String _filter = 'All', _search = '';
  Future<void> _writes = Future.value();

  @override
  void initState() { super.initState(); _load(); }

  void _message(String text) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _load() async {
    try {
      final raw = await _storage.getString('rplanv2_2');
      if (raw != null) {
        final j = jsonDecode(raw) as Map<String, dynamic>;
        final courses = (j['courses'] as List).map((c) => Course.fromJson(Map<String, dynamic>.from(c))).toList();
        final sessions = (j['sessions'] as List).map((s) => Session.fromJson(Map<String, dynamic>.from(s))).toList();
        if (!mounted) return;
        setState(() {
          _courses = courses; _sessions = sessions;
          _start = DateTime.parse(j['start']); _daily = j['daily'];
          _hours = j['hours']; _unscheduled = j['unscheduled'];
        });
      }
    } catch (_) { _message('Could not restore your saved plan. Storage has not been overwritten.'); }
    if (mounted) setState(() => _loading = false);
  }

  void _save() {
    final snapshot = jsonEncode({'courses': _courses.map((c) => c.toJson()).toList(),
      'sessions': _sessions.map((s) => s.toJson()).toList(), 'start': _start.toIso8601String(),
      'daily': _daily, 'hours': _hours, 'unscheduled': _unscheduled});
    _writes = _writes.then((_) => _storage.setString('rplanv2_2', snapshot)).catchError((Object e) {
      _message('Could not save this change. Keep the app open and try again.');
    });
  }

  void _rebuild({bool notify = true}) {
    final today = day(DateTime.now());
    final result = schedule(_courses, _sessions, _start.isAfter(today) ? _start : today, _daily, _hours);
    setState(() { _sessions = result.sessions; _unscheduled = result.unscheduled; });
    _save();
    if (notify) _message('Roadmap rebuilt. Completed work is preserved.');
  }

  void _demo() {
    final now = day(DateTime.now());
    setState(() {
      _start = now;
      _courses = [
        Course('demo-code', 'Programming', 4, DateTime(now.year, now.month, now.day + 45), ['Functions & parameters', 'Objects & classes', 'Data structures', 'Practice problems']),
        Course('demo-math', 'Calculus', 3, DateTime(now.year, now.month, now.day + 35), ['Limits', 'Derivatives', 'Integration', 'Past papers']),
        Course('demo-net', 'Networks', 3, DateTime(now.year, now.month, now.day + 50), ['OSI model', 'Routing', 'Transport protocols', 'Revision']),
      ];
      _sessions = [];
    });
    _rebuild(notify: false);
  }

  Future<void> _courseDialog() async {
    final name = TextEditingController(), credits = TextEditingController(text: '3'), outline = TextEditingController();
    final form = GlobalKey<FormState>();
    var exam = DateTime(_start.year, _start.month, _start.day + 60);
    final course = await showDialog<Course>(context: context, builder: (context) => StatefulBuilder(builder: (context, update) => AlertDialog(
      title: const Text('Add a course'),
      content: SizedBox(width: 440, child: Form(key: form, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextFormField(controller: name, decoration: const InputDecoration(labelText: 'Course name'), validator: (v) => v == null || v.trim().isEmpty ? 'Enter a course name' : null),
        const SizedBox(height: 12),
        TextFormField(controller: credits, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Credit hours'), validator: (v) {
          final n = int.tryParse(v ?? ''); return n == null || n < 1 || n > 12 ? 'Use 1–12 credits' : null;
        }),
        const SizedBox(height: 12),
        TextFormField(controller: outline, minLines: 4, maxLines: 8, decoration: const InputDecoration(labelText: 'Topics (one per line)', alignLabelWithHint: true), validator: (v) => v == null || v.trim().isEmpty ? 'Add at least one topic' : null),
        const SizedBox(height: 12),
        OutlinedButton.icon(icon: const Icon(Icons.event), label: Text('Exam: ${dateLabel(exam)}'), onPressed: () async {
          final selected = await showDatePicker(context: context, initialDate: exam, firstDate: day(DateTime.now()), lastDate: DateTime(DateTime.now().year + 5));
          if (selected != null) update(() => exam = selected);
        }),
      ])))),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: () {
          if (!form.currentState!.validate()) return;
          if (!exam.isAfter(_start) || !exam.isAfter(day(DateTime.now()))) {
            _message('Choose an exam after today and the plan start.'); return;
          }
          Navigator.pop(context, Course(DateTime.now().microsecondsSinceEpoch.toString(), name.text.trim(), int.parse(credits.text), exam,
            outline.text.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toSet().toList()));
        }, child: const Text('Add course'))],
    )));
    // Controllers may still be referenced during the dialog's closing animation.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    name.dispose(); credits.dispose(); outline.dispose();
    if (course != null && mounted) { setState(() => _courses.add(course)); _rebuild(notify: false); }
  }

  Future<void> _remove(Course c) async {
    final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: Text('Remove ${c.name}?'), content: const Text('This removes the course and its study progress.'),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Remove'))]));
    if (confirmed == true && mounted) {
      setState(() { _courses.remove(c); _sessions.removeWhere((s) => s.courseId == c.id); });
      _rebuild(notify: false);
    }
  }

  Course _course(Session s) => _courses.firstWhere((c) => c.id == s.courseId);
  Widget _panel(Widget child) => Card(child: Padding(padding: const EdgeInsets.all(20), child: child));
  Widget _heading(String title, String subtitle) => Padding(padding: const EdgeInsets.only(bottom: 20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
    const SizedBox(height: 8), Text(subtitle, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
  ]));

  Widget _session(Session s) => Card(child: CheckboxListTile(
    value: s.done, onChanged: (v) { setState(() => s.done = v!); _save(); },
    title: Text(s.topic, style: TextStyle(decoration: s.done ? TextDecoration.lineThrough : null)),
    subtitle: Text('${_course(s).name} · ${dateLabel(s.date)} · ${s.minutes} min'),
    secondary: Icon(s.done ? Icons.task_alt : Icons.menu_book_outlined),
    controlAffinity: ListTileControlAffinity.trailing,
  ));

  Widget _dashboard() {
    final today = day(DateTime.now());
    final todayWork = _sessions.where((s) => s.date == today).toList();
    final total = _sessions.fold(0, (int n, s) => n + s.minutes) + _unscheduled;
    final done = _sessions.where((s) => s.done).fold(0, (int n, s) => n + s.minutes);
    final overdue = _sessions.where((s) => !s.done && s.date.isBefore(today)).length;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _heading('Your semester. Replanned.', 'Small steps today. A calmer exam season.'),
      _panel(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('MAKE ROOM FOR PROGRESS', style: TextStyle(color: Theme.of(context).colorScheme.primary, letterSpacing: 2, fontSize: 12)),
        const SizedBox(height: 16), Text('${total == 0 ? 0 : (100 * done / total).round()}% of your study journey complete', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 16), LinearProgressIndicator(value: total == 0 ? 0 : done / total, minHeight: 8),
        const SizedBox(height: 16), Text('${_courses.length} courses  ·  ${(done / 60).toStringAsFixed(1)} hours done  ·  ${((total - done) / 60).toStringAsFixed(1)} hours left'),
      ])),
      if (_unscheduled > 0) _panel(Text('${(_unscheduled / 60).toStringAsFixed(1)} hours cannot fit before exams. Increase daily capacity, reduce workload, or review deadlines.', style: TextStyle(color: Theme.of(context).colorScheme.error))),
      if (overdue > 0) _panel(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('$overdue unfinished sessions are overdue.'),
        TextButton.icon(onPressed: _rebuild, icon: const Icon(Icons.refresh), label: const Text('Replan from today')),
      ])),
      const SizedBox(height: 24), Text('Today’s study', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 12),
      if (todayWork.isEmpty) _panel(const Text('No sessions today. Add a course or check your roadmap.')),
      ...todayWork.map(_session),
      if (_courses.isEmpty) Padding(padding: const EdgeInsets.only(top: 16), child: FilledButton.tonalIcon(onPressed: _demo, icon: const Icon(Icons.auto_awesome), label: const Text('Try the 3-course demo'))),
    ]);
  }

  Widget _courseList() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    _heading('Your courses', 'Workload = credits × study hours per credit. Topics share the workload equally.'),
    for (final c in _courses) _panel(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [Icon(Icons.school_outlined, color: Theme.of(context).colorScheme.primary), const SizedBox(width: 12),
        Expanded(child: Text(c.name, style: Theme.of(context).textTheme.titleLarge)),
        IconButton(onPressed: () => _remove(c), tooltip: 'Remove course', icon: const Icon(Icons.delete_outline))]),
      const SizedBox(height: 8), Text('${c.credits} credits · Exam ${dateLabel(c.exam)} · ${c.credits * _hours} study hours'),
      const SizedBox(height: 12), ...c.topics.map((t) => Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $t'))),
    ])),
    if (_courses.isEmpty) _panel(const Text('Add your first course and paste its topic outline.')),
    const SizedBox(height: 16), FilledButton.icon(onPressed: _courseDialog, icon: const Icon(Icons.add), label: const Text('Add course')),
  ]);

  Widget _roadmap() {
    final rows = _sessions.where((s) {
      final matches = '${_course(s).name} ${s.topic}'.toLowerCase().contains(_search.toLowerCase());
      return matches && (_filter == 'All' || (_filter == 'Done' && s.done) || (_filter == 'Pending' && !s.done) || (_filter == 'Today' && s.date == day(DateTime.now())));
    }).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _heading('Study roadmap', 'Check off completed sessions. Replan unfinished work when life happens.'),
      OutlinedButton.icon(onPressed: _rebuild, icon: const Icon(Icons.refresh), label: const Text('Replan from today')),
      const SizedBox(height: 16), TextField(onChanged: (v) => setState(() => _search = v), decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Find a course or topic', border: OutlineInputBorder())),
      const SizedBox(height: 12), Wrap(spacing: 8, children: ['All', 'Today', 'Pending', 'Done'].map((f) => ChoiceChip(label: Text(f), selected: _filter == f, onSelected: (_) => setState(() => _filter = f))).toList()),
      const SizedBox(height: 16), Text('${rows.length} sessions'), const SizedBox(height: 8),
      if (rows.isEmpty) _panel(const Text('No sessions match this view.')),
      ...rows.map(_session),
    ]);
  }

  Widget _settings() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    _heading('Plan your pace', 'Changes rebuild pending sessions and preserve completed work.'),
    _panel(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Daily study capacity: ${(_daily / 60).toStringAsFixed(1)} hours'),
      Slider(value: _daily.toDouble(), min: 30, max: 480, divisions: 15, label: '${(_daily / 60).toStringAsFixed(1)} h', onChanged: (v) => setState(() => _daily = v.round()), onChangeEnd: (_) => _rebuild(notify: false)),
      const SizedBox(height: 16), Text('Study hours per credit: $_hours'),
      Slider(value: _hours.toDouble(), min: 1, max: 40, divisions: 39, label: '$_hours h', onChanged: (v) => setState(() => _hours = v.round()), onChangeEnd: (_) => _rebuild(notify: false)),
      const SizedBox(height: 16), OutlinedButton.icon(icon: const Icon(Icons.event), label: Text('Start: ${dateLabel(_start)}'), onPressed: () async {
        final now = day(DateTime.now());
        final selected = await showDatePicker(context: context, initialDate: _start.isBefore(now) ? now : _start, firstDate: now, lastDate: DateTime(now.year + 5));
        if (selected != null && mounted) { setState(() => _start = selected); _rebuild(notify: false); }
      }),
    ])),
    _panel(const Text('Plans save locally on this device. Sessions are allocated before each course’s exam, within your daily capacity. Replanning starts today or your future start date.')),
  ]);

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 800;
    const destinations = [NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Today'), NavigationDestination(icon: Icon(Icons.school_outlined), label: 'Courses'), NavigationDestination(icon: Icon(Icons.route_outlined), label: 'Roadmap'), NavigationDestination(icon: Icon(Icons.tune), label: 'Settings')];
    final body = _loading ? const Center(child: CircularProgressIndicator()) : SingleChildScrollView(
      padding: EdgeInsets.all(wide ? 32 : 16), child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 960),
        child: switch (_tab) { 0 => _dashboard(), 1 => _courseList(), 2 => _roadmap(), _ => _settings() })));
    return Scaffold(
      appBar: AppBar(title: const Text('replan / 2.2', style: TextStyle(fontWeight: FontWeight.w800)), actions: [if (!_loading) IconButton(onPressed: _courseDialog, tooltip: 'Add course', icon: const Icon(Icons.add))]),
      body: wide ? Row(children: [NavigationRail(selectedIndex: _tab, onDestinationSelected: (i) => setState(() => _tab = i), labelType: NavigationRailLabelType.all,
        destinations: destinations.map((d) => NavigationRailDestination(icon: d.icon, label: Text(d.label))).toList()), const VerticalDivider(width: 1), Expanded(child: body)]) : body,
      bottomNavigationBar: wide ? null : NavigationBar(selectedIndex: _tab, onDestinationSelected: (i) => setState(() => _tab = i), destinations: destinations),
    );
  }
}
