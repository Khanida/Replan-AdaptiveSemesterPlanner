# RePlan — Adaptive Semester Planner

RePlan turns courses, topics, exam deadlines and study availability into a daily roadmap. It preserves completed work when rebuilding unfinished sessions and reports work that cannot fit before exams.

**Status: working local prototype.** For the latest RePlan experience, use **v2 (Web app)**, **v2_1 (Desktop app)**, or **v2_1 (Mobile app)**. The desktop app shares the browser application's interface; the mobile app uses Flutter and has its own local storage. Historical Python/Tkinter editions are retained for reference; new users should start with the latest apps below.

## Start here

- **Web users:** use [RePlan v2 — Web app](#web-app-v2), served from `replanv2.html`.

- **Desktop users:** use [RePlan v2_1 — Desktop app](#desktop-app-v2_1), launched with `replanv2_1.py`.
- **Mobile users:** use [RePlan v2_1 — Mobile app](#mobile-app-v2_1), built from the Flutter source in [`rplanv2_2/`](rplanv2_2/README.md).

### Web app v2

The browser app needs no build step or third-party JavaScript packages:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/replanv2.html`, then choose **Try the 3-course demo** or add courses. The core planner also works by opening `replanv2.html` directly; optional account features need the localhost server and [provider configuration](AUTH_SETUP.md).

Keep the HTML, CSS, `replanv2.js`, `replanv2-engine.js`, `replanv2-calendar.js`, `replanv2-pdf.js`, `replanv2-auth.js`, and `replan-auth.json` together.

The web app includes the current course rotation, topic estimates, daily/weekly availability, completion tracking, Google-only sign-in, calendar synchronization, and **Download PDF** daily checklists. Desktop 2.1 shares these files, so it receives the same updates.

**Download PDF** exports the complete active roadmap as daily A4 checklist sections, including completion boxes, study time, notes and page numbers. Busy days continue onto additional pages. JSON/CSV tools are under **Plan backup and recovery** in Study roadmap. PDF is a printable checklist; JSON remains the format for restoring an editable plan.

If a saved browser plan cannot be restored, autosave pauses and **Export original saved data** becomes available under Plan backup and recovery. Restoring a valid backup first retains the unreadable original in a separate recovery key, or requires an exported copy if storage is full.

## What works

- Multiple courses, credit hours, unique topic outlines and separate exam dates.
- Shared daily capacity, daily course rotation and sessions of up to one hour.
- Optional **topic estimates in hours**, one per outline topic. Blank estimates use the credit-based default. Add revision and practice as explicit topics when needed.
- Optional weekday availability and date exceptions. Blank weekdays use the default daily limit; zero means a day off. Date exceptions take priority.
- Completion, missed-session history, manual replanning and automatic overdue catch-up in the browser app.
- Explicit unscheduled workload when remaining time cannot accommodate all topics.
- Search, filters, progress, topic timelines, workload views and configurable local coaching.
- Local autosave, full JSON backup/import, CSV plus metadata, printable PDF checklists and `.ics` calendar export.
- Optional Google account sign-in and Google Calendar synchronization. Accounts do not upload or back up the plan.

## Scheduling contract

Each day rotates through courses, selecting one unfinished topic per course in outline order. Initial priority is earliest exam, then higher credits and course name. Each course gets a turn of up to one hour before any course gets another turn on that same topic. Courses that receive no time get the first turns the next day. A long topic may span days; the next topic starts on a later day. This keeps the daily plan varied rather than filling it with one course. All courses share the same daily budget, including completed work already recorded on that date. No new session is placed on or after its exam date. Replanning keeps completed sessions, retains missed history, and replaces pending work; a completed session does not block the rest of its day. A session marked missed can be recovered later the same day if capacity remains. Set today's available hours to zero if no more study is possible today.

Workload defaults to `credits × study hours per credit`, divided equally across topics, with explicit topic estimates replacing the default for those topics. Credit hours are a rough starting estimate, not a measurement of study effort. Review the estimates yourself. “Adaptive” means redistributing unfinished work as dates and availability change; the application does **not** infer mastery or learn study speed from actual durations.

An impossible plan retains the full topic workload and reports the part that is unscheduled. It does not exceed capacity to pretend the plan fits. Imported historical completed work can already exceed a newly lowered capacity; it is retained and flagged instead of erased.

The browser uses hundredths of an hour; Flutter uses whole minutes. Shared [contract fixtures](test-fixtures/scheduling.json) run against both engines to guard the common behavior. Each client can import the other client’s JSON backup. Flutter rounds browser durations to whole minutes and omits missed-session history; the active recovered work remains. Browser import rounds minute-based workload to hundredths of an hour. Keep the original backup when transferring. Feature sets remain separate.

## Backups and calendars

**JSON backup** is the browser's complete portable plan. Save it outside browser storage regularly. CSV needs its matching `.csv.meta.json` file to retain exact workload, availability, deadlines and course details. Without metadata, a CSV represents only its exported rows; unscheduled work cannot be reconstructed from it.

Google Calendar uses a plan identity preserved in JSON backups and CSV metadata. **All sessions** sync with every course selected first uploads the complete active roadmap and then removes outdated events tagged as owned by that plan. **Upcoming** and **Selected** sync never delete other events. Cleanup starts only after all uploads succeed. Manually created events, other plans and older untagged RePlan events are retained. Events from versions predating plan tags need manual cleanup. Missed history is never exported as active calendar work. Clearing the whole roadmap and using All sessions can clear the current plan's tagged events.

`.ics` files are snapshots for manual import; repeated imports are not a managed two-way sync. Authorization and native file dialogs need the manual checks in [release validation](docs/RELEASE_CHECKLIST.md).

## Security and privacy

Browser imports are limited to 20 MB total and validated before replacing a plan. Flutter rejects backup files larger than 20 MB and validates their contents. The browser and Flutter web entry pages set a Content Security Policy that limits scripts to app assets, disables embedded objects, and prevents referrer data from being sent. Hosting these pages over HTTPS is recommended; configure response headers such as `frame-ancestors 'none'` and `X-Content-Type-Options: nosniff` at the web server because HTML meta policies cannot set them.

Plans are stored on the device. JSON/CSV backups are not encrypted, so protect exported files like personal records. Sign-in is optional; Google Calendar receives only the events selected for sync. Supabase publishable keys may be included in client configuration; never put service-role keys, provider client secrets, or other private credentials in app assets.

## Desktop app v2_1

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python replanv2_1.py
```

Python with pywebview is required. macOS uses WebKit, Windows needs WebView2, and Linux needs a supported webview backend. Exports use a native Save As dialog. Cancelling does not save a file.

Desktop storage is a separate `.replanv2-desktop/` profile. Its stable localhost port is `17863`; changing `--port` changes the storage origin. Use JSON backups to transfer browser/desktop plans. Keep the assets beside the launcher. No pandas or Google Python SDK is needed by this maintained desktop edition.

## Mobile app v2_1

Use the latest mobile app, **RePlan v2_1**. Its Flutter source currently lives in `rplanv2_2/`; see [Flutter setup and supported features](rplanv2_2/README.md) for Android/iOS build instructions. It enforces daily capacity, supports explicit topic estimates and availability overrides, and provides a **Download PDF daily checklist** button plus optional Google sign-in. JSON backup/import remains under **Plan backup and recovery** in Settings. A failed restore pauses autosave and exposes the original data for recovery. JSON backups can be transferred between clients, with the precision and history differences described above.

## Checks

```sh
node --test *.cjs
python3 -m unittest test_replan_auth test_replanv2_1 -v
cd rplanv2_2
flutter pub get --enforce-lockfile
flutter analyze --fatal-infos
flutter test
flutter build web --release
```

The full Python historical suite additionally needs pandas and Python with Tkinter:

```sh
python3 -m pip install -r requirements-legacy.txt
python3 -m unittest discover -v
```

[CI](.github/workflows/checks.yml) runs JavaScript, Python and Flutter checks, shared scheduling contracts, and a Flutter web release build on pushes and pull requests. Live provider authorization, native dialogs and physical-device behavior remain manual release checks.

## Maintenance and next steps

[Maintenance policy](docs/MAINTENANCE.md) identifies authoritative modules and archived editions. [Release checks](docs/RELEASE_CHECKLIST.md) distinguish automated coverage from verification that needs configured accounts or devices.

Implemented: course/topic models, manual outlines, capacity-constrained scheduling, progress, replanning, feasibility alerts, persistence and the flagship demo interface. Future research includes automatic outline import, observed study-duration feedback and evidence-based learning-performance adjustments. Those are not claimed as current capabilities.

## License

Commercial use of RePlan requires the copyright holder's prior written permission and a separate written agreement covering payment to the copyright holder. Repository visibility does not grant permission to sell, sublicense, or include RePlan in a commercial product. This project is not offered under an open-source license.
