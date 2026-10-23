# RePlan 2.2 — Flutter secondary client

The flagship is the [browser/desktop app](../README.md). This Flutter client shares scheduling contracts, and has its own storage. It can import browser/desktop JSON backups, and the browser/desktop edition can import Flutter JSON backups.

## Run

Use Flutter with Dart 3.9 or later. Web and macOS runners are included:

```sh
flutter pub get --enforce-lockfile
flutter run -d chrome
# Or, with Xcode installed:
flutter run -d macos
```

For Android/iOS development, generate the missing runners first with `flutter create --platforms=android,ios .`, then install the corresponding platform SDK. Mobile builds have not been verified by the automated desktop/web checks.

## Features and recovery

- Multiple courses, credits, deadlines and topic outlines.
- Earliest-deadline scheduling, shared daily capacity, sessions up to 60 minutes and explicit unscheduled work.
- Optional per-topic estimates in minutes. Otherwise topics divide the credit-based estimate equally.
- Weekday/date availability overrides, entered in minutes in Settings. Sunday is 0 and Saturday is 6; date entries override weekday entries. Zero means no study that day.
- Completion tracking, roadmap filtering, explicit replanning from today, and an overdue reminder. Replanning preserves completed work; there is no automatic learning-performance model.
- Local autosave using shared_preferences and **Export JSON backup / Import JSON backup** in Settings. Backups contain settings, availability, topics, sessions and completion.
- Web exports download a JSON file. Desktop exports open Save As; cancellation leaves files untouched. On Android/iOS, export copies JSON to the clipboard; paste it into a file outside the app. Import uses the native file picker.
- Restore validates the complete backup before replacing state and asks before replacement. Unsupported versions, malformed dates, invalid settings and unknown session references are rejected.
- If autosave cannot be restored, autosave pauses. **Export original data** preserves the unreadable text; **Import JSON backup** restores a validated backup. Before replacing unreadable storage, the app also retains the original in a separate recovery key.

Browser/desktop backups are converted to whole minutes and omit missed history; recovered active work is retained. Transferring back to the browser uses hundredths of an hour. Keep the original backup because small rounding differences are possible. Keep a copy outside app/site storage: uninstalling or clearing site data removes local storage. There is no cloud backup.

Course changes use remove and add; removing requires confirmation and clears that course's progress. Browser PDF/CSV/calendar integration and coaching controls are not implemented here.

## Checks

```sh
dart format --output=none --set-exit-if-changed lib test
flutter analyze --fatal-infos
flutter test
flutter build web --release
```

Tests cover capacity, completion preservation, impossible deadlines, shared JavaScript/Dart fixtures, malformed backups, backup roundtrips and failed-restore autosave protection. Native file-dialog behavior and platform release builds require the [manual release checks](../docs/RELEASE_CHECKLIST.md).
