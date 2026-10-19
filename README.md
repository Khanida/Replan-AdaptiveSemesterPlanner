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
