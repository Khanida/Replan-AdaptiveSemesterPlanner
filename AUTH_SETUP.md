# Optional Google sign-in

The app is configured for Supabase project `zhdgciafkwqbxwtvnbkj`, and its
public auth settings confirm Google is enabled. Complete the redirect allowlist
below and verify an interactive login before release.
Users never enter
API keys or OAuth client IDs. They choose Google or Continue as guest.

## Configure the project once

1. Create a Supabase project. In **Authentication → Providers**, enable Google
   following the official guides below. Configure the provider with
   the Supabase callback URL shown in its dashboard. Enable Google Calendar API
   in the Google Cloud project used by your Google OAuth web client.
2. In `replan-auth.json`, set `supabaseUrl` to the project's HTTPS origin, and
   `supabasePublishableKey` to its public `sb_publishable_…` key (the legacy
   `anon` key also works). These two values are public app configuration. Never
   put a service-role key, secret key, or Google secret here.
3. In **Authentication → URL Configuration → Redirect URLs**, allow:
   - Desktop: `http://127.0.0.1:*/auth/callback/**` (an ephemeral loopback port
     and random per-attempt callback path).
   - Local browser preview: `http://127.0.0.1:8765/replanv2.html?replan_auth=*`.
   - For a deployed browser edition, the corresponding HTTPS page URL with
     `?replan_auth=*`. Keep this restricted to your actual app domain and path.
4. If your Google consent screen is in testing mode, add your test accounts.
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

Verify Google sign-in, denial/cancellation, sign-out, and a Google Calendar sync
using test accounts after configuring the real project. Signing in alone asks
for identity access; Calendar requests its permission when adding tasks.

## Session behavior

The desktop app uses a loopback callback and PKCE instead of embedded provider
login pages. Browser callbacks require the initiating popup, matching origin,
and a random attempt identifier. Both exchange the code with Supabase and verify
the account through its authenticated user endpoint before showing signed-in
state. Tokens are not written to the planner's autosave or a token file. Restart
or reload requires sign-in again. Plans continue saving locally; account sign-in
does not implement cloud plan sync.

## Flutter mobile and web authorization

The Flutter client uses the same Supabase project through its bundled public configuration at `rplanv2_2/assets/replan-auth.json`. Keep this file aligned with the root `replan-auth.json` when changing projects. No provider secrets belong in either file.

Before testing live login, add these entries in **Supabase → Authentication → URL Configuration → Redirect URLs**:

- Native Android/iOS/macOS: `io.replan.semester://auth/callback`.
- Local Flutter web: run `flutter run -d chrome --web-port 8766`, then allow the exact URL used by Flutter, such as `http://localhost:8766/` (or `http://127.0.0.1:8766/` if that is the host you open).
- Deployment: allow the exact HTTPS base path of the Flutter web app.

Android intent filters, iOS/macOS URL schemes, network permissions and PKCE callback filtering are included in the source. The default Flutter deep-link handler is disabled so Supabase's app-links handler can process authorization results. The app restricts callbacks to its expected scheme/host/path or web origin/path, and only accepts authorization codes/errors. The SDK exchanges codes using PKCE. Session tokens remain in memory; the temporary PKCE verifier uses the SDK's storage so a browser redirect or cold start can finish the flow. Sign-out clears the local account session without removing study plans.

The project's public settings were checked on October 23, 2026: **Google enabled**. Google is the only supported sign-in provider. The app checks provider availability before opening authorization and explains unavailable providers. Provider dashboard configuration and the redirect allowlist cannot be changed by editing Flutter files alone.

Verify successful Google login, denied consent, closed browser/timeouts, wrong callback origin/path, guest fallback, sign-out and an app cold-start callback. Native testing requires Android SDK or Xcode and an actual emulator/device. These are account sign-ins only; Flutter does not request Google Calendar permission or implement cloud plan storage.

## References

- [Supabase Google provider setup](https://supabase.com/docs/guides/auth/social-login/auth-google)
- [Supabase PKCE flow](https://supabase.com/docs/guides/auth/sessions/pkce-flow)
- [Supabase redirect allowlists](https://supabase.com/docs/guides/auth/redirect-urls)
