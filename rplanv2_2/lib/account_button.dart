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
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _busy = false;
  bool _createAccount = false;
  String? _error;
  String? _status;
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
          _status = null;
        });
      },
      onError: (Object error) {
        if (!mounted) return;
        _timeout?.cancel();
        setState(() {
          _busy = false;
          _error = 'Sign-in was cancelled or could not finish. Try again or continue as a guest.';
          _status = null;
        });
      },
    );
  }

  @override
  void dispose() {
    _timeout?.cancel();
    _subscription?.cancel();
    _emailController.dispose();
    _passwordController.dispose();
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
      _status = 'Finish authorization in your browser, then return to RePlan.';
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
            _status = null;
          });
      });
    } on AuthUnavailable catch (error) {
      if (mounted)
        setState(() {
          _busy = false;
          _error = error.message;
          _status = null;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          _busy = false;
          _error = 'Could not open or complete sign-in. Check your connection, try again, or continue as a guest.';
          _status = null;
        });
    }
  }

  Future<void> _submitEmail() async {
    if (_busy) return;
    final client = PlannerAuth.client;
    if (client == null) {
      setState(
        () => _error =
            PlannerAuth.setupError ??
            'Sign-in is not configured. You can continue as a guest.',
      );
      return;
    }
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter your email and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _status = _createAccount ? 'Creating your account…' : 'Signing in…';
    });
    try {
      if (_createAccount) {
        final response = await client.auth.signUp(
          email: email,
          password: password,
        );
        if (!mounted) return;
        if (response.session == null) {
          _passwordController.clear();
          setState(() {
            _createAccount = false;
            _status = 'Account created. Check your email to confirm it, then sign in.';
          });
        } else {
          setState(
            () =>
                _status = 'Signed in. Your plan is still saved on this device.',
          );
        }
      } else {
        await client.auth.signInWithPassword(email: email, password: password);
        if (!mounted) return;
        setState(
          () => _status = 'Signed in. Your plan is still saved on this device.',
        );
      }
    } on AuthException catch (error) {
      if (mounted) {
        setState(() {
          _status = null;
          _error = error.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _status = null;
          _error = 'Could not complete email sign-in. Check your connection and try again.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
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
      scrollable: true,
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
              const SizedBox(height: 12),
              const Divider(),
              const Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('Or use email'),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'Email'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _passwordController,
                obscureText: true,
                autofillHints: _createAccount
                    ? const [AutofillHints.newPassword]
                    : const [AutofillHints.password],
                enabled: !_busy,
                decoration: const InputDecoration(labelText: 'Password'),
                onSubmitted: _busy ? null : (_) => _submitEmail(),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _busy ? null : _submitEmail,
                child: Text(
                  _createAccount ? 'Create account' : 'Sign in with email',
                ),
              ),
              TextButton(
                onPressed: _busy
                    ? null
                    : () => setState(() {
                        _createAccount = !_createAccount;
                        _error = null;
                        _status = null;
                      }),
                child: Text(
                  _createAccount
                      ? 'Already have an account? Sign in'
                      : 'Need an account? Create one',
                ),
              ),
            ],
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (_status != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_status!),
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
