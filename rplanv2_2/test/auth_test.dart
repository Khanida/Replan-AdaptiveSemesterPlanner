import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rplanv2_2/auth_service.dart';
import 'package:rplanv2_2/account_button.dart';

void main() {
  test('only HTTPS origins and public keys are accepted', () {
    final config = {
      'supabaseUrl': 'https://example.supabase.co',
      'supabasePublishableKey': 'sb_publishable_test',
    };
    expect(AuthConfig.fromJson(config).url, 'https://example.supabase.co');
    for (final url in [
      'http://example.com',
      'https://user:password@example.com',
      'https://example.com/path',
      'https://example.com?key=test',
    ]) {
      expect(
        () => AuthConfig.fromJson({...config, 'supabaseUrl': url}),
        throwsFormatException,
      );
    }
    final privateJwt =
        'x.${base64Url.encode(utf8.encode(jsonEncode({'role': 'service_role'})))}.x';
    for (final key in ['sb_secret_test', privateJwt, ''])
      expect(
        () => AuthConfig.fromJson({...config, 'supabasePublishableKey': key}),
        throwsFormatException,
      );
  });
  test('auth callbacks require the right origin/path and a code or error', () {
    final base = Uri.parse('https://example.com/planner/');
    expect(
      isAuthCallback(
        Uri.parse('https://example.com/planner/?code=valid'),
        base,
        web: true,
      ),
      isTrue,
    );
    for (final value in [
      'https://evil.com/planner/?code=forged',
      'https://example.com/other/?code=forged',
      'https://example.com/planner/',
      'io.replan.semester://auth/callback?code=wrong-platform',
    ])
      expect(isAuthCallback(Uri.parse(value), base, web: true), isFalse);
    expect(
      isAuthCallback(
        Uri.parse('$mobileAuthRedirect?code=valid'),
        base,
        web: false,
      ),
      isTrue,
    );
    expect(
      isAuthCallback(
        Uri.parse('$mobileAuthRedirect?error=access_denied'),
        base,
        web: false,
      ),
      isTrue,
    );
    expect(
      isAuthCallback(
        Uri.parse('io.replan.semester://other/callback?code=forged'),
        base,
        web: false,
      ),
      isFalse,
    );
    expect(
      isAuthCallback(
        Uri.parse('$mobileAuthRedirect#error=access_denied'),
        base,
        web: false,
      ),
      isTrue,
    );
    expect(
      isAuthCallback(
        Uri.parse('$mobileAuthRedirect#access_token=forged'),
        base,
        web: false,
      ),
      isFalse,
    );
    expect(
      isAuthCallback(Uri.parse(mobileAuthRedirect), base, web: false),
      isFalse,
    );
  });
  testWidgets(
    'unconfigured sign-in shows a recoverable error and keeps guest use available',
    (tester) async {
      PlannerAuth.client = null;
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: AccountButton())),
      );
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(find.text('Continue with Google'), findsOneWidget);
      expect(find.text('Continue with Apple'), findsNothing);
      await tester.tap(find.text('Continue with Google'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Sign-in is not configured'), findsOneWidget);
      await tester.tap(find.text('Continue as guest'));
      await tester.pumpAndSettle();
      expect(find.text('Sign in to RePlan'), findsNothing);
    },
  );
}
