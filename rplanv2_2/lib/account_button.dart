import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'auth_service.dart';

class AccountButton extends StatelessWidget {
  const AccountButton({super.key});
  @override
  Widget build(BuildContext context) {
    final client = PlannerAuth.client;
    return StreamBuilder<AuthState>(
      stream: client?.auth.onAuthStateChange,
      builder: (context, snapshot) {
        final signedIn = client?.auth.currentUser != null;
        return TextButton.icon(
          icon: Icon(signedIn ? Icons.account_circle : Icons.login),
          label: Text(signedIn ? 'Account' : 'Sign in'),
          onPressed: () => showDialog<void>(
            context: context,
            builder: (_) => const _AccountDialog(),
          ),
        );
      },
    );
  }
}

class _AccountDialog extends StatefulWidget {
  const _AccountDialog();
  @override
  State<_AccountDialog> createState() => _AccountDialogState();
}

class _AccountDialogState extends State<_AccountDialog> {
  StreamSubscription<AuthState>? _subscription;
  Timer? _timeout;
  bool _busy = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _subscription = PlannerAuth.client?.auth.onAuthStateChange.listen(
      (event) {
        if (!mounted) return;
        _timeout?.cancel();
        setState(() {
          _busy = false;
          _error = null;
        });
      },
      onError: (Object error) {
        if (!mounted) return;
        _timeout?.cancel();
        setState(() {
          _busy = false;
          _error = 'Sign-in was cancelled or could not finish. Try again or continue as a guest.';
        });
      },
    );
  }

  @override
  void dispose() {
    _timeout?.cancel();
    _subscription?.cancel();
    super.dispose();
  }

  Future<void> _signIn(OAuthProvider provider) async {
    final client = PlannerAuth.client;
    if (client == null) {
      setState(
        () => _error =
            PlannerAuth.setupError ??
            'Sign-in is not configured. You can continue as a guest.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await PlannerAuth.ensureProviderEnabled(provider);
      if (!mounted) return;
      final launched = await client.auth.signInWithOAuth(
        provider,
        redirectTo: kIsWeb
            ? Uri.base.replace(query: '', fragment: '').toString()
            : mobileAuthRedirect,
        authScreenLaunchMode: LaunchMode.externalApplication,
        queryParams: provider == OAuthProvider.google
            ? {'prompt': 'select_account'}
            : null,
      );
      if (!launched) throw StateError('Browser unavailable');
      if (!mounted) return;
      _timeout = Timer(const Duration(minutes: 3), () {
        if (mounted)
          setState(() {
            _busy = false;
            _error = 'Sign-in timed out. You can retry or continue as a guest.';
          });
      });
    } on AuthUnavailable catch (error) {
      if (mounted)
        setState(() {
          _busy = false;
          _error = error.message;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          _busy = false;
          _error = 'Could not open or complete sign-in. Check your connection, try again, or continue as a guest.';
        });
    }
  }

  Future<void> _signOut() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await PlannerAuth.client!.auth.signOut(scope: SignOutScope.local);
    } catch (_) {
      if (mounted)
        setState(() => _error = 'Could not sign out. Please try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = PlannerAuth.client?.auth.currentUser;
    return AlertDialog(
      title: Text(user == null ? 'Sign in to RePlan' : 'Your account'),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (user != null) ...[
              Text(user.email ?? 'Signed in'),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _busy ? null : _signOut,
                child: const Text('Sign out'),
              ),
            ] else ...[
              const Text(
                'Choose an account or continue as a guest. Your study plan stays on this device.',
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _busy ? null : () => _signIn(OAuthProvider.google),
                child: const Text('Continue with Google'),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: _busy ? null : () => _signIn(OAuthProvider.apple),
                child: const Text('Continue with Apple'),
              ),
            ],
            if (_busy)
              const Padding(
                padding: EdgeInsets.only(top: 16),
                child: Text(
                  'Finish authorization in your browser, then return to RePlan.',
                ),
              ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 16),
            const Text(
              'Sign-in does not upload your plan or grant calendar access. Sessions stay in memory; reload or restart requires sign-in again.',
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(user == null ? 'Continue as guest' : 'Close'),
        ),
      ],
    );
  }
}
