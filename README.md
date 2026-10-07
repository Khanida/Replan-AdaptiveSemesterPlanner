# RePlan - Adaptive Semester Planner 🎓
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

## Suggested Tech Stack

| Layer | Suggested technology |
| --- | --- |
| Core scheduling logic | Python |
| Prototype interface | Streamlit or Tkinter |
| Local persistence | SQLite |
| Testing | pytest |
| Optional later web API | FastAPI |

*The final stack should be updated to match the actual implementation.*

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
