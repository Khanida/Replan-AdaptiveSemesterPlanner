#!/usr/bin/env python3
"""
RePlan Desktop 🎓 - a Tkinter desktop interface for the RePlan study planner.

Standard library only (tkinter, json, dataclasses, datetime). Nothing to install.

    python3 replan_desktop.py

Features
  • Semester setup (start, end, daily study hours, plan "today")
  • Course management (icon, credit hours, exam date)
  • Topic management (estimated minutes, difficulty 1-5)
  • Schedule generation that respects the daily study limit
  • Mark milestones done; missed sessions are rebuilt automatically
  • Progress bars, feasibility alerts, and a "today" card
  • Save / open plans as JSON
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

DATE_FMT = "%Y-%m-%d"
ICONS = ["💻", "📐", "🌐", "🔬", "📖", "🎨", "🧠"]

THEME = {
    "bg": "#FFF7FB",
    "header": "#E9D5FF",
    "accent": "#8B5CF6",
    "accent_hover": "#7C3AED",
    "text": "#4B3B5C",
    "muted": "#8E7CA3",
    "done": "#D1FAE5",
    "today": "#EDE9FE",
    "warn": "#FEF3C7",
    "danger": "#FEE2E2",
    "ok": "#DCFCE7",
}


# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------
@dataclass
class Topic:
    name: str
    est_minutes: int
    difficulty: int = 3  # 1 = easy ... 5 = hard


@dataclass
class Course:
    name: str
    icon: str
    credit_hours: int
    exam_date: date
    topics: List[Topic] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        return sum(t.est_minutes for t in self.topics)


@dataclass
class Milestone:
    course: str
    topic: str
    day: date
    minutes: int
    done: bool = False


@dataclass
class Semester:
    start: date
    end: date
    daily_minutes: int = 150


@dataclass
class WorkItem:
    course: str
    topic: str
    deadline: date
    remaining: int
    score: float


# ----------------------------------------------------------------------
# Scheduling engine
# ----------------------------------------------------------------------
def build_schedule(
    courses: List[Course],
    semester: Semester,
    today: date,
    done_milestones: List[Milestone],
) -> Tuple[List[Milestone], List[str]]:
    """Create milestones for all unfinished work.

    Ordering is earliest-deadline-first, which fits work before deadlines
    most reliably on a fixed daily budget. Credit hours and difficulty
    break ties between topics that share a deadline.

    Completed milestones count against both the topic estimate and that
    day's capacity, so the daily limit is never silently exceeded.
    Returns (new_milestones, alerts).
    """
    done_topic: Dict[Tuple[str, str], int] = {}
    done_day: Dict[date, int] = {}
    for m in done_milestones:
        if m.done:
            key = (m.course, m.topic)
            done_topic[key] = done_topic.get(key, 0) + m.minutes
            done_day[m.day] = done_day.get(m.day, 0) + m.minutes

    total_ch = sum(c.credit_hours for c in courses) or 1
    items: List[WorkItem] = []
    for c in courses:
        deadline = min(c.exam_date - timedelta(days=1), semester.end)
        for t in c.topics:
            remaining = t.est_minutes - done_topic.get((c.name, t.name), 0)
            if remaining > 0:
                score = (c.credit_hours / total_ch) * (0.8 + 0.1 * t.difficulty)
                items.append(WorkItem(c.name, t.name, deadline, remaining, score))

    items.sort(key=lambda w: (w.deadline, -w.score))

    new_milestones: List[Milestone] = []
    if items:
        day = max(today, semester.start)
        last_day = max(w.deadline for w in items)
        while day <= last_day:
            cap = semester.daily_minutes - done_day.get(day, 0)
            for w in items:
                if cap <= 0:
                    break
                if w.remaining <= 0 or w.deadline < day:
                    continue
                take = min(cap, w.remaining)
                new_milestones.append(Milestone(w.course, w.topic, day, take))
                w.remaining -= take
                cap -= take
            day += timedelta(days=1)

    alerts = []
    if semester.daily_minutes <= 0 and items:
        alerts.append("Daily study time is 0, so nothing can be scheduled.")
    for w in items:
        if w.remaining > 0:
            alerts.append(
                f"{w.course} · '{w.topic}': {fmt_min(w.remaining)} can't fit before "
                f"{w.deadline:%b %d}. Add study time, extend the deadline, or trim the topic."
            )
    return new_milestones, alerts


def topic_done_minutes(milestones: List[Milestone]) -> Dict[Tuple[str, str], int]:
    done: Dict[Tuple[str, str], int] = {}
    for m in milestones:
        if m.done:
            key = (m.course, m.topic)
            done[key] = done.get(key, 0) + m.minutes
    return done


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def fmt_min(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


def iso(d: date) -> str:
    return d.strftime(DATE_FMT)


def parse_date(text: str, label: str) -> date:
    try:
        return datetime.strptime(text.strip(), DATE_FMT).date()
    except ValueError:
        raise ValueError(f"{label} must look like YYYY-MM-DD (for example 2025-09-01).")


def parse_int(text: str, label: str, lo: int, hi: int) -> int:
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.")
    if not lo <= value <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}.")
    return value


def parse_hours(text: str) -> float:
    try:
        hours = float(text)
    except ValueError:
        raise ValueError("Daily study hours must be a number, like 2.5.")
    if not 0 <= hours <= 16:
        raise ValueError("Daily study hours must be between 0 and 16.")
    return hours


def default_semester(today: date) -> Semester:
    return Semester(start=today, end=today + timedelta(days=120), daily_minutes=150)


def clear_tree(tree: ttk.Treeview) -> None:
    for iid in tree.get_children():
        tree.delete(iid)


def make_tree(parent, spec, height=10):
    """Return (frame, treeview) with a vertical scrollbar.
    spec: list of (column_id, title, width, anchor)."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(
        frame,
        columns=[c[0] for c in spec],
        show="headings",
        height=height,
        selectmode="browse",
    )
    for cid, title, width, anchor in spec:
        tree.heading(cid, text=title)
        tree.column(cid, width=width, anchor=anchor, stretch=True)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, tree


# ----------------------------------------------------------------------
# Form dialog (used for courses, topics)
# ----------------------------------------------------------------------
class FormDialog(tk.Toplevel):
    """Simple modal form. fields = [(key, label, default, choices_or_None)]."""

    def __init__(self, parent, title, fields, validator=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.result = None
        self.validator = validator
        self._vars: Dict[str, tk.StringVar] = {}

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        first_widget = None
        for row, (key, label, default, choices) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
            var = tk.StringVar(value=str(default))
            if choices:
                widget = ttk.Combobox(body, textvariable=var, values=choices, state="readonly", width=26)
            else:
                widget = ttk.Entry(body, textvariable=var, width=28)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self._vars[key] = var
            first_widget = first_widget or widget

        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="💾 Save", style="Accent.TButton", command=self._submit).pack(side="right")

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.after(20, self._grab)
        if first_widget is not None:
            first_widget.focus_set()

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _submit(self):
        raw = {k: v.get().strip() for k, v in self._vars.items()}
        try:
            self.result = self.validator(raw) if self.validator else raw
        except ValueError as exc:
            messagebox.showerror("Check your input", str(exc), parent=self)
            return
        self.destroy()

    @staticmethod
    def ask(parent, title, fields, validator=None):
        dlg = FormDialog(parent, title, fields, validator)
        dlg.wait_window()
        return dlg.result


def course_fields(course: Optional[Course] = None):
    default_exam = date.today() + timedelta(days=60)
    return [
        ("name", "Course name", course.name if course else "", None),
        ("icon", "Icon", course.icon if course else ICONS[0], ICONS),
        ("credit_hours", "Credit hours (CH)", course.credit_hours if course else 3, None),
        ("exam_date", "Exam date (YYYY-MM-DD)",
         iso(course.exam_date) if course else iso(default_exam), None),
    ]


def validate_course(raw):
    if not raw["name"]:
        raise ValueError("Please give the course a name.")
    return {
        "name": raw["name"],
        "icon": raw["icon"] or ICONS[0],
        "credit_hours": parse_int(raw["credit_hours"], "Credit hours", 1, 30),
        "exam_date": parse_date(raw["exam_date"], "Exam date"),
    }


def topic_fields(topic: Optional[Topic] = None):
    return [
        ("name", "Topic name", topic.name if topic else "", None),
        ("est_minutes", "Estimated study minutes", topic.est_minutes if topic else 60, None),
        ("difficulty", "Difficulty (1 easy … 5 hard)", topic.difficulty if topic else 3,
         ["1", "2", "3", "4", "5"]),
    ]


def validate_topic(raw):
    if not raw["name"]:
        raise ValueError("Please give the topic a name.")
    return {
        "name": raw["name"],
        "est_minutes": parse_int(raw["est_minutes"], "Estimated minutes", 5, 2000),
        "difficulty": parse_int(raw["difficulty"], "Difficulty", 1, 5),
    }


# ----------------------------------------------------------------------
# Main application
# ----------------------------------------------------------------------
class RePlanDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1180x720")
        self.minsize(1000, 620)
        self.configure(bg=THEME["bg"])

        self.file_path: Optional[Path] = None
        self.note = ""
        self.alerts: List[str] = []
        self._set_state(default_semester(date.today()), [], [], date.today())

        self._styles()
        self._menu()
        self._layout()
        self.replan()

    # ---------------- state ----------------
    def _set_state(self, semester, courses, milestones, plan_today):
        self.semester = semester
        self.courses = courses
        self.milestones = milestones
        self.plan_today = plan_today
        self.alerts = []
        self.note = ""

    def _course_named(self, name: str) -> Optional[Course]:
        for c in self.courses:
            if c.name.lower() == name.lower():
                return c
        return None

    def _selected_sidebar_course(self) -> Optional[Course]:
        sel = self.course_tree.selection()
        return self._course_named(sel[0]) if sel else None

    def _topic_course(self) -> Optional[Course]:
        return self._course_named(self.topic_course.get())

    # ---------------- styling ----------------
    def _styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg, text = THEME["bg"], THEME["text"]
        style.configure(".", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg)
        style.configure("Muted.TLabel", background=bg, foreground=THEME["muted"])
        style.configure("TLabelframe", background=bg)
        style.configure("TLabelframe.Label", background=bg, foreground=THEME["accent"],
                        font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", padding=(14, 6), font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background=THEME["accent"], foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=(10, 4))
        style.map("Accent.TButton", background=[("active", THEME["accent_hover"])])
        style.configure("Treeview", background="white", fieldbackground="white", rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Horizontal.TProgressbar", background=THEME["accent"])

    # ---------------- menu ----------------
    def _menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New plan", command=self.new_plan)
        file_menu.add_command(label="Load demo (Programming · Calculus · Networks)",
                              command=self.load_demo)
        file_menu.add_separator()
        file_menu.add_command(label="Open…", accelerator="Ctrl+O", command=self.open_plan)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_plan)
        file_menu.add_command(label="Save as…", command=self.save_plan_as)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)
        self.bind("<Control-s>", lambda e: self.save_plan())
        self.bind("<Control-o>", lambda e: self.open_plan())

    # ---------------- layout ----------------
    def _layout(self):
        header = tk.Frame(self, bg=THEME["header"])
        header.pack(fill="x")
        tk.Label(header, text="🎓 RePlan Desktop", bg=THEME["header"], fg=THEME["text"],
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(header, text="Your semester, planned smarter ✨", bg=THEME["header"],
                 fg=THEME["muted"], font=("Segoe UI", 10, "italic")).pack(side="left")
        self.banner = tk.Label(header, text="", bg=THEME["header"], fg="#9A3412",
                               font=("Segoe UI", 10, "bold"))
        self.banner.pack(side="right", padx=16)

        self.status = tk.Label(self, text="Welcome! Load the demo or add a course to begin.",
                               anchor="w", bg=THEME["header"], fg=THEME["text"], padx=10, pady=4)
        self.status.pack(side="bottom", fill="x")

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        self._build_sidebar(body).pack(side="left", fill="y", padx=(0, 10))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(side="left", fill="both", expand=True)
        self._build_dashboard_tab()
        self._build_schedule_tab()
        self._build_topics_tab()

    def _build_sidebar(self, parent):
        side = ttk.Frame(parent)

        cfg = ttk.LabelFrame(side, text="🗓  Semester", padding=10)
        cfg.pack(fill="x")
        self.var_start = tk.StringVar()
        self.var_end = tk.StringVar()
        self.var_hours = tk.StringVar()
        self.var_today = tk.StringVar()
        rows = [
            ("Start (YYYY-MM-DD)", self.var_start),
            ("End (YYYY-MM-DD)", self.var_end),
            ("Daily study hours", self.var_hours),
            ("Today (plan date)", self.var_today),
        ]
        for r, (label, var) in enumerate(rows):
            ttk.Label(cfg, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(cfg, textvariable=var, width=14).grid(row=r, column=1, sticky="e", pady=3, padx=(8, 0))
        btns = ttk.Frame(cfg)
        btns.grid(row=len(rows), column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="💾 Apply", style="Accent.TButton", command=self.apply_settings).pack(side="left")
        ttk.Button(btns, text="⏭ Next day", command=self.next_day).pack(side="left", padx=6)

        crs = ttk.LabelFrame(side, text="📚  Courses", padding=10)
        crs.pack(fill="both", expand=True, pady=(10, 0))
        frame, self.course_tree = make_tree(crs, [
            ("icon", "", 36, "center"),
            ("name", "Course", 120, "w"),
            ("ch", "CH", 40, "center"),
            ("exam", "Exam", 90, "center"),
        ], height=8)
        frame.pack(fill="both", expand=True)
        self.course_tree.bind("<<TreeviewSelect>>", self._on_course_select)
        self.course_tree.bind("<Double-1>", lambda e: self.edit_course())

        row = ttk.Frame(crs)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="＋ Add", command=self.add_course).pack(side="left")
        ttk.Button(row, text="✏ Edit", command=self.edit_course).pack(side="left", padx=4)
        ttk.Button(row, text="🗑 Remove", command=self.delete_course).pack(side="left")
        return side

    def _build_dashboard_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="🏠 Dashboard")

        today_box = ttk.LabelFrame(tab, text="🌸 Today's Cozy Study Cups", padding=10)
        today_box.pack(fill="x")
        frame, self.today_tree = make_tree(today_box, [
            ("course", "Course", 200, "w"),
            ("topic", "Milestone", 340, "w"),
            ("minutes", "Time", 90, "center"),
            ("status", "Status", 110, "w"),
        ], height=4)
        frame.pack(fill="x")
        self.today_tree.tag_configure("done", background=THEME["done"])
        row = ttk.Frame(today_box)
        row.pack(fill="x", pady=(8, 0))
        self.today_total = ttk.Label(row, text="")
        self.today_total.pack(side="left")
        ttk.Button(row, text="✨ Yay! Finished All Today's Study! 🎉", style="Accent.TButton",
                   command=self.finish_today).pack(side="right")

        progress_box = ttk.LabelFrame(tab, text="📈 Progress", padding=10)
        progress_box.pack(fill="x", pady=10)
        self.progress_frame = ttk.Frame(progress_box)
        self.progress_frame.pack(fill="x")

        insight_box = ttk.LabelFrame(tab, text="🧠 Feasibility & Insights", padding=10)
        insight_box.pack(fill="both", expand=True)
        self.alert_box = tk.Text(insight_box, height=7, wrap="word", bg="white", relief="flat",
                                 padx=8, pady=6, font=("Segoe UI", 10), state="disabled")
        self.alert_box.pack(fill="both", expand=True)
        self.alert_box.tag_configure("warn", background=THEME["danger"])
        self.alert_box.tag_configure("ok", background=THEME["ok"])
        self.alert_box.tag_configure("info", foreground=THEME["muted"])

    def _build_schedule_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="📅 Schedule")

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="✅ Mark done", style="Accent.TButton",
                   command=lambda: self._mark_selected(True)).pack(side="left")
        ttk.Button(bar, text="↩ Mark not done",
                   command=lambda: self._mark_selected(False)).pack(side="left", padx=6)
        ttk.Button(bar, text="🔄 Replan", command=self.replan).pack(side="left")
        ttk.Label(bar, text="Double-click a row to toggle it", style="Muted.TLabel").pack(side="right")

        frame, self.sched_tree = make_tree(tab, [
            ("date", "Date", 120, "w"),
            ("course", "Course", 160, "w"),
            ("topic", "Milestone", 320, "w"),
            ("minutes", "Minutes", 80, "center"),
            ("status", "Status", 110, "w"),
        ], height=20)
        frame.pack(fill="both", expand=True)
        self.sched_tree.tag_configure("done", background=THEME["done"])
        self.sched_tree.tag_configure("today", background=THEME["today"])
        self.sched_tree.bind("<Double-1>", lambda e: self._mark_selected(None))

    def _build_topics_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="🧩 Topics")

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Course:").pack(side="left")
        self.topic_course = ttk.Combobox(bar, state="readonly", width=28)
        self.topic_course.pack(side="left", padx=6)
        self.topic_course.bind("<<ComboboxSelected>>", lambda e: self.refresh_topics())
        ttk.Button(bar, text="＋ Add topic", style="Accent.TButton",
                   command=self.add_topic).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="✏ Edit", command=self.edit_topic).pack(side="left", padx=4)
        ttk.Button(bar, text="🗑 Delete", command=self.delete_topic).pack(side="left")

        self.topic_summary = ttk.Label(tab, text="", style="Muted.TLabel")
        self.topic_summary.pack(anchor="w", pady=(0, 6))

        frame, self.topic_tree = make_tree(tab, [
            ("topic", "Topic", 260, "w"),
            ("est", "Estimate", 90, "center"),
            ("diff", "Difficulty", 100, "center"),
            ("done", "Done", 90, "center"),
            ("rem", "Remaining", 100, "center"),
            ("status", "Status", 130, "w"),
        ], height=18)
        frame.pack(fill="both", expand=True)
        self.topic_tree.bind("<Double-1>", lambda e: self.edit_topic())

    # ---------------- refresh ----------------
    def refresh_all(self):
        self.refresh_sidebar()
        self.refresh_schedule()
        self.refresh_today()
        self.refresh_progress()
        self.refresh_alerts()
        self.refresh_topics()
        self.refresh_banner()

    def refresh_sidebar(self):
        self.var_start.set(iso(self.semester.start))
        self.var_end.set(iso(self.semester.end))
        self.var_hours.set(f"{self.semester.daily_minutes / 60:g}")
        self.var_today.set(iso(self.plan_today))
        clear_tree(self.course_tree)
        for c in sorted(self.courses, key=lambda c: c.exam_date):
            self.course_tree.insert("", "end", iid=c.name,
                                    values=(c.icon, c.name, c.credit_hours, f"{c.exam_date:%b %d}"))

    def _status(self, m: Milestone) -> Tuple[str, str]:
        if m.done:
            return "✅ Done", "done"
        if m.day == self.plan_today:
            return "🌸 Today", "today"
        return "📅 Planned", ""

    def refresh_schedule(self):
        clear_tree(self.sched_tree)
        icons = {c.name: c.icon for c in self.courses}
        for i, m in enumerate(self.milestones):
            status, tag = self._status(m)
            self.sched_tree.insert(
                "", "end", iid=str(i), tags=(tag,) if tag else (),
                values=(f"{m.day:%a %b %d}", f"{icons.get(m.course, '')} {m.course}",
                        m.topic, m.minutes, status),
            )

    def refresh_today(self):
        clear_tree(self.today_tree)
        icons = {c.name: c.icon for c in self.courses}
        todays = [m for m in self.milestones if m.day == self.plan_today]
        for i, m in enumerate(self.milestones):
            if m.day != self.plan_today:
                continue
            status, tag = self._status(m)
            self.today_tree.insert("", "end", iid=f"t{i}", tags=(tag,) if tag == "done" else (),
                                   values=(f"{icons.get(m.course, '')} {m.course}", m.topic,
                                           f"{m.minutes} min", status))
        pending = sum(m.minutes for m in todays if not m.done)
        if not self.courses:
            text = "Add a course to get started 🌱"
        elif not todays:
            text = "No sessions today. Enjoy the breather 🌷"
        else:
            text = f"Left today: {fmt_min(pending)} (daily cap {fmt_min(self.semester.daily_minutes)})"
        self.today_total.config(text=text)

    def refresh_progress(self):
        for w in self.progress_frame.winfo_children():
            w.destroy()
        if not self.courses:
            ttk.Label(self.progress_frame, text="No courses yet. Add one to see progress here 🌱").pack(anchor="w")
            return
        done_by_topic = topic_done_minutes(self.milestones)
        for row, c in enumerate(self.courses):
            total = c.total_minutes
            done = sum(min(done_by_topic.get((c.name, t.name), 0), t.est_minutes) for t in c.topics)
            pct = 100 * done / total if total else 0
            ttk.Label(self.progress_frame,
                      text=f"{c.icon} {c.name}  ·  {c.credit_hours} CH  ·  exam {c.exam_date:%b %d}",
                      width=44, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
            ttk.Progressbar(self.progress_frame, maximum=100, value=pct,
                            length=260).grid(row=row, column=1, padx=10)
            ttk.Label(self.progress_frame,
                      text=f"{fmt_min(done)} / {fmt_min(total)}  ({pct:.0f}%)").grid(row=row, column=2, sticky="w")

    def refresh_alerts(self):
        box = self.alert_box
        box.config(state="normal")
        box.delete("1.0", "end")
        pending = [m for m in self.milestones if not m.done]
        days = len({m.day for m in pending})
        box.insert("end", f"📊 {len(pending)} milestone(s) across {days} study day(s) · "
                          f"daily cap {fmt_min(self.semester.daily_minutes)}\n", "info")
        if self.alerts:
            for alert in self.alerts:
                box.insert("end", f"⚠ {alert}\n", "warn")
        else:
            box.insert("end", "✅ Everything fits before your exam dates. You've got this! 💜\n", "ok")
        box.config(state="disabled")

    def refresh_topics(self):
        names = [c.name for c in self.courses]
        self.topic_course.config(values=names)
        if self.topic_course.get() not in names:
            self.topic_course.set(names[0] if names else "")
        clear_tree(self.topic_tree)

        course = self._topic_course()
        if course is None:
            self.topic_summary.config(text="Add a course first, then break it into topics. 🌱")
            return
        done_by_topic = topic_done_minutes(self.milestones)
        for t in course.topics:
            done = min(done_by_topic.get((course.name, t.name), 0), t.est_minutes)
            rem = t.est_minutes - done
            if rem == 0:
                status = "✅ Complete"
            elif done:
                status = "🔥 In progress"
            else:
                status = "⏳ Not started"
            dots = "●" * t.difficulty + "○" * (5 - t.difficulty)
            self.topic_tree.insert("", "end", iid=t.name,
                                   values=(t.name, f"{t.est_minutes} min", dots,
                                           f"{done} min", f"{rem} min", status))
        self.topic_summary.config(
            text=f"{course.icon} {course.name} · {course.credit_hours} CH · "
                 f"{len(course.topics)} topics · {fmt_min(course.total_minutes)} estimated"
        )

    def refresh_banner(self):
        parts = []
        if self.note:
            parts.append(self.note)
        if self.alerts:
            parts.append(f"⚠ {len(self.alerts)} feasibility alert(s)")
        self.banner.config(text="  ·  ".join(parts))

    def set_status(self, text: str):
        self.status.config(text=text)

    # ---------------- core actions ----------------
    def replan(self):
        """Keep completed work, rebuild everything else from plan_today."""
        missed = [m for m in self.milestones if not m.done and m.day < self.plan_today]
        done = [m for m in self.milestones if m.done]
        new_ms, self.alerts = build_schedule(self.courses, self.semester, self.plan_today, done)
        self.milestones = sorted(done + new_ms, key=lambda m: (m.day, m.course, m.topic))
        self.note = f"🔄 Rebuilt {len(missed)} missed session(s)" if missed else ""

        name = self.file_path.name if self.file_path else "untitled plan"
        self.title(f"RePlan Desktop 🎓 — {name}")
        self.refresh_all()

        msg = f"🗓 Plan rebuilt from {self.plan_today:%b %d}: {len(new_ms)} milestone(s) scheduled"
        if missed:
            msg += f" · rescheduled {len(missed)} missed"
        if self.alerts:
            msg += f" · ⚠ {len(self.alerts)} alert(s)"
        self.set_status(msg)

    def apply_settings(self):
        try:
            start = parse_date(self.var_start.get(), "Semester start")
            end = parse_date(self.var_end.get(), "Semester end")
            today = parse_date(self.var_today.get(), "Today")
            hours = parse_hours(self.var_hours.get())
            if end < start:
                raise ValueError("Semester end must be on or after the start date.")
        except ValueError as exc:
            messagebox.showerror("Check your settings", str(exc), parent=self)
            return
        self.semester = Semester(start, end, round(hours * 60))
        self.plan_today = today
        self.replan()

    def next_day(self):
        """Simulate a day passing (useful for testing missed sessions)."""
        self.var_today.set(iso(self.plan_today + timedelta(days=1)))
        self.apply_settings()

    def _selected_milestone(self) -> Optional[Milestone]:
        sel = self.sched_tree.selection()
        return self.milestones[int(sel[0])] if sel else None

    def _mark_selected(self, done: Optional[bool]):
        m = self._selected_milestone()
        if m is None:
            self.set_status("🌷 Select a milestone in the Schedule tab first.")
            return
        m.done = (not m.done) if done is None else done
        self.replan()

    def finish_today(self):
        count = 0
        for m in self.milestones:
            if m.day == self.plan_today and not m.done:
                m.done = True
                count += 1
        if not count:
            messagebox.showinfo("All caught up", "Nothing left for today. You're already all caught up! 🌷",
                                parent=self)
            return
        self.replan()
        messagebox.showinfo("🎉 Yay!", f"Amazing work! {count} session(s) complete.\n"
                                       "Your remaining plan has been updated. 💜", parent=self)

    def _on_course_select(self, _event=None):
        sel = self.course_tree.selection()
        if sel:
            self.topic_course.set(sel[0])
            self.refresh_topics()

    # ---------------- courses ----------------
    def add_course(self):
        res = FormDialog.ask(self, "➕ Add a course", course_fields(), validate_course)
        if res is None:
            return
        if self._course_named(res["name"]):
            messagebox.showerror("Duplicate course", f"'{res['name']}' already exists.", parent=self)
            return
        self.courses.append(Course(res["name"], res["icon"], res["credit_hours"], res["exam_date"]))
        self.replan()

    def edit_course(self):
        course = self._selected_sidebar_course()
        if course is None:
            self.set_status("🌷 Select a course first.")
            return
        res = FormDialog.ask(self, f"✏ Edit {course.name}", course_fields(course), validate_course)
        if res is None:
            return
        other = self._course_named(res["name"])
        if other is not None and other is not course:
            messagebox.showerror("Duplicate course", f"'{res['name']}' already exists.", parent=self)
            return
        old_name = course.name
        for m in self.milestones:
            if m.course == old_name:
                m.course = res["name"]
        for key, value in res.items():
            setattr(course, key, value)
        self.replan()

    def delete_course(self):
        course = self._selected_sidebar_course()
        if course is None:
            self.set_status("🌷 Select a course first.")
            return
        if not messagebox.askyesno("Remove course",
                                   f"Remove {course.name} and all its milestones?", parent=self):
            return
        self.courses.remove(course)
        self.milestones = [m for m in self.milestones if m.course != course.name]
        self.replan()

    # ---------------- topics ----------------
    def add_topic(self):
        course = self._topic_course()
        if course is None:
            self.set_status("🌷 Add a course first.")
            return
        res = FormDialog.ask(self, f"➕ Add topic to {course.name}", topic_fields(), validate_topic)
        if res is None:
            return
        if any(t.name.lower() == res["name"].lower() for t in course.topics):
            messagebox.showerror("Duplicate topic", "That topic already exists in this course.", parent=self)
            return
        course.topics.append(Topic(res["name"], res["est_minutes"], res["difficulty"]))
        self.replan()

    def _selected_topic(self, course: Course) -> Optional[Topic]:
        sel = self.topic_tree.selection()
        if not sel:
            return None
        return next((t for t in course.topics if t.name == sel[0]), None)

    def edit_topic(self):
        course = self._topic_course()
        topic = self._selected_topic(course) if course else None
        if topic is None:
            self.set_status("🌷 Select a topic first.")
            return
        res = FormDialog.ask(self, f"✏ Edit {topic.name}", topic_fields(topic), validate_topic)
        if res is None:
            return
        if res["name"].lower() != topic.name.lower() and any(
                t.name.lower() == res["name"].lower() for t in course.topics):
            messagebox.showerror("Duplicate topic", "That topic already exists in this course.", parent=self)
            return
        old_name = topic.name
        for m in self.milestones:
            if m.course == course.name and m.topic == old_name:
                m.topic = res["name"]
        for key, value in res.items():
            setattr(topic, key, value)
        self.replan()

    def delete_topic(self):
        course = self._topic_course()
        topic = self._selected_topic(course) if course else None
        if topic is None:
            self.set_status("🌷 Select a topic first.")
            return
        if not messagebox.askyesno("Delete topic",
                                   f"Delete '{topic.name}' and its milestones?", parent=self):
            return
        course.topics.remove(topic)
        self.milestones = [m for m in self.milestones
                           if not (m.course == course.name and m.topic == topic.name)]
        self.replan()

    # ---------------- demo / new ----------------
    def new_plan(self):
        if self.courses and not messagebox.askyesno(
                "Start a new plan?", "This clears the current plan. Make sure you've saved first.", parent=self):
            return
        today = date.today()
        self._set_state(default_semester(today), [], [], today)
        self.file_path = None
        self.replan()

    def load_demo(self):
        today = date.today()

        def d(days: int) -> date:
            return today + timedelta(days=days)

        courses = [
            Course("Programming", "💻", 4, d(70), [
                Topic("Variables & control flow", 120, 2),
                Topic("Functions and parameters", 180, 3),
                Topic("Recursion", 150, 4),
                Topic("Lists & dictionaries", 150, 3),
                Topic("Final project", 240, 5),
            ]),
            Course("Calculus", "📐", 3, d(80), [
                Topic("Limits", 120, 3),
                Topic("Derivatives", 180, 4),
                Topic("Integration", 210, 5),
                Topic("Integration practice", 120, 4),
            ]),
            Course("Networks", "🌐", 3, d(75), [
                Topic("OSI model revision", 90, 2),
                Topic("TCP/IP", 120, 3),
                Topic("Routing", 120, 4),
                Topic("Subnetting", 150, 4),
            ]),
        ]
        self._set_state(Semester(today, today + timedelta(days=110), 150), courses, [], today)
        self.file_path = None
        self.replan()
        self.set_status("🌸 Demo loaded: 3 courses, 2.5 h/day. Try ⏭ Next day, then mark some sessions done!")

    # ---------------- save / open ----------------
    def _to_dict(self) -> dict:
        return {
            "app": "RePlan",
            "version": 1,
            "semester": {
                "start": iso(self.semester.start),
                "end": iso(self.semester.end),
                "daily_minutes": self.semester.daily_minutes,
            },
            "plan_today": iso(self.plan_today),
            "courses": [
                {
                    "name": c.name,
                    "icon": c.icon,
                    "credit_hours": c.credit_hours,
                    "exam_date": iso(c.exam_date),
                    "topics": [{"name": t.name, "est_minutes": t.est_minutes,
                                "difficulty": t.difficulty} for t in c.topics],
                }
                for c in self.courses
            ],
            "milestones": [
                {"course": m.course, "topic": m.topic, "day": iso(m.day),
                 "minutes": m.minutes, "done": m.done}
                for m in self.milestones
            ],
        }

    def _from_dict(self, data: dict):
        s = data["semester"]
        semester = Semester(parse_date(s["start"], "Start"), parse_date(s["end"], "End"),
                            int(s["daily_minutes"]))
        courses = [
            Course(
                name=c["name"],
                icon=c.get("icon", ICONS[0]),
                credit_hours=int(c["credit_hours"]),
                exam_date=parse_date(c["exam_date"], "Exam date"),
                topics=[Topic(t["name"], int(t["est_minutes"]), int(t.get("difficulty", 3)))
                        for t in c["topics"]],
            )
            for c in data["courses"]
        ]
        milestones = [
            Milestone(m["course"], m["topic"], parse_date(m["day"], "Milestone day"),
                      int(m["minutes"]), bool(m["done"]))
            for m in data.get("milestones", [])
        ]
        saved_today = parse_date(data.get("plan_today", iso(date.today())), "Plan date")
        # Plans catch up to the real calendar when reopened.
        plan_today = max(saved_today, date.today())
        self._set_state(semester, courses, milestones, plan_today)

    def save_plan(self):
        if self.file_path is None:
            self.save_plan_as()
        else:
            self._write(self.file_path)

    def save_plan_as(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            filetypes=[("RePlan plan", "*.json")],
                                            initialfile="my_semester.json")
        if path:
            self.file_path = Path(path)
            self._write(self.file_path)

    def _write(self, path: Path):
        try:
            path.write_text(json.dumps(self._to_dict(), indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save", str(exc), parent=self)
            return
        self.title(f"RePlan Desktop 🎓 — {path.name}")
        self.set_status(f"💾 Saved to {path.name}")

    def open_plan(self):
        path = filedialog.askopenfilename(parent=self,
                                          filetypes=[("RePlan plan", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self._from_dict(data)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror("Could not open plan",
                                 f"That file isn't a valid RePlan plan.\n\n{exc}", parent=self)
            return
        self.file_path = Path(path)
        self.replan()
        self.set_status(f"📂 Opened {self.file_path.name}")


if __name__ == "__main__":
    RePlanDesktop().mainloop()