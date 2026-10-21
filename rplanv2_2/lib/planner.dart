import 'dart:math';

DateTime day(DateTime d) => DateTime(d.year, d.month, d.day);
String dateLabel(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class Course {
  Course(this.id, this.name, this.credits, this.exam, this.topics);
  final String id, name;
  final int credits;
  final DateTime exam;
  final List<String> topics;
  Map<String, dynamic> toJson() => {'id': id, 'name': name, 'credits': credits, 'exam': exam.toIso8601String(), 'topics': topics};
  factory Course.fromJson(Map<String, dynamic> j) => Course(j['id'], j['name'], j['credits'], DateTime.parse(j['exam']), List<String>.from(j['topics']));
}

class Session {
  Session(this.courseId, this.topic, this.date, this.minutes, {this.done = false});
  final String courseId, topic;
  final DateTime date;
  final int minutes;
  bool done;
  Map<String, dynamic> toJson() => {'courseId': courseId, 'topic': topic, 'date': date.toIso8601String(), 'minutes': minutes, 'done': done};
  factory Session.fromJson(Map<String, dynamic> j) => Session(j['courseId'], j['topic'], DateTime.parse(j['date']), j['minutes'], done: j['done']);
}

class PlanResult {
  PlanResult(this.sessions, this.unscheduled);
  final List<Session> sessions;
  final int unscheduled;
}

// Earliest deadline first, with credits breaking ties. All work is in minutes;
// completed work consumes capacity and is never regenerated.
PlanResult schedule(List<Course> courses, List<Session> previous, DateTime start,
    int dailyMinutes, int hoursPerCredit) {
  final sessions = previous.where((s) => s.done).toList();
  final used = <String, int>{};
  for (final s in sessions) {
    used.update(dateLabel(s.date), (v) => v + s.minutes, ifAbsent: () => s.minutes);
  }
  final sorted = [...courses]..sort((a, b) {
    final comparison = a.exam.compareTo(b.exam);
    return comparison == 0 ? b.credits.compareTo(a.credits) : comparison;
  });
  var unscheduled = 0;
  for (final c in sorted) {
    final total = c.credits * hoursPerCredit * 60;
    for (var i = 0; i < c.topics.length; i++) {
      final target = total ~/ c.topics.length + (i < total % c.topics.length ? 1 : 0);
      final completed = sessions.where((s) => s.courseId == c.id && s.topic == c.topics[i]).fold(0, (int n, s) => n + s.minutes);
      var left = max(0, target - completed);
      var date = day(start);
      while (left > 0 && date.isBefore(day(c.exam))) {
        final key = dateLabel(date);
        final available = max(0, dailyMinutes - (used[key] ?? 0));
        final amount = min(left, min(60, available));
        if (amount > 0) {
          sessions.add(Session(c.id, c.topics[i], date, amount));
          used[key] = (used[key] ?? 0) + amount;
          left -= amount;
        } else {
          date = DateTime(date.year, date.month, date.day + 1);
        }
      }
      unscheduled += left;
    }
  }
  sessions.sort((a, b) => a.date.compareTo(b.date));
  return PlanResult(sessions, unscheduled);
}
