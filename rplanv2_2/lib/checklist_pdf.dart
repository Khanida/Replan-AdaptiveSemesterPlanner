import 'dart:typed_data';

import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import 'planner.dart';

/// One date per section, with automatic continuation pages for busy days.
Future<Uint8List> buildDailyChecklist(
  PlanSnapshot plan, {
  required ByteData fontData,
  required ByteData arabicFontData,
}) async {
  if (plan.sessions.isEmpty)
    throw StateError('Generate a roadmap before downloading a checklist.');
  final names = {for (final c in plan.courses) c.id: c.name};
  final dates = plan.sessions.map((s) => dateLabel(s.date)).toSet().toList()
    ..sort();
  final font = pw.Font.ttf(fontData);
  final arabic = pw.Font.ttf(arabicFontData);
  final document = pw.Document(
    title: 'RePlan daily study checklist',
    author: 'RePlan',
    compress: true,
  );
  pw.Widget text(String value, {double size = 10}) {
    final arabicPattern = RegExp(r'[\u0600-\u06ff]');
    pw.Widget run(String content) {
      final rtl = arabicPattern.hasMatch(content);
      return pw.Text(
        content,
        textDirection: rtl ? pw.TextDirection.rtl : pw.TextDirection.ltr,
        style: pw.TextStyle(
          font: rtl ? arabic : font,
          fontFallback: [font, arabic],
          fontSize: size,
        ),
      );
    }

    // Keep opposite-direction runs in separate blocks. This avoids the PDF
    // renderer reversing Latin words when a long Arabic/English topic wraps.
    if (arabicPattern.hasMatch(value) && RegExp(r'[A-Za-z]').hasMatch(value)) {
      final runs =
          RegExp(r'[\u0600-\u06ff]+(?:\s+[\u0600-\u06ff]+)*|[^\u0600-\u06ff]+')
              .allMatches(value)
              .map((m) => m.group(0)!.trim())
              .where((v) => v.isNotEmpty);
      return pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.stretch,
        mainAxisSize: pw.MainAxisSize.min,
        children: runs.map(run).toList(),
      );
    }
    return run(value);
  }

  for (final date in dates) {
    final rows = plan.sessions.where((s) => dateLabel(s.date) == date).toList();
    final minutes = rows.fold(0, (int n, s) => n + s.minutes);
    document.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        maxPages: 1000,
        theme: pw.ThemeData.withFont(
          base: font,
          bold: font,
          fontFallback: [arabic],
        ),
        header: (context) => pw.Padding(
          padding: const pw.EdgeInsets.only(bottom: 18),
          child: pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              text('REPLAN / DAILY STUDY CHECKLIST', size: 18),
              pw.SizedBox(height: 8),
              text(
                '$date   |   ${rows.length} sessions   |   $minutes minutes',
                size: 11,
              ),
              if (plan.unscheduled > 0)
                pw.Padding(
                  padding: const pw.EdgeInsets.only(top: 6),
                  child: text(
                    '${plan.unscheduled} minutes remain unscheduled in this plan. Review capacity and deadlines.',
                  ),
                ),
            ],
          ),
        ),
        footer: (context) => pw.Padding(
          padding: const pw.EdgeInsets.only(top: 16),
          child: pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            mainAxisSize: pw.MainAxisSize.min,
            children: [
              text('NOTES / NEXT STEPS', size: 9),
              for (var i = 0; i < 3; i++)
                pw.Container(
                  height: 18,
                  decoration: const pw.BoxDecoration(
                    border: pw.Border(
                      bottom: pw.BorderSide(color: PdfColors.grey400),
                    ),
                  ),
                ),
              pw.SizedBox(height: 10),
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
                children: [
                  text(
                    'Check each box after studying. Keep completed sessions as your record.',
                    size: 8,
                  ),
                  text('Page ${context.pageNumber}', size: 8),
                ],
              ),
            ],
          ),
        ),
        build: (context) => [
          pw.Table(
            columnWidths: {
              0: const pw.FixedColumnWidth(36),
              1: const pw.FlexColumnWidth(2),
              2: const pw.FlexColumnWidth(4),
              3: const pw.FixedColumnWidth(45),
            },
            border: pw.TableBorder(
              horizontalInside: const pw.BorderSide(color: PdfColors.grey300),
            ),
            children: [
              pw.TableRow(
                repeat: true,
                decoration: const pw.BoxDecoration(color: PdfColors.grey200),
                children: [
                  for (final label in ['Done', 'Course', 'Topic', 'Min'])
                    pw.Padding(
                      padding: const pw.EdgeInsets.symmetric(
                        vertical: 10,
                        horizontal: 4,
                      ),
                      child: text(label, size: 9),
                    ),
                ],
              ),
              for (final session in rows)
                pw.TableRow(
                  verticalAlignment: pw.TableCellVerticalAlignment.middle,
                  children: [
                    pw.Padding(
                      padding: const pw.EdgeInsets.symmetric(
                        vertical: 12,
                        horizontal: 4,
                      ),
                      child: pw.Align(
                        alignment: pw.Alignment.centerLeft,
                        child: pw.Container(
                          width: 13,
                          height: 13,
                          alignment: pw.Alignment.center,
                          decoration: pw.BoxDecoration(
                            border: pw.Border.all(width: 1),
                          ),
                          child: session.done ? text('X', size: 9) : null,
                        ),
                      ),
                    ),
                    pw.Padding(
                      padding: const pw.EdgeInsets.all(6),
                      child: text(names[session.courseId] ?? session.courseId),
                    ),
                    pw.Padding(
                      padding: const pw.EdgeInsets.all(6),
                      child: text(session.topic),
                    ),
                    pw.Padding(
                      padding: const pw.EdgeInsets.all(6),
                      child: text('${session.minutes}'),
                    ),
                  ],
                ),
            ],
          ),
        ],
      ),
    );
  }
  return document.save();
}
