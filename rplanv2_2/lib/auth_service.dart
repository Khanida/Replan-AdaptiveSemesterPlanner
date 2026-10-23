import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

const mobileAuthRedirect = 'io.replan.semester://auth/callback';

class AuthConfig {
  AuthConfig(this.url, this.key);
  final String url, key;
  factory AuthConfig.fromJson(Map<String, dynamic> input) {
    final url = Uri.tryParse(
      input['supabaseUrl'] is String ? input['supabaseUrl'] : '',
    );
    final key = input['supabasePublishableKey'];
    var publicKey = key is String && key.startsWith('sb_publishable_');
    if (!publicKey && key is String) {
      try {
        final claims = jsonDecode(
          utf8.decode(base64Url.decode(base64Url.normalize(key.split('.')[1]))),
        );
        publicKey = claims['role'] == 'anon';
      } catch (_) {
        publicKey = false;
      }
    }
    if (url == null ||
        url.scheme != 'https' ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        (url.path.isNotEmpty && url.path != '/') ||
        url.hasQuery ||
        url.hasFragment ||
        !publicKey) {
      throw const FormatException(
        'Sign-in is not configured. You can continue as a guest.',
      );
    }
    return AuthConfig(url.origin, key as String);
  }
}

bool isAuthCallback(Uri uri, Uri webBase, {required bool web}) {
  Map<String, String> fragment;
  try {
    fragment = Uri.splitQueryString(uri.fragment);
  } catch (_) {
    return false;
  }
  final hasResult =
      uri.queryParameters.containsKey('code') ||
      ['error', 'error_code', 'error_description'].any(
        (key) =>
            uri.queryParameters.containsKey(key) || fragment.containsKey(key),
      );
  if (!hasResult) return false;
  if (web)
    return uri.scheme == webBase.scheme &&
        uri.host == webBase.host &&
        uri.port == webBase.port &&
        uri.path == webBase.path;
  return uri.scheme == 'io.replan.semester' &&
      uri.host == 'auth' &&
      uri.path == '/callback';
}

/// Authentication is optional. Sessions stay in memory and never enter backups.
class PlannerAuth {
  static SupabaseClient? client;
  static AuthConfig? _config;
  static String? setupError;
  static Future<void> ensureProviderEnabled(OAuthProvider provider) async {
    if (provider != OAuthProvider.google)
      throw AuthUnavailable('Use Google sign-in or continue as a guest.');
    final config = _config;
    if (config == null) return;
    final response = await http
        .get(
          Uri.parse('${config.url}/auth/v1/settings'),
          headers: {'apikey': config.key},
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200)
      throw StateError('Could not check sign-in availability');
    final settings = jsonDecode(response.body) as Map<String, dynamic>;
    if (settings['external']?[provider.name] != true)
      throw AuthUnavailable(
        'Google sign-in is not available yet. Choose another option or continue as a guest.',
      );
  }

  static Future<void> initialize() async {
    try {
      final config = AuthConfig.fromJson(
        jsonDecode(await rootBundle.loadString('assets/replan-auth.json'))
            as Map<String, dynamic>,
      );
      _config = config;
      final webBase = Uri.base;
      await Supabase.initialize(
        url: config.url,
        publishableKey: config.key,
        debug: false,
        authOptions: FlutterAuthClientOptions(
          authFlowType: AuthFlowType.pkce,
          persistSession: false,
          detectSessionInUriPredicate: (uri) =>
              isAuthCallback(uri, webBase, web: kIsWeb),
        ),
      );
      client = Supabase.instance.client;
    } catch (_) {
      setupError = 'Sign-in could not initialize. You can continue as a guest.';
    }
  }
}

class AuthUnavailable implements Exception {
  AuthUnavailable(this.message);
  final String message;
}
