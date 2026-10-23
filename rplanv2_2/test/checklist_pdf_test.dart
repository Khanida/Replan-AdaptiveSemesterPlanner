import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:rplanv2_2/checklist_pdf.dart';
import 'package:rplanv2_2/planner.dart';

void main() {
  final font = ByteData.sublistView(
    File('assets/fonts/NotoSans-Regular.ttf').readAsBytesSync(),
  );
  final arabic = ByteData.sublistView(
    File('assets/fonts/NotoSansArabic-Regular.ttf').readAsBytesSync(),
  );
  test('an empty plan cannot export a misleading blank checklist', () async {
    final plan = PlanSnapshot([], [], DateTime(2026, 10, 23), 120, 1, 0, {});
    await expectLater(
      buildDailyChecklist(plan, fontData: font, arabicFontData: arabic),
      throwsStateError,
    );
  });
  test('PDF exports multiple dates, long topics, Unicode and completion without mutating the plan', () async {
    final c = Course('a', 'Mathematics', 1, DateTime(2026, 12, 1), ['Limits']);
    final rows = List.generate(
      60,
      (i) => Session(
        'a',
        i % 2 == 0
            ? '${'Long topic details ' * 12}'
            : 'مراجعة الرياضيات - Worked examples and revision',
        DateTime(2026, 10, 23 + i ~/ 30),
        30,
        done: i == 0,
      ),
    );
    final plan = PlanSnapshot(
      [c],
      rows,
      DateTime(2026, 10, 23),
      1440,
      1,
      120,
      {},
    );
    final before = rows.map((s) => s.toJson()).toList();
    final bytes = await buildDailyChecklist(
      plan,
      fontData: font,
      arabicFontData: arabic,
    );
    expect(String.fromCharCodes(bytes.take(5)), '%PDF-');
    expect(bytes.length, greaterThan(5000));
    expect(rows.map((s) => s.toJson()).toList(), before);
  });
}
