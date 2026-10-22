# Optional Google and Apple sign-in

The app is configured for Supabase project `zhdgciafkwqbxwtvnbkj`, and its
public auth settings confirm Google is enabled. Complete the redirect allowlist
below and verify an interactive login before release. Apple is not enabled.
Users never enter
API keys or OAuth client IDs. They choose Google, Apple, or Continue as guest.

## Configure the project once

1. Create a Supabase project. In **Authentication → Providers**, enable Google
   and Apple following the official guides below. Configure each provider with
   the Supabase callback URL shown in its dashboard. Enable Google Calendar API
   in the Google Cloud project used by your Google OAuth web client.
2. Apple requires a Services ID and Sign in with Apple configuration in an Apple
   Developer account. Keep its private key and generated client secret in
   Supabase. Renew the Apple client secret before it expires.
3. In `replan-auth.json`, set `supabaseUrl` to the project's HTTPS origin, and
   `supabasePublishableKey` to its public `sb_publishable_…` key (the legacy
   `anon` key also works). These two values are public app configuration. Never
   put a service-role key, secret key, Google secret, or Apple private key here.
4. In **Authentication → URL Configuration → Redirect URLs**, allow:
   - Desktop: `http://127.0.0.1:*/auth/callback/**` (an ephemeral loopback port
     and random per-attempt callback path).
   - Local browser preview: `http://127.0.0.1:8765/replanv2.html?replan_auth=*`.
   - For a deployed browser edition, the corresponding HTTPS page URL with
     `?replan_auth=*`. Keep this restricted to your actual app domain and path.
5. If your Google consent screen is in testing mode, add your test accounts.
   Calendar access may require Google's verification before public release.

## Run and check

Run `python3 replanv2_1.py`, choose **Sign in**, and tap a provider. Desktop sign-in
opens the system browser. Complete the provider's consent/account prompt, then
return to Replan. A cancelled flow or missing setup leaves guest use available.
Closing the browser tab without completing desktop sign-in times out after
three minutes; the planner remains usable while the sign-in attempt is pending.

For browser use, serve this directory on localhost or HTTPS. Allow the sign-in
popup. Opening the HTML directly with `file://` supports the planner and ICS
export, but not sign-in.

Verify both providers, denial/cancellation, sign-out, and a Google Calendar sync
using test accounts after configuring the real project. Signing in alone asks
for identity access; Calendar requests its permission when adding tasks. An
Apple login cannot grant Google Calendar permission, so that action opens a
separate Google authorization flow.

## Session behavior

The desktop app uses a loopback callback and PKCE instead of embedded provider
login pages. Browser callbacks require the initiating popup, matching origin,
and a random attempt identifier. Both exchange the code with Supabase and verify
the account through its authenticated user endpoint before showing signed-in
state. Tokens are not written to the planner's autosave or a token file. Restart
or reload requires sign-in again. Plans continue saving locally; account sign-in
does not implement cloud plan sync.

## References

- [Supabase Google provider setup](https://supabase.com/docs/guides/auth/social-login/auth-google)
- [Supabase Apple provider setup](https://supabase.com/docs/guides/auth/social-login/auth-apple)
- [Supabase PKCE flow](https://supabase.com/docs/guides/auth/sessions/pkce-flow)
- [Supabase redirect allowlists](https://supabase.com/docs/guides/auth/redirect-urls)
- [Apple web sign-in configuration](https://developer.apple.com/help/account/capabilities/configure-sign-in-with-apple-for-the-web/)
