# Replan 2.2 — Flutter

Native Flutter semester planner. Main interface: `lib/rplanv2_2.dart`.
The existing Python and browser versions remain independent.

## Run

Install a current stable Flutter SDK (Dart 3.9 or later) and its platform prerequisites. From this directory:

```bash
flutter create --project-name rplanv2_2 --platforms=android,ios,web,macos .
flutter pub get
flutter run -d chrome
```

The first command generates the platform runner folders that are not included in this source-only project. Keep the supplied `lib/`, `test/`, and `pubspec.yaml` files. Use `flutter devices` and `flutter run -d <device-id>` for another target. iOS and macOS require Xcode on macOS; Android requires the Android SDK.

```bash
flutter analyze
flutter test
```

## Features

- Responsive dark charcoal and peach Material interface with Today, Courses, Roadmap, and Settings.
- Multiple courses with credits, exam date, and one topic per line; three-course demo on an empty plan.
- Daily capacity and study-hours-per-credit controls; future plan start date.
- Study milestones up to 60 minutes, allocated strictly before exams by earliest deadline first. Credits break deadline ties. Topics share each course's estimated workload equally.
- Session completion, topic/course search, and All/Today/Pending/Done filters.
- Replan from today, preserving completed work and reporting work that cannot fit. Replanning is explicit; overdue work triggers a dashboard reminder.
- Local autosave using shared_preferences. This app has separate storage from the Python/browser versions. Uninstalling the app or clearing site data removes its saved plan.

This initial Flutter version does not include the browser edition's PDF/CSV/JSON exports, calendar integration, theme intensity controls, or existing-plan import. Course changes currently use remove and add; removing a course requires confirmation and clears its progress.

Flutter/Dart were unavailable in the authoring environment, so the supplied tests and platform builds still need to be run with the Flutter SDK.
