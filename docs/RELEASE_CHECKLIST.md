# Release validation

Automated checks are defined in `.github/workflows/checks.yml`. They exercise the browser engine, PDF layout, mocked authentication, isolated calendar reconciliation, desktop exports, historical Python engines, Flutter validation/recovery, shared scheduling contracts and a Flutter web release build. They do not establish live provider correctness or native platform usability.

Run these manual checks for each release and record the OS, browser/runtime version, date and result in the release notes:

- Browser: start empty; add competing courses; set different weekday hours and a day off; verify no allocation exceeds capacity; complete one topic and replan on the final study day; verify completed work survives and spare time remains usable.
- Estimates: give a difficult topic more time; add revision as a separate topic; confirm total workload, capacity and unscheduled warnings change consistently.
- Recovery: export a JSON backup, reload, restore it and compare progress. Test unavailable/full storage. Flutter malformed saved data must show recovery controls and never overwrite the original automatically. Restore a valid backup after exporting the original.
- Desktop: launch with stable port; export PDF/CSV/JSON; cancel each Save As dialog; reload and verify persistent progress. Test a second instance/occupied port and unavailable webview backend.
- Flutter desktop/web: download the daily PDF checklist and inspect checkboxes, completed marks, day sections, notes and pagination; export/import a JSON backup; cancel import/export; reject corrupt backups without replacing the current plan; check narrow/wide layouts, keyboard navigation and day rollover. Verify PDF share/save and clipboard backup on mobile before shipping mobile support.
- Google and Apple: use configured test accounts for successful login, cancellation, denied permission, popup closure, timeout and sign-out. Confirm no credentials enter plan backups. Calendar permission must be requested separately.
- Calendar: sync a complete plan; move a session by replanning; sync All sessions and confirm the old tagged event disappears. Selected/Upcoming must retain unselected/past events. Other plans and manual events must remain untouched. Test interrupted upload, expired token and repeated sync. Legacy untagged events require manual removal.
- Install/build: test on each advertised OS/device with a fresh environment. Browser and desktop are separate storage profiles; Flutter imports/exports JSON across clients with documented rounding and missed-history differences. Document migration limits explicitly.

Unverified checks remain release blockers for the affected feature/platform. Do not mark them complete from unit tests or a successful build alone.
