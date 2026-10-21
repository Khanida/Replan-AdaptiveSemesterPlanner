import 'package:flutter_test/flutter_test.dart';
import 'package:rplanv2_2/planner.dart';

void main() {
  final start = DateTime(2026, 10, 19);
  test('respects shared daily capacity and excludes exam day', () {
    final courses = [Course('a', 'Math', 1, DateTime(2026, 10, 21), ['Limits']),
      Course('b', 'Code', 1, DateTime(2026, 10, 21), ['Functions'])];
    final result = schedule(courses, [], start, 45, 1);
    final totals = <DateTime, int>{};
    for (final s in result.sessions) {
      expect(s.date.isBefore(DateTime(2026, 10, 21)), isTrue);
      totals.update(s.date, (n) => n + s.minutes, ifAbsent: () => s.minutes);
    }
    expect(totals.values.every((n) => n <= 45), isTrue);
    expect(result.unscheduled, 30);
    expect(result.sessions.fold(0, (int n, s) => n + s.minutes) + result.unscheduled, 120);
  });
  test('preserves completion and counts it against capacity', () {
    final c = Course('a', 'Math', 1, DateTime(2026, 10, 22), ['Limits']);
    final done = Session('a', 'Limits', start, 30, done: true);
    final result = schedule([c], [done], start, 45, 1);
    expect(result.sessions.contains(done), isTrue);
    expect(result.sessions.where((s) => s.date == start).fold(0, (int n, s) => n + s.minutes), 45);
    expect(result.sessions.fold(0, (int n, s) => n + s.minutes), 60);
    expect(result.unscheduled, 0);
    final again = schedule([c], result.sessions, start, 45, 1);
    expect(again.sessions.map((s) => s.toJson()), result.sessions.map((s) => s.toJson()));
  });
  test('expired work is reported and pending history is replaced', () {
    final c = Course('a', 'Math', 1, start, ['Limits']);
    final result = schedule([c], [Session('a', 'Limits', DateTime(2026, 10, 18), 60)], start, 120, 1);
    expect(result.sessions, isEmpty);
    expect(result.unscheduled, 60);
  });
  test('allocates urgent course first and retains every topic minute', () {
    final late = Course('late', 'Late', 1, DateTime(2026, 10, 25), ['A', 'B', 'C', 'D', 'E', 'F', 'G']);
    final urgent = Course('urgent', 'Urgent', 1, DateTime(2026, 10, 20), ['X']);
    final result = schedule([late, urgent], [], start, 60, 1);
    expect(result.sessions.first.courseId, 'urgent');
    expect(result.sessions.where((s) => s.courseId == 'late').fold(0, (int n, s) => n + s.minutes), 60);
    expect(result.unscheduled, 0);
  });
}
