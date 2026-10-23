# RePlan v2_1 — Mobile app (Flutter)

The flagship is the [browser/desktop app](../README.md). This Flutter client shares scheduling contracts, and has its own storage. It can import browser/desktop JSON backups, and the browser/desktop edition can import Flutter JSON backups.

## Run

Use Flutter 3.47 or later with Dart 3.13 or later (matching the locked dependencies). Android, iOS, web and macOS runners are included:

```sh
flutter pub get --enforce-lockfile
flutter run -d chrome
# Or, with Xcode installed:
flutter run -d macos
```

For Android/iOS development, install the corresponding platform SDK and run `flutter run -d <device-id>`. The runners include the sign-in callback scheme. Physical-device builds and live authorization still need verification.

## Features and recovery

- Multiple courses, credits, deadlines and topic outlines.
- Daily course rotation with one unfinished topic per course per day, shared daily capacity and sessions up to 60 minutes. Earlier exams and higher credits get initial priority; courses that receive no time carry over first the next day. Long topics may span days. Work that cannot fit is reported as unscheduled.
- Optional per-topic estimates in minutes. Otherwise topics divide the credit-based estimate equally.
- Weekday/date availability overrides, entered in minutes in Settings. Sunday is 0 and Saturday is 6; date entries override weekday entries. Zero means no study that day.
- Completion tracking, roadmap filtering, explicit replanning from today, and an overdue reminder. Replanning preserves completed work; there is no automatic learning-performance model.
- **Download PDF daily checklist** is the primary export in the app bar and Settings. Each date starts a new section/page, busy days continue automatically, and every session has a completion box, course, topic and estimated minutes. Completed work is marked; notes space and page numbers are included. Web downloads a PDF, desktop opens Save As, and mobile opens the system share/save sheet.
- Optional **Sign in** with Google opens your system browser and returns through a PKCE callback. Account details appear under **Account**, with Sign out available. Guest use remains available; sign-in does not back up your plan or grant Calendar permission. Sessions stay in memory rather than in plan storage. See [provider setup](../AUTH_SETUP.md#flutter-mobile-and-web-authorization).
- Local autosave using shared_preferences and **Export JSON backup / Import JSON backup** under Settings → **Plan backup and recovery**. Backups contain settings, availability, topics, sessions and completion.
- Web exports download a JSON file. Desktop exports open Save As; cancellation leaves files untouched. On Android/iOS, export copies JSON to the clipboard; paste it into a file outside the app. Import uses the native file picker.
- Restore validates the complete backup before replacing state and asks before replacement. Unsupported versions, malformed dates, invalid settings and unknown session references are rejected.
- If autosave cannot be restored, autosave pauses. **Export original data** preserves the unreadable text; **Import JSON backup** restores a validated backup. Before replacing unreadable storage, the app also retains the original in a separate recovery key.

Browser/desktop backups are converted to whole minutes and omit missed history; recovered active work is retained. Transferring back to the browser uses hundredths of an hour. Keep the original backup because small rounding differences are possible. Keep a copy outside app/site storage: uninstalling or clearing site data removes local storage. There is no cloud backup.

Course changes use remove and add; removing requires confirmation and clears that course's progress. CSV/calendar integration and coaching controls from the browser edition are not implemented here. PDF checklist export is available.

## Checks

```sh
dart format --output=none --set-exit-if-changed lib test
flutter analyze --fatal-infos
flutter test
flutter build web --release
```

Tests cover PDF generation, invalid/forged auth callback routing, public-key configuration, guest fallback, capacity, completion preservation, impossible deadlines, shared JavaScript/Dart fixtures, malformed backups, backup roundtrips and failed-restore autosave protection. Native file-dialog behavior and platform release builds require the [manual release checks](../docs/RELEASE_CHECKLIST.md).
