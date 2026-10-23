// Run from rplanv2_2: dart run tool/checklist_preview.dart /tmp/replan-checklist-preview.pdf
import 'dart:io';
import 'dart:typed_data';

import '../lib/checklist_pdf.dart';
import '../lib/planner.dart';

Future<void> main(List<String> args) async {
  final courses = [
    Course('math', 'Calculus', 3, DateTime(2026, 12, 1), [
      'Integration practice',
    ]),
    Course('code', 'Programming', 4, DateTime(2026, 12, 1), [
      'Functions and parameters',
    ]),
    Course('arabic', 'الرياضيات', 3, DateTime(2026, 12, 1), ['مراجعة الدروس']),
  ];
  final sessions = <Session>[];
  for (var d = 0; d < 2; d++)
    for (var i = 0; i < (d == 0 ? 3 : 48); i++) {
      final c = courses[i % 3];
      sessions.add(
        Session(
          c.id,
          d == 0
              ? c.topics.first
              : '${c.topics.first} - ${'Detailed revision notes and worked examples. ' * 5}',
          DateTime(2026, 10, 23 + d),
          20,
          done: i == 0,
        ),
      );
    }
  final plan = PlanSnapshot(
    courses,
    sessions,
    DateTime(2026, 10, 23),
    1440,
    1,
    90,
    {},
  );
  final bytes = await buildDailyChecklist(
    plan,
    fontData: ByteData.sublistView(
      await File('assets/fonts/NotoSans-Regular.ttf').readAsBytes(),
    ),
    arabicFontData: ByteData.sublistView(
      await File('assets/fonts/NotoSansArabic-Regular.ttf').readAsBytes(),
    ),
  );
  await File(args.isEmpty ? '/tmp/replan-checklist-preview.pdf' : args.first)
      .writeAsBytes(bytes);
}
