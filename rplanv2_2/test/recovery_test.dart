import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rplanv2_2/planner.dart';
import 'package:rplanv2_2/rplanv2_2.dart';

void main() {
  Map<String, dynamic> backup() => PlanSnapshot(
    [
      Course('a', 'Math', 1, DateTime(2026, 12, 1), ['Limits']),
    ],
    [Session('a', 'Limits', DateTime(2026, 10, 23), 30, done: true)],
    DateTime(2026, 10, 23),
    120,
    1,
    30,
    {
      'weekdays': {'0': 0},
      'dates': {},
    },
  ).toJson();

  test('backup roundtrip preserves completion, estimates and availability', () {
    final input = backup();
    input['courses'][0]['topicMinutes'] = {'Limits': 90};
    input['unscheduled'] = 60;
    final restored = PlanSnapshot.fromJson(jsonDecode(jsonEncode(input)));
    expect(restored.toJson(), input);
    final result = schedule(
      restored.courses,
      restored.sessions,
      DateTime(2026, 10, 23),
      restored.daily,
      restored.hours,
      availability: restored.availability,
    );
    expect(result.sessions.fold(0, (int n, s) => n + s.minutes), 90);
  });

  test('malformed backups reject invalid settings, dates and references atomically', () {
    final mutations = <void Function(Map<String, dynamic>)>[
      (j) => j['daily'] = -1,
      (j) => j['hours'] = 0,
      (j) => j['unscheduled'] = -1,
      (j) => j['unscheduled'] = 0,
      (j) => j['start'] = '2026-02-30',
      (j) => j['courses'][0]['topics'] = [],
      (j) => j['courses'][0]['topicMinutes'] = {'Limits': -1},
      (j) => j['courses'].add(j['courses'][0]),
      (j) => j['sessions'][0]['courseId'] = 'missing',
      (j) => j['sessions'][0]['topic'] = 'missing',
      (j) => j['sessions'][0]['minutes'] = -30,
      (j) => j['sessions'][0]['done'] = 'true',
      (j) => j['sessions'][0]['date'] = '2026-12-01',
      (j) => j['availability'] = {
        'weekdays': {'7': 60},
      },
      (j) => j['version'] = 999,
    ];
    for (final mutation in mutations) {
      final input = backup();
      mutation(input);
      expect(() => PlanSnapshot.fromJson(input), throwsA(anything));
    }
  });

  test(
    'browser JSON imports completion, fractional credits and availability',
    () {
      final input = jsonDecode(
        File('../test-fixtures/browser-backup.json').readAsStringSync(),
      ) as Map<String, dynamic>;
      final restored = PlanSnapshot.fromJson(input);
      expect(restored.planId, 'portable-contract');
      expect(restored.courses.single.credits, 1.5);
      expect(restored.courses.single.topicMinutes, {'Easy': 30, 'Hard': 150});
      expect(
        restored.sessions
            .where((s) => s.done)
            .fold(0, (int n, s) => n + s.minutes),
        30,
      );
      expect(restored.availability['dates']!['2026-10-24'], 60);
      expect(
        PlanSnapshot.fromJson(restored.toJson()).toJson(),
        restored.toJson(),
      );
      final result = schedule(
        restored.courses,
        restored.sessions,
        restored.start,
        restored.daily,
        restored.hours,
        availability: restored.availability,
      );
      expect(result.unscheduled, 0);
      expect(result.sessions.fold(0, (int n, s) => n + s.minutes), 180);
    },
  );

  testWidgets(
    'failed restore visibly pauses autosave and does not overwrite original data',
    (tester) async {
      final writes = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: PlannerPage(
            readPlan: () async => '{broken JSON',
            writePlan: (value) async {
              writes.add(value);
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byTooltip('Export original data'), findsOneWidget);
      expect(find.byTooltip('Add course'), findsNothing);
      expect(find.text('Try the 3-course demo'), findsNothing);
      await tester.tap(find.text('Settings').last);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byType(Slider).first);
      await tester.drag(find.byType(Slider).first, const Offset(80, 0));
      await tester.pumpAndSettle();
      expect(writes, isEmpty);
      expect(find.textContaining('Recovery mode:'), findsOneWidget);
    },
  );
}
