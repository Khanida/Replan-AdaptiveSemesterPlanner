import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:rplanv2_2/planner.dart';

void main() {
  final fixtures =
      jsonDecode(File('../test-fixtures/scheduling.json').readAsStringSync())
          as List;
  for (final f in fixtures) {
    test('shared Dart/JavaScript contract: ${f['name']}', () {
      final courses = (f['courses'] as List)
          .map((c) => Course.fromJson(Map<String, dynamic>.from(c)))
          .toList();
      final done = (f['done'] as List)
          .map((s) => Session.fromJson(Map<String, dynamic>.from(s)))
          .toList();
      final availability = <String, Map<String, int>>{};
      for (final kind in ['weekdays', 'dates']) {
        availability[kind] = Map<String, int>.from(
          f['availability']?[kind] ?? {},
        );
      }
      final result = schedule(
        courses,
        done,
        checkedDate(f['start']),
        f['cap'],
        f['rate'],
        availability: availability,
      );
      final daily = <String, int>{};
      for (final session in result.sessions) {
        daily.update(
          dateLabel(session.date),
          (m) => m + session.minutes,
          ifAbsent: () => session.minutes,
        );
      }
      expect(result.unscheduled, f['unscheduled']);
      expect(daily, f['daily']);
    });
  }
}
