/* Optional Google/Apple OAuth. Public configuration only; tokens stay in memory. */
(function () {
  'use strict';
  const params = new URLSearchParams(location.search);
  if (params.has('replan_auth') && window.opener) {
    window.opener.postMessage({type: 'replan-auth', state: params.get('replan_auth'),
      code: params.get('code'), error: params.get('error')}, location.origin);
    history.replaceState(null, '', location.pathname);
    window.close();
    return;
  }
  let busy = false;
  const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  async function config() {
    const response = await fetch('replan-auth.json', {cache: 'no-store'});
    if (!response.ok) throw Error('Sign-in is not available yet. You can continue as a guest.');
    const value = await response.json();
    let url;
    try { url = new URL(value.supabaseUrl); } catch { /* handled below */ }
    const key = value.supabasePublishableKey;
    let publicKey = typeof key === 'string' && key.startsWith('sb_publishable_');
    if (!publicKey && typeof key === 'string') {
      try { publicKey = JSON.parse(atob(key.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).role === 'anon'; } catch { /* reject private keys */ }
    }
    if (!url || url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash || !publicKey)
      throw Error('Sign-in is not configured yet. You can continue as a guest.');
    return {url: url.origin, key};
  }
  async function request(settings, path, body, token) {
    const response = await fetch(settings.url + '/auth/v1' + path, {
      method: body ? 'POST' : 'GET', headers: {apikey: settings.key, 'Content-Type': 'application/json',
        ...(token ? {Authorization: 'Bearer ' + token} : {})}, body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(20000)});
    if (!response.ok) throw Error('Sign-in could not finish. Please try again or continue as a guest.');
    return response.json();
  }
  async function signIn(provider, calendar = false) {
    if (!['google', 'apple'].includes(provider) || (calendar && provider !== 'google')) throw Error('Choose Google or Apple.');
    // The native bridge opens the default browser and receives its loopback callback.
    if (window.pywebview?.api?.sign_in) return window.pywebview.api.sign_in(provider, calendar);
    if (busy) throw Error('A sign-in window is already open.');
    if (!['http:', 'https:'].includes(location.protocol) || !window.isSecureContext)
      throw Error('Open Replan on localhost or HTTPS to sign in.');
    const popup = window.open('about:blank', 'replan-sign-in', 'popup,width=520,height=720');
    if (!popup) throw Error('Allow popups for Replan, then try again.');
    busy = true;
    try {
      popup.document.body.textContent = 'Opening secure sign-in…';
      const settings = await config();
      const verifier = base64url(crypto.getRandomValues(new Uint8Array(48)));
      const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
      const state = base64url(crypto.getRandomValues(new Uint8Array(32)));
      const redirect = new URL(location.pathname, location.origin);
      redirect.searchParams.set('replan_auth', state);
      const authorize = new URL(settings.url + '/auth/v1/authorize');
      authorize.search = new URLSearchParams({provider, redirect_to: redirect.href,
        code_challenge: challenge, code_challenge_method: 's256'});
      if (provider === 'google') {
        authorize.searchParams.set('scopes', 'openid email profile' + (calendar ? ' https://www.googleapis.com/auth/calendar' : ''));
        authorize.searchParams.set('prompt', calendar ? 'consent' : 'select_account');
      }
      const code = await new Promise((resolve, reject) => {
        let closed, timeout;
        const cleanup = () => {window.removeEventListener('message', receive); clearInterval(closed); clearTimeout(timeout);};
        const receive = event => {
          if (event.origin !== location.origin || event.source !== popup || event.data?.type !== 'replan-auth' || event.data.state !== state) return;
          cleanup();
          if (event.data.error || !event.data.code) reject(Error('Sign-in was cancelled or declined. You can continue as a guest.'));
          else resolve(event.data.code);
        };
        window.addEventListener('message', receive);
        closed = setInterval(() => {if (popup.closed) {cleanup(); reject(Error('Sign-in cancelled. You can continue as a guest.'));}}, 500);
        timeout = setTimeout(() => {cleanup(); reject(Error('Sign-in timed out. Please try again.'));}, 180000);
        popup.location.href = authorize.href;
      });
      const session = await request(settings, '/token?grant_type=pkce', {auth_code: code, code_verifier: verifier});
      if (!session.access_token) throw Error('Sign-in did not return a session. Please try again.');
      const user = await request(settings, '/user', null, session.access_token);
      if (!user.id) throw Error('Could not verify your account.');
      if (calendar && !session.provider_token) throw Error('Google Calendar permission was not received. Please try again.');
      return {provider, profile: {name: user.user_metadata?.full_name || user.user_metadata?.name, email: user.email},
        calendarToken: calendar ? session.provider_token : null};
    } finally {
      busy = false;
      if (!popup.closed) popup.close();
    }
  }
  window.ReplanAuth = {signIn};
})();
