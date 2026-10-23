import 'dart:math';

DateTime day(DateTime d) => DateTime(d.year, d.month, d.day);
String dateLabel(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class Course {
  Course(
    this.id,
    this.name,
    this.credits,
    this.exam,
    this.topics, {
    this.topicMinutes = const {},
  });
  final String id, name;
  final num credits;
  final DateTime exam;
  final List<String> topics;
  final Map<String, int> topicMinutes;
  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'credits': credits,
    'exam': exam.toIso8601String(),
    'topics': topics,
    'topicMinutes': topicMinutes,
  };
  factory Course.fromJson(Map<String, dynamic> j) {
    final course = Course(
      j['id'],
      j['name'],
      j['credits'],
      checkedDate(j['exam']),
      List<String>.from(j['topics']),
      topicMinutes: Map<String, int>.from(j['topicMinutes'] ?? {}),
    );
    validateCourse(course);
    return course;
  }
}

class Session {
  Session(
    this.courseId,
    this.topic,
    this.date,
    this.minutes, {
    this.done = false,
  });
  final String courseId, topic;
  final DateTime date;
  final int minutes;
  bool done;
  Map<String, dynamic> toJson() => {
    'courseId': courseId,
    'topic': topic,
    'date': date.toIso8601String(),
    'minutes': minutes,
    'done': done,
  };
  factory Session.fromJson(Map<String, dynamic> j) {
    if (j['minutes'] is! int ||
        j['minutes'] < 1 ||
        j['minutes'] > 1440 ||
        j['done'] is! bool) {
      throw const FormatException('Invalid session');
    }
    return Session(
      j['courseId'],
      j['topic'],
      checkedDate(j['date']),
      j['minutes'],
      done: j['done'],
    );
  }
}

class PlanResult {
  PlanResult(this.sessions, this.unscheduled);
  final List<Session> sessions;
  final int unscheduled;
}

// Daily course rotation, initially ordered by exam date and credits. All work is in minutes;
// completed work consumes capacity and is never regenerated.
PlanResult schedule(
  List<Course> courses,
  List<Session> previous,
  DateTime start,
  int dailyMinutes,
  int hoursPerCredit, {
  Map<String, Map<String, int>> availability = const {},
}) {
  if (dailyMinutes < 0 ||
      dailyMinutes > 1440 ||
      hoursPerCredit < 1 ||
      hoursPerCredit > 100)
    throw ArgumentError('Invalid capacity or workload');
  for (final c in courses) {
    validateCourse(c);
  }
  final sessions = previous.where((s) => s.done).toList();
  final used = <String, int>{};
  for (final s in sessions) {
    used.update(
      dateLabel(s.date),
      (v) => v + s.minutes,
      ifAbsent: () => s.minutes,
    );
  }
  final sorted = [...courses]
    ..sort((a, b) {
      final comparison = a.exam.compareTo(b.exam);
      if (comparison != 0) return comparison;
      final credits = b.credits.compareTo(a.credits);
      return credits == 0 ? a.name.compareTo(b.name) : credits;
    });
  final remaining = <String, List<int>>{};
  for (final c in sorted) {
    final total = (c.credits * hoursPerCredit * 60).round();
    remaining[c.id] = List.generate(c.topics.length, (i) {
      final target =
          c.topicMinutes[c.topics[i]] ??
          (total ~/ c.topics.length + (i < total % c.topics.length ? 1 : 0));
      final completed = sessions
          .where((s) => s.courseId == c.id && s.topic == c.topics[i])
          .fold(0, (int n, s) => n + s.minutes);
      return max(0, target - completed);
    });
  }
  var queue = [...sorted];
  final end = sorted.fold(
    day(start),
    (DateTime end, c) => c.exam.isAfter(end) ? day(c.exam) : end,
  );
  if (end.difference(day(start)).inDays > 1827)
    throw ArgumentError('Choose exams within five years of the plan start');
  for (
    var date = day(start);
    date.isBefore(end);
    date = DateTime(date.year, date.month, date.day + 1)
  ) {
    final key = dateLabel(date);
    final capacity =
        availability['dates']?[key] ??
        availability['weekdays']?['${date.weekday % 7}'] ??
        dailyMinutes;
    var budget = max(0, capacity - (used[key] ?? 0));
    queue = queue
        .where(
          (c) =>
              date.isBefore(day(c.exam)) && remaining[c.id]!.any((m) => m > 0),
        )
        .toList();
    final selected = {
      for (final c in queue) c.id: remaining[c.id]!.indexWhere((m) => m > 0),
    };
    final served = <String>{};
    var changed = true;
    while (budget > 0 && changed) {
      changed = false;
      for (final c in queue) {
        if (budget == 0) break;
        final i = selected[c.id]!;
        final amount = min(budget, min(60, remaining[c.id]![i]));
        if (amount == 0) continue;
        sessions.add(Session(c.id, c.topics[i], date, amount));
        remaining[c.id]![i] -= amount;
        budget -= amount;
        served.add(c.id);
        changed = true;
      }
    }
    queue = [
      ...queue.where((c) => !served.contains(c.id)),
      ...queue.where((c) => served.contains(c.id)),
    ];
  }
  final unscheduled = remaining.values
      .expand((m) => m)
      .fold(0, (int n, m) => n + m);
  sessions.sort((a, b) => a.date.compareTo(b.date));
  return PlanResult(sessions, unscheduled);
}

/// Decode the entire snapshot before replacing any live state.
class PlanSnapshot {
  PlanSnapshot(
    this.courses,
    this.sessions,
    this.start,
    this.daily,
    this.hours,
    this.unscheduled,
    this.availability, {
    String? planId,
  }) : planId = planId ?? newPlanIdentity();
  final List<Course> courses;
  final List<Session> sessions;
  final DateTime start;
  final int daily, hours, unscheduled;
  final String planId;
  final Map<String, Map<String, int>> availability;

  Map<String, dynamic> toJson() => {
    'version': 1,
    'app': 'Replan Flutter',
    'planId': planId,
    'courses': courses.map((c) => c.toJson()).toList(),
    'sessions': sessions.map((s) => s.toJson()).toList(),
    'start': dateLabel(start),
    'daily': daily,
    'hours': hours,
    'unscheduled': unscheduled,
    'availability': availability,
  };

  factory PlanSnapshot.fromJson(Map<String, dynamic> j) {
    if (j['rows'] is List && j['courses'] is List) j = browserBackupToNative(j);
    if (j['version'] != null && j['version'] != 1) {
      throw const FormatException('Unsupported backup version');
    }
    int integer(dynamic value, int min, int max) {
      if (value is! int || value < min || value > max) {
        throw const FormatException('Invalid numeric setting');
      }
      return value;
    }

    final daily = integer(j['daily'], 0, 1440);
    final hours = integer(j['hours'], 1, 100);
    final start = checkedDate(j['start']);
    if (j['courses'] is! List ||
        (j['courses'] as List).length > 50 ||
        j['sessions'] is! List ||
        (j['sessions'] as List).length > 100000) {
      throw const FormatException('Invalid or oversized plan');
    }
    final courses = (j['courses'] as List)
        .map((c) => Course.fromJson(Map<String, dynamic>.from(c)))
        .toList();
    final ids = <String>{};
    final names = <String>{};
    for (final c in courses) {
      if (!ids.add(c.id) || !names.add(c.name.toLowerCase()))
        throw const FormatException('Duplicate course ID or name');
    }
    final sessions = (j['sessions'] as List)
        .map((s) => Session.fromJson(Map<String, dynamic>.from(s)))
        .toList();
    for (final s in sessions) {
      final matches = courses.where((c) => c.id == s.courseId);
      if (matches.isEmpty ||
          !matches.first.topics.contains(s.topic) ||
          !s.date.isBefore(matches.first.exam)) {
        throw const FormatException(
          'Session has an invalid course, topic or date',
        );
      }
    }
    var expectedUnscheduled = 0;
    for (final c in courses) {
      final total = (c.credits * hours * 60).round();
      for (var i = 0; i < c.topics.length; i++) {
        final topic = c.topics[i];
        final target =
            c.topicMinutes[topic] ??
            (total ~/ c.topics.length + (i < total % c.topics.length ? 1 : 0));
        final rows = sessions.where(
          (s) => s.courseId == c.id && s.topic == topic,
        );
        final completed = rows
            .where((s) => s.done)
            .fold(0, (int n, s) => n + s.minutes);
        final allocated = rows.fold(0, (int n, s) => n + s.minutes);
        final retainedTarget = max(target, completed);
        if (allocated > retainedTarget)
          throw const FormatException('Sessions exceed topic workload');
        expectedUnscheduled += retainedTarget - allocated;
      }
    }
    if (integer(j['unscheduled'], 0, 100000000) != expectedUnscheduled) {
      throw const FormatException(
        'Unscheduled workload does not match the plan',
      );
    }
    final availability = <String, Map<String, int>>{
      'weekdays': {},
      'dates': {},
    };
    final raw = j['availability'] ?? {};
    if (raw is! Map) throw const FormatException('Invalid availability');
    for (final kind in availability.keys) {
      final entries = raw[kind] ?? {};
      if (entries is! Map) throw const FormatException('Invalid availability');
      for (final entry in entries.entries) {
        final key = entry.key.toString();
        if (kind == 'dates') {
          checkedDate(key);
        } else if (!RegExp(r'^[0-6]$').hasMatch(key)) {
          throw const FormatException('Weekday must be 0–6');
        }
        availability[kind]![key] = integer(entry.value, 0, 1440);
      }
    }
    if (j['planId'] != null &&
        (j['planId'] is! String ||
            !RegExp(r'^[-a-zA-Z0-9]{1,100}$').hasMatch(j['planId']))) {
      throw const FormatException('Invalid plan identity');
    }
    return PlanSnapshot(
      courses,
      sessions,
      start,
      daily,
      hours,
      integer(j['unscheduled'], 0, 100000000),
      availability,
      planId: j['planId'],
    );
  }
}

DateTime checkedDate(dynamic value) {
  if (value is! String ||
      !RegExp(r'^\d{4}-\d{2}-\d{2}(T.*)?$').hasMatch(value)) {
    throw const FormatException('Invalid date');
  }
  final date = DateTime.parse(value);
  if (dateLabel(date) != value.substring(0, 10)) {
    throw const FormatException('Invalid calendar date');
  }
  return day(date);
}

void validateCourse(Course c) {
  if (c.topicMinutes.entries.any(
    (e) => !c.topics.contains(e.key) || e.value < 0 || e.value > 600000,
  ))
    throw const FormatException('Invalid topic estimate');
  if (c.id.isEmpty ||
      c.id.length > 100 ||
      c.name.trim().isEmpty ||
      c.name.length > 100 ||
      !c.credits.isFinite ||
      c.credits < 0.1 ||
      c.credits > 30 ||
      c.topics.isEmpty ||
      c.topics.length > 150 ||
      c.topics.any((t) => t.trim().isEmpty || t.length > 300) ||
      c.topics.map((t) => t.toLowerCase()).toSet().length != c.topics.length) {
    throw const FormatException('Invalid course');
  }
}

/// Browser backup conversion preserves active work and rounds durations to minutes.
/// Missed history is excluded; its recovered workload is represented by active work.
Map<String, dynamic> browserBackupToNative(Map<String, dynamic> j) {
  if (j['version'] != 2 || j['workload'] is! Map)
    throw const FormatException('Invalid browser backup');
  int minutes(dynamic hours) {
    if (hours is! num || !hours.isFinite || hours < 0 || hours > 100000)
      throw const FormatException('Invalid browser hours');
    return (hours * 60).round();
  }

  final courses = <Map<String, dynamic>>[];
  final sessions = <Map<String, dynamic>>[];
  final names = <String>{};
  for (final c in j['courses'] as List) {
    if (c['name'] is! String || !names.add(c['name']))
      throw const FormatException('Invalid course names');
    final topics = List<String>.from(c['topics']);
    final topicMinutes = <String, int>{};
    for (final t in topics) {
      final workload = j['workload'][c['name']]?[t];
      if (workload is! num)
        throw const FormatException('Missing topic workload');
      topicMinutes[t] = minutes(workload / 100);
    }
    courses.add({
      'id': c['name'],
      'name': c['name'],
      'credits': c['credit_hours'],
      'exam': c['exam_date'],
      'topics': topics,
      'topicMinutes': topicMinutes,
    });
  }
  for (final r in j['rows'] as List) {
    if (![
      'Pending',
      'Rescheduled',
      'Completed',
      'Missed',
    ].contains(r['Status']))
      throw const FormatException('Unknown session status');
    if (r['Status'] == 'Missed') continue;
    sessions.add({
      'courseId': r['Course'],
      'topic': r['Topic'],
      'date': r['Date'],
      'minutes': minutes(r['Target Hours']),
      'done': r['Status'] == 'Completed',
    });
  }
  var unscheduled = 0;
  for (final c in courses) {
    final estimates = c['topicMinutes'] as Map<String, int>;
    for (final topic in estimates.keys.toList()) {
      final allocated = sessions
          .where((s) => s['courseId'] == c['id'] && s['topic'] == topic)
          .fold(0, (int n, s) => n + (s['minutes'] as int));
      estimates[topic] = max(estimates[topic]!, allocated);
      unscheduled += estimates[topic]! - allocated;
    }
  }
  final availability = <String, Map<String, int>>{};
  for (final kind in ['weekdays', 'dates']) {
    availability[kind] = {
      for (final e in ((j['availability']?[kind] ?? {}) as Map).entries)
        e.key.toString(): minutes(e.value),
    };
  }
  return {
    'version': 1,
    'app': 'Replan Flutter',
    'courses': courses,
    'sessions': sessions,
    'start': j['start'],
    'daily': minutes(j['cap']),
    'hours': (j['hoursPerCH'] as num).round(),
    'unscheduled': unscheduled,
    'availability': availability,
    if (j['planId'] != null) 'planId': j['planId'],
  };
}

String newPlanIdentity() {
  final random = Random.secure();
  return List.generate(
    16,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}
