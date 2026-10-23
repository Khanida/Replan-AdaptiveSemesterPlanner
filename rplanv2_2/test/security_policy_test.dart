import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Flutter web sets a restrictive content and referrer policy', () {
    final html = File('web/index.html').readAsStringSync();
    expect(html, contains("default-src 'self'"));
    expect(html, contains("object-src 'none'"));
    expect(html, contains("script-src 'self'"));
    expect(html, isNot(contains("script-src 'self' 'unsafe-inline'")));
    expect(html, contains('name="referrer" content="no-referrer"'));
    expect(
      html.indexOf('Content-Security-Policy'),
      lessThan(html.indexOf('<base ')),
    );
  });
}
