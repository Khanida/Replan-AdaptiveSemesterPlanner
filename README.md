# RePlan 🎓
### Your semester, planned smarter.

**RePlan** is a proposed adaptive study-planning application that transforms semester dates, course outlines, credit hours, and personal availability into manageable **daily study milestones**. When a student misses a session, RePlan aims to rebuild the remaining schedule instead of leaving them with an outdated to-do list.

> **Project status:** Concept / competition prototype. Features described below are planned unless demonstrated in the repository.

## The Problem

Students often juggle several courses, different credit-hour loads, assignments, and exam deadlines. Conventional calendars require them to break down every syllabus manually and rearrange missed tasks themselves. This makes it difficult to know whether their study plan is realistic.

## The Solution

RePlan is designed to turn semester-level requirements into an actionable day-by-day roadmap, adapting as deadlines approach and progress changes.

## Planned Features

- **Semester setup:** Enter start/end dates, exam dates, and available study hours.
- **Course planning:** Add courses, credit hours (CH), outlines, and topic-level estimates.
- **Automatic milestones:** Divide course content into achievable daily tasks.
- **Weighted prioritization:** Consider credit hours, topic workload, urgency, and perceived difficulty.
- **Adaptive rescheduling:** Redistribute unfinished work without silently exceeding daily capacity.
- **Feasibility alerts:** Highlight when remaining workload cannot fit before deadlines.
- **Progress tracking:** Record completed topics and compare planned versus actual progress.

## Example Workflow

1. Set a semester running from September through December.
2. Add Programming (4 CH), Calculus (3 CH), and Networks (3 CH).
3. Enter each course outline, deadlines, and estimated topic durations.
4. Set a daily study limit of 2.5 hours.
5. Generate a schedule, complete milestones, and replan missed sessions.

**Illustrative daily output**

| Course | Milestone | Estimated time |
| --- | --- | ---: |
| Programming | Functions and parameters | 45 min |
| Calculus | Integration practice | 60 min |
| Networks | OSI model revision | 30 min |
| **Total** | | **2 hr 15 min** |

## Scheduling Approach

A possible baseline allocation is:

```text
credit_hour_weight = course_credit_hours / total_credit_hours
```

This can be adjusted using deadline proximity, remaining topic effort, and user-reported difficulty. Credit hours indicate relative course load, **not** exact independent-study hours; topic estimates and student availability must also be considered.

The scheduling engine should:

1. Estimate time required for each remaining topic.
2. Rank work using urgency, difficulty, and course load.
3. Allocate tasks into available daily time slots before deadlines.
4. Preserve completed work and redistribute missed milestones.
5. Report any workload that cannot be scheduled within the available time.

## Running the Applications

### RePlan Roast Desktop

Run the standard-library desktop app (Python with Tkinter):

```bash
python3 replan_desktop.py
```

Start with **Load demo**, or add courses and topics, set your daily study hours, then apply your semester settings.

- Sarcastic, progress-aware study coaching with Off, Mild, Medium, and Extra spicy settings. Feedback is generated locally; no AI service or account is required.
- A charcoal and orange interface with completion, remaining workload, today's work, and next-exam metrics.
- Complete individual sessions directly from the dashboard or finish the whole day.
- Search the schedule by course or topic and filter by Today, Pending, or Done.
- Inspect daily workload and remaining capacity in the Daily workload tab.
- Export the complete schedule as CSV, or pending sessions as all-day `.ics` events for manual calendar import. This does not connect to or sync a calendar account.
- Save and reopen JSON plans, including roast intensity. Unsaved changes prompt before closing or replacing a plan. Use Ctrl+S / Ctrl+O or Command+S / Command+O on Mac.
- Unfinished sessions are rebuilt from the plan date while preserving completed work and reporting infeasible deadlines.

Run the desktop regression checks with `python3 -m unittest test_replan_desktop -v`.

### Replan 2.2 — Flutter

The native Flutter source is in [`rplanv2_2`](rplanv2_2/README.md), with the main interface in `rplanv2_2/lib/rplanv2_2.dart`. It includes courses, capacity-aware daily milestones, completion tracking, replanning, roadmap filters, and local saving. See its README to generate platform runners and run the app with Flutter.

### Replan desktop 2.1

`replanv2_1.py` opens the current v2 planner in a native desktop window with all four intensity themes, the journal logo, adaptive scheduling, and printable PDF checklists. It shares the browser edition’s source files, so interface changes apply to both versions.

```bash
python3 -m pip install -r requirements-desktop.txt
python3 replanv2_1.py
```

If using this repository’s virtual environment, run `.venv/bin/python replanv2_1.py`.

- Keep the `replanv2` web assets, `replan_auth.py`, and `replan-auth.json` beside the launcher.
- Exports use a native **Save As** dialog; cancelling does not write a file or report a successful save.
- Desktop autosave uses a separate profile in `.replanv2-desktop/` (ignored by git). It does not automatically import browser storage; transfer an existing plan with **JSON backup** and **Open plan**.
- The internal server uses localhost port `17863` to retain a stable storage origin. `--port` can choose another port; that origin has separate browser storage.
- Calendar `.ics` export works without account setup. Optional Google and Apple sign-in opens the system browser and returns to the desktop app; see [authentication setup](AUTH_SETUP.md).
- macOS uses the native WebKit renderer. Windows needs WebView2; Linux needs a supported GTK or Qt webview backend. See [pywebview’s platform documentation](https://pywebview.flowrl.com/guide/installation.html).

Check native export behavior with `python3 -m unittest test_replanv2_1 -v`.

### Replan - Adaptive Semester Planner (browser edition)

Open `replanv2.html` in a browser. Keep `replanv2.css`, `replanv2-engine.js`, `replanv2-pdf.js`, `replanv2-auth.js`, `replan-auth.json`, and `replanv2.js` beside it. The core planner runs locally without a build step or third-party JavaScript libraries.

The browser edition includes the v1.2 multi-course workflow: course add/edit/remove with badge themes, outlines and exam-date presets; configurable credit-hour workload estimates; daily milestones; individual and batch completion/missed/pending controls; adaptive replanning; automatic overdue catch-up; roadmap search, filters, sorting and jump-to-today; course progress and topic timelines; daily workload and feasibility alerts; insights and replan history; adjustable roast intensity; JSON backups; desktop-compatible CSV and companion metadata; calendar export; and print/save-to-PDF.

- **Start:** click **Try the 3-course demo**, or add courses and generate a roadmap.
- **Save / print:** **Save plan (PDF)** downloads an A4 weekly schedule with a large checkbox beside every session, notes space, and page numbers. Completed sessions are ticked; missed history is excluded because that work is recovered in the updated roadmap. The PDF uses white pages and dark text for printing and hanging on a wall. It includes the whole active roadmap, regardless of search filters.
- **Persistence:** plans autosave in browser storage when available. **JSON backup** in Study roadmap downloads a complete backup with settings and progress. Ctrl/Command+S downloads the PDF checklist.
- **Desktop CSV:** select a `.csv` and its matching `.csv.meta.json` together in **Open plan**. Without metadata, course credits and exam dates are inferred and should be reviewed. Export **CSV** and **CSV metadata** together to preserve course details for the Python app.
- **Workload:** credits × study hours per credit estimates total work. Required hours spread across days strictly before each exam; the daily limit diagnoses overload. Missed rows stay as history, while recovered work counts once. Completed work and all remaining topics are preserved during replanning. Expired deadlines show unscheduled hours.
- **Calendar:** select courses, upcoming/all/selected sessions, all-day or timed events, a start time, and reminders. `.ics` export works without Google sign-in. Timed sessions run consecutively per day.
- **Optional account:** click **Sign in** at the top right, then **Continue with Google** or **Continue with Apple**. **Continue as guest** keeps the app available without an account. No user enters client IDs. Developer setup lives in [AUTH_SETUP.md](AUTH_SETUP.md). Account details and calendar tokens stay in memory; sign out clears them from Replan. This does not sign out of Google or Apple in your browser. Sign-in does not upload or back up your plan.
- **Google sync:** **Calendar → Add tasks to Google Calendar** asks for Google Calendar permission separately from account sign-in. Apple users can connect a Google account for Calendar while keeping their Apple sign-in. Sync creates or uses a named study calendar and updates matching sessions on repeated sync. It does not delete earlier events when a roadmap changes. Live authorization requires the configured providers and has not been verified by automated checks.

For localhost preview and Google authorization, run:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/replanv2.html`. Allow this page’s callback URL in Supabase as described in [AUTH_SETUP.md](AUTH_SETUP.md).

Run browser-engine checks with `node --test test-no-replan.cjs test-no-replan-pdf.cjs`.

### RePlan v1.2 — Roast Edition 🔥

```bash
python3 replanv1_2.py
```

The multi-course planner with a charcoal/orange theme, sarcastic accountability banner, and blunt study check-ins. Roasts react to overdue sessions, overloaded days, rescheduling, today's work, and completion. Choose **Off**, **Mild**, **Medium**, or **Extra spicy**, or click **Roast me again** for another line. Feedback runs locally without an AI service. Existing CSV and optional Google Calendar features are retained. Requires pandas and Python with Tkinter.

### RePlan v1.1 (Cozy & Friendly Multi-Course Planner) 🌸🎓
A cute, delightful, and encouraging study companion with a cozy pastel theme, motivational quotes, course icons, and gentle adaptive rescheduling:
```bash
python3 replanv1_1.py
```
Key features in v1.1:
- **Cozy & Friendly Interface:** Warm pastel palette, cheering study quotes, and stress-free academic vibes.
- **Multiple Courses with Cute Badges & Icons:** Customize course themes with icons (💻, 📐, 🌐, 🔬, 📖, 🎨, 🧠).
- **Today's Cozy Study Cups:** Friendly check-in card with one-click *"✨ Yay! Finished All Today's Study! 🎉"* celebration and restful rescheduling.
- **Gentle Adaptive Rescheduling:** If you miss a session, RePlan gently reorganizes your milestones before each exam deadline and highlights them in **dreamy lavender**.
- **Daily Harmony & Workload Pace:** Tracks daily study cup hours and flags busy days with caring reminders to take breaks.
- **Supportive Insights & Cheerleader:** Encouraging semester diagnostic with actionable tips and safety buffer analysis.

### RePlan v1 (Multi-Course Semester Planner) 🚀
Multi-course engine with individual outlines, credit hours, and distinct exam dates:
```bash
python3 replanv1.py
```

### RePlan v0 (Single-Course Prototype)
Original single-course prototype:
```bash
python3 replanv0.py
```

## Suggested Tech Stack

## Development Roadmap

- [ ] Define semester, course, topic, and milestone data models
- [ ] Implement manual course-outline entry
- [ ] Generate daily milestones with capacity limits
- [ ] Save and restore plans
- [ ] Track completion and reschedule unfinished work
- [ ] Add feasibility warnings
- [ ] Test edge cases (overlapping deadlines, zero availability, impossible workloads)
- [ ] Build a polished demo interface
- [ ] Explore optional outline import and smarter time estimation

## Why RePlan?

RePlan is not just another checklist. Its central challenge is **constraint-aware scheduling**: producing a realistic plan from academic requirements and revising that plan when real life changes.

## Contributing

Ideas, bug reports, and contributions are welcome as the prototype develops. Open an issue to discuss a proposed improvement.

## License

No license has been selected yet. Add a `LICENSE` file before describing the project as open source.
