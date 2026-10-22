const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const source = fs.readFileSync('replanv2-auth.js', 'utf8');

function environment({configured = true, denied = false} = {}) {
  const listeners = new Map(), calls = [];
  const location = {search: '', protocol: 'http:', origin: 'http://127.0.0.1:8765', pathname: '/replanv2.html'};
  let request;
  const popup = {closed: false, document: {body: {}}, close() {this.closed = true;}, location: {}};
  const window = {isSecureContext: true, open: () => popup,
    addEventListener: (name, callback) => listeners.set(name, callback),
    removeEventListener: name => listeners.delete(name)};
  Object.defineProperty(popup.location, 'href', {set(url) {
    request = new URL(url);
    const redirect = new URL(request.searchParams.get('redirect_to'));
    const receive = listeners.get('message');
    // A forged origin must not trigger the code exchange.
    receive({origin: 'https://attacker.example', source: popup,
      data: {type: 'replan-auth', state: redirect.searchParams.get('replan_auth'), code: 'attacker'}});
    setImmediate(() => receive({origin: location.origin, source: popup,
      data: {type: 'replan-auth', state: redirect.searchParams.get('replan_auth'),
        code: denied ? null : 'valid-code', error: denied ? 'access_denied' : null}}));
  }});
  const fetch = async (url, options) => {
    calls.push({url, options});
    if (url === 'replan-auth.json') return {ok: true, json: async () => ({
      supabaseUrl: configured ? 'https://example.supabase.co' : '', supabasePublishableKey: 'sb_publishable_public'})};
    if (url.includes('/token?')) {
      const body = JSON.parse(options.body);
      assert.equal(body.auth_code, 'valid-code');
      const digest = Buffer.from(await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(body.code_verifier))).toString('base64url');
      assert.equal(digest, request.searchParams.get('code_challenge'));
      return {ok: true, json: async () => ({access_token: 'session-token', provider_token: 'calendar-token'})};
    }
    assert.ok(url.endsWith('/user'));
    assert.equal(options.headers.Authorization, 'Bearer session-token');
    return {ok: true, json: async () => ({id: 'verified', email: 'student@example.com'})};
  };
  vm.runInNewContext(source, {window, location, URL, URLSearchParams, fetch, crypto: webcrypto,
    Uint8Array, TextEncoder, btoa, atob, AbortSignal, setTimeout, clearTimeout, setInterval, clearInterval});
  return {window, popup, calls, get request() {return request;}};
}

test('browser sign-in verifies PKCE and ignores a forged callback origin', async () => {
  const env = environment();
  const result = await env.window.ReplanAuth.signIn('google');
  assert.equal(result.profile.email, 'student@example.com');
  assert.equal(result.calendarToken, null);
  assert.equal(env.calls.length, 3);
  assert.equal(env.popup.closed, true);
});

test('Apple and Google Calendar use distinct scopes', async () => {
  const apple = environment();
  assert.equal((await apple.window.ReplanAuth.signIn('apple')).provider, 'apple');
  assert.equal(apple.request.searchParams.has('scopes'), false);
  const calendar = environment();
  assert.equal((await calendar.window.ReplanAuth.signIn('google', true)).calendarToken, 'calendar-token');
  assert.ok(calendar.request.searchParams.get('scopes').includes('/auth/calendar'));
});

test('missing configuration closes popup and preserves guest use', async () => {
  const env = environment({configured: false});
  await assert.rejects(env.window.ReplanAuth.signIn('google'), /guest/);
  assert.equal(env.calls.length, 1);
  assert.equal(env.popup.closed, true);
});

test('denied consent never exchanges a code or creates signed-in state', async () => {
  const env = environment({denied: true});
  await assert.rejects(env.window.ReplanAuth.signIn('google'), /cancelled or declined/);
  assert.equal(env.calls.length, 1);
});

test('desktop delegates to the native system-browser flow', async () => {
  const env = environment();
  env.window.pywebview = {api: {sign_in: async (provider, calendar) => ({provider, calendar})}};
  const result = await env.window.ReplanAuth.signIn('apple');
  assert.equal(result.provider, 'apple');
  assert.equal(result.calendar, false);
  assert.equal(env.calls.length, 0);
});
