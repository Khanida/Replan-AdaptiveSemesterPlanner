"""
RePlan v1.1 — Cozy & Friendly Adaptive Multi-Course Semester Planner 🌸🎓
GUI Desktop Application

Designed to be your supportive, delightful academic companion!
Transforms multiple course outlines, distinct exam dates, and credit hours
into manageable, stress-free daily study milestones.

When life gets busy and you miss a session, RePlan v1.1 gently redistributes
your tasks strictly before each course's individual exam deadline, highlights
rescheduled tasks in dreamy lavender, and keeps your study pace peaceful and balanced.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
import os
import random
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
import webbrowser

import pandas as pd

# Google Calendar API imports (graceful optional check)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


# ---------------------------------------------------------------------------
# Cute & Friendly Color Palette ("Cozy Pastel Scholar" Theme)
# ---------------------------------------------------------------------------
BG_CREAM = "#faf7f2"        # Cozy warm pearl / cream app background
BG_HEADER = "#241e38"       # Deep twilight velvet with subtle violet warmth
BG_CARD = "#ffffff"         # Crisp clean white surface for cards
BORDER_COZY = "#eeded2"     # Soft warm cashmere border
BORDER_LIGHT = "#f1ece5"    # Very gentle divider border

TEXT_DARK = "#28233a"       # Rich cozy dark espresso text (high contrast)
TEXT_MUTED = "#766d86"      # Soft heather purple-gray text
TEXT_LIGHT = "#fdfbf7"      # Inverted warm light text

# Cheerful & Pastel Accents
COLOR_BLOSSOM = "#8b5cf6"       # Dreamy Lavender Violet (Primary)
COLOR_BLOSSOM_HOVER = "#7c3aed"
COLOR_BLOSSOM_BG = "#f3e8ff"
COLOR_BLOSSOM_TEXT = "#581c87"

COLOR_MINT = "#10b981"          # Matcha Mint Green (Success / Done)
COLOR_MINT_HOVER = "#059669"
COLOR_MINT_BG = "#ecfdf5"
COLOR_MINT_TEXT = "#065f46"

COLOR_PEACH = "#f43f5e"         # Soft Strawberry Coral (Missed / Gentle alert)
COLOR_PEACH_HOVER = "#e11d48"
COLOR_PEACH_BG = "#fff1f2"
COLOR_PEACH_TEXT = "#9f1239"

COLOR_HONEY = "#f59e0b"         # Warm Honey Amber (Today / Attention)
COLOR_HONEY_HOVER = "#d97706"
COLOR_HONEY_BG = "#fef3c7"
COLOR_HONEY_TEXT = "#78350f"

COLOR_SKY = "#0ea5e9"           # Sky Bubble Blue (Info)
COLOR_SKY_BG = "#f0f9ff"
COLOR_SKY_TEXT = "#0369a1"

# Rescheduled Highlighting Palette (Dreamy Lavender & Violet)
COLOR_RESCHEDULED_BG = "#f3e8ff"     # Soft Lavender 100
COLOR_RESCHEDULED_TEXT = "#581c87"   # Deep Violet 900
COLOR_RESCHEDULED_BORDER = "#d8b4fe" # Lilac 300

# Cute Course Badges & Icons
COURSE_THEMES = [
    {"name": "Lavender Dream", "icon": "💻", "primary": "#7c3aed", "bg": "#ede9fe", "text": "#5b21b6"},
    {"name": "Mint Matcha",     "icon": "📐", "primary": "#059669", "bg": "#d1fae5", "text": "#065f46"},
    {"name": "Peach Sunset",    "icon": "🌐", "primary": "#ea580c", "bg": "#ffedd5", "text": "#9a3412"},
    {"name": "Sakura Blossom",  "icon": "🔬", "primary": "#db2777", "bg": "#fce7f3", "text": "#9d174d"},
    {"name": "Sky Breeze",      "icon": "📖", "primary": "#0284c7", "bg": "#e0f2fe", "text": "#075985"},
    {"name": "Honey Butter",    "icon": "🎨", "primary": "#d97706", "bg": "#fef3c7", "text": "#92400e"},
    {"name": "Emerald Leaf",    "icon": "🧠", "primary": "#0d9488", "bg": "#ccfbf1", "text": "#115e59"},
]

DEFAULT_CSV_PATH = "replanv1_semester_plan.csv"
STUDY_HOURS_PER_CH = 45.0  # 1 Credit Hour = 45 study hours

# Friendly Motivational Quotes & Study Tips
CHEERFUL_QUOTES = [
    "🌱 Small cozy study sessions turn into magnificent semester blooms!",
    "✨ You are doing wonderfully. One gentle step at a time!",
    "☕ Grab a warm drink, take a deep breath, and let's explore today's goals!",
    "🌸 Missing a session happens to everyone! RePlan gently rearranged it for you 💖",
    "💫 Progress isn't about perfection; it's about showing up with a smile!",
    "🌿 Celebrate every topic you check off — every bit of learning counts!",
    "🧁 You've got this! Be kind to yourself while you learn and grow.",
]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class CourseConfig:
    name: str
    credit_hours: float
    exam_date: date
    topics: List[str]
    color: str = "#7c3aed"
    icon: str = "📚"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "credit_hours": self.credit_hours,
            "exam_date": self.exam_date.strftime("%Y-%m-%d"),
            "topics": self.topics,
            "color": self.color,
            "icon": self.icon,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CourseConfig:
        exam_d = datetime.strptime(data["exam_date"], "%Y-%m-%d").date()
        return cls(
            name=data["name"],
            credit_hours=float(data["credit_hours"]),
            exam_date=exam_d,
            topics=list(data.get("topics", [])),
            color=data.get("color", "#7c3aed"),
            icon=data.get("icon", "📚"),
        )


@dataclass
class TopicPeriod:
    course_name: str
    topic_num: int
    topic: str
    duration_days: int
    total_hours: float
    start_date: str
    end_date: str
    completed_days: int = 0
    missed_days: int = 0
    pending_days: int = 0

    @property
    def progress_pct(self) -> float:
        if self.duration_days == 0:
            return 0.0
        return round((self.completed_days / self.duration_days) * 100, 1)


# ---------------------------------------------------------------------------
# Multi-Course Scheduling & Adaptive Rescheduling Engine
# ---------------------------------------------------------------------------
class MultiCourseReplanEngine:
    """Core scheduling engine supporting multiple courses with individual outlines and exam dates."""

    @staticmethod
    def parse_date(date_str: str) -> date:
        """Flexible parser supporting YYYY-MM-DD, slashes, or word formats."""
        clean = date_str.strip()
        if not clean:
            raise ValueError("Please provide a valid date.")
        try:
            return pd.to_datetime(clean).date()
        except Exception:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                try:
                    return datetime.strptime(clean, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse '{clean}'. Please use YYYY-MM-DD format (e.g. 2026-12-15).")

    @staticmethod
    def generate_multi_course_schedule(
        courses: List[CourseConfig],
        start_date: Optional[date] = None,
        hours_per_ch: float = STUDY_HOURS_PER_CH,
    ) -> Tuple[pd.DataFrame, List[TopicPeriod], Dict[str, Any]]:
        if not courses:
            raise ValueError("🌸 Please add at least one course to start building your study plan!")

        curr_date = start_date or date.today()
        all_rows: List[Dict[str, Any]] = []
        topic_periods: List[TopicPeriod] = []
        course_meta: Dict[str, Any] = {}

        seen_names = set()
        for c in courses:
            clean_name = c.name.strip()
            if not clean_name:
                raise ValueError("Course name cannot be blank.")
            if clean_name in seen_names:
                raise ValueError(f"Duplicate course name: '{clean_name}'. Please make each course name distinct.")
            seen_names.add(clean_name)

            if c.credit_hours <= 0:
                raise ValueError(f"Credit hours for '{clean_name}' must be greater than zero.")

            clean_topics = [t.strip() for t in c.topics if t.strip()]
            if not clean_topics:
                raise ValueError(f"Please provide at least one topic for '{clean_name}'.")

            rem_days = (c.exam_date - curr_date).days
            if rem_days <= 0:
                raise ValueError(
                    f"Exam date for '{clean_name}' ({c.exam_date}) must be in the future (after {curr_date})."
                )

            num_topics = len(clean_topics)
            total_study_hours = round(c.credit_hours * hours_per_ch, 2)
            daily_hours = round(total_study_hours / rem_days, 2)

            base_days = rem_days // num_topics
            extra_days = rem_days % num_topics
            durations = [base_days + 1 if i < extra_days else base_days for i in range(num_topics)]

            course_meta[clean_name] = {
                "credit_hours": c.credit_hours,
                "total_study_hours": total_study_hours,
                "daily_hours": daily_hours,
                "rem_days": rem_days,
                "exam_date": c.exam_date.strftime("%Y-%m-%d"),
                "topics": clean_topics,
                "color": c.color,
                "icon": c.icon,
            }

            day_counter = 0
            for idx, topic in enumerate(clean_topics):
                dur = durations[idx]
                topic_start = curr_date + timedelta(days=day_counter)
                topic_end = curr_date + timedelta(days=day_counter + max(0, dur - 1))
                topic_hours = round(dur * daily_hours, 1)

                topic_periods.append(
                    TopicPeriod(
                        course_name=clean_name,
                        topic_num=idx + 1,
                        topic=topic,
                        duration_days=dur,
                        total_hours=topic_hours,
                        start_date=topic_start.strftime("%Y-%m-%d"),
                        end_date=topic_end.strftime("%Y-%m-%d"),
                        pending_days=dur,
                    )
                )

                for d in range(dur):
                    day_date = curr_date + timedelta(days=day_counter)
                    all_rows.append(
                        {
                            "Date": day_date.strftime("%Y-%m-%d"),
                            "Weekday": day_date.strftime("%A"),
                            "Course": clean_name,
                            "Topic Day": f"{d + 1}/{dur}",
                            "Topic": topic,
                            "Target Hours": daily_hours,
                            "Status": "Pending",
                            "Rescheduled_From": "",
                        }
                    )
                    day_counter += 1

        df = pd.DataFrame(all_rows)
        df = df.sort_values(by=["Date", "Course"]).reset_index(drop=True)

        date_to_day: Dict[str, int] = {}
        for d_str in df["Date"].unique():
            row_d = datetime.strptime(d_str, "%Y-%m-%d").date()
            date_to_day[d_str] = (row_d - curr_date).days + 1

        df["Day"] = df["Date"].map(date_to_day)

        ordered_cols = [
            "Day",
            "Date",
            "Weekday",
            "Course",
            "Topic Day",
            "Topic",
            "Target Hours",
            "Status",
            "Rescheduled_From",
        ]
        df = df[ordered_cols]

        nearest_exam = min(c.exam_date for c in courses)
        latest_exam = max(c.exam_date for c in courses)
        total_ch = sum(c.credit_hours for c in courses)
        total_study_hours = sum(m["total_study_hours"] for m in course_meta.values())

        summary = {
            "start_date": curr_date.strftime("%Y-%m-%d"),
            "nearest_exam_date": nearest_exam.strftime("%Y-%m-%d"),
            "latest_exam_date": latest_exam.strftime("%Y-%m-%d"),
            "days_to_nearest_exam": (nearest_exam - curr_date).days,
            "total_courses": len(courses),
            "total_credit_hours": total_ch,
            "total_study_hours": total_study_hours,
            "courses": course_meta,
        }
        return df, topic_periods, summary

    @staticmethod
    def compute_topic_periods_from_df(df: pd.DataFrame) -> List[TopicPeriod]:
        if df.empty or "Course" not in df.columns or "Topic" not in df.columns:
            return []

        periods: List[TopicPeriod] = []
        for course_name in df["Course"].unique():
            course_df = df[df["Course"] == course_name]

            unique_topics: List[str] = []
            for t in course_df["Topic"]:
                clean_t = str(t).split(" • 🔄")[0].split(" (🔄")[0].strip()
                if not unique_topics or unique_topics[-1] != clean_t:
                    unique_topics.append(clean_t)

            topic_counter = 1
            for topic in unique_topics:
                mask = course_df["Topic"].apply(
                    lambda x: str(x).split(" • 🔄")[0].split(" (🔄")[0].strip() == topic
                )
                sub = course_df[mask]
                if sub.empty:
                    continue
                duration = len(sub)
                total_hours = round(float(sub["Target Hours"].sum()), 2)
                start_date = str(sub["Date"].iloc[0])
                end_date = str(sub["Date"].iloc[-1])
                comp = int((sub["Status"] == "Completed").sum())
                missed = int((sub["Status"] == "Missed").sum())
                pending = int((sub["Status"].isin(["Pending", "Rescheduled"])).sum())

                periods.append(
                    TopicPeriod(
                        course_name=str(course_name),
                        topic_num=topic_counter,
                        topic=topic,
                        duration_days=duration,
                        total_hours=total_hours,
                        start_date=start_date,
                        end_date=end_date,
                        completed_days=comp,
                        missed_days=missed,
                        pending_days=pending,
                    )
                )
                topic_counter += 1

        return periods

    @staticmethod
    def reschedule_missed_tasks(
        df: pd.DataFrame,
        today_date: Optional[date] = None,
        max_daily_cap: float = 5.0,
        course_baseline_hours: Optional[Dict[str, float]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Adaptive Rescheduling Engine:
        Gently catches missed past sessions and moves remaining curriculum forward
        strictly before each course's exam deadline with peaceful pace adjustments.
        """
        if df.empty:
            raise ValueError("No active study plan to adapt.")

        df = df.copy()
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""

        if today_date is None:
            today_date = date.today()

        date_series = pd.to_datetime(df["Date"]).dt.date

        # Mark past uncompleted as Missed
        past_uncompleted = (date_series < today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
        if past_uncompleted.any():
            df.loc[past_uncompleted, "Status"] = "Missed"

        unique_courses = df["Course"].unique().tolist()
        course_stats: Dict[str, Any] = {}
        total_rescheduled_count = 0
        first_rescheduled_info: Optional[Dict[str, str]] = None

        for c_name in unique_courses:
            c_mask = df["Course"] == c_name
            c_indices = df[c_mask].index.tolist()
            sub = df.loc[c_indices]

            curriculum = []
            for _, r in sub.iterrows():
                curriculum.append(
                    {
                        "Topic": str(r["Topic"]).split(" • 🔄")[0].split(" (🔄")[0].strip(),
                        "Topic Day": str(r["Topic Day"]).strip(),
                    }
                )

            num_completed = int((sub["Status"] == "Completed").sum())

            avail_mask = (c_mask) & (date_series >= today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
            avail_indices = df[avail_mask].index.tolist()
            num_available = len(avail_indices)

            missed_mask = (c_mask) & (df["Status"] == "Missed")
            missed_indices = df[missed_mask].index.tolist()
            num_missed = len(missed_indices)

            prev_target = float(sub.loc[avail_indices[0], "Target Hours"]) if avail_indices else 0.0
            course_resched_count = 0

            if num_missed > 0 and num_available > 0:
                for i, slot_idx in enumerate(avail_indices):
                    task_idx = num_completed + i
                    if task_idx < len(curriculum):
                        task = curriculum[task_idx]
                        df.loc[slot_idx, "Topic"] = task["Topic"]
                        df.loc[slot_idx, "Topic Day"] = task["Topic Day"]

                    if i < num_missed:
                        missed_idx = missed_indices[min(i, num_missed - 1)]
                        from_day = df.loc[missed_idx, "Day"]
                        from_date = df.loc[missed_idx, "Date"]
                        df.loc[slot_idx, "Status"] = "Rescheduled"
                        df.loc[slot_idx, "Rescheduled_From"] = f"Day {from_day} ({from_date})"
                        course_resched_count += 1
                        total_rescheduled_count += 1

                        if first_rescheduled_info is None:
                            first_rescheduled_info = {
                                "date": str(df.loc[slot_idx, "Date"]),
                                "course": c_name,
                                "topic": f"{df.loc[slot_idx, 'Topic']} ({df.loc[slot_idx, 'Topic Day']})",
                            }
                    else:
                        if df.loc[slot_idx, "Status"] == "Rescheduled":
                            df.loc[slot_idx, "Status"] = "Pending"
                            df.loc[slot_idx, "Rescheduled_From"] = ""
            else:
                for slot_idx in avail_indices:
                    if df.loc[slot_idx, "Status"] == "Rescheduled":
                        df.loc[slot_idx, "Status"] = "Pending"
                        df.loc[slot_idx, "Rescheduled_From"] = ""

            completed_hours = float(df.loc[(c_mask) & (df["Status"] == "Completed"), "Target Hours"].sum())
            baseline_h = (course_baseline_hours or {}).get(c_name)
            if baseline_h is not None and baseline_h > 0:
                uncompleted_hours = max(0.0, baseline_h - completed_hours)
            else:
                uncomp_mask = (c_mask) & (df["Status"].isin(["Pending", "Missed", "Rescheduled"]))
                uncompleted_hours = float(df.loc[uncomp_mask, "Target Hours"].sum())

            if num_available > 0:
                new_daily_hours = round(uncompleted_hours / num_available, 2)
            else:
                new_daily_hours = 0.0

            df.loc[avail_indices, "Target Hours"] = new_daily_hours

            course_stats[c_name] = {
                "num_available_days": num_available,
                "num_missed": num_missed,
                "num_completed": num_completed,
                "rescheduled_count": course_resched_count,
                "prev_target": prev_target,
                "new_daily_hours": new_daily_hours,
                "rate_change": round(new_daily_hours - prev_target, 2),
                "uncompleted_hours": round(uncompleted_hours, 2),
            }

        future_mask = date_series >= today_date
        future_df = df[future_mask]
        daily_pace_series = future_df[future_df["Status"].isin(["Pending", "Rescheduled"])].groupby("Date")["Target Hours"].sum()

        max_daily_pace = float(daily_pace_series.max()) if not daily_pace_series.empty else 0.0
        avg_daily_pace = float(daily_pace_series.mean()) if not daily_pace_series.empty else 0.0
        over_cap_dates = daily_pace_series[daily_pace_series > max_daily_cap].to_dict()

        overall_stats = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_rescheduled_count": total_rescheduled_count,
            "first_rescheduled": first_rescheduled_info,
            "max_daily_cap": max_daily_cap,
            "max_daily_pace": round(max_daily_pace, 2),
            "avg_daily_pace": round(avg_daily_pace, 2),
            "is_over_cap": len(over_cap_dates) > 0,
            "over_cap_days_count": len(over_cap_dates),
            "over_cap_dates": {k: round(v, 2) for k, v in list(over_cap_dates.items())[:5]},
            "course_stats": course_stats,
        }
        return df, overall_stats

    @staticmethod
    def load_csv(filepath: str) -> Tuple[pd.DataFrame, List[CourseConfig]]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        df = pd.read_csv(filepath)
        required_cols = ["Day", "Date", "Weekday", "Target Hours", "Topic Day", "Topic", "Status"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"CSV is missing expected columns: {missing}")

        if "Course" not in df.columns:
            df["Course"] = "Course 1"

        df["Day"] = pd.to_numeric(df["Day"], errors="coerce").fillna(0).astype(int)
        df["Target Hours"] = pd.to_numeric(df["Target Hours"], errors="coerce").fillna(0.0).round(2)
        df["Status"] = df["Status"].fillna("Pending").astype(str)
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""
        else:
            df["Rescheduled_From"] = df["Rescheduled_From"].fillna("").astype(str)

        courses: List[CourseConfig] = []
        meta_path = filepath + ".meta.json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("courses", []):
                        courses.append(CourseConfig.from_dict(item))
            except Exception as e:
                print(f"Warning: could not load companion metadata: {e}")

        if not courses:
            for idx, c_name in enumerate(df["Course"].unique()):
                sub = df[df["Course"] == c_name]
                last_d = pd.to_datetime(sub["Date"].iloc[-1]).date()
                unique_topics = list(dict.fromkeys(
                    str(t).split(" • 🔄")[0].split(" (🔄")[0].strip() for t in sub["Topic"]
                ))
                approx_hours = float(sub["Target Hours"].sum())
                approx_ch = max(1.0, round(approx_hours / STUDY_HOURS_PER_CH, 1))
                theme = COURSE_THEMES[idx % len(COURSE_THEMES)]
                courses.append(
                    CourseConfig(
                        name=str(c_name),
                        credit_hours=approx_ch,
                        exam_date=last_d,
                        topics=unique_topics,
                        color=theme["primary"],
                        icon=theme["icon"],
                    )
                )

        return df, courses

    @staticmethod
    def save_csv(df: pd.DataFrame, filepath: str, courses: Optional[List[CourseConfig]] = None) -> None:
        df.to_csv(filepath, index=False)
        if courses:
            meta_path = filepath + ".meta.json"
            try:
                meta_data = {"courses": [c.to_dict() for c in courses]}
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
            except Exception as e:
                print(f"Warning: could not write metadata: {e}")


# ---------------------------------------------------------------------------
# Cute Metric Card Widget
# ---------------------------------------------------------------------------
class CuteMetricCard(tk.Frame):
    """Pastel-accented card with friendly icons and soft rounded aesthetic."""

    def __init__(
        self,
        parent,
        title: str,
        initial_val: str = "--",
        subtitle: str = "",
        accent_color: str = COLOR_BLOSSOM,
        icon: str = "🌸",
        **kwargs,
    ):
        super().__init__(
            parent,
            bg=BG_CARD,
            highlightthickness=1,
            highlightbackground=BORDER_COZY,
            padx=12,
            pady=9,
            **kwargs,
        )
        self.accent_color = accent_color

        top_row = tk.Frame(self, bg=BG_CARD)
        top_row.pack(fill="x", expand=True)

        self.lbl_icon = tk.Label(top_row, text=icon, font=("Helvetica Neue", 13), fg=accent_color, bg=BG_CARD)
        self.lbl_icon.pack(side="left")

        self.lbl_title = tk.Label(
            top_row,
            text=f" {title.upper()}",
            font=("Helvetica Neue", 8, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        self.lbl_title.pack(side="left")

        self.lbl_val = tk.Label(
            self,
            text=initial_val,
            font=("Helvetica Neue", 15, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
            anchor="w",
        )
        self.lbl_val.pack(fill="x", pady=(2, 1))

        self.lbl_sub = tk.Label(
            self,
            text=subtitle,
            font=("Helvetica Neue", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            anchor="w",
        )
        self.lbl_sub.pack(fill="x")

    def update_card(self, value: str, subtitle: Optional[str] = None, val_color: Optional[str] = None) -> None:
        self.lbl_val.config(text=value)
        if val_color:
            self.lbl_val.config(fg=val_color)
        if subtitle is not None:
            self.lbl_sub.config(text=subtitle)


# ---------------------------------------------------------------------------
# Cute Course Add / Edit Modal Dialog
# ---------------------------------------------------------------------------
class CuteCourseDialog(tk.Toplevel):
    """Sweet and friendly modal dialog for adding or editing a course outline."""

    def __init__(
        self,
        parent: tk.Tk,
        title: str = "🌸 Add New Course",
        course: Optional[CourseConfig] = None,
        theme_index: int = 0,
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("540x590")
        self.minsize(490, 520)
        self.configure(bg=BG_CREAM)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[CourseConfig] = None
        self.theme_index = theme_index

        self._build_ui(course)
        self.center_window(parent)

    def center_window(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self, course: Optional[CourseConfig]) -> None:
        # Header banner with twilight purple and cozy sparkles
        hdr = tk.Frame(self, bg=BG_HEADER, padx=20, pady=12)
        hdr.pack(side="top", fill="x")

        lbl_hdr = tk.Label(
            hdr,
            text="🌸 Course Outline & Exam Setup",
            font=("Helvetica Neue", 13, "bold"),
            fg="#ffffff",
            bg=BG_HEADER,
        )
        lbl_hdr.pack(anchor="w")

        lbl_sub = tk.Label(
            hdr,
            text="Fill in your course syllabus topics and target exam date — RePlan handles the rest! ✨",
            font=("Helvetica Neue", 9),
            fg="#c4b5fd",
            bg=BG_HEADER,
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg=BG_CREAM, padx=20, pady=12)
        body.pack(side="top", fill="both", expand=True)

        # 1. Course Name
        tk.Label(body, text="📚 Course Name / Code:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_DARK, bg=BG_CREAM).pack(anchor="w")
        self.entry_name = tk.Entry(body, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_DARK, relief="solid", bd=1)
        self.entry_name.pack(fill="x", pady=(2, 10))

        # 2. Credit Hours & Theme Picker
        row_params = tk.Frame(body, bg=BG_CREAM)
        row_params.pack(fill="x", pady=(0, 10))

        col_ch = tk.Frame(row_params, bg=BG_CREAM)
        col_ch.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(col_ch, text="⏱️ Credit Hours (CH):", font=("Helvetica Neue", 9, "bold"), fg=TEXT_DARK, bg=BG_CREAM).pack(anchor="w")
        self.entry_ch = tk.Entry(col_ch, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_DARK, relief="solid", bd=1)
        self.entry_ch.pack(fill="x", pady=(2, 0))

        col_theme = tk.Frame(row_params, bg=BG_CREAM)
        col_theme.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(col_theme, text="🎨 Badge Theme:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_DARK, bg=BG_CREAM).pack(anchor="w")
        theme_labels = [f"{t['icon']} {t['name']}" for t in COURSE_THEMES]
        self.combo_theme = ttk.Combobox(col_theme, values=theme_labels, state="readonly", font=("Helvetica Neue", 10))
        self.combo_theme.current(self.theme_index % len(COURSE_THEMES))
        self.combo_theme.pack(fill="x", pady=(2, 0))

        # 3. Exam Date
        tk.Label(body, text="📅 Course Exam Date (YYYY-MM-DD):", font=("Helvetica Neue", 9, "bold"), fg=TEXT_DARK, bg=BG_CREAM).pack(anchor="w")
        self.entry_exam = tk.Entry(body, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_DARK, relief="solid", bd=1)
        self.entry_exam.pack(fill="x", pady=(2, 4))

        # Quick preset buttons for exam date
        quick_frame = tk.Frame(body, bg=BG_CREAM)
        quick_frame.pack(fill="x", pady=(0, 10))
        tk.Label(quick_frame, text="Quick Presets: ", font=("Helvetica Neue", 8), fg=TEXT_MUTED, bg=BG_CREAM).pack(side="left")
        for days in [30, 60, 75, 90, 120]:
            btn = tk.Button(
                quick_frame,
                text=f"+{days}d",
                font=("Helvetica Neue", 8),
                bg="#ffffff",
                fg=COLOR_BLOSSOM,
                relief="solid",
                bd=1,
                command=lambda d=days: self._set_exam_days(d),
                padx=6,
                pady=1,
                cursor="pointinghand",
            )
            btn.pack(side="left", padx=2)

        # 4. Course Outline / Topics
        tk.Label(
            body,
            text="📝 Syllabus Topics (One per line or comma-separated):",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_DARK,
            bg=BG_CREAM,
        ).pack(anchor="w")

        self.txt_topics = tk.Text(
            body,
            height=6,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_DARK,
            relief="solid",
            bd=1,
            wrap="word",
        )
        self.txt_topics.pack(fill="both", expand=True, pady=(2, 12))

        # Prepopulate if editing
        if course:
            self.entry_name.insert(0, course.name)
            self.entry_ch.insert(0, str(course.credit_hours))
            self.entry_exam.insert(0, course.exam_date.strftime("%Y-%m-%d"))
            self.txt_topics.insert("1.0", "\n".join(course.topics))
            for i, t in enumerate(COURSE_THEMES):
                if t["primary"] == course.color:
                    self.combo_theme.current(i)
                    break
        else:
            default_exam = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
            self.entry_exam.insert(0, default_exam)
            self.entry_ch.insert(0, "3.0")

        # Footer Buttons
        footer = tk.Frame(self, bg=BG_CREAM, padx=20, pady=12)
        footer.pack(side="bottom", fill="x")

        btn_cancel = tk.Button(
            footer,
            text="Cancel",
            command=self.destroy,
            font=("Helvetica Neue", 9),
            bg="#ffffff",
            fg=TEXT_MUTED,
            relief="solid",
            bd=1,
            padx=16,
            pady=6,
            cursor="pointinghand",
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = tk.Button(
            footer,
            text="💖 Save Course",
            command=self._on_save,
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_BLOSSOM,
            fg="#ffffff",
            activebackground=COLOR_BLOSSOM_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            padx=18,
            pady=6,
            cursor="pointinghand",
        )
        btn_save.pack(side="right")

    def _set_exam_days(self, days: int) -> None:
        target = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")
        self.entry_exam.delete(0, tk.END)
        self.entry_exam.insert(0, target)

    def _on_save(self) -> None:
        try:
            name = self.entry_name.get().strip()
            if not name:
                messagebox.showerror("Validation Error", "Please provide a Course Name.", parent=self)
                return

            try:
                ch = float(self.entry_ch.get().strip())
                if ch <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Validation Error", "Credit Hours must be a positive number (e.g. 3.0).", parent=self)
                return

            exam_str = self.entry_exam.get().strip()
            try:
                exam_d = MultiCourseReplanEngine.parse_date(exam_str)
            except Exception as e:
                messagebox.showerror("Validation Error", f"Invalid Exam Date: {e}", parent=self)
                return

            topics_raw = self.txt_topics.get("1.0", tk.END).strip()
            topics = [t.strip() for line in topics_raw.split("\n") for t in line.split(",") if t.strip()]
            if not topics:
                messagebox.showerror("Validation Error", "Please enter at least one topic in the syllabus.", parent=self)
                return

            theme_idx = self.combo_theme.current()
            selected_theme = COURSE_THEMES[theme_idx % len(COURSE_THEMES)]

            self.result = CourseConfig(
                name=name,
                credit_hours=ch,
                exam_date=exam_d,
                topics=topics,
                color=selected_theme["primary"],
                icon=selected_theme["icon"],
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


# ---------------------------------------------------------------------------
# Google Calendar Integration & Permission Engine
# ---------------------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/calendar"]
REPLAN_CALENDAR_NAME = "🌸 RePlan Study Roadmap"
REPLAN_CALENDAR_DESC = "Adaptive semester study milestones generated by RePlan v1.1 🌸🎓"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


class GoogleCalendarSyncManager:
    """Manages Google Calendar API authentication, calendar creation, and event synchronization."""

    @staticmethod
    def is_available() -> bool:
        return GOOGLE_API_AVAILABLE

    @staticmethod
    def has_token() -> bool:
        return os.path.exists(TOKEN_FILE)

    @staticmethod
    def has_credentials() -> bool:
        return os.path.exists(CREDENTIALS_FILE)

    @staticmethod
    def get_service(credentials_path: Optional[str] = None) -> Any:
        if not GOOGLE_API_AVAILABLE:
            raise RuntimeError(
                "Google Calendar API client libraries are not installed.\n"
                "Please run: pip install google-api-python-client google-auth-oauthlib"
            )

        creds = None
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                cred_path = credentials_path or CREDENTIALS_FILE
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(
                        f"'{cred_path}' was not found.\n\n"
                        "To use direct Google Calendar API sync, please place your Google Cloud OAuth "
                        "Client ID 'credentials.json' in this folder, or select it when prompted.\n\n"
                        "Alternatively, you can use the instant 'Export .ICS File' option to import into Google Calendar with zero setup!"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
                token_f.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    @staticmethod
    def get_or_create_calendar(service, calendar_name: str = REPLAN_CALENDAR_NAME) -> str:
        """Finds or creates a dedicated study calendar in the user's Google Calendar account."""
        calendar_list = service.calendarList().list().execute()
        for item in calendar_list.get("items", []):
            if item.get("summary") == calendar_name:
                return item["id"]

        new_cal = {
            "summary": calendar_name,
            "description": REPLAN_CALENDAR_DESC,
            "timeZone": "UTC",
        }
        created = service.calendars().insert(body=new_cal).execute()
        return created["id"]

    @staticmethod
    def sync_milestones(
        service,
        calendar_id: str,
        milestones: List[Dict[str, Any]],
        courses_by_name: Dict[str, CourseConfig],
        preferred_hour: int = 18,
        all_day: bool = False,
        reminder_minutes: int = 15,
        progress_callback: Optional[Any] = None,
    ) -> int:
        """Adds study milestone events to Google Calendar with clear descriptions and reminders."""
        added_count = 0
        total = len(milestones)

        for row in milestones:
            date_str = str(row["Date"])  # YYYY-MM-DD
            course_name = str(row["Course"])
            topic = str(row["Topic"])
            topic_day = str(row["Topic Day"])
            hours = float(row.get("Target Hours", 1.5))
            status = str(row.get("Status", "Pending"))
            resched_from = str(row.get("Rescheduled_From", "") or "")

            c_info = courses_by_name.get(course_name)
            icon = c_info.icon if c_info else "📚"

            summary = f"{icon} {course_name}: {topic} ({topic_day})"
            desc_lines = [
                "🌸 RePlan Study Milestone",
                f"• Course: {course_name}",
                f"• Topic: {topic} (Day {topic_day})",
                f"• Planned Study Hours: {hours:.2f} hrs",
                f"• Status: {status}",
            ]
            if resched_from:
                desc_lines.append(f"• Rescheduled From: {resched_from}")
            desc_lines.append("\nPlanned with RePlan v1.1 Cozy Adaptive Semester Planner 🌸🎓")
            description = "\n".join(desc_lines)

            reminders_dict = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}] if reminder_minutes > 0 else [],
            }

            if all_day:
                next_day = (datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d")
                event_body = {
                    "summary": summary,
                    "description": description,
                    "start": {"date": date_str},
                    "end": {"date": next_day},
                    "reminders": reminders_dict,
                }
            else:
                start_dt = datetime.strptime(f"{date_str} {preferred_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
                duration_mins = max(30, int(hours * 60))
                end_dt = start_dt + timedelta(minutes=duration_mins)
                event_body = {
                    "summary": summary,
                    "description": description,
                    "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                    "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
                    "reminders": reminders_dict,
                }

            service.events().insert(calendarId=calendar_id, body=event_body).execute()
            added_count += 1
            if progress_callback:
                progress_callback(added_count, total)

        return added_count

    @staticmethod
    def generate_ics_content(
        milestones: List[Dict[str, Any]],
        courses_by_name: Dict[str, CourseConfig],
        preferred_hour: int = 18,
        all_day: bool = False,
    ) -> str:
        """Generates standard iCalendar (.ics) format string for universal calendar import."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RePlan//Cozy Adaptive Semester Planner v1.1//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:🌸 RePlan Study Roadmap",
        ]

        now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        for idx, row in enumerate(milestones):
            date_clean = str(row["Date"]).replace("-", "")
            course_name = str(row["Course"])
            topic = str(row["Topic"]).replace(",", "\\,")
            topic_day = str(row["Topic Day"])
            hours = float(row.get("Target Hours", 1.5))
            status = str(row.get("Status", "Pending"))

            c_info = courses_by_name.get(course_name)
            icon = c_info.icon if c_info else "📚"

            uid = f"replan-{date_clean}-{idx}@replan.app"
            summary = f"{icon} {course_name}: {topic} ({topic_day})"
            desc = f"Target: {hours:.2f} hrs | Status: {status} | Planned with RePlan v1.1 🌸"

            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uid}")
            lines.append(f"DTSTAMP:{now_stamp}")

            if all_day:
                d_obj = datetime.strptime(str(row["Date"]), "%Y-%m-%d").date()
                d_end = (d_obj + timedelta(days=1)).strftime("%Y%m%d")
                lines.append(f"DTSTART;VALUE=DATE:{date_clean}")
                lines.append(f"DTEND;VALUE=DATE:{d_end}")
            else:
                lines.append(f"DTSTART:{date_clean}T{preferred_hour:02d}0000")
                duration_mins = max(30, int(hours * 60))
                end_dt = datetime.strptime(f"{row['Date']} {preferred_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S") + timedelta(minutes=duration_mins)
                lines.append(f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}")

            lines.append(f"SUMMARY:{summary}")
            lines.append(f"DESCRIPTION:{desc}")
            lines.append("STATUS:CONFIRMED")
            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    @staticmethod
    def export_ics_file(
        filepath: str,
        milestones: List[Dict[str, Any]],
        courses_by_name: Dict[str, CourseConfig],
        preferred_hour: int = 18,
        all_day: bool = False,
    ) -> None:
        content = GoogleCalendarSyncManager.generate_ics_content(
            milestones=milestones,
            courses_by_name=courses_by_name,
            preferred_hour=preferred_hour,
            all_day=all_day,
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def open_google_calendar() -> None:
        webbrowser.open("https://calendar.google.com")

    @staticmethod
    def open_google_calendar_import_settings() -> None:
        webbrowser.open("https://calendar.google.com/calendar/u/0/r/settings/export")


# ---------------------------------------------------------------------------
# Google Calendar Permission & Customization Dialog
# ---------------------------------------------------------------------------
class GoogleCalendarPermissionDialog(tk.Toplevel):
    """
    Modal dialog asking for user's explicit permission before syncing tasks
    to Google Calendar, with customization options for courses and study time.
    """

    def __init__(
        self,
        parent: tk.Tk,
        df_schedule: pd.DataFrame,
        courses: List[CourseConfig],
    ):
        super().__init__(parent)
        self.title("🌸 Connect to Google Calendar")
        self.geometry("580x690")
        self.minsize(520, 600)
        self.configure(bg=BG_CREAM)
        self.transient(parent)
        self.grab_set()

        self.df_schedule = df_schedule
        self.courses = courses
        self.courses_by_name = {c.name: c for c in courses}

        self.course_vars: Dict[str, tk.BooleanVar] = {}
        self.scope_var = tk.StringVar(value="upcoming")  # 'upcoming' or 'all'
        self.calendar_var = tk.StringVar(value="dedicated")  # 'dedicated' or 'primary'
        self.timing_var = tk.StringVar(value="timed")  # 'timed' or 'allday'
        self.time_hour_var = tk.StringVar(value="18:00 (6:00 PM)")
        self.reminder_var = tk.StringVar(value="15 minutes before")

        self._build_ui()
        self.center_window(parent)

    def center_window(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        # Header banner
        hdr = tk.Frame(self, bg=BG_HEADER, padx=20, pady=12)
        hdr.pack(side="top", fill="x")

        lbl_hdr = tk.Label(
            hdr,
            text="📅 Connect with Google Calendar",
            font=("Helvetica Neue", 13, "bold"),
            fg="#ffffff",
            bg=BG_HEADER,
        )
        lbl_hdr.pack(anchor="w")

        lbl_sub = tk.Label(
            hdr,
            text="🌸 RePlan requires your explicit permission before adding any tasks to your calendar.",
            font=("Helvetica Neue", 9),
            fg="#c4b5fd",
            bg=BG_HEADER,
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg=BG_CREAM, padx=18, pady=10)
        body.pack(side="top", fill="both", expand=True)

        # Permission Card
        perm_card = tk.Frame(body, bg="#fefce8", highlightthickness=1, highlightbackground="#fef08a", padx=12, pady=8)
        perm_card.pack(fill="x", pady=(0, 10))

        lbl_perm_msg = tk.Label(
            perm_card,
            text="🛡️ Permission Notice:\nNo events will be added without your consent. You can select which courses "
                 "to include, choose your study time, and even create a separate '🌸 RePlan Study Roadmap' calendar "
                 "so your personal calendar stays neat!",
            font=("Helvetica Neue", 8),
            fg="#854d0e",
            bg="#fefce8",
            justify="left",
            wraplength=500,
        )
        lbl_perm_msg.pack(anchor="w")

        # 1. Course Selection Card
        card_courses = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=8)
        card_courses.pack(fill="x", pady=(0, 10))

        tk.Label(
            card_courses,
            text="📚 Select Courses to Add to Calendar:",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 4))

        # Checkboxes for each course
        for c in self.courses:
            var = tk.BooleanVar(value=True)
            self.course_vars[c.name] = var
            sub_count = len(self.df_schedule[self.df_schedule["Course"] == c.name]) if not self.df_schedule.empty else 0
            cb = tk.Checkbutton(
                card_courses,
                text=f"{c.icon} {c.name} ({sub_count} milestones, Exam: {c.exam_date.strftime('%Y-%m-%d')})",
                variable=var,
                font=("Helvetica Neue", 9),
                fg=TEXT_DARK,
                bg=BG_CARD,
                activebackground=BG_CARD,
                activeforeground=TEXT_DARK,
                anchor="w",
            )
            cb.pack(fill="x", pady=1)

        # 2. Scope & Status Selection
        card_scope = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=8)
        card_scope.pack(fill="x", pady=(0, 10))

        tk.Label(
            card_scope,
            text="🎯 Task Scope to Include:",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 4))

        rb1 = tk.Radiobutton(
            card_scope,
            text="Upcoming Pending & Rescheduled tasks only (Recommended)",
            variable=self.scope_var,
            value="upcoming",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
            activebackground=BG_CARD,
        )
        rb1.pack(anchor="w")

        rb2 = tk.Radiobutton(
            card_scope,
            text="All scheduled milestones across entire semester roadmap",
            variable=self.scope_var,
            value="all",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
            activebackground=BG_CARD,
        )
        rb2.pack(anchor="w")

        # 3. Calendar & Time Preferences
        card_prefs = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=8)
        card_prefs.pack(fill="x", pady=(0, 10))

        tk.Label(
            card_prefs,
            text="⚙️ Target Calendar & Study Time:",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 4))

        # Target Calendar
        row_cal = tk.Frame(card_prefs, bg=BG_CARD)
        row_cal.pack(fill="x", pady=2)
        tk.Label(row_cal, text="Target Calendar:", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD, width=15, anchor="w").pack(side="left")
        rb_cal1 = tk.Radiobutton(
            row_cal,
            text="Dedicated '🌸 RePlan Study Roadmap' (Recommended)",
            variable=self.calendar_var,
            value="dedicated",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
        )
        rb_cal1.pack(side="left")
        rb_cal2 = tk.Radiobutton(
            row_cal,
            text="Primary Calendar",
            variable=self.calendar_var,
            value="primary",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
        )
        rb_cal2.pack(side="left", padx=10)

        # Time of day
        row_timing = tk.Frame(card_prefs, bg=BG_CARD)
        row_timing.pack(fill="x", pady=2)
        tk.Label(row_timing, text="Time Slot:", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD, width=15, anchor="w").pack(side="left")
        rb_time1 = tk.Radiobutton(
            row_timing,
            text="Timed Study Blocks at:",
            variable=self.timing_var,
            value="timed",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
        )
        rb_time1.pack(side="left")

        time_options = [
            "08:00 (8:00 AM)", "09:00 (9:00 AM)", "10:00 (10:00 AM)",
            "14:00 (2:00 PM)", "16:00 (4:00 PM)", "18:00 (6:00 PM)",
            "20:00 (8:00 PM)", "21:00 (9:00 PM)",
        ]
        self.combo_hour = ttk.Combobox(row_timing, values=time_options, textvariable=self.time_hour_var, state="readonly", width=16)
        self.combo_hour.current(5)  # 18:00
        self.combo_hour.pack(side="left", padx=6)

        row_allday = tk.Frame(card_prefs, bg=BG_CARD)
        row_allday.pack(fill="x", pady=2)
        tk.Label(row_allday, text="", font=("Helvetica Neue", 9), bg=BG_CARD, width=15).pack(side="left")
        rb_time2 = tk.Radiobutton(
            row_allday,
            text="All-day milestone events",
            variable=self.timing_var,
            value="allday",
            font=("Helvetica Neue", 9),
            fg=TEXT_DARK,
            bg=BG_CARD,
        )
        rb_time2.pack(side="left")

        # Reminder
        row_rem = tk.Frame(card_prefs, bg=BG_CARD)
        row_rem.pack(fill="x", pady=(4, 0))
        tk.Label(row_rem, text="Notification:", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD, width=15, anchor="w").pack(side="left")
        rem_options = ["15 minutes before", "30 minutes before", "1 hour before", "No reminder"]
        self.combo_reminder = ttk.Combobox(row_rem, values=rem_options, textvariable=self.reminder_var, state="readonly", width=18)
        self.combo_reminder.current(0)
        self.combo_reminder.pack(side="left")

        # Footer Actions
        footer = tk.Frame(self, bg=BG_CREAM, padx=18, pady=12)
        footer.pack(side="bottom", fill="x")

        btn_cancel = tk.Button(
            footer,
            text="❌ Cancel / Don't Add",
            command=self.destroy,
            font=("Helvetica Neue", 9),
            bg="#ffffff",
            fg=TEXT_MUTED,
            relief="solid",
            bd=1,
            padx=12,
            pady=6,
            cursor="pointinghand",
        )
        btn_cancel.pack(side="left")

        btn_ics = tk.Button(
            footer,
            text="📥 Save .ICS File (Universal Import)",
            command=self._on_export_ics_option,
            font=("Helvetica Neue", 9),
            bg="#fdf4ff",
            fg=COLOR_BLOSSOM,
            activebackground="#fae8ff",
            relief="solid",
            bd=1,
            padx=12,
            pady=6,
            cursor="pointinghand",
        )
        btn_ics.pack(side="left", padx=8)

        btn_grant = tk.Button(
            footer,
            text="✅ Yes, Add to Google Calendar 🌸",
            command=self._on_grant_permission_and_sync,
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_BLOSSOM,
            fg="#ffffff",
            activebackground=COLOR_BLOSSOM_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=6,
            cursor="pointinghand",
        )
        btn_grant.pack(side="right")

    def _get_selected_milestones(self) -> List[Dict[str, Any]]:
        if self.df_schedule.empty:
            return []

        selected_courses = [c for c, v in self.course_vars.items() if v.get()]
        if not selected_courses:
            return []

        mask = self.df_schedule["Course"].isin(selected_courses)

        if self.scope_var.get() == "upcoming":
            today_d = date.today()
            date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
            mask = mask & (date_series >= today_d) & self.df_schedule["Status"].isin(["Pending", "Rescheduled"])

        sub = self.df_schedule[mask]
        return sub.to_dict("records")

    def _get_preferred_hour(self) -> int:
        h_str = self.time_hour_var.get()
        try:
            return int(h_str.split(":")[0])
        except Exception:
            return 18

    def _get_reminder_minutes(self) -> int:
        rem_str = self.reminder_var.get()
        if "15" in rem_str:
            return 15
        elif "30" in rem_str:
            return 30
        elif "1" in rem_str:
            return 60
        return 0

    def _on_export_ics_option(self) -> None:
        milestones = self._get_selected_milestones()
        if not milestones:
            messagebox.showwarning("No Tasks Selected", "Please select at least one course with scheduled tasks.", parent=self)
            return

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Save RePlan Calendar (.ics)",
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics")],
            initialfile="replan_study_roadmap.ics",
            initialdir=os.getcwd(),
            parent=self,
        )
        if path:
            try:
                GoogleCalendarSyncManager.export_ics_file(
                    filepath=path,
                    milestones=milestones,
                    courses_by_name=self.courses_by_name,
                    preferred_hour=self._get_preferred_hour(),
                    all_day=(self.timing_var.get() == "allday"),
                )
                msg = (
                    f"🌸 Success!\n\nSaved {len(milestones)} study milestones to:\n{path}\n\n"
                    f"Would you like to open Google Calendar in your browser now so you can import it?"
                )
                if messagebox.askyesno("Open Google Calendar", msg, parent=self):
                    GoogleCalendarSyncManager.open_google_calendar_import_settings()
                self.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=self)

    def _on_grant_permission_and_sync(self) -> None:
        milestones = self._get_selected_milestones()
        if not milestones:
            messagebox.showwarning("No Tasks Selected", "Please select at least one course with tasks to sync.", parent=self)
            return

        # Explicit confirmation
        count = len(milestones)
        target_name = "Dedicated '🌸 RePlan Study Roadmap'" if self.calendar_var.get() == "dedicated" else "Primary Calendar"
        confirm_msg = (
            f"🌸 Confirm Google Calendar Sync:\n\n"
            f"• Milestones to add: {count} study sessions\n"
            f"• Target Calendar: {target_name}\n"
            f"• Style: {'All-Day Event' if self.timing_var.get() == 'allday' else f'Timed block at {self._get_preferred_hour()}:00'}\n\n"
            f"Do you grant permission to add these tasks to your Google Calendar?"
        )
        if not messagebox.askyesno("Grant Permission 🌸", confirm_msg, parent=self):
            return

        # Check credentials
        if not GoogleCalendarSyncManager.has_token() and not GoogleCalendarSyncManager.has_credentials():
            # Prompt guide dialog
            setup_dlg = tk.Toplevel(self)
            setup_dlg.title("🌸 Google Calendar Connection Setup")
            setup_dlg.geometry("520x420")
            setup_dlg.configure(bg=BG_CREAM)
            setup_dlg.transient(self)
            setup_dlg.grab_set()

            tk.Label(
                setup_dlg,
                text="🔑 Google Cloud OAuth Credentials",
                font=("Helvetica Neue", 12, "bold"),
                fg=TEXT_DARK,
                bg=BG_CREAM,
            ).pack(anchor="w", padx=20, pady=(16, 4))

            guide_text = (
                "To connect directly via Google's secure OAuth API:\n\n"
                "1. RePlan connects via your Google Cloud OAuth Client credentials ('credentials.json').\n"
                "2. If you already downloaded your credentials file from Google Cloud Console, click "
                "'Select credentials.json' below.\n\n"
                "💡 Don't have a Google Cloud Developer project?\n"
                "You can click 'Instant 1-Click .ICS Import' below to add all your study tasks to Google Calendar "
                "in 5 seconds right now without needing any cloud setup!"
            )
            tk.Label(
                setup_dlg,
                text=guide_text,
                font=("Helvetica Neue", 9),
                fg=TEXT_MUTED,
                bg=BG_CREAM,
                justify="left",
                wraplength=470,
            ).pack(padx=20, pady=8)

            btn_box = tk.Frame(setup_dlg, bg=BG_CREAM)
            btn_box.pack(fill="x", padx=20, pady=12)

            def select_cred_file():
                from tkinter import filedialog
                import shutil
                c_path = filedialog.askopenfilename(
                    title="Select Google OAuth credentials.json",
                    filetypes=[("JSON files", "*.json")],
                    parent=setup_dlg,
                )
                if c_path:
                    try:
                        shutil.copy(c_path, CREDENTIALS_FILE)
                        setup_dlg.destroy()
                        self._execute_api_sync(milestones)
                    except Exception as err:
                        messagebox.showerror("File Error", str(err), parent=setup_dlg)

            def instant_ics():
                setup_dlg.destroy()
                self._on_export_ics_option()

            def open_cloud_console():
                webbrowser.open("https://console.cloud.google.com/apis/credentials")

            tk.Button(
                btn_box,
                text="📂 Select credentials.json...",
                command=select_cred_file,
                font=("Helvetica Neue", 9, "bold"),
                bg=COLOR_BLOSSOM,
                fg="#ffffff",
                relief="flat",
                pady=6,
                cursor="pointinghand",
            ).pack(fill="x", pady=4)

            tk.Button(
                btn_box,
                text="📥 Instant 1-Click .ICS Import (Zero Cloud Setup)",
                command=instant_ics,
                font=("Helvetica Neue", 9, "bold"),
                bg=COLOR_MINT,
                fg="#ffffff",
                relief="flat",
                pady=6,
                cursor="pointinghand",
            ).pack(fill="x", pady=4)

            tk.Button(
                btn_box,
                text="🌐 Open Google Cloud Console Guide",
                command=open_cloud_console,
                font=("Helvetica Neue", 8),
                bg="#ffffff",
                fg=TEXT_MUTED,
                relief="solid",
                bd=1,
                pady=4,
                cursor="pointinghand",
            ).pack(fill="x", pady=4)

            return

        # Run direct API sync
        self._execute_api_sync(milestones)

    def _execute_api_sync(self, milestones: List[Dict[str, Any]]) -> None:
        try:
            # Show progress indicator
            prog_win = tk.Toplevel(self)
            prog_win.title("Syncing to Google Calendar 🌸")
            prog_win.geometry("380x160")
            prog_win.configure(bg=BG_CREAM)
            prog_win.transient(self)
            prog_win.grab_set()

            lbl_stat = tk.Label(
                prog_win,
                text="Connecting to Google Calendar...\nPlease complete Google login in your browser if prompted.",
                font=("Helvetica Neue", 9),
                fg=TEXT_DARK,
                bg=BG_CREAM,
                justify="center",
            )
            lbl_stat.pack(pady=16)

            pb = ttk.Progressbar(prog_win, mode="determinate", maximum=len(milestones))
            pb.pack(fill="x", padx=24, pady=8)
            prog_win.update()

            def update_pb(curr, total):
                pb["value"] = curr
                lbl_stat.config(text=f"🌸 Adding task {curr} of {total} to Google Calendar...")
                prog_win.update()

            service = GoogleCalendarSyncManager.get_service()

            if self.calendar_var.get() == "dedicated":
                cal_id = GoogleCalendarSyncManager.get_or_create_calendar(service, REPLAN_CALENDAR_NAME)
                cal_display = f"'{REPLAN_CALENDAR_NAME}'"
            else:
                cal_id = "primary"
                cal_display = "your Primary Calendar"

            added = GoogleCalendarSyncManager.sync_milestones(
                service=service,
                calendar_id=cal_id,
                milestones=milestones,
                courses_by_name=self.courses_by_name,
                preferred_hour=self._get_preferred_hour(),
                all_day=(self.timing_var.get() == "allday"),
                reminder_minutes=self._get_reminder_minutes(),
                progress_callback=update_pb,
            )

            prog_win.destroy()

            success_msg = (
                f"🎉 Hooray! Successfully synced {added} study milestone(s) to {cal_display}!\n\n"
                f"Would you like to open Google Calendar in your browser to view your roadmap?"
            )
            if messagebox.askyesno("Calendar Sync Complete ✨", success_msg, parent=self):
                GoogleCalendarSyncManager.open_google_calendar()

            self.destroy()

        except Exception as e:
            if 'prog_win' in locals() and prog_win.winfo_exists():
                prog_win.destroy()
            messagebox.showerror("Google Calendar Sync Error", f"Unable to sync with Google Calendar:\n\n{e}", parent=self)

class ReplanV11App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RePlan v1.1 — Cozy & Friendly Adaptive Semester Planner 🌸🎓")
        self.geometry("1340x900")
        self.minsize(1120, 730)
        self.configure(bg=BG_CREAM)

        # Application State
        self.courses: List[CourseConfig] = []
        self.df_schedule: pd.DataFrame = pd.DataFrame()
        self.topic_periods: List[TopicPeriod] = []
        self.schedule_summary: Dict[str, Any] = {}
        self.replan_history: List[Dict[str, Any]] = []
        self.current_file_path: Optional[str] = None
        self.course_baseline_hours: Dict[str, float] = {}

        self._init_styles()
        self._build_header()
        self._build_cheerleader_bar()
        self._build_metric_ribbon()
        self._build_main_layout()
        self._build_status_bar()

        # Load friendly multi-course sample by default
        self._load_sample_courses(auto_generate=True)

    def _init_styles(self) -> None:
        self.option_add("*Entry.foreground", TEXT_DARK)
        self.option_add("*Entry.background", "#ffffff")
        self.option_add("*Entry.insertBackground", TEXT_DARK)
        self.option_add("*Text.foreground", TEXT_DARK)
        self.option_add("*Text.background", "#ffffff")
        self.option_add("*Text.insertBackground", TEXT_DARK)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Cozy pastel tabs
        self.style.configure(
            "TNotebook",
            background=BG_CREAM,
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )
        self.style.configure(
            "TNotebook.Tab",
            padding=[16, 8],
            font=("Helvetica Neue", 10, "bold"),
            background="#efe8dd",
            foreground=TEXT_MUTED,
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", BG_CARD)],
            foreground=[("selected", COLOR_BLOSSOM)],
        )

        # Treeview styling with softer rows
        self.style.configure(
            "Treeview",
            background=BG_CARD,
            foreground=TEXT_DARK,
            fieldbackground=BG_CARD,
            rowheight=28,
            font=("Helvetica Neue", 10),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Helvetica Neue", 9, "bold"),
            background="#f8f4ee",
            foreground=TEXT_DARK,
            relief="flat",
            padding=[6, 5],
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", "#eeded2")],
        )

        # Combobox styling
        self.style.configure(
            "TCombobox",
            foreground=TEXT_DARK,
            background="#ffffff",
            fieldbackground="#ffffff",
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            foreground=[("readonly", TEXT_DARK)],
        )

    # -----------------------------------------------------------------------
    # Top Header
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        header_frame = tk.Frame(self, bg=BG_HEADER, height=62, padx=22, pady=10)
        header_frame.pack(side="top", fill="x")

        brand_frame = tk.Frame(header_frame, bg=BG_HEADER)
        brand_frame.pack(side="left", fill="y")

        lbl_logo = tk.Label(
            brand_frame,
            text="🌸 RePlan v1.1",
            font=("Helvetica Neue", 18, "bold"),
            fg="#ffffff",
            bg=BG_HEADER,
        )
        lbl_logo.pack(side="left")

        lbl_tagline = tk.Label(
            brand_frame,
            text=" | Your Cozy Adaptive Study Planner • Multi-Course Outlines & Exam Milestones ✨",
            font=("Helvetica Neue", 10),
            fg="#c4b5fd",
            bg=BG_HEADER,
        )
        lbl_tagline.pack(side="left", padx=(8, 0))

        btn_bar = tk.Frame(header_frame, bg=BG_HEADER)
        btn_bar.pack(side="right")

        self._create_header_btn(btn_bar, "📂 Open Plan", self._on_load_csv_dialog)
        self._create_header_btn(btn_bar, "💾 Save Plan", self._on_save_csv_dialog)
        self._create_header_btn(btn_bar, "📅 Google Calendar", self._on_sync_google_calendar)
        self._create_header_btn(btn_bar, "✨ Load 3-Course Preset", lambda: self._load_sample_courses(auto_generate=True))
        self._create_header_btn(btn_bar, "➕ Add Course", self._on_add_course_dialog)
        self._create_header_btn(btn_bar, "💖 Friendly Guide", self._show_about_dialog)

    def _create_header_btn(self, parent, text: str, command) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Helvetica Neue", 9, "bold"),
            bg="#362d52",
            fg="#fdfbf7",
            activebackground="#4a3e6f",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=11,
            pady=5,
            cursor="pointinghand",
        )
        btn.pack(side="left", padx=3)
        return btn

    # -----------------------------------------------------------------------
    # Cheerful Motivational Banner
    # -----------------------------------------------------------------------
    def _build_cheerleader_bar(self) -> None:
        self.banner_bar = tk.Frame(self, bg="#faf0e6", highlightthickness=1, highlightbackground=BORDER_COZY, padx=20, pady=5)
        self.banner_bar.pack(side="top", fill="x")

        self.lbl_quote = tk.Label(
            self.banner_bar,
            text=random.choice(CHEERFUL_QUOTES),
            font=("Helvetica Neue", 9, "italic"),
            fg="#78350f",
            bg="#faf0e6",
        )
        self.lbl_quote.pack(side="left")

        btn_refresh_quote = tk.Button(
            self.banner_bar,
            text="💫 New Sparkle",
            command=self._cycle_cheer_quote,
            font=("Helvetica Neue", 8),
            bg="#ffffff",
            fg=COLOR_BLOSSOM,
            relief="solid",
            bd=1,
            padx=6,
            pady=1,
            cursor="pointinghand",
        )
        btn_refresh_quote.pack(side="right")

    def _cycle_cheer_quote(self) -> None:
        self.lbl_quote.config(text=random.choice(CHEERFUL_QUOTES))

    # -----------------------------------------------------------------------
    # Metric Ribbon (6 Friendly Cards)
    # -----------------------------------------------------------------------
    def _build_metric_ribbon(self) -> None:
        ribbon_frame = tk.Frame(self, bg=BG_CREAM, padx=20, pady=10)
        ribbon_frame.pack(side="top", fill="x")

        self.card_courses = CuteMetricCard(
            ribbon_frame,
            title="Active Adventures",
            initial_val="0 Courses",
            subtitle="Configured courses",
            accent_color="#8b5cf6",
            icon="📚",
        )
        self.card_courses.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.card_nearest_exam = CuteMetricCard(
            ribbon_frame,
            title="Nearest Exam",
            initial_val="--",
            subtitle="Upcoming deadline",
            accent_color="#f59e0b",
            icon="⏰",
        )
        self.card_nearest_exam.pack(side="left", fill="x", expand=True, padx=4)

        self.card_total_hours = CuteMetricCard(
            ribbon_frame,
            title="Total Study Cups",
            initial_val="--",
            subtitle="Required semester work",
            accent_color="#db2777",
            icon="☕",
        )
        self.card_total_hours.pack(side="left", fill="x", expand=True, padx=4)

        self.card_target = CuteMetricCard(
            ribbon_frame,
            title="Today's Target Pace",
            initial_val="--",
            subtitle="Peaceful daily hours",
            accent_color=COLOR_BLOSSOM,
            icon="🎯",
        )
        self.card_target.pack(side="left", fill="x", expand=True, padx=4)

        self.card_progress = CuteMetricCard(
            ribbon_frame,
            title="Blooming Progress",
            initial_val="0%",
            subtitle="0 completed",
            accent_color=COLOR_MINT,
            icon="🌸",
        )
        self.card_progress.pack(side="left", fill="x", expand=True, padx=4)

        self.card_feasibility = CuteMetricCard(
            ribbon_frame,
            title="Daily Harmony",
            initial_val="Ready",
            subtitle="Cap: 5.0h/day",
            accent_color=COLOR_MINT,
            icon="🌿",
        )
        self.card_feasibility.pack(side="left", fill="x", expand=True, padx=(6, 0))

    # -----------------------------------------------------------------------
    # Main Paned / Side-by-Side Layout
    # -----------------------------------------------------------------------
    def _build_main_layout(self) -> None:
        content_frame = tk.Frame(self, bg=BG_CREAM, padx=20, pady=2)
        content_frame.pack(side="top", fill="both", expand=True)

        # Left Column: Controls (~395px)
        left_col = tk.Frame(content_frame, bg=BG_CREAM, width=395)
        left_col.pack(side="left", fill="y", padx=(0, 14))
        left_col.pack_propagate(False)

        # Right Column: Tabbed Views
        right_col = tk.Frame(content_frame, bg=BG_CREAM)
        right_col.pack(side="left", fill="both", expand=True)

        self._build_sidebar_controls(left_col)
        self._build_right_notebook(right_col)

    # -----------------------------------------------------------------------
    # Left Sidebar Controls (Today's Check-in, Courses Setup, Gentle Replan)
    # -----------------------------------------------------------------------
    def _build_sidebar_controls(self, parent: tk.Frame) -> None:
        # Card 0: Today's Cozy Study Check-in Box
        self.card_checkin = tk.Frame(
            parent,
            bg=BG_CARD,
            highlightthickness=2,
            highlightbackground=COLOR_BLOSSOM,
            padx=14,
            pady=11,
        )
        self.card_checkin.pack(side="top", fill="x", pady=(0, 10))

        top_checkin = tk.Frame(self.card_checkin, bg=BG_CARD)
        top_checkin.pack(fill="x")

        lbl_checkin_title = tk.Label(
            top_checkin,
            text="☕ TODAY'S COZY STUDY CHECK-IN",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_BLOSSOM,
            bg=BG_CARD,
        )
        lbl_checkin_title.pack(side="left")

        today_str = date.today().strftime("%Y-%m-%d")
        lbl_today_badge = tk.Label(
            top_checkin,
            text=f"📅 {today_str}",
            font=("Helvetica Neue", 8, "bold"),
            fg=TEXT_MUTED,
            bg="#fdf4ff",
            padx=7,
            pady=2,
        )
        lbl_today_badge.pack(side="right")

        # Container for today's course tasks
        self.today_tasks_container = tk.Frame(self.card_checkin, bg=BG_CARD)
        self.today_tasks_container.pack(fill="x", pady=(6, 8))

        # Check-in Master Actions
        checkin_actions = tk.Frame(self.card_checkin, bg=BG_CARD)
        checkin_actions.pack(fill="x")

        btn_done_all = tk.Button(
            checkin_actions,
            text="✨ Yay! Finished All Today's Study! 🎉",
            command=self._mark_all_today_done,
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_MINT,
            fg="#ffffff",
            activebackground=COLOR_MINT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=7,
            cursor="pointinghand",
        )
        btn_done_all.pack(fill="x", pady=(0, 4))

        row_sub_actions = tk.Frame(checkin_actions, bg=BG_CARD)
        row_sub_actions.pack(fill="x")

        btn_miss_today = tk.Button(
            row_sub_actions,
            text="🌸 Rested Today (Reschedule) 💤",
            command=self._mark_all_today_missed,
            font=("Helvetica Neue", 8, "bold"),
            bg=COLOR_PEACH_BG,
            fg=COLOR_PEACH_TEXT,
            activebackground="#ffe4e6",
            relief="flat",
            bd=0,
            pady=5,
            cursor="pointinghand",
        )
        btn_miss_today.pack(side="left", fill="x", expand=True, padx=(0, 2))

        btn_reset_today = tk.Button(
            row_sub_actions,
            text="⏳ Reset Today",
            command=self._mark_all_today_pending,
            font=("Helvetica Neue", 8),
            bg="#f8f4ee",
            fg=TEXT_DARK,
            activebackground="#eeded2",
            relief="flat",
            bd=0,
            pady=5,
            cursor="pointinghand",
        )
        btn_reset_today.pack(side="left", fill="x", expand=True, padx=(2, 0))

        btn_gcal = tk.Button(
            checkin_actions,
            text="📅 Sync Roadmap to Google Calendar 🌸",
            command=self._on_sync_google_calendar,
            font=("Helvetica Neue", 8, "bold"),
            bg="#fdf4ff",
            fg=COLOR_BLOSSOM,
            activebackground="#fae8ff",
            relief="solid",
            bd=1,
            pady=4,
            cursor="pointinghand",
        )
        btn_gcal.pack(fill="x", pady=(4, 0))

        # Card 1: Enrolled Courses & Setup
        card_setup = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=10)
        card_setup.pack(side="top", fill="x", pady=(0, 10))

        hdr_setup = tk.Frame(card_setup, bg=BG_CARD)
        hdr_setup.pack(fill="x", pady=(0, 6))

        lbl_sec1 = tk.Label(
            hdr_setup,
            text="📚 YOUR ENROLLED COURSES",
            font=("Helvetica Neue", 10, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        lbl_sec1.pack(side="left")

        # Treeview for Courses List
        course_tree_frame = tk.Frame(card_setup, bg=BG_CARD)
        course_tree_frame.pack(fill="x", pady=(0, 6))

        c_cols = ("Course", "CH", "Exam Date", "Topics")
        self.tree_courses = ttk.Treeview(course_tree_frame, columns=c_cols, show="headings", height=4, selectmode="browse")
        self.tree_courses.heading("Course", text="Course")
        self.tree_courses.heading("CH", text="CH")
        self.tree_courses.heading("Exam Date", text="Exam Date")
        self.tree_courses.heading("Topics", text="Topics")

        self.tree_courses.column("Course", width=145, anchor="w")
        self.tree_courses.column("CH", width=40, anchor="center")
        self.tree_courses.column("Exam Date", width=85, anchor="center")
        self.tree_courses.column("Topics", width=50, anchor="center")

        self.tree_courses.pack(fill="x")
        self.tree_courses.bind("<Double-1>", lambda e: self._on_edit_course_dialog())

        # Course Action Buttons
        course_btn_row = tk.Frame(card_setup, bg=BG_CARD)
        course_btn_row.pack(fill="x", pady=(0, 8))

        btn_add_c = tk.Button(
            course_btn_row,
            text="➕ Add",
            command=self._on_add_course_dialog,
            font=("Helvetica Neue", 8, "bold"),
            bg="#f8f4ee",
            fg=TEXT_DARK,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_add_c.pack(side="left", padx=(0, 3))

        btn_edit_c = tk.Button(
            course_btn_row,
            text="✏️ Edit",
            command=self._on_edit_course_dialog,
            font=("Helvetica Neue", 8),
            bg="#f8f4ee",
            fg=TEXT_DARK,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_edit_c.pack(side="left", padx=3)

        btn_del_c = tk.Button(
            course_btn_row,
            text="🗑️ Remove",
            command=self._on_delete_course,
            font=("Helvetica Neue", 8),
            bg=COLOR_PEACH_BG,
            fg=COLOR_PEACH_TEXT,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_del_c.pack(side="left", padx=3)

        btn_load_preset = tk.Button(
            course_btn_row,
            text="✨ 3-Course Preset",
            command=lambda: self._load_sample_courses(auto_generate=False),
            font=("Helvetica Neue", 8),
            bg="#f3e8ff",
            fg=COLOR_BLOSSOM,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_load_preset.pack(side="right")

        # Global Parameters Box
        params_box = tk.Frame(card_setup, bg="#fcfaf7", highlightthickness=1, highlightbackground=BORDER_COZY, padx=8, pady=6)
        params_box.pack(fill="x", pady=(0, 8))

        row_p1 = tk.Frame(params_box, bg="#fcfaf7")
        row_p1.pack(fill="x", pady=(0, 4))

        tk.Label(row_p1, text="Semester Start Date:", font=("Helvetica Neue", 8, "bold"), fg=TEXT_MUTED, bg="#fcfaf7").pack(side="left")
        self.entry_start_date = tk.Entry(row_p1, font=("Helvetica Neue", 9), bg="#ffffff", fg=TEXT_DARK, width=11, relief="solid", bd=1)
        self.entry_start_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.entry_start_date.pack(side="right")

        row_p2 = tk.Frame(params_box, bg="#fcfaf7")
        row_p2.pack(fill="x")

        tk.Label(row_p2, text="Max Daily Limit (h/d):", font=("Helvetica Neue", 8, "bold"), fg=TEXT_MUTED, bg="#fcfaf7").pack(side="left")
        self.entry_cap = tk.Entry(row_p2, font=("Helvetica Neue", 9), bg="#ffffff", fg=TEXT_DARK, width=6, relief="solid", bd=1)
        self.entry_cap.insert(0, "5.0")
        self.entry_cap.pack(side="right")

        # Master Schedule Generation Button
        btn_generate = tk.Button(
            card_setup,
            text="🚀 Generate Whole Semester Plan ✨",
            command=self._on_generate_schedule,
            font=("Helvetica Neue", 10, "bold"),
            bg=COLOR_BLOSSOM,
            fg="#ffffff",
            activebackground=COLOR_BLOSSOM_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=8,
            cursor="pointinghand",
        )
        btn_generate.pack(fill="x")

        # Card 2: Gentle Adaptive Rescheduling Card
        card_replan = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=10)
        card_replan.pack(side="top", fill="x")

        lbl_sec2 = tk.Label(
            card_replan,
            text="🌸 GENTLE ADAPTIVE REPLAN",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_BLOSSOM,
            bg=BG_CARD,
        )
        lbl_sec2.pack(anchor="w")

        lbl_replan_desc = tk.Label(
            card_replan,
            text="Missed any study days? RePlan gently reorganizes your uncompleted topics into remaining days before each exam deadline so you can rest easy.",
            font=("Helvetica Neue", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            wraplength=350,
            justify="left",
        )
        lbl_replan_desc.pack(anchor="w", pady=(3, 8))

        btn_replan = tk.Button(
            card_replan,
            text="🔄 Adaptively Replan Now 💖",
            command=self._on_adaptive_replan,
            font=("Helvetica Neue", 10, "bold"),
            bg=COLOR_BLOSSOM,
            fg="#ffffff",
            activebackground=COLOR_BLOSSOM_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=8,
            cursor="pointinghand",
        )
        btn_replan.pack(fill="x")

    # -----------------------------------------------------------------------
    # Right Tabbed Notebook
    # -----------------------------------------------------------------------
    def _build_right_notebook(self, parent: tk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Master Schedule
        self.tab_schedule = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_schedule, text="  📋 Master Study Roadmap  ")
        self._build_schedule_tab(self.tab_schedule)

        # Tab 2: Course Outlines & Timelines
        self.tab_courses = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_courses, text="  🌸 Course Outlines & Timelines  ")
        self._build_courses_tab(self.tab_courses)

        # Tab 3: Daily Workload & Harmony
        self.tab_daily = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_daily, text="  ☕ Daily Workload & Harmony  ")
        self._build_daily_tab(self.tab_daily)

        # Tab 4: Study Insights & Cheerleader
        self.tab_insights = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_insights, text="  ✨ Study Insights & Cheerleader  ")
        self._build_insights_tab(self.tab_insights)

    # -----------------------------------------------------------------------
    # Tab 1: Day-by-Day Master Schedule Table
    # -----------------------------------------------------------------------
    def _build_schedule_tab(self, parent: tk.Frame) -> None:
        action_bar = tk.Frame(parent, bg="#faf7f2", highlightthickness=1, highlightbackground=BORDER_COZY, padx=12, pady=7)
        action_bar.pack(side="top", fill="x", padx=12, pady=(10, 6))

        lbl_action_title = tk.Label(
            action_bar,
            text="Mark Selected:",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_DARK,
            bg="#faf7f2",
        )
        lbl_action_title.pack(side="left", padx=(0, 8))

        btn_done = tk.Button(
            action_bar,
            text="✨ Done Studying",
            command=lambda: self._set_selected_status("Completed"),
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_MINT,
            fg="#ffffff",
            activebackground=COLOR_MINT_HOVER,
            relief="flat",
            bd=0,
            padx=11,
            pady=4,
            cursor="pointinghand",
        )
        btn_done.pack(side="left", padx=(0, 5))

        btn_miss = tk.Button(
            action_bar,
            text="💤 Missed Session",
            command=lambda: self._set_selected_status("Missed"),
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_PEACH,
            fg="#ffffff",
            activebackground=COLOR_PEACH_HOVER,
            relief="flat",
            bd=0,
            padx=11,
            pady=4,
            cursor="pointinghand",
        )
        btn_miss.pack(side="left", padx=(0, 5))

        btn_pending = tk.Button(
            action_bar,
            text="⏳ Reset Pending",
            command=lambda: self._set_selected_status("Pending"),
            font=("Helvetica Neue", 9),
            bg="#ffffff",
            fg=TEXT_DARK,
            relief="solid",
            bd=1,
            padx=9,
            pady=4,
            cursor="pointinghand",
        )
        btn_pending.pack(side="left", padx=(0, 14))

        self.lbl_selected_preview = tk.Label(
            action_bar,
            text="Select row(s) below to mark your study milestones",
            font=("Helvetica Neue", 9),
            fg=TEXT_MUTED,
            bg="#faf7f2",
        )
        self.lbl_selected_preview.pack(side="left")

        btn_cal_sync = tk.Button(
            action_bar,
            text="📅 Sync Google Calendar",
            command=self._on_sync_google_calendar,
            font=("Helvetica Neue", 9, "bold"),
            bg="#fdf4ff",
            fg=COLOR_BLOSSOM,
            activebackground="#fae8ff",
            relief="solid",
            bd=1,
            padx=11,
            pady=4,
            cursor="pointinghand",
        )
        btn_cal_sync.pack(side="right")

        # Filter & Search Toolbar
        filter_bar = tk.Frame(parent, bg=BG_CARD, padx=12, pady=5)
        filter_bar.pack(side="top", fill="x")

        tk.Label(filter_bar, text="Filter Course:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.combo_course_filter = ttk.Combobox(filter_bar, values=["All Courses"], state="readonly", width=16)
        self.combo_course_filter.current(0)
        self.combo_course_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_schedule_view())
        self.combo_course_filter.pack(side="left", padx=(4, 12))

        tk.Label(filter_bar, text="Status:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.combo_status_filter = ttk.Combobox(
            filter_bar,
            values=["All", "Pending", "Completed", "Missed", "Rescheduled"],
            state="readonly",
            width=12,
        )
        self.combo_status_filter.current(0)
        self.combo_status_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_schedule_view())
        self.combo_status_filter.pack(side="left", padx=(4, 12))

        tk.Label(filter_bar, text="Search:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.entry_search = tk.Entry(
            filter_bar,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_DARK,
            relief="solid",
            bd=1,
            width=16,
        )
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_schedule_view())
        self.entry_search.pack(side="left", padx=(4, 12))

        btn_jump_today = tk.Button(
            filter_bar,
            text="⚡ Jump to Today",
            command=self._jump_to_today,
            font=("Helvetica Neue", 9),
            bg="#fdf4ff",
            fg=COLOR_BLOSSOM,
            relief="solid",
            bd=1,
            padx=8,
            pady=2,
            cursor="pointinghand",
        )
        btn_jump_today.pack(side="left")

        self.lbl_table_count = tk.Label(filter_bar, text="0 milestones scheduled", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD)
        self.lbl_table_count.pack(side="right")

        # Table Container
        table_container = tk.Frame(parent, bg=BG_CARD)
        table_container.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        columns = ("Day", "Date", "Weekday", "Course", "Topic Day", "Topic", "Target Hours", "Status")
        self.tree_schedule = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")

        col_configs = {
            "Day": (50, "center"),
            "Date": (90, "center"),
            "Weekday": (90, "w"),
            "Course": (160, "w"),
            "Topic Day": (75, "center"),
            "Topic": (270, "w"),
            "Target Hours": (85, "center"),
            "Status": (120, "center"),
        }

        for col, (width, anchor) in col_configs.items():
            self.tree_schedule.heading(col, text=col, command=lambda c=col: self._sort_schedule_by_column(c))
            self.tree_schedule.column(col, width=width, anchor=anchor)

        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_schedule.yview)
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree_schedule.xview)
        self.tree_schedule.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree_schedule.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

        # Row Tags & Highlighting
        self.tree_schedule.tag_configure("completed", background=COLOR_MINT_BG, foreground=COLOR_MINT_TEXT)
        self.tree_schedule.tag_configure("missed", background=COLOR_PEACH_BG, foreground=COLOR_PEACH_TEXT)
        self.tree_schedule.tag_configure("rescheduled", background=COLOR_RESCHEDULED_BG, foreground=COLOR_RESCHEDULED_TEXT)
        self.tree_schedule.tag_configure("today", background=COLOR_HONEY_BG, foreground=COLOR_HONEY_TEXT)
        self.tree_schedule.tag_configure("pending", background="#ffffff", foreground=TEXT_DARK)

        self.tree_schedule.bind("<<TreeviewSelect>>", self._on_tree_selection_change)
        self.tree_schedule.bind("<Double-1>", self._on_tree_double_click)
        self.tree_schedule.bind("<Button-2>", self._show_tree_context_menu)
        self.tree_schedule.bind("<Button-3>", self._show_tree_context_menu)

        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="✨ Mark Done Studying", command=lambda: self._set_selected_status("Completed"))
        self.tree_menu.add_command(label="💤 Mark Missed Session", command=lambda: self._set_selected_status("Missed"))
        self.tree_menu.add_command(label="⏳ Reset to Pending", command=lambda: self._set_selected_status("Pending"))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="🌸 Run Adaptive Replan", command=self._on_adaptive_replan)

    # -----------------------------------------------------------------------
    # Tab 2: Course Outlines & Timelines
    # -----------------------------------------------------------------------
    def _build_courses_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="🌸 ENROLLED COURSES & BLOOMING PROGRESS",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        t1_frame = tk.Frame(container, bg=BG_CARD)
        t1_frame.pack(fill="x", pady=(0, 14))

        cols1 = ("Course", "CH", "Exam Date", "Days Left", "Total Hrs", "Daily Pace", "Completed", "Blooming Progress")
        self.tree_course_summary = ttk.Treeview(t1_frame, columns=cols1, show="headings", height=4)
        col_w = {
            "Course": (170, "w"),
            "CH": (50, "center"),
            "Exam Date": (95, "center"),
            "Days Left": (80, "center"),
            "Total Hrs": (85, "center"),
            "Daily Pace": (85, "center"),
            "Completed": (85, "center"),
            "Blooming Progress": (120, "center"),
        }
        for c, (w, a) in col_w.items():
            self.tree_course_summary.heading(c, text=c)
            self.tree_course_summary.column(c, width=w, anchor=a)

        self.tree_course_summary.pack(fill="x")
        self.tree_course_summary.bind("<<TreeviewSelect>>", self._on_course_summary_select)

        # Section 2: Detailed Syllabus Breakdown for Selected Course
        hdr2 = tk.Frame(container, bg=BG_CARD)
        hdr2.pack(fill="x", pady=(4, 6))

        tk.Label(
            hdr2,
            text="📅 SYLLABUS TOPIC PERIODS BREAKDOWN",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(side="left")

        self.lbl_selected_course_topics = tk.Label(
            hdr2,
            text="(All Courses)",
            font=("Helvetica Neue", 10),
            fg=COLOR_BLOSSOM,
            bg=BG_CARD,
        )
        self.lbl_selected_course_topics.pack(side="left", padx=8)

        t2_frame = tk.Frame(container, bg=BG_CARD)
        t2_frame.pack(fill="both", expand=True)

        cols2 = ("Course", "Topic #", "Topic", "Duration", "Total Hours", "Start Date", "End Date", "Completed", "Pending", "Progress")
        self.tree_topics = ttk.Treeview(t2_frame, columns=cols2, show="headings", selectmode="browse")
        col2_w = {
            "Course": (140, "w"),
            "Topic #": (60, "center"),
            "Topic": (230, "w"),
            "Duration": (75, "center"),
            "Total Hours": (80, "center"),
            "Start Date": (90, "center"),
            "End Date": (90, "center"),
            "Completed": (75, "center"),
            "Pending": (75, "center"),
            "Progress": (80, "center"),
        }
        for c, (w, a) in col2_w.items():
            self.tree_topics.heading(c, text=c)
            self.tree_topics.column(c, width=w, anchor=a)

        v_scroll2 = ttk.Scrollbar(t2_frame, orient="vertical", command=self.tree_topics.yview)
        self.tree_topics.configure(yscrollcommand=v_scroll2.set)

        self.tree_topics.grid(row=0, column=0, sticky="nsew")
        v_scroll2.grid(row=0, column=1, sticky="ns")

        t2_frame.rowconfigure(0, weight=1)
        t2_frame.columnconfigure(0, weight=1)

    # -----------------------------------------------------------------------
    # Tab 3: Daily Workload & Harmony
    # -----------------------------------------------------------------------
    def _build_daily_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="☕ DAILY STUDY CUPS & HARMONY ACROSS ALL COURSES",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_DARK,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        t_frame = tk.Frame(container, bg=BG_CARD)
        t_frame.pack(fill="both", expand=True)

        cols = ("Day", "Date", "Weekday", "Active Courses", "Target Hours", "Completed Hours", "Status Summary", "Study Mood")
        self.tree_daily = ttk.Treeview(t_frame, columns=cols, show="headings", selectmode="browse")
        col_w = {
            "Day": (50, "center"),
            "Date": (95, "center"),
            "Weekday": (95, "w"),
            "Active Courses": (180, "w"),
            "Target Hours": (120, "center"),
            "Completed Hours": (115, "center"),
            "Status Summary": (140, "center"),
            "Study Mood": (130, "center"),
        }
        for c, (w, a) in col_w.items():
            self.tree_daily.heading(c, text=c)
            self.tree_daily.column(c, width=w, anchor=a)

        v_scroll = ttk.Scrollbar(t_frame, orient="vertical", command=self.tree_daily.yview)
        self.tree_daily.configure(yscrollcommand=v_scroll.set)

        self.tree_daily.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        t_frame.rowconfigure(0, weight=1)
        t_frame.columnconfigure(0, weight=1)

        self.tree_daily.tag_configure("overcap", background=COLOR_PEACH_BG, foreground=COLOR_PEACH_TEXT)
        self.tree_daily.tag_configure("today", background=COLOR_HONEY_BG, foreground=COLOR_HONEY_TEXT)
        self.tree_daily.tag_configure("feasible", background="#ffffff", foreground=TEXT_DARK)

    # -----------------------------------------------------------------------
    # Tab 4: Study Insights & Cheerleader
    # -----------------------------------------------------------------------
    def _build_insights_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=16, pady=12)
        container.pack(fill="both", expand=True)

        self.banner_feasibility = tk.Frame(
            container,
            bg=COLOR_MINT_BG,
            highlightthickness=1,
            highlightbackground="#bbf7d0",
            padx=14,
            pady=10,
        )
        self.banner_feasibility.pack(fill="x", pady=(0, 10))

        self.lbl_feasibility_text = tk.Label(
            self.banner_feasibility,
            text="✨ STUDY HARMONY: Your semester plan is peaceful, balanced, and sustainable!",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_MINT_TEXT,
            bg=COLOR_MINT_BG,
            anchor="w",
        )
        self.lbl_feasibility_text.pack(fill="x")

        self.txt_insights = tk.Text(
            container,
            height=14,
            font=("Menlo", 10),
            bg="#ffffff",
            fg=TEXT_DARK,
            relief="solid",
            bd=1,
            padx=10,
            pady=10,
        )
        self.txt_insights.pack(fill="both", expand=True, pady=(0, 8))

    # -----------------------------------------------------------------------
    # Bottom Status Bar
    # -----------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        self.status_bar = tk.Frame(self, bg="#f3ede3", height=24, padx=14, pady=4)
        self.status_bar.pack(side="bottom", fill="x")

        self.lbl_status_file = tk.Label(
            self.status_bar,
            text="🌸 Ready to learn",
            font=("Helvetica Neue", 9),
            fg=TEXT_MUTED,
            bg="#f3ede3",
        )
        self.lbl_status_file.pack(side="left")

        self.lbl_status_msg = tk.Label(
            self.status_bar,
            text="Ready ✨",
            font=("Helvetica Neue", 9),
            fg=COLOR_BLOSSOM,
            bg="#f3ede3",
        )
        self.lbl_status_msg.pack(side="right")

    # -----------------------------------------------------------------------
    # Course Management Actions
    # -----------------------------------------------------------------------
    def _refresh_course_list_ui(self) -> None:
        for item in self.tree_courses.get_children():
            self.tree_courses.delete(item)

        for c in self.courses:
            self.tree_courses.insert(
                "",
                "end",
                values=(
                    f"{c.icon} {c.name}",
                    f"{c.credit_hours:.1f}",
                    c.exam_date.strftime("%Y-%m-%d"),
                    len(c.topics),
                ),
            )

        course_names = ["All Courses"] + [c.name for c in self.courses]
        curr_val = self.combo_course_filter.get()
        self.combo_course_filter["values"] = course_names
        if curr_val in course_names:
            self.combo_course_filter.set(curr_val)
        else:
            self.combo_course_filter.current(0)

    def _on_add_course_dialog(self) -> None:
        dlg = CuteCourseDialog(self, title="🌸 Add New Course", theme_index=len(self.courses))
        self.wait_window(dlg)
        if dlg.result:
            if any(c.name.lower() == dlg.result.name.lower() for c in self.courses):
                messagebox.showerror("Duplicate Course", f"A course named '{dlg.result.name}' already exists.")
                return
            self.courses.append(dlg.result)
            self._refresh_course_list_ui()
            self.set_status_message(f"Added {dlg.result.icon} '{dlg.result.name}' ✨")

    def _on_edit_course_dialog(self) -> None:
        selected = self.tree_courses.selection()
        if not selected:
            messagebox.showinfo("Select Course", "Please select a course to edit.")
            return

        row_course_str = self.tree_courses.item(selected[0], "values")[0]
        # Remove icon if present
        c_name = row_course_str.split(" ", 1)[-1].strip() if " " in row_course_str else row_course_str
        match = [c for c in self.courses if c.name == c_name or f"{c.icon} {c.name}" == row_course_str]
        if not match:
            return
        target_course = match[0]
        idx = self.courses.index(target_course)

        dlg = CuteCourseDialog(self, title=f"Edit {target_course.name}", course=target_course, theme_index=idx)
        self.wait_window(dlg)
        if dlg.result:
            self.courses[idx] = dlg.result
            self._refresh_course_list_ui()
            self.set_status_message(f"Updated {dlg.result.icon} '{dlg.result.name}' 💖")

    def _on_delete_course(self) -> None:
        selected = self.tree_courses.selection()
        if not selected:
            messagebox.showinfo("Select Course", "Please select a course to remove.")
            return

        row_course_str = self.tree_courses.item(selected[0], "values")[0]
        c_name = row_course_str.split(" ", 1)[-1].strip() if " " in row_course_str else row_course_str
        if messagebox.askyesno("Confirm Delete", f"Remove '{c_name}' from your semester roadmap?"):
            self.courses = [c for c in self.courses if c.name != c_name and f"{c.icon} {c.name}" != row_course_str]
            self._refresh_course_list_ui()
            self.set_status_message(f"Removed course: '{c_name}'")

    def _load_sample_courses(self, auto_generate: bool = True) -> None:
        today = date.today()
        self.courses = [
            CourseConfig(
                name="Programming & Problem Solving",
                credit_hours=4.0,
                exam_date=today + timedelta(days=90),
                topics=[
                    "Introduction & Syntax",
                    "Control Structures & Functions",
                    "Data Structures & OOP",
                    "File Handling & Algorithms",
                    "Semester Project & Final Revision",
                ],
                color=COURSE_THEMES[0]["primary"],
                icon="💻",
            ),
            CourseConfig(
                name="Calculus & Linear Algebra",
                credit_hours=3.0,
                exam_date=today + timedelta(days=65),
                topics=[
                    "Limits & Continuity",
                    "Differential Calculus",
                    "Integral Calculus",
                    "Vectors & Matrices",
                    "Past Papers & Final Prep",
                ],
                color=COURSE_THEMES[1]["primary"],
                icon="📐",
            ),
            CourseConfig(
                name="Computer Networks",
                credit_hours=3.0,
                exam_date=today + timedelta(days=105),
                topics=[
                    "Network Architecture & OSI Model",
                    "Data Link Layer & LANs",
                    "Network Layer & IP Routing",
                    "Transport Layer (TCP/UDP)",
                    "Application Layer & Security Review",
                ],
                color=COURSE_THEMES[2]["primary"],
                icon="🌐",
            ),
        ]
        self._refresh_course_list_ui()
        if auto_generate:
            self._on_generate_schedule()
        self.set_status_message("Loaded friendly 3-course semester preset ✨")

    # -----------------------------------------------------------------------
    # Schedule Generation & Adaptive Rescheduling Handlers
    # -----------------------------------------------------------------------
    def _on_generate_schedule(self) -> None:
        if not self.courses:
            messagebox.showwarning("No Courses", "Please add at least one course before generating a schedule.")
            return

        try:
            start_date_str = self.entry_start_date.get().strip()
            start_d = MultiCourseReplanEngine.parse_date(start_date_str)

            df, periods, summary = MultiCourseReplanEngine.generate_multi_course_schedule(
                courses=self.courses,
                start_date=start_d,
            )

            self.df_schedule = df
            self.topic_periods = periods
            self.schedule_summary = summary
            self.course_baseline_hours = {c: summary["courses"][c]["total_study_hours"] for c in summary["courses"]}
            self.current_file_path = DEFAULT_CSV_PATH

            self._refresh_all_views()
            self._auto_check_missed_past_tasks()
            self.set_status_message(
                f"Generated plan: {len(df)} milestones across {len(self.courses)} courses ({summary['total_study_hours']} total hrs) ✨"
            )

        except Exception as e:
            messagebox.showerror("Generation Error", str(e))

    def _on_adaptive_replan(self) -> None:
        self._run_reschedule_engine(show_toast=True, source_reason="Gentle Adaptive Replan")

    def _run_reschedule_engine(self, show_toast: bool = True, source_reason: str = "Adaptive Replan") -> None:
        if self.df_schedule.empty:
            return

        try:
            try:
                cap = float(self.entry_cap.get().strip())
            except ValueError:
                cap = 5.0

            updated_df, stats = MultiCourseReplanEngine.reschedule_missed_tasks(
                self.df_schedule,
                today_date=date.today(),
                max_daily_cap=cap,
                course_baseline_hours=self.course_baseline_hours,
            )

            self.df_schedule = updated_df
            self.topic_periods = MultiCourseReplanEngine.compute_topic_periods_from_df(updated_df)
            self.replan_history.append(stats)

            self._refresh_all_views()

            # Find and highlight first rescheduled row in Treeview
            resched_items = []
            for item_id in self.tree_schedule.get_children():
                tags = self.tree_schedule.item(item_id, "tags")
                if "rescheduled" in tags:
                    resched_items.append(item_id)

            if resched_items:
                self.tree_schedule.selection_set(resched_items[0])
                self.tree_schedule.see(resched_items[0])

            if show_toast:
                if stats["total_rescheduled_count"] > 0:
                    first = stats.get("first_rescheduled") or {}
                    msg = (
                        f"🌸 Gentle Rescheduling Done! 💖\n\n"
                        f"• Reason: {source_reason}\n"
                        f"• Rescheduled Milestones: {stats['total_rescheduled_count']} task(s) adjusted\n"
                        f"• Next Adjusted Task: {first.get('date', '--')} [{first.get('course', '')}: {first.get('topic', '')}]\n"
                        f"• Visual Indicator: Highlighted in DREAMY LAVENDER in your roadmap!\n\n"
                        f"• Peak Daily Study Pace: {stats['max_daily_pace']} hrs/day\n"
                        f"• Average Daily Pace: {stats['avg_daily_pace']} hrs/day"
                    )
                    if stats["is_over_cap"]:
                        msg += f"\n\n☕ Note: Your pace reaches {stats['max_daily_pace']} h/d on {stats['over_cap_days_count']} busy day(s). Remember to pace yourself with water and rest!"
                        messagebox.showwarning("Roadmap Updated (Busy Days Ahead)", msg)
                    else:
                        messagebox.showinfo("Roadmap Updated ✨", msg)
                else:
                    msg = (
                        f"✨ You're completely on track!\n\n"
                        f"• Peak Study Pace: {stats['max_daily_pace']} hrs/day\n"
                        f"• Average Pace: {stats['avg_daily_pace']} hrs/day\n"
                        f"Keep enjoying the journey! 🌸"
                    )
                    messagebox.showinfo("All On Track ✨", msg)

            self.set_status_message(
                f"Rescheduled {stats['total_rescheduled_count']} task(s) • Peak pace: {stats['max_daily_pace']} h/d 🌸"
            )

        except Exception as e:
            messagebox.showerror("Adaptive Reschedule Error", str(e))

    def _auto_check_missed_past_tasks(self) -> None:
        if self.df_schedule.empty:
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
        past_uncompleted = (date_series < today_d) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))

        if past_uncompleted.any():
            num_past = int(past_uncompleted.sum())
            self._run_reschedule_engine(
                show_toast=True,
                source_reason=f"Gently detected {num_past} past uncompleted session(s)",
            )

    # -----------------------------------------------------------------------
    # Today's Study Check-in Handlers
    # -----------------------------------------------------------------------
    def _mark_all_today_done(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = self.df_schedule["Date"] == today_str
        if not mask.any():
            messagebox.showinfo("No Tasks Today", f"No study sessions are scheduled for today ({today_str}). Enjoy your restful day! 🌸")
            return

        self.df_schedule.loc[mask, "Status"] = "Completed"
        self._refresh_all_views()
        self.set_status_message(f"🎉 Beautiful work! Completed all {mask.sum()} milestone(s) for today! ✨")
        messagebox.showinfo(
            "Celebrate Yourself! 🎉✨",
            f"Woohoo! You have marked all study tasks for today ({today_str}) as Done Studying!\n\n"
            f"You're making steady, beautiful progress toward your exams. Treat yourself to a warm cup or a nice break! 🧁💖"
        )

    def _mark_all_today_missed(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = (self.df_schedule["Date"] == today_str) & (self.df_schedule["Status"] != "Completed")
        if not mask.any():
            messagebox.showinfo("No Pending Tasks", "No pending tasks to reschedule today.")
            return

        self.df_schedule.loc[mask, "Status"] = "Missed"
        self._run_reschedule_engine(show_toast=True, source_reason=f"Rested today ({today_str})")

    def _mark_all_today_pending(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = self.df_schedule["Date"] == today_str
        if not mask.any():
            return
        self.df_schedule.loc[mask, "Status"] = "Pending"
        self.df_schedule.loc[mask, "Rescheduled_From"] = ""
        self._refresh_all_views()
        self.set_status_message(f"Reset today's tasks to Pending ({today_str}).")

    def _toggle_today_task_status(self, course_name: str) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = (self.df_schedule["Date"] == today_str) & (self.df_schedule["Course"] == course_name)
        if not mask.any():
            return

        curr_status = self.df_schedule.loc[mask, "Status"].iloc[0]
        if curr_status == "Completed":
            next_status = "Missed"
        elif curr_status == "Missed":
            next_status = "Pending"
        else:
            next_status = "Completed"

        self.df_schedule.loc[mask, "Status"] = next_status
        if next_status == "Missed":
            self._run_reschedule_engine(show_toast=True, source_reason=f"Rested {course_name} on {today_str}")
        else:
            if next_status == "Pending":
                self.df_schedule.loc[mask, "Rescheduled_From"] = ""
            self._refresh_all_views()
            self.set_status_message(f"{course_name} marked {next_status} ✨")

    # -----------------------------------------------------------------------
    # Table Selection & Interaction
    # -----------------------------------------------------------------------
    def _set_selected_status(self, new_status: str) -> None:
        selected_items = self.tree_schedule.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one row in the roadmap table.")
            return

        for item_id in selected_items:
            vals = self.tree_schedule.item(item_id, "values")
            day_num = int(vals[0])
            course_name = str(vals[3])
            date_val = str(vals[1])

            mask = (self.df_schedule["Day"] == day_num) & (self.df_schedule["Course"] == course_name) & (self.df_schedule["Date"] == date_val)
            if mask.any():
                self.df_schedule.loc[mask, "Status"] = new_status
                if new_status != "Rescheduled":
                    self.df_schedule.loc[mask, "Rescheduled_From"] = ""

        if new_status == "Missed":
            self._run_reschedule_engine(show_toast=True, source_reason=f"Marked {len(selected_items)} session(s) Missed")
        else:
            self._refresh_all_views()
            self.set_status_message(f"Updated {len(selected_items)} milestone(s) to {new_status} ✨")

    def _on_tree_double_click(self, event) -> None:
        item_id = self.tree_schedule.identify_row(event.y)
        if not item_id:
            return

        vals = self.tree_schedule.item(item_id, "values")
        day_num = int(vals[0])
        course_name = str(vals[3])
        date_val = str(vals[1])
        status_val = str(vals[7])

        if "Completed" in status_val or "Done" in status_val:
            next_status = "Missed"
        elif "Missed" in status_val:
            next_status = "Pending"
        else:
            next_status = "Completed"

        mask = (self.df_schedule["Day"] == day_num) & (self.df_schedule["Course"] == course_name) & (self.df_schedule["Date"] == date_val)
        if mask.any():
            self.df_schedule.loc[mask, "Status"] = next_status
            if next_status != "Rescheduled":
                self.df_schedule.loc[mask, "Rescheduled_From"] = ""

        if next_status == "Missed":
            self._run_reschedule_engine(show_toast=True, source_reason=f"{course_name} marked Missed on {date_val}")
        else:
            self._refresh_all_views()
            self.set_status_message(f"Updated {course_name} ({date_val}) to {next_status}")

    def _on_tree_selection_change(self, event) -> None:
        selected = self.tree_schedule.selection()
        if not selected:
            self.lbl_selected_preview.config(text="Select row(s) below to mark completed/missed")
            return

        if len(selected) == 1:
            vals = self.tree_schedule.item(selected[0], "values")
            day_num, row_date, _, course, topic_day, topic, _, status = vals
            self.lbl_selected_preview.config(
                text=f"Selected: Day {day_num} ({row_date}) • {course}: {topic} • Current: {status}"
            )
        else:
            self.lbl_selected_preview.config(text=f"Selected {len(selected)} tasks for batch update")

    def _show_tree_context_menu(self, event) -> None:
        row_id = self.tree_schedule.identify_row(event.y)
        if row_id:
            if row_id not in self.tree_schedule.selection():
                self.tree_schedule.selection_set(row_id)
            self.tree_menu.post(event.x_root, event.y_root)

    def _jump_to_today(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        for item_id in self.tree_schedule.get_children():
            vals = self.tree_schedule.item(item_id, "values")
            if vals and vals[1] == today_str:
                self.tree_schedule.selection_set(item_id)
                self.tree_schedule.see(item_id)
                return
        messagebox.showinfo("Date Info", f"Today ({today_str}) is not within the scheduled dates.")

    # -----------------------------------------------------------------------
    # File I/O (CSV & Metadata)
    # -----------------------------------------------------------------------
    def _on_load_csv_dialog(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Open Semester Plan CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        if path:
            try:
                df, courses = MultiCourseReplanEngine.load_csv(path)
                self.df_schedule = df
                self.courses = courses
                self.topic_periods = MultiCourseReplanEngine.compute_topic_periods_from_df(df)
                self.current_file_path = path

                self.course_baseline_hours = {}
                for c_name in df["Course"].unique():
                    self.course_baseline_hours[c_name] = float(df[df["Course"] == c_name]["Target Hours"].sum())

                self._refresh_course_list_ui()
                self._refresh_all_views()
                self._auto_check_missed_past_tasks()
                self.set_status_message(f"Loaded plan with {len(courses)} course(s) from {os.path.basename(path)} 🌸")
            except Exception as e:
                messagebox.showerror("Load Plan Error", str(e))

    def _on_save_csv_dialog(self) -> None:
        if self.df_schedule.empty:
            messagebox.showwarning("Empty Schedule", "There is no schedule to save.")
            return

        from tkinter import filedialog
        initial_file = os.path.basename(self.current_file_path or DEFAULT_CSV_PATH)
        path = filedialog.asksaveasfilename(
            title="Save Semester Plan",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=initial_file,
            initialdir=os.getcwd(),
        )
        if path:
            try:
                MultiCourseReplanEngine.save_csv(self.df_schedule, path, self.courses)
                self.current_file_path = path
                self.lbl_status_file.config(text=f"Plan: {os.path.basename(path)}")
                self.set_status_message(f"Saved plan to {path} ✨")
                messagebox.showinfo("Saved ✨", f"Your semester plan and course outlines were saved successfully to:\n{path}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    def _on_sync_google_calendar(self) -> None:
        """Opens the Google Calendar Permission & Customization Dialog."""
        if self.df_schedule.empty:
            messagebox.showwarning(
                "No Plan Generated",
                "Please generate or load a semester plan before syncing with Google Calendar. 🌸"
            )
            return

        GoogleCalendarPermissionDialog(
            parent=self,
            df_schedule=self.df_schedule,
            courses=self.courses,
        )

    # -----------------------------------------------------------------------
    # View Refreshes & Computations
    # -----------------------------------------------------------------------
    def _refresh_all_views(self) -> None:
        self._refresh_today_checkin_card()
        self._refresh_metric_ribbon()
        self._refresh_schedule_view()
        self._refresh_courses_tab_view()
        self._refresh_daily_tab_view()
        self._refresh_insights_view()
        if self.current_file_path:
            self.lbl_status_file.config(text=f"Active Plan: {os.path.basename(self.current_file_path)}")

    def _refresh_today_checkin_card(self) -> None:
        for child in self.today_tasks_container.winfo_children():
            child.destroy()

        if self.df_schedule.empty:
            tk.Label(
                self.today_tasks_container,
                text="No active plan loaded yet 🌱",
                font=("Helvetica Neue", 9),
                fg=TEXT_MUTED,
                bg=BG_CARD,
            ).pack(anchor="w")
            self.card_checkin.config(highlightbackground=BORDER_COZY)
            return

        today_str = date.today().strftime("%Y-%m-%d")
        today_rows = self.df_schedule[self.df_schedule["Date"] == today_str]

        if today_rows.empty:
            self.card_checkin.config(highlightbackground=BORDER_COZY)
            date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
            today_d = date.today()
            if today_d < date_series.iloc[0]:
                msg = f"Upcoming roadmap begins on {date_series.iloc[0]} 🌸"
            else:
                msg = "Semester exams concluded! Congratulations! 🎓✨"
            tk.Label(
                self.today_tasks_container,
                text=msg,
                font=("Helvetica Neue", 9, "bold"),
                fg=TEXT_MUTED,
                bg=BG_CARD,
            ).pack(anchor="w")
            return

        all_completed = bool((today_rows["Status"] == "Completed").all())
        has_missed = bool((today_rows["Status"] == "Missed").any())
        has_resched = bool((today_rows["Status"] == "Rescheduled").any())

        if all_completed:
            self.card_checkin.config(highlightbackground=COLOR_MINT)
        elif has_missed:
            self.card_checkin.config(highlightbackground=COLOR_PEACH)
        elif has_resched:
            self.card_checkin.config(highlightbackground=COLOR_BLOSSOM)
        else:
            self.card_checkin.config(highlightbackground=COLOR_BLOSSOM)

        for _, row in today_rows.iterrows():
            c_name = row["Course"]
            topic = row["Topic"]
            topic_day = row["Topic Day"]
            hrs = row["Target Hours"]
            status = row["Status"]
            resched_from = str(row.get("Rescheduled_From", "") or "")

            item_frame = tk.Frame(self.today_tasks_container, bg="#faf7f2", highlightthickness=1, highlightbackground=BORDER_COZY, padx=9, pady=5)
            item_frame.pack(fill="x", pady=2)

            left_info = tk.Frame(item_frame, bg="#faf7f2")
            left_info.pack(side="left", fill="x", expand=True)

            # Look up course icon
            c_icon = "📚"
            for c in self.courses:
                if c.name == c_name:
                    c_icon = c.icon
                    break

            lbl_course = tk.Label(
                left_info,
                text=f"{c_icon} {c_name}",
                font=("Helvetica Neue", 9, "bold"),
                fg=COLOR_BLOSSOM,
                bg="#faf7f2",
                anchor="w",
            )
            lbl_course.pack(fill="x")

            topic_text = f"• {topic} ({topic_day}) — {hrs:.2f} hrs"
            if resched_from:
                topic_text += f" [🔄 from {resched_from}]"

            lbl_sub = tk.Label(
                left_info,
                text=topic_text,
                font=("Helvetica Neue", 8),
                fg=TEXT_MUTED,
                bg="#faf7f2",
                anchor="w",
            )
            lbl_sub.pack(fill="x")

            if status == "Completed":
                btn_txt = "✨ Done"
                btn_bg = COLOR_MINT_BG
                btn_fg = COLOR_MINT_TEXT
            elif status == "Missed":
                btn_txt = "💤 Missed"
                btn_bg = COLOR_PEACH_BG
                btn_fg = COLOR_PEACH_TEXT
            elif status == "Rescheduled":
                btn_txt = "🌸 Resched"
                btn_bg = COLOR_RESCHEDULED_BG
                btn_fg = COLOR_RESCHEDULED_TEXT
            else:
                btn_txt = "🌱 Pending"
                btn_bg = "#ffffff"
                btn_fg = TEXT_DARK

            btn_toggle = tk.Button(
                item_frame,
                text=btn_txt,
                command=lambda c=c_name: self._toggle_today_task_status(c),
                font=("Helvetica Neue", 8, "bold"),
                bg=btn_bg,
                fg=btn_fg,
                relief="solid",
                bd=1,
                padx=8,
                pady=2,
                cursor="pointinghand",
            )
            btn_toggle.pack(side="right", padx=(6, 0))

    def _refresh_metric_ribbon(self) -> None:
        if self.df_schedule.empty:
            self.card_courses.update_card("0 Courses", "Configured courses")
            self.card_nearest_exam.update_card("--", "Countdown")
            self.card_total_hours.update_card("--", "Total study workload")
            self.card_target.update_card("--", "Daily pace")
            self.card_progress.update_card("0%", "0 completed")
            self.card_feasibility.update_card("Ready", "Cap: 5.0h/day", COLOR_MINT)
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date

        unique_courses = self.df_schedule["Course"].unique().tolist()
        self.card_courses.update_card(
            f"{len(unique_courses)} Courses",
            ", ".join(unique_courses[:2]) + ("..." if len(unique_courses) > 2 else ""),
        )

        exam_dates = []
        for c in self.courses:
            exam_dates.append((c.exam_date, c.name, c.icon))
        if not exam_dates:
            for c_name in unique_courses:
                last_d = date_series[self.df_schedule["Course"] == c_name].iloc[-1]
                exam_dates.append((last_d, c_name, "📚"))

        future_exams = [(d, n, ic) for d, n, ic in exam_dates if d >= today_d]
        if future_exams:
            min_d, min_name, min_ic = min(future_exams, key=lambda x: x[0])
            days_left = (min_d - today_d).days
            self.card_nearest_exam.update_card(
                f"{days_left} Sleeps Left 🌙",
                f"{min_ic} {min_name[:12]} ({min_d.strftime('%b %d')})",
            )
        else:
            self.card_nearest_exam.update_card("Exams Done 🎓", "All reached!")

        total_hours = float(self.df_schedule["Target Hours"].sum())
        total_ch = sum(c.credit_hours for c in self.courses) if self.courses else 0.0
        self.card_total_hours.update_card(
            f"{total_hours:.1f} hrs",
            f"{total_ch:.1f} Total Credit Hours ☕",
        )

        today_str = today_d.strftime("%Y-%m-%d")
        today_rows = self.df_schedule[self.df_schedule["Date"] == today_str]
        if not today_rows.empty:
            today_target = float(today_rows["Target Hours"].sum())
        else:
            future_slots = self.df_schedule[(date_series >= today_d) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))]
            if not future_slots.empty:
                next_date = future_slots["Date"].iloc[0]
                today_target = float(future_slots[future_slots["Date"] == next_date]["Target Hours"].sum())
            else:
                today_target = 0.0

        self.card_target.update_card(
            f"{today_target:.2f} h/d",
            "Target for active courses",
        )

        total_milestones = len(self.df_schedule)
        completed_m = int((self.df_schedule["Status"] == "Completed").sum())
        missed_m = int((self.df_schedule["Status"] == "Missed").sum())
        resched_m = int((self.df_schedule["Status"] == "Rescheduled").sum())
        pct = round((completed_m / total_milestones) * 100, 1) if total_milestones else 0.0
        self.card_progress.update_card(
            f"{pct}% Bloomed 🌱",
            f"{completed_m} Done • {missed_m} Rested • {resched_m} Resched",
        )

        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 5.0

        future_mask = date_series >= today_d
        future_df = self.df_schedule[future_mask & self.df_schedule["Status"].isin(["Pending", "Rescheduled"])]
        daily_sums = future_df.groupby("Date")["Target Hours"].sum()
        max_pace = float(daily_sums.max()) if not daily_sums.empty else 0.0
        is_over = max_pace > cap

        if is_over:
            self.card_feasibility.update_card(
                "⚠️ Busy Days Ahead",
                f"Peak {max_pace:.2f} > {cap:.1f}h limit",
                val_color=COLOR_PEACH,
            )
        else:
            self.card_feasibility.update_card(
                "✅ Harmonious & Calm",
                f"Peak: {max_pace:.2f} ≤ {cap:.1f}h/day",
                val_color=COLOR_MINT,
            )

    def _refresh_schedule_view(self) -> None:
        for item in self.tree_schedule.get_children():
            self.tree_schedule.delete(item)

        if self.df_schedule.empty:
            self.lbl_table_count.config(text="0 milestones scheduled")
            return

        course_filter = self.combo_course_filter.get()
        status_filter = self.combo_status_filter.get()
        query = self.entry_search.get().strip().lower()

        today_str = date.today().strftime("%Y-%m-%d")
        displayed = 0

        for _, row in self.df_schedule.iterrows():
            c_name = str(row["Course"])
            status = str(row["Status"])
            topic = str(row["Topic"])
            row_date = str(row["Date"])
            resched_from = str(row.get("Rescheduled_From", "") or "")
            is_resched = status == "Rescheduled" or bool(resched_from)

            if course_filter != "All Courses" and c_name != course_filter:
                continue

            if status_filter != "All":
                if status_filter == "Rescheduled" and not is_resched:
                    continue
                elif status_filter != "Rescheduled" and status != status_filter:
                    continue

            if query:
                combined_text = f"{c_name} {topic} {row_date}".lower()
                if query not in combined_text:
                    continue

            if status == "Completed":
                tag = "completed"
                status_icon = "✨ Done"
            elif status == "Missed":
                tag = "missed"
                status_icon = "💤 Missed"
            elif is_resched:
                tag = "rescheduled"
                status_icon = "🌸 Rescheduled"
            elif row_date == today_str:
                tag = "today"
                status_icon = "📌 Today"
            else:
                tag = "pending"
                status_icon = "🌱 Pending"

            topic_display = topic
            if is_resched and resched_from:
                topic_display = f"{topic} (🔄 from {resched_from})"

            self.tree_schedule.insert(
                "",
                "end",
                values=(
                    row["Day"],
                    row_date,
                    row["Weekday"],
                    c_name,
                    row["Topic Day"],
                    topic_display,
                    f"{float(row['Target Hours']):.2f}",
                    status_icon,
                ),
                tags=(tag,),
            )
            displayed += 1

        self.lbl_table_count.config(text=f"Showing {displayed} of {len(self.df_schedule)} milestones ✨")

    def _refresh_courses_tab_view(self) -> None:
        for item in self.tree_course_summary.get_children():
            self.tree_course_summary.delete(item)

        if self.df_schedule.empty:
            return

        today_d = date.today()

        for c in self.courses:
            sub = self.df_schedule[self.df_schedule["Course"] == c.name]
            if sub.empty:
                continue

            days_left = max(0, (c.exam_date - today_d).days)
            total_hrs = float(sub["Target Hours"].sum())
            total_tasks = len(sub)
            completed_tasks = int((sub["Status"] == "Completed").sum())
            pct = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0.0

            sub_date_series = pd.to_datetime(sub["Date"]).dt.date
            avail_sub = sub[(sub_date_series >= today_d) & sub["Status"].isin(["Pending", "Rescheduled"])]
            daily_pace = float(avail_sub["Target Hours"].iloc[0]) if not avail_sub.empty else 0.0

            bloom_str = f"{pct}% 🌸" if pct >= 50 else f"{pct}% 🌱"

            self.tree_course_summary.insert(
                "",
                "end",
                values=(
                    f"{c.icon} {c.name}",
                    f"{c.credit_hours:.1f}",
                    c.exam_date.strftime("%Y-%m-%d"),
                    f"{days_left}d",
                    f"{total_hrs:.1f}h",
                    f"{daily_pace:.2f} h/d",
                    f"{completed_tasks}/{total_tasks}",
                    bloom_str,
                ),
            )

        self._refresh_topic_periods_table()

    def _on_course_summary_select(self, event) -> None:
        selected = self.tree_course_summary.selection()
        if not selected:
            return
        row_str = self.tree_course_summary.item(selected[0], "values")[0]
        c_name = row_str.split(" ", 1)[-1].strip() if " " in row_str else row_str
        self.lbl_selected_course_topics.config(text=f"({c_name})")
        self._refresh_topic_periods_table(selected_course=c_name)

    def _refresh_topic_periods_table(self, selected_course: Optional[str] = None) -> None:
        for item in self.tree_topics.get_children():
            self.tree_topics.delete(item)

        if not self.topic_periods:
            self.topic_periods = MultiCourseReplanEngine.compute_topic_periods_from_df(self.df_schedule)

        for p in self.topic_periods:
            if selected_course and p.course_name != selected_course:
                continue

            self.tree_topics.insert(
                "",
                "end",
                values=(
                    p.course_name,
                    p.topic_num,
                    p.topic,
                    f"{p.duration_days} days",
                    f"{p.total_hours:.1f} hrs",
                    p.start_date,
                    p.end_date,
                    f"{p.completed_days}d",
                    f"{p.pending_days}d",
                    f"{p.progress_pct}%",
                ),
            )

    def _refresh_daily_tab_view(self) -> None:
        for item in self.tree_daily.get_children():
            self.tree_daily.delete(item)

        if self.df_schedule.empty:
            return

        today_str = date.today().strftime("%Y-%m-%d")
        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 5.0

        grouped = self.df_schedule.groupby("Date", sort=False)
        for date_str, group in grouped:
            day_num = group["Day"].iloc[0]
            weekday = group["Weekday"].iloc[0]
            active_courses = ", ".join(group["Course"].unique())
            total_target = float(group["Target Hours"].sum())
            completed_hours = float(group[group["Status"] == "Completed"]["Target Hours"].sum())

            c_cnt = int((group["Status"] == "Completed").sum())
            m_cnt = int((group["Status"] == "Missed").sum())
            r_cnt = int((group["Status"] == "Rescheduled").sum())
            p_cnt = int((group["Status"] == "Pending").sum())
            summary_str = f"{c_cnt} Done • {p_cnt + r_cnt} Left"
            if m_cnt:
                summary_str += f" ({m_cnt} Rested)"

            is_over = total_target > cap and (p_cnt + r_cnt) > 0
            if is_over:
                tag = "overcap"
                mood = f"⚡ Intense (+{total_target - cap:.1f}h)"
            elif date_str == today_str:
                tag = "today"
                mood = "📌 Today's Focus"
            elif total_target < 2.5:
                tag = "feasible"
                mood = "🌿 Light & Easy"
            else:
                tag = "feasible"
                mood = "☕ Steady Focus"

            self.tree_daily.insert(
                "",
                "end",
                values=(
                    day_num,
                    date_str,
                    weekday,
                    active_courses,
                    f"{total_target:.2f} hrs",
                    f"{completed_hours:.2f} hrs",
                    summary_str,
                    mood,
                ),
                tags=(tag,),
            )

    def _refresh_insights_view(self) -> None:
        if self.df_schedule.empty:
            self.txt_insights.delete("1.0", tk.END)
            self.txt_insights.insert("1.0", "Generate or load a study plan to see supportive analytics and cheerful reports! 🌸")
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date

        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 5.0

        future_mask = date_series >= today_d
        future_df = self.df_schedule[future_mask & self.df_schedule["Status"].isin(["Pending", "Rescheduled"])]
        daily_pace_series = future_df.groupby("Date")["Target Hours"].sum()

        max_daily_pace = float(daily_pace_series.max()) if not daily_pace_series.empty else 0.0
        avg_daily_pace = float(daily_pace_series.mean()) if not daily_pace_series.empty else 0.0
        over_cap_days = daily_pace_series[daily_pace_series > cap]
        is_over = len(over_cap_days) > 0

        if is_over:
            self.banner_feasibility.config(bg=COLOR_PEACH_BG, highlightbackground="#fecdd3")
            self.lbl_feasibility_text.config(
                text=f"⚡ HEADS UP: Daily study pace peaks at {max_daily_pace:.2f} hrs/day on {len(over_cap_days)} date(s). Remember to schedule cozy breaks!",
                fg=COLOR_PEACH_TEXT,
                bg=COLOR_PEACH_BG,
            )
        else:
            self.banner_feasibility.config(bg=COLOR_MINT_BG, highlightbackground="#bbf7d0")
            self.lbl_feasibility_text.config(
                text=f"✨ HARMONIOUS PACE: Your study roadmap is relaxed & completely doable (peak {max_daily_pace:.2f} hrs/day within {cap:.1f}h limit)!",
                fg=COLOR_MINT_TEXT,
                bg=COLOR_MINT_BG,
            )

        report = []
        report.append("=" * 74)
        report.append("🌸 REPLAN v1.1 — CHEERFUL & SUPPORTIVE SEMESTER INSIGHTS REPORT 💖")
        report.append("=" * 74)
        report.append(f"• Active Courses:             {len(self.courses)} adventures in learning")
        report.append(f"• Total Planned Study Cups:   {float(self.df_schedule['Target Hours'].sum()):.1f} hours of focused knowledge")
        report.append(f"• Peak Combined Pace:         {max_daily_pace:.2f} hrs/day (Your Comfort Limit: {cap:.1f} hrs/day)")
        report.append(f"• Gentle Average Daily Pace:  {avg_daily_pace:.2f} hrs/day")
        report.append("")

        report.append("-" * 74)
        report.append("📚 COURSE ROADMAP BREAKDOWN & COUNTDOWN:")
        report.append("-" * 74)
        for c in self.courses:
            sub = self.df_schedule[self.df_schedule["Course"] == c.name]
            if sub.empty:
                continue
            days_left = max(0, (c.exam_date - today_d).days)
            total_h = float(sub["Target Hours"].sum())
            comp_h = float(sub[sub["Status"] == "Completed"]["Target Hours"].sum())
            miss_h = float(sub[sub["Status"] == "Missed"]["Target Hours"].sum())
            rem_h = total_h - comp_h
            comp_days = int((sub["Status"] == "Completed").sum())
            rem_days = int((sub["Status"].isin(["Pending", "Rescheduled"])).sum())
            pace = round(rem_h / rem_days, 2) if rem_days else 0.0

            report.append(f"▶ {c.icon} {c.name.upper()} ({c.credit_hours} CH)")
            report.append(f"   • Exam Date:         {c.exam_date.strftime('%Y-%m-%d')} ({days_left} calendar days left)")
            report.append(f"   • Peaceful Pace:     {pace:.2f} hrs/day across {rem_days} remaining sessions")
            report.append(f"   • Progress Bloom:    {comp_h:.1f}/{total_h:.1f} hrs ({comp_days} done, {miss_h:.1f} hrs rested)")
            report.append(f"   • Core Topics:       {', '.join(c.topics[:3])}{'...' if len(c.topics) > 3 else ''}")
            report.append("")

        report.append("-" * 74)
        report.append("🌱 COZY STUDY CHEER & RECOMMENDATIONS:")
        report.append("-" * 74)
        if is_over:
            report.append(f"☕ Some days have a heavier workload than your {cap:.1f}h limit:")
            for d_str, pace_val in list(over_cap_days.items())[:5]:
                report.append(f"   • {d_str}: ~{pace_val:.2f} hrs (+{pace_val - cap:.2f}h above ceiling)")
            report.append("\n  Friendly Tips to Keep Things Stress-Free:")
            report.append(f"  1. Increase your daily cap slightly (e.g. to {max_daily_pace:.2f}h) if you have free study weekends.")
            report.append("  2. Focus on high-yield revision topics for whichever exam is nearest.")
            report.append("  3. Remember: It's all about consistent small sessions. Drink water & take tea breaks!")
        else:
            buffer = round(cap - max_daily_pace, 2)
            report.append(f"🎉 Your schedule is in sweet harmony! You have a comfortable buffer of {buffer} hrs/day")
            report.append(f"   below your maximum limit of {cap:.1f} hrs/day. Follow today's check-in and bloom! 🌸")

        report.append("")
        report.append("-" * 74)
        report.append("🔄 GENTLE ADAPTIVE REPLAN LOG:")
        report.append("-" * 74)
        if not self.replan_history:
            report.append("No replanning events recorded yet in this session — everything is peaceful! ✨")
        else:
            for idx, h in enumerate(reversed(self.replan_history), 1):
                report.append(
                    f"[{h['timestamp']}] Replan #{len(self.replan_history) - idx + 1}: "
                    f"Pace {h['max_daily_pace']} h/d | Rescheduled {h.get('total_rescheduled_count', 0)} task(s) into available days."
                )

        self.txt_insights.delete("1.0", tk.END)
        self.txt_insights.insert("1.0", "\n".join(report))

    def _sort_schedule_by_column(self, col: str) -> None:
        if self.df_schedule.empty:
            return
        ascending = getattr(self, f"_sort_asc_{col}", True)
        setattr(self, f"_sort_asc_{col}", not ascending)

        try:
            self.df_schedule = self.df_schedule.sort_values(by=col, ascending=ascending)
            self._refresh_schedule_view()
        except Exception:
            pass

    def set_status_message(self, msg: str) -> None:
        self.lbl_status_msg.config(text=msg)

    def _show_about_dialog(self) -> None:
        msg = (
            "🌸 RePlan v1.1 — Cozy & Friendly Adaptive Semester Planner 💖\n\n"
            "An encouraging, stress-free academic companion designed to help you\n"
            "plan multiple courses, syllabus outlines, and individual exam dates with peace of mind.\n\n"
            "Key Features in v1.1:\n"
            "• Cute & Cozy Design: Warm pastel palette, cheerful icons, and encouraging cheerleader prompts!\n"
            "• Multi-Course Outlines: Add courses with distinct themes and syllabus outlines.\n"
            "• Individual Exam Deadlines: Every course paces its study before its specific exam date.\n"
            "• Cozy Today's Check-in: Celebrate your wins with 1-click 'Yay! Finished Today!' ✨\n"
            "• Gentle Adaptive Rescheduling: Life happens! When you miss a day, RePlan reorganizes\n"
            "  your unfinished topics strictly before each exam and highlights them in DREAMY LAVENDER 🌸\n"
            "• Daily Harmony & Workload Pace: Peacefully alerts you if study days are overloaded.\n"
            "• Save & Share: Saves full plans and outlines to CSV and companion metadata.\n\n"
            "Remember: You are capable, resilient, and ready to shine! 🌸🎓"
        )
        messagebox.showinfo("About RePlan v1.1 🌸", msg)


# ---------------------------------------------------------------------------
# CLI / Main Entrypoint
# ---------------------------------------------------------------------------
def main():
    app = ReplanV11App()
    app.mainloop()


if __name__ == "__main__":
    main()
