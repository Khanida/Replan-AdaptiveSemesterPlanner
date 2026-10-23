"""Exercise OAuth callbacks and code exchange without a browser or network."""
import base64
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import replan_auth as auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / 'replan-auth.json'
        self.config.write_text(json.dumps({'supabaseUrl': 'https://example.supabase.co',
                                          'supabasePublishableKey': 'sb_publishable_example'}))

    def test_missing_setup_leaves_guest_available_without_opening_browser(self):
        self.config.unlink()
        with patch.object(auth.webbrowser, 'open') as browser:
            with self.assertRaisesRegex(ValueError, 'guest'):
                auth.DesktopAuth(self.root).sign_in('google')
            browser.assert_not_called()

    def test_rejects_private_keys_and_insecure_project_urls(self):
        for url, key in [('http://example.com', 'sb_publishable_public'),
                         ('https://example.com', 'sb_secret_private'),
                         ('https://user@example.com', 'sb_publishable_public')]:
            self.config.write_text(json.dumps({'supabaseUrl': url, 'supabasePublishableKey': key}))
            with self.assertRaises(ValueError):
                auth.load_config(self.root)

    def test_only_supported_provider_and_calendar_combinations_are_allowed(self):
        for provider, calendar in [('unknown', False), ('apple', True), ('google', 'true')]:
            with self.assertRaises(ValueError):
                auth.DesktopAuth(self.root).sign_in(provider, calendar)

    def flow(self, provider='google', calendar=False, cancelled=False, bad_callback=False):
        captured = {}

        class Server:
            server_port = 43521

            def __init__(self, address, handler):
                self.handler = handler

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def handle_request(self):
                redirect = urlsplit(captured['params']['redirect_to'][0])
                handler = self.handler.__new__(self.handler)
                handler.server = self
                handler.headers = {'Host': redirect.netloc}
                handler.wfile = io.BytesIO()
                handler.send_response = lambda code: None
                handler.send_header = lambda *args: None
                handler.end_headers = lambda: None
                handler.send_error = lambda code: captured.update(rejected=code)
                if bad_callback and not captured.get('rejected'):
                    handler.path = '/unrelated?code=attacker'
                else:
                    handler.path = redirect.path + ('?error=access_denied' if cancelled else '?code=valid-code')
                handler.do_GET()

        def browser(url):
            captured['params'] = parse_qs(urlsplit(url).query)
            return True

        def request(config, path, body=None, token=None):
            if path.startswith('/token'):
                self.assertEqual(body['auth_code'], 'valid-code')
                digest = hashlib.sha256(body['code_verifier'].encode()).digest()
                self.assertEqual(base64.urlsafe_b64encode(digest).decode().rstrip('='),
                                 captured['params']['code_challenge'][0])
                return {'access_token': 'verified-session', 'provider_token': 'calendar-token'}
            self.assertEqual(path, '/user')
            self.assertEqual(token, 'verified-session')
            return {'id': 'verified-user', 'email': 'student@example.com',
                    'user_metadata': {'full_name': 'Student'}}

        with patch.object(auth, 'HTTPServer', Server), patch.object(auth.webbrowser, 'open', browser), patch.object(auth, 'auth_request', request):
            return auth.DesktopAuth(self.root).sign_in(provider, calendar), captured

    def test_google_login_checks_user_and_keeps_calendar_permission_separate(self):
        result, captured = self.flow()
        self.assertEqual(result['profile']['email'], 'student@example.com')
        self.assertIsNone(result['calendarToken'])
        self.assertNotIn('calendar', captured['params']['scopes'][0])
        self.assertNotIn('access_token', result)

    def test_calendar_connection_requests_google_permission(self):
        result, captured = self.flow(calendar=True)
        self.assertEqual(result['calendarToken'], 'calendar-token')
        self.assertIn('https://www.googleapis.com/auth/calendar', captured['params']['scopes'][0])

    def test_apple_login_is_rejected(self):
        with self.assertRaises(ValueError):
            auth.DesktopAuth(self.root).sign_in('apple')

    def test_unrelated_callback_cannot_complete_login(self):
        result, captured = self.flow(bad_callback=True)
        self.assertEqual(captured['rejected'], 404)
        self.assertEqual(result['profile']['name'], 'Student')

    def test_denied_login_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, 'cancelled or declined'):
            self.flow(cancelled=True)


if __name__ == '__main__':
    unittest.main()
