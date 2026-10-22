"""Optional desktop OAuth via hosted Supabase Auth and the system browser.

Only public project configuration belongs in replan-auth.json. Provider secrets
live in Supabase, not in the desktop application. Sessions remain in memory.
"""
from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import ssl
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
import webbrowser


def load_config(root: Path) -> dict:
    try:
        config = json.loads((root / 'replan-auth.json').read_text())
    except (OSError, ValueError):
        raise ValueError('Sign-in is not available yet. You can continue as a guest.') from None
    if not isinstance(config, dict):
        raise ValueError('Sign-in configuration must be an object.')
    url = str(config.get('supabaseUrl', '')).rstrip('/')
    parsed = urlsplit(url)
    key = config.get('supabasePublishableKey', '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment
            or not isinstance(key, str) or not key):
        raise ValueError('Sign-in is not configured yet. You can continue as a guest.')
    # Never accept a server-side key, including legacy service-role JWTs.
    if not key.startswith('sb_publishable_'):
        try:
            payload = key.split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
            if claims.get('role') != 'anon':
                raise ValueError()
        except (ValueError, IndexError, TypeError):
            raise ValueError('Auth configuration requires a public publishable key.') from None
    return {'url': url, 'key': key}


def auth_request(config: dict, path: str, body=None, token=None) -> dict:
    headers = {'apikey': config['key'], 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(config['url'] + '/auth/v1' + path,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers=headers)
    context = ssl.create_default_context()
    # python.org macOS installations may lack their optional CA bundle.
    # Use the system trust bundle while retaining certificate verification.
    if sys.platform == 'darwin' and not ssl.get_default_verify_paths().cafile:
        system_bundle = Path('/etc/ssl/cert.pem')
        if system_bundle.is_file():
            context.load_verify_locations(cafile=str(system_bundle))
    try:
        with urlopen(request, timeout=20, context=context) as response:
            return json.load(response)
    except (HTTPError, URLError, ValueError):
        raise RuntimeError('Sign-in could not finish. Please try again or continue as a guest.') from None


class DesktopAuth:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.Lock()

    def sign_in(self, provider: str, calendar: bool = False) -> dict:
        if provider not in ('google', 'apple') or not isinstance(calendar, bool):
            raise ValueError('Choose Google or Apple.')
        if calendar and provider != 'google':
            raise ValueError('Google Calendar requires a Google account.')
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('A sign-in window is already open in your browser.')
        try:
            return self._sign_in(provider, calendar)
        finally:
            self._lock.release()

    def _sign_in(self, provider: str, calendar: bool) -> dict:
        config = load_config(self.root)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        callback_path = '/auth/callback/' + secrets.token_urlsafe(32)
        result = {}

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path != callback_path or self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                    self.send_error(404)
                    return
                params = parse_qs(parsed.query)
                code = params.get('code', [''])[0]
                if not code or len(code) > 4096:
                    result['error'] = 'Sign-in was cancelled or declined. You can continue as a guest.'
                else:
                    result['code'] = code
                page = b'<!doctype html><meta charset="utf-8"><title>Replan</title><p>Return to Replan to finish signing in. You can close this tab.</p>'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *args):
                pass  # Authorization codes must never appear in request logs.

        with HTTPServer(('127.0.0.1', 0), Callback) as server:
            server.timeout = 0.5
            redirect = f'http://127.0.0.1:{server.server_port}{callback_path}'
            params = {'provider': provider, 'redirect_to': redirect,
                      'code_challenge': challenge, 'code_challenge_method': 's256'}
            if provider == 'google':
                params['scopes'] = 'openid email profile' + (' https://www.googleapis.com/auth/calendar' if calendar else '')
                params['prompt'] = 'consent' if calendar else 'select_account'
            if not webbrowser.open(config['url'] + '/auth/v1/authorize?' + urlencode(params)):
                raise RuntimeError('Could not open your browser. Please try again.')
            deadline = time.monotonic() + 180
            while not result and time.monotonic() < deadline:
                server.handle_request()
        if 'error' in result:
            raise RuntimeError(result['error'])
        if 'code' not in result:
            raise RuntimeError('Sign-in timed out. Please try again or continue as a guest.')
        session = auth_request(config, '/token?grant_type=pkce',
                               {'auth_code': result['code'], 'code_verifier': verifier})
        token = session.get('access_token')
        if not token:
            raise RuntimeError('Sign-in did not return a session. Please try again.')
        user = auth_request(config, '/user', token=token)
        if not user.get('id'):
            raise RuntimeError('Could not verify your account. Please try again.')
        if calendar and not session.get('provider_token'):
            raise RuntimeError('Google Calendar permission was not received. Please try again.')
        metadata = user.get('user_metadata') or {}
        return {'provider': provider, 'profile': {'name': metadata.get('full_name') or metadata.get('name'),
                                                'email': user.get('email')},
                'calendarToken': session.get('provider_token') if calendar else None}
