"""
RePlan v1 — Adaptive Multi-Course Semester Planner 🎓
GUI Desktop Application

Transforms multiple course outlines, distinct exam dates, credit hours,
and daily availability limits into a cohesive master semester study roadmap.

When a student misses a session (or forgets to click 'Done Studying'),
RePlan adaptively redistributes missed course tasks into upcoming available study days
strictly before each course's individual exam deadline, highlights rescheduled tasks
in purple, and recalibrates daily study pace.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
import json
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Color Palette & Constants
# ---------------------------------------------------------------------------
BG_DARK = "#0f172a"        # Deep slate (header)
BG_LIGHT = "#f8fafc"       # Slate 50 (main app bg)
BG_CARD = "#ffffff"        # Card surface
BORDER_COLOR = "#e2e8f0"   # Subtle border
TEXT_MAIN = "#0f172a"      # Primary text (deep slate)
TEXT_MUTED = "#64748b"     # Secondary text
TEXT_LIGHT = "#f8fafc"     # Inverted light text

COLOR_PRIMARY = "#4f46e5"  # Indigo 600
COLOR_PRIMARY_HOVER = "#4338ca"
COLOR_SUCCESS = "#10b981"  # Emerald 500
COLOR_SUCCESS_HOVER = "#059669"
COLOR_SUCCESS_BG = "#ecfdf5"
COLOR_SUCCESS_TEXT = "#065f46"
COLOR_DANGER = "#ef4444"   # Rose/Red 500
COLOR_DANGER_HOVER = "#dc2626"
COLOR_DANGER_BG = "#fef2f2"
COLOR_DANGER_TEXT = "#991b1b"
COLOR_WARNING = "#f59e0b"  # Amber 500
COLOR_WARNING_BG = "#fffbeb"
COLOR_WARNING_TEXT = "#92400e"
COLOR_INFO = "#3b82f6"     # Blue 500
COLOR_TODAY_BG = "#fef3c7" # Soft warm amber highlight for today
COLOR_TODAY_TEXT = "#78350f"

# Rescheduled Highlighting Palette (Soft Lavender & Deep Violet)
COLOR_RESCHEDULED = "#8b5cf6"        # Violet 500
COLOR_RESCHEDULED_HOVER = "#7c3aed"  # Violet 600
COLOR_RESCHEDULED_BG = "#f3e8ff"     # Violet 100 (prominent highlight background)
COLOR_RESCHEDULED_TEXT = "#581c87"   # Violet 900 (clear dark text)
COLOR_RESCHEDULED_BORDER = "#c084fc" # Violet 400

# Distinct Palette for Courses
COURSE_PALETTE = [
    {"name": "Indigo",  "primary": "#4f46e5", "bg": "#e0e7ff", "text": "#3730a3"},
    {"name": "Emerald", "primary": "#059669", "bg": "#d1fae5", "text": "#065f46"},
    {"name": "Amber",   "primary": "#d97706", "bg": "#fef3c7", "text": "#92400e"},
    {"name": "Violet",  "primary": "#7c3aed", "bg": "#ede9fe", "text": "#5b21b6"},
    {"name": "Rose",    "primary": "#e11d48", "bg": "#ffe4e6", "text": "#9f1239"},
    {"name": "Cyan",    "primary": "#0891b2", "bg": "#cffafe", "text": "#155e75"},
    {"name": "Teal",    "primary": "#0d9488", "bg": "#ccfbf1", "text": "#115e59"},
]

DEFAULT_CSV_PATH = "replanv1_semester_plan.csv"
STUDY_HOURS_PER_CH = 45.0  # 1 Credit Hour = 45 study hours


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class CourseConfig:
    name: str
    credit_hours: float
    exam_date: date
    topics: List[str]
    color: str = "#4f46e5"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "credit_hours": self.credit_hours,
            "exam_date": self.exam_date.strftime("%Y-%m-%d"),
            "topics": self.topics,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CourseConfig:
        exam_d = datetime.strptime(data["exam_date"], "%Y-%m-%d").date()
        return cls(
            name=data["name"],
            credit_hours=float(data["credit_hours"]),
            exam_date=exam_d,
            topics=list(data.get("topics", [])),
            color=data.get("color", "#4f46e5"),
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
    """Core scheduling engine supporting multiple courses with independent outlines and exam dates."""

    @staticmethod
    def parse_date(date_str: str) -> date:
        """Flexible parser supporting YYYY-MM-DD, slashes, or word formats."""
        clean = date_str.strip()
        if not clean:
            raise ValueError("Date string cannot be empty.")
        try:
            return pd.to_datetime(clean).date()
        except Exception:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                try:
                    return datetime.strptime(clean, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse '{clean}' as a date. Use YYYY-MM-DD format (e.g. 2026-12-15).")

    @staticmethod
    def generate_multi_course_schedule(
        courses: List[CourseConfig],
        start_date: Optional[date] = None,
        hours_per_ch: float = STUDY_HOURS_PER_CH,
    ) -> Tuple[pd.DataFrame, List[TopicPeriod], Dict[str, Any]]:
        """
        Generates unified master schedule across multiple courses.
        Each course distributes its required hours (CH * 45) evenly across
        its remaining days up to its specific exam date, and divides days across its syllabus topics.
        """
        if not courses:
            raise ValueError("At least one course is required to generate a semester plan.")

        curr_date = start_date or date.today()
        all_rows: List[Dict[str, Any]] = []
        topic_periods: List[TopicPeriod] = []
        course_meta: Dict[str, Any] = {}

        # Validation
        seen_names = set()
        for c in courses:
            clean_name = c.name.strip()
            if not clean_name:
                raise ValueError("Course name cannot be blank.")
            if clean_name in seen_names:
                raise ValueError(f"Duplicate course name found: '{clean_name}'. Course names must be unique.")
            seen_names.add(clean_name)

            if c.credit_hours <= 0:
                raise ValueError(f"Credit hours for '{clean_name}' must be greater than zero.")

            clean_topics = [t.strip() for t in c.topics if t.strip()]
            if not clean_topics:
                raise ValueError(f"Course '{clean_name}' must have at least one outline topic.")

            rem_days = (c.exam_date - curr_date).days
            if rem_days <= 0:
                raise ValueError(
                    f"Exam date for '{clean_name}' ({c.exam_date}) must be strictly after the start date ({curr_date}). "
                    f"Remaining study days: {rem_days}."
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
        # Sort chronologically by Date, then Course Name
        df = df.sort_values(by=["Date", "Course"]).reset_index(drop=True)

        # Map calendar dates to unified semester Day numbers (Day 1, Day 2, etc.)
        date_to_day: Dict[str, int] = {}
        for d_str in df["Date"].unique():
            row_d = datetime.strptime(d_str, "%Y-%m-%d").date()
            date_to_day[d_str] = (row_d - curr_date).days + 1

        df["Day"] = df["Date"].map(date_to_day)

        # Reorder columns with Day first
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
        """Derives topic period metrics from any multi-course schedule DataFrame."""
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
        Adaptive Multi-Course Rescheduling Engine:
        1. Automatically identifies past uncompleted sessions before today and marks them as Missed.
        2. Course-by-Course Rescheduling:
           For each course independently, redistributes all unfinished curriculum tasks across
           its remaining available study days strictly before that course's exam date.
        3. Flags and highlights rescheduled tasks (Status: 'Rescheduled', purple background).
        4. Recalibrates individual course paces and analyzes combined daily study pace against max cap.
        """
        if df.empty:
            raise ValueError("No schedule available to replan.")

        df = df.copy()
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""

        if today_date is None:
            today_date = date.today()

        date_series = pd.to_datetime(df["Date"]).dt.date

        # 1. Past days where user did not click 'Done Studying' are marked Missed
        past_uncompleted = (date_series < today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
        if past_uncompleted.any():
            df.loc[past_uncompleted, "Status"] = "Missed"

        unique_courses = df["Course"].unique().tolist()
        course_stats: Dict[str, Any] = {}
        total_rescheduled_count = 0
        first_rescheduled_info: Optional[Dict[str, str]] = None

        # 2. Reschedule each course respecting its own sequence and exam deadline
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

            # Available future slots for this course
            avail_mask = (c_mask) & (date_series >= today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
            avail_indices = df[avail_mask].index.tolist()
            num_available = len(avail_indices)

            missed_mask = (c_mask) & (df["Status"] == "Missed")
            missed_indices = df[missed_mask].index.tolist()
            num_missed = len(missed_indices)

            prev_target = float(sub.loc[avail_indices[0], "Target Hours"]) if avail_indices else 0.0
            course_rescheduled_count = 0

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
                        course_rescheduled_count += 1
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

            # Recalculate adaptive daily target hours for this course
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
                "rescheduled_count": course_rescheduled_count,
                "prev_target": prev_target,
                "new_daily_hours": new_daily_hours,
                "rate_change": round(new_daily_hours - prev_target, 2),
                "uncompleted_hours": round(uncompleted_hours, 2),
            }

        # Multi-Course Combined Daily Workload & Feasibility Check
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
        """Loads schedule CSV and optional companion course metadata."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        df = pd.read_csv(filepath)
        required_cols = ["Day", "Date", "Weekday", "Target Hours", "Topic Day", "Topic", "Status"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"CSV file is missing expected columns: {missing}")

        # If older CSV without Course column is loaded, provide a fallback
        if "Course" not in df.columns:
            df["Course"] = "Course 1"

        df["Day"] = pd.to_numeric(df["Day"], errors="coerce").fillna(0).astype(int)
        df["Target Hours"] = pd.to_numeric(df["Target Hours"], errors="coerce").fillna(0.0).round(2)
        df["Status"] = df["Status"].fillna("Pending").astype(str)
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""
        else:
            df["Rescheduled_From"] = df["Rescheduled_From"].fillna("").astype(str)

        # Attempt to load companion course metadata (.meta.json)
        courses: List[CourseConfig] = []
        meta_path = filepath + ".meta.json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("courses", []):
                        courses.append(CourseConfig.from_dict(item))
            except Exception as e:
                print(f"Warning: could not load metadata from {meta_path}: {e}")

        # If no meta file exists, reconstruct CourseConfig approximations from DataFrame
        if not courses:
            for idx, c_name in enumerate(df["Course"].unique()):
                sub = df[df["Course"] == c_name]
                last_d = pd.to_datetime(sub["Date"].iloc[-1]).date()
                unique_topics = list(dict.fromkeys(
                    str(t).split(" • 🔄")[0].split(" (🔄")[0].strip() for t in sub["Topic"]
                ))
                approx_hours = float(sub["Target Hours"].sum())
                approx_ch = max(1.0, round(approx_hours / STUDY_HOURS_PER_CH, 1))
                color = COURSE_PALETTE[idx % len(COURSE_PALETTE)]["primary"]
                courses.append(
                    CourseConfig(
                        name=str(c_name),
                        credit_hours=approx_ch,
                        exam_date=last_d,
                        topics=unique_topics,
                        color=color,
                    )
                )

        return df, courses

    @staticmethod
    def save_csv(df: pd.DataFrame, filepath: str, courses: Optional[List[CourseConfig]] = None) -> None:
        """Saves schedule DataFrame to CSV and course configs to companion .meta.json."""
        df.to_csv(filepath, index=False)
        if courses:
            meta_path = filepath + ".meta.json"
            try:
                meta_data = {"courses": [c.to_dict() for c in courses]}
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
            except Exception as e:
                print(f"Warning: could not write course metadata to {meta_path}: {e}")


# ---------------------------------------------------------------------------
# Custom Metric Card Widget
# ---------------------------------------------------------------------------
class MetricCard(tk.Frame):
    """Modern card display for key stats and progress indicators."""

    def __init__(
        self,
        parent,
        title: str,
        initial_val: str = "--",
        subtitle: str = "",
        accent_color: str = COLOR_PRIMARY,
        icon: str = "•",
        **kwargs,
    ):
        super().__init__(
            parent,
            bg=BG_CARD,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=12,
            pady=8,
            **kwargs,
        )
        self.accent_color = accent_color

        top_row = tk.Frame(self, bg=BG_CARD)
        top_row.pack(fill="x", expand=True)

        self.lbl_icon = tk.Label(top_row, text=icon, font=("Helvetica Neue", 12), fg=accent_color, bg=BG_CARD)
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
            fg=TEXT_MAIN,
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
# Course Add / Edit Modal Dialog
# ---------------------------------------------------------------------------
class CourseDialog(tk.Toplevel):
    """Modal dialog for creating or updating a course outline and exam date."""

    def __init__(
        self,
        parent: tk.Tk,
        title: str = "Course Details",
        course: Optional[CourseConfig] = None,
        palette_index: int = 0,
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("540x560")
        self.minsize(480, 500)
        self.configure(bg=BG_LIGHT)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[CourseConfig] = None
        self.palette_index = palette_index

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
        # Header banner
        hdr = tk.Frame(self, bg=BG_DARK, padx=18, pady=12)
        hdr.pack(side="top", fill="x")

        lbl_hdr = tk.Label(
            hdr,
            text="📘 Course Configuration & Exam Date",
            font=("Helvetica Neue", 12, "bold"),
            fg="#ffffff",
            bg=BG_DARK,
        )
        lbl_hdr.pack(anchor="w")

        body = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=14)
        body.pack(side="top", fill="both", expand=True)

        # 1. Course Name
        tk.Label(body, text="Course Name / Code:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_LIGHT).pack(anchor="w")
        self.entry_name = tk.Entry(body, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_MAIN, relief="solid", bd=1)
        self.entry_name.pack(fill="x", pady=(2, 10))

        # 2. Credit Hours & Color
        row_params = tk.Frame(body, bg=BG_LIGHT)
        row_params.pack(fill="x", pady=(0, 10))

        col_ch = tk.Frame(row_params, bg=BG_LIGHT)
        col_ch.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(col_ch, text="Credit Hours (CH):", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_LIGHT).pack(anchor="w")
        self.entry_ch = tk.Entry(col_ch, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_MAIN, relief="solid", bd=1)
        self.entry_ch.pack(fill="x", pady=(2, 0))

        col_color = tk.Frame(row_params, bg=BG_LIGHT)
        col_color.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(col_color, text="Badge Color:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_LIGHT).pack(anchor="w")
        palette_names = [p["name"] for p in COURSE_PALETTE]
        self.combo_color = ttk.Combobox(col_color, values=palette_names, state="readonly", font=("Helvetica Neue", 10))
        self.combo_color.current(self.palette_index % len(COURSE_PALETTE))
        self.combo_color.pack(fill="x", pady=(2, 0))

        # 3. Exam Date
        tk.Label(body, text="Course Exam Date (YYYY-MM-DD):", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_LIGHT).pack(anchor="w")
        self.entry_exam = tk.Entry(body, font=("Helvetica Neue", 10), bg="#ffffff", fg=TEXT_MAIN, relief="solid", bd=1)
        self.entry_exam.pack(fill="x", pady=(2, 4))

        # Quick preset buttons for exam date
        quick_frame = tk.Frame(body, bg=BG_LIGHT)
        quick_frame.pack(fill="x", pady=(0, 10))
        tk.Label(quick_frame, text="Quick Presets: ", font=("Helvetica Neue", 8), fg=TEXT_MUTED, bg=BG_LIGHT).pack(side="left")
        for days in [30, 60, 75, 90, 120]:
            btn = tk.Button(
                quick_frame,
                text=f"+{days}d",
                font=("Helvetica Neue", 8),
                bg="#e2e8f0",
                fg=TEXT_MAIN,
                relief="flat",
                command=lambda d=days: self._set_exam_days(d),
                padx=6,
                pady=1,
            )
            btn.pack(side="left", padx=2)

        # 4. Course Outline / Topics
        tk.Label(
            body,
            text="Course Outline / Syllabus Topics (One per line or comma-separated):",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_MAIN,
            bg=BG_LIGHT,
        ).pack(anchor="w")

        self.txt_topics = tk.Text(
            body,
            height=6,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            relief="solid",
            bd=1,
            wrap="word",
        )
        self.txt_topics.pack(fill="both", expand=True, pady=(2, 14))

        # Prepopulate if editing
        if course:
            self.entry_name.insert(0, course.name)
            self.entry_ch.insert(0, str(course.credit_hours))
            self.entry_exam.insert(0, course.exam_date.strftime("%Y-%m-%d"))
            self.txt_topics.insert("1.0", "\n".join(course.topics))
            # match color
            for i, p in enumerate(COURSE_PALETTE):
                if p["primary"] == course.color:
                    self.combo_color.current(i)
                    break
        else:
            default_exam = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
            self.entry_exam.insert(0, default_exam)
            self.entry_ch.insert(0, "3.0")

        # Footer Buttons
        footer = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=12)
        footer.pack(side="bottom", fill="x")

        btn_cancel = tk.Button(
            footer,
            text="Cancel",
            command=self.destroy,
            font=("Helvetica Neue", 9),
            bg="#e2e8f0",
            fg=TEXT_MAIN,
            relief="flat",
            padx=16,
            pady=6,
            cursor="pointinghand",
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = tk.Button(
            footer,
            text="💾 Save Course",
            command=self._on_save,
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_PRIMARY,
            fg="#ffffff",
            activebackground=COLOR_PRIMARY_HOVER,
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
            # Split by lines and commas
            topics = [t.strip() for line in topics_raw.split("\n") for t in line.split(",") if t.strip()]
            if not topics:
                messagebox.showerror("Validation Error", "Please enter at least one topic in the course outline.", parent=self)
                return

            color_idx = self.combo_color.current()
            color = COURSE_PALETTE[color_idx % len(COURSE_PALETTE)]["primary"]

            self.result = CourseConfig(
                name=name,
                credit_hours=ch,
                exam_date=exam_d,
                topics=topics,
                color=color,
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


# ---------------------------------------------------------------------------
# Main RePlan v1 GUI Application
# ---------------------------------------------------------------------------
class ReplanV1App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RePlan v1 — Adaptive Multi-Course Semester Planner 🎓")
        self.geometry("1320x890")
        self.minsize(1100, 720)
        self.configure(bg=BG_LIGHT)

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
        self._build_metric_ribbon()
        self._build_main_layout()
        self._build_status_bar()

        # Load standard multi-course sample by default
        self._load_sample_courses(auto_generate=True)

    def _init_styles(self) -> None:
        """Global ttk styles for crisp typography and cross-platform visibility."""
        self.option_add("*Entry.foreground", TEXT_MAIN)
        self.option_add("*Entry.background", "#ffffff")
        self.option_add("*Entry.insertBackground", TEXT_MAIN)
        self.option_add("*Text.foreground", TEXT_MAIN)
        self.option_add("*Text.background", "#ffffff")
        self.option_add("*Text.insertBackground", TEXT_MAIN)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Notebook tabs
        self.style.configure(
            "TNotebook",
            background=BG_LIGHT,
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )
        self.style.configure(
            "TNotebook.Tab",
            padding=[14, 7],
            font=("Helvetica Neue", 10, "bold"),
            background="#e2e8f0",
            foreground=TEXT_MUTED,
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", BG_CARD)],
            foreground=[("selected", COLOR_PRIMARY)],
        )

        # Treeview styling
        self.style.configure(
            "Treeview",
            background=BG_CARD,
            foreground=TEXT_MAIN,
            fieldbackground=BG_CARD,
            rowheight=27,
            font=("Helvetica Neue", 10),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Helvetica Neue", 9, "bold"),
            background="#f1f5f9",
            foreground=TEXT_MAIN,
            relief="flat",
            padding=[6, 5],
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", "#e2e8f0")],
        )

        # Combobox styling
        self.style.configure(
            "TCombobox",
            foreground=TEXT_MAIN,
            background="#ffffff",
            fieldbackground="#ffffff",
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            foreground=[("readonly", TEXT_MAIN)],
        )

    # -----------------------------------------------------------------------
    # Top Header
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        header_frame = tk.Frame(self, bg=BG_DARK, height=60, padx=20, pady=8)
        header_frame.pack(side="top", fill="x")

        brand_frame = tk.Frame(header_frame, bg=BG_DARK)
        brand_frame.pack(side="left", fill="y")

        lbl_logo = tk.Label(
            brand_frame,
            text="🎓 RePlan v1",
            font=("Helvetica Neue", 17, "bold"),
            fg="#ffffff",
            bg=BG_DARK,
        )
        lbl_logo.pack(side="left")

        lbl_tagline = tk.Label(
            brand_frame,
            text=" | Adaptive Multi-Course Semester Planner • Multiple Outlines & Distinct Exam Dates",
            font=("Helvetica Neue", 10),
            fg="#94a3b8",
            bg=BG_DARK,
        )
        lbl_tagline.pack(side="left", padx=(6, 0))

        btn_bar = tk.Frame(header_frame, bg=BG_DARK)
        btn_bar.pack(side="right")

        self._create_header_btn(btn_bar, "📂 Open Plan", self._on_load_csv_dialog)
        self._create_header_btn(btn_bar, "💾 Save Plan", self._on_save_csv_dialog)
        self._create_header_btn(btn_bar, "✨ Load 3-Course Sample", lambda: self._load_sample_courses(auto_generate=True))
        self._create_header_btn(btn_bar, "➕ Add Course", self._on_add_course_dialog)
        self._create_header_btn(btn_bar, "ℹ️ About", self._show_about_dialog)

    def _create_header_btn(self, parent, text: str, command) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Helvetica Neue", 9, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
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
    # Metric Ribbon (6 Key Multi-Course Cards)
    # -----------------------------------------------------------------------
    def _build_metric_ribbon(self) -> None:
        ribbon_frame = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=10)
        ribbon_frame.pack(side="top", fill="x")

        self.card_courses = MetricCard(
            ribbon_frame,
            title="Enrolled Courses",
            initial_val="0 Courses",
            subtitle="Configured in semester",
            accent_color="#3b82f6",
            icon="📚",
        )
        self.card_courses.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.card_nearest_exam = MetricCard(
            ribbon_frame,
            title="Nearest Exam",
            initial_val="--",
            subtitle="Countdown to first deadline",
            accent_color="#f59e0b",
            icon="⏰",
        )
        self.card_nearest_exam.pack(side="left", fill="x", expand=True, padx=4)

        self.card_total_hours = MetricCard(
            ribbon_frame,
            title="Total Study Hours",
            initial_val="--",
            subtitle="Across all courses",
            accent_color="#8b5cf6",
            icon="⏱️",
        )
        self.card_total_hours.pack(side="left", fill="x", expand=True, padx=4)

        self.card_target = MetricCard(
            ribbon_frame,
            title="Today's Target Pace",
            initial_val="--",
            subtitle="Sum across active courses",
            accent_color=COLOR_PRIMARY,
            icon="🎯",
        )
        self.card_target.pack(side="left", fill="x", expand=True, padx=4)

        self.card_progress = MetricCard(
            ribbon_frame,
            title="Overall Progress",
            initial_val="0%",
            subtitle="0 completed",
            accent_color=COLOR_SUCCESS,
            icon="📈",
        )
        self.card_progress.pack(side="left", fill="x", expand=True, padx=4)

        self.card_feasibility = MetricCard(
            ribbon_frame,
            title="Feasibility Pace",
            initial_val="Ready",
            subtitle="Limit: 5.0h/day",
            accent_color=COLOR_SUCCESS,
            icon="🛡️",
        )
        self.card_feasibility.pack(side="left", fill="x", expand=True, padx=(6, 0))

    # -----------------------------------------------------------------------
    # Main Paned / Side-by-Side Layout
    # -----------------------------------------------------------------------
    def _build_main_layout(self) -> None:
        content_frame = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=4)
        content_frame.pack(side="top", fill="both", expand=True)

        # Left Column: Controls (~390px)
        left_col = tk.Frame(content_frame, bg=BG_LIGHT, width=390)
        left_col.pack(side="left", fill="y", padx=(0, 14))
        left_col.pack_propagate(False)

        # Right Column: Tabbed Views
        right_col = tk.Frame(content_frame, bg=BG_LIGHT)
        right_col.pack(side="left", fill="both", expand=True)

        self._build_sidebar_controls(left_col)
        self._build_right_notebook(right_col)

    # -----------------------------------------------------------------------
    # Left Sidebar Controls
    # -----------------------------------------------------------------------
    def _build_sidebar_controls(self, parent: tk.Frame) -> None:
        # Card 0: Today's Multi-Course Study Check-in Hero Box
        self.card_checkin = tk.Frame(
            parent,
            bg=BG_CARD,
            highlightthickness=2,
            highlightbackground=COLOR_PRIMARY,
            padx=12,
            pady=10,
        )
        self.card_checkin.pack(side="top", fill="x", pady=(0, 10))

        top_checkin = tk.Frame(self.card_checkin, bg=BG_CARD)
        top_checkin.pack(fill="x")

        lbl_checkin_title = tk.Label(
            top_checkin,
            text="🎯 TODAY'S STUDY CHECK-IN",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_PRIMARY,
            bg=BG_CARD,
        )
        lbl_checkin_title.pack(side="left")

        today_str = date.today().strftime("%Y-%m-%d")
        lbl_today_badge = tk.Label(
            top_checkin,
            text=today_str,
            font=("Helvetica Neue", 8, "bold"),
            fg=TEXT_MUTED,
            bg="#f1f5f9",
            padx=6,
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
            text="✅ Done All Studying Today!",
            command=self._mark_all_today_done,
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_SUCCESS,
            fg="#ffffff",
            activebackground=COLOR_SUCCESS_HOVER,
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
            text="❌ Missed Today",
            command=self._mark_all_today_missed,
            font=("Helvetica Neue", 8, "bold"),
            bg=COLOR_DANGER_BG,
            fg=COLOR_DANGER_TEXT,
            activebackground="#fee2e2",
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
            bg="#f1f5f9",
            fg=TEXT_MAIN,
            activebackground="#e2e8f0",
            relief="flat",
            bd=0,
            pady=5,
            cursor="pointinghand",
        )
        btn_reset_today.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # Card 1: Enrolled Courses Setup & Manager
        card_setup = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=12, pady=10)
        card_setup.pack(side="top", fill="x", pady=(0, 10))

        hdr_setup = tk.Frame(card_setup, bg=BG_CARD)
        hdr_setup.pack(fill="x", pady=(0, 6))

        lbl_sec1 = tk.Label(
            hdr_setup,
            text="📚 ENROLLED COURSES",
            font=("Helvetica Neue", 10, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        lbl_sec1.pack(side="left")

        # Compact Treeview for Courses List
        course_tree_frame = tk.Frame(card_setup, bg=BG_CARD)
        course_tree_frame.pack(fill="x", pady=(0, 6))

        c_cols = ("Course", "CH", "Exam Date", "Topics")
        self.tree_courses = ttk.Treeview(course_tree_frame, columns=c_cols, show="headings", height=4, selectmode="browse")
        self.tree_courses.heading("Course", text="Course")
        self.tree_courses.heading("CH", text="CH")
        self.tree_courses.heading("Exam Date", text="Exam Date")
        self.tree_courses.heading("Topics", text="Topics")

        self.tree_courses.column("Course", width=140, anchor="w")
        self.tree_courses.column("CH", width=40, anchor="center")
        self.tree_courses.column("Exam Date", width=85, anchor="center")
        self.tree_courses.column("Topics", width=55, anchor="center")

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
            bg="#f1f5f9",
            fg=TEXT_MAIN,
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
            bg="#f1f5f9",
            fg=TEXT_MAIN,
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
            bg=COLOR_DANGER_BG,
            fg=COLOR_DANGER_TEXT,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_del_c.pack(side="left", padx=3)

        btn_load_preset = tk.Button(
            course_btn_row,
            text="✨ Preset",
            command=lambda: self._load_sample_courses(auto_generate=False),
            font=("Helvetica Neue", 8),
            bg="#e0e7ff",
            fg=COLOR_PRIMARY,
            relief="flat",
            padx=6,
            pady=3,
            cursor="pointinghand",
        )
        btn_load_preset.pack(side="right")

        # Global Parameters (Semester Start Date & Max Daily Cap)
        params_box = tk.Frame(card_setup, bg="#f8fafc", highlightthickness=1, highlightbackground=BORDER_COLOR, padx=8, pady=6)
        params_box.pack(fill="x", pady=(0, 8))

        row_p1 = tk.Frame(params_box, bg="#f8fafc")
        row_p1.pack(fill="x", pady=(0, 4))

        tk.Label(row_p1, text="Start Date:", font=("Helvetica Neue", 8, "bold"), fg=TEXT_MUTED, bg="#f8fafc").pack(side="left")
        self.entry_start_date = tk.Entry(row_p1, font=("Helvetica Neue", 9), bg="#ffffff", fg=TEXT_MAIN, width=11, relief="solid", bd=1)
        self.entry_start_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.entry_start_date.pack(side="right")

        row_p2 = tk.Frame(params_box, bg="#f8fafc")
        row_p2.pack(fill="x")

        tk.Label(row_p2, text="Max Daily Cap (h/d):", font=("Helvetica Neue", 8, "bold"), fg=TEXT_MUTED, bg="#f8fafc").pack(side="left")
        self.entry_cap = tk.Entry(row_p2, font=("Helvetica Neue", 9), bg="#ffffff", fg=TEXT_MAIN, width=6, relief="solid", bd=1)
        self.entry_cap.insert(0, "5.0")
        self.entry_cap.pack(side="right")

        # Master Schedule Generation Button
        btn_generate = tk.Button(
            card_setup,
            text="🚀 Generate Whole Semester Plan",
            command=self._on_generate_schedule,
            font=("Helvetica Neue", 10, "bold"),
            bg=COLOR_PRIMARY,
            fg="#ffffff",
            activebackground=COLOR_PRIMARY_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=8,
            cursor="pointinghand",
        )
        btn_generate.pack(fill="x")

        # Card 2: Adaptive Rescheduling Hero Card
        card_replan = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=12, pady=10)
        card_replan.pack(side="top", fill="x")

        lbl_sec2 = tk.Label(
            card_replan,
            text="🔄 ADAPTIVE REPLAN ENGINE",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_PRIMARY,
            bg=BG_CARD,
        )
        lbl_sec2.pack(anchor="w")

        lbl_replan_desc = tk.Label(
            card_replan,
            text="Missed any study sessions? RePlan automatically redistributes unfinished work into future days before each course's individual exam deadline.",
            font=("Helvetica Neue", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            wraplength=350,
            justify="left",
        )
        lbl_replan_desc.pack(anchor="w", pady=(3, 8))

        btn_replan = tk.Button(
            card_replan,
            text="🔄 Adaptive Replan Now",
            command=self._on_adaptive_replan,
            font=("Helvetica Neue", 10, "bold"),
            bg=COLOR_PRIMARY,
            fg="#ffffff",
            activebackground=COLOR_PRIMARY_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=8,
            cursor="pointinghand",
        )
        btn_replan.pack(fill="x")

    # -----------------------------------------------------------------------
    # Right Tabbed Panels
    # -----------------------------------------------------------------------
    def _build_right_notebook(self, parent: tk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Master Day-by-Day Schedule
        self.tab_schedule = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_schedule, text="  📋 Day-by-Day Master Schedule  ")
        self._build_schedule_tab(self.tab_schedule)

        # Tab 2: Course Outlines & Timeline
        self.tab_courses = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_courses, text="  📚 Course Outlines & Timeline  ")
        self._build_courses_tab(self.tab_courses)

        # Tab 3: Daily Workload & Pace
        self.tab_daily = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_daily, text="  📅 Daily Workload & Pace  ")
        self._build_daily_tab(self.tab_daily)

        # Tab 4: Multi-Course Insights & Feasibility
        self.tab_insights = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_insights, text="  📊 Multi-Course Insights & Feasibility  ")
        self._build_insights_tab(self.tab_insights)

    # -----------------------------------------------------------------------
    # Tab 1: Day-by-Day Schedule Table (Multi-Course)
    # -----------------------------------------------------------------------
    def _build_schedule_tab(self, parent: tk.Frame) -> None:
        # Top Action Bar: Quick status tagging for selected row(s)
        action_bar = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground=BORDER_COLOR, padx=12, pady=7)
        action_bar.pack(side="top", fill="x", padx=12, pady=(10, 6))

        lbl_action_title = tk.Label(
            action_bar,
            text="Mark Study Status:",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_MAIN,
            bg="#f8fafc",
        )
        lbl_action_title.pack(side="left", padx=(0, 8))

        btn_done = tk.Button(
            action_bar,
            text="✅ Done Studying",
            command=lambda: self._set_selected_status("Completed"),
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_SUCCESS,
            fg="#ffffff",
            activebackground=COLOR_SUCCESS_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=11,
            pady=4,
            cursor="pointinghand",
        )
        btn_done.pack(side="left", padx=(0, 5))

        btn_miss = tk.Button(
            action_bar,
            text="❌ Missed Studying",
            command=lambda: self._set_selected_status("Missed"),
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_DANGER,
            fg="#ffffff",
            activebackground=COLOR_DANGER_HOVER,
            activeforeground="#ffffff",
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
            bg="#e2e8f0",
            fg=TEXT_MAIN,
            activebackground="#cbd5e1",
            relief="flat",
            bd=0,
            padx=9,
            pady=4,
            cursor="pointinghand",
        )
        btn_pending.pack(side="left", padx=(0, 14))

        self.lbl_selected_preview = tk.Label(
            action_bar,
            text="Select row(s) below to mark completed/missed",
            font=("Helvetica Neue", 9),
            fg=TEXT_MUTED,
            bg="#f8fafc",
        )
        self.lbl_selected_preview.pack(side="left")

        # Filter & Search Toolbar
        filter_bar = tk.Frame(parent, bg=BG_CARD, padx=12, pady=5)
        filter_bar.pack(side="top", fill="x")

        # Course filter
        tk.Label(filter_bar, text="Filter Course:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.combo_course_filter = ttk.Combobox(filter_bar, values=["All Courses"], state="readonly", width=16)
        self.combo_course_filter.current(0)
        self.combo_course_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_schedule_view())
        self.combo_course_filter.pack(side="left", padx=(4, 12))

        # Status filter
        tk.Label(filter_bar, text="Filter Status:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.combo_status_filter = ttk.Combobox(
            filter_bar,
            values=["All", "Pending", "Completed", "Missed", "Rescheduled"],
            state="readonly",
            width=12,
        )
        self.combo_status_filter.current(0)
        self.combo_status_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_schedule_view())
        self.combo_status_filter.pack(side="left", padx=(4, 12))

        # Search topic/keyword
        tk.Label(filter_bar, text="Search:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.entry_search = tk.Entry(
            filter_bar,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
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
            bg="#f1f5f9",
            fg=TEXT_MAIN,
            relief="flat",
            padx=8,
            pady=2,
            cursor="pointinghand",
        )
        btn_jump_today.pack(side="left")

        self.lbl_table_count = tk.Label(filter_bar, text="0 milestones scheduled", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD)
        self.lbl_table_count.pack(side="right")

        # Treeview with Scrollbars
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
        self.tree_schedule.tag_configure("completed", background=COLOR_SUCCESS_BG, foreground=COLOR_SUCCESS_TEXT)
        self.tree_schedule.tag_configure("missed", background=COLOR_DANGER_BG, foreground=COLOR_DANGER_TEXT)
        self.tree_schedule.tag_configure("rescheduled", background=COLOR_RESCHEDULED_BG, foreground=COLOR_RESCHEDULED_TEXT)
        self.tree_schedule.tag_configure("today", background=COLOR_TODAY_BG, foreground=COLOR_TODAY_TEXT)
        self.tree_schedule.tag_configure("pending", background="#ffffff", foreground=TEXT_MAIN)

        # Bind events
        self.tree_schedule.bind("<<TreeviewSelect>>", self._on_tree_selection_change)
        self.tree_schedule.bind("<Double-1>", self._on_tree_double_click)
        self.tree_schedule.bind("<Button-2>", self._show_tree_context_menu)
        self.tree_schedule.bind("<Button-3>", self._show_tree_context_menu)

        # Context menu
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="✅ Mark Done Studying", command=lambda: self._set_selected_status("Completed"))
        self.tree_menu.add_command(label="❌ Mark Missed Session", command=lambda: self._set_selected_status("Missed"))
        self.tree_menu.add_command(label="⏳ Reset to Pending", command=lambda: self._set_selected_status("Pending"))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="🔄 Run Adaptive Replan", command=self._on_adaptive_replan)

    # -----------------------------------------------------------------------
    # Tab 2: Course Outlines & Timeline
    # -----------------------------------------------------------------------
    def _build_courses_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12)
        container.pack(fill="both", expand=True)

        # Section 1: Course Summary Table
        tk.Label(
            container,
            text="📚 ENROLLED COURSES SUMMARY & EXAM COUNTDOWNS",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        t1_frame = tk.Frame(container, bg=BG_CARD)
        t1_frame.pack(fill="x", pady=(0, 14))

        cols1 = ("Course", "CH", "Exam Date", "Days Left", "Total Hrs", "Daily Pace", "Completed", "Progress")
        self.tree_course_summary = ttk.Treeview(t1_frame, columns=cols1, show="headings", height=4)
        col_w = {
            "Course": (170, "w"),
            "CH": (50, "center"),
            "Exam Date": (95, "center"),
            "Days Left": (80, "center"),
            "Total Hrs": (85, "center"),
            "Daily Pace": (85, "center"),
            "Completed": (85, "center"),
            "Progress": (85, "center"),
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
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(side="left")

        self.lbl_selected_course_topics = tk.Label(
            hdr2,
            text="(All Courses)",
            font=("Helvetica Neue", 10),
            fg=COLOR_PRIMARY,
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
    # Tab 3: Daily Workload & Pace
    # -----------------------------------------------------------------------
    def _build_daily_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="📅 AGGREGATED DAILY STUDY WORKLOAD ACROSS ALL COURSES",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        t_frame = tk.Frame(container, bg=BG_CARD)
        t_frame.pack(fill="both", expand=True)

        cols = ("Day", "Date", "Weekday", "Active Courses", "Combined Target Hours", "Completed Hours", "Status Summary", "Feasibility Flag")
        self.tree_daily = ttk.Treeview(t_frame, columns=cols, show="headings", selectmode="browse")
        col_w = {
            "Day": (50, "center"),
            "Date": (95, "center"),
            "Weekday": (95, "w"),
            "Active Courses": (180, "w"),
            "Combined Target Hours": (145, "center"),
            "Completed Hours": (115, "center"),
            "Status Summary": (140, "center"),
            "Feasibility Flag": (120, "center"),
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

        self.tree_daily.tag_configure("overcap", background=COLOR_DANGER_BG, foreground=COLOR_DANGER_TEXT)
        self.tree_daily.tag_configure("today", background=COLOR_TODAY_BG, foreground=COLOR_TODAY_TEXT)
        self.tree_daily.tag_configure("feasible", background="#ffffff", foreground=TEXT_MAIN)

    # -----------------------------------------------------------------------
    # Tab 4: Multi-Course Insights & Feasibility
    # -----------------------------------------------------------------------
    def _build_insights_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=16, pady=12)
        container.pack(fill="both", expand=True)

        self.banner_feasibility = tk.Frame(
            container,
            bg=COLOR_SUCCESS_BG,
            highlightthickness=1,
            highlightbackground="#bbf7d0",
            padx=14,
            pady=10,
        )
        self.banner_feasibility.pack(fill="x", pady=(0, 10))

        self.lbl_feasibility_text = tk.Label(
            self.banner_feasibility,
            text="✅ FEASIBILITY STATUS: Study plan is well-balanced across all courses.",
            font=("Helvetica Neue", 10, "bold"),
            fg=COLOR_SUCCESS_TEXT,
            bg=COLOR_SUCCESS_BG,
            anchor="w",
        )
        self.lbl_feasibility_text.pack(fill="x")

        self.txt_insights = tk.Text(
            container,
            height=14,
            font=("Menlo", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
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
        self.status_bar = tk.Frame(self, bg="#f1f5f9", height=24, padx=14, pady=4)
        self.status_bar.pack(side="bottom", fill="x")

        self.lbl_status_file = tk.Label(
            self.status_bar,
            text="No active plan file",
            font=("Helvetica Neue", 9),
            fg=TEXT_MUTED,
            bg="#f1f5f9",
        )
        self.lbl_status_file.pack(side="left")

        self.lbl_status_msg = tk.Label(
            self.status_bar,
            text="Ready",
            font=("Helvetica Neue", 9),
            fg=COLOR_PRIMARY,
            bg="#f1f5f9",
        )
        self.lbl_status_msg.pack(side="right")

    # -----------------------------------------------------------------------
    # Course Management Actions (Add, Edit, Delete, Preset)
    # -----------------------------------------------------------------------
    def _refresh_course_list_ui(self) -> None:
        """Updates the sidebar course treeview."""
        for item in self.tree_courses.get_children():
            self.tree_courses.delete(item)

        for c in self.courses:
            self.tree_courses.insert(
                "",
                "end",
                values=(
                    c.name,
                    f"{c.credit_hours:.1f}",
                    c.exam_date.strftime("%Y-%m-%d"),
                    len(c.topics),
                ),
            )

        # Update course filter dropdown in schedule tab
        course_names = ["All Courses"] + [c.name for c in self.courses]
        curr_val = self.combo_course_filter.get()
        self.combo_course_filter["values"] = course_names
        if curr_val in course_names:
            self.combo_course_filter.set(curr_val)
        else:
            self.combo_course_filter.current(0)

    def _on_add_course_dialog(self) -> None:
        dlg = CourseDialog(self, title="Add Course", palette_index=len(self.courses))
        self.wait_window(dlg)
        if dlg.result:
            # Check for duplicate names
            if any(c.name.lower() == dlg.result.name.lower() for c in self.courses):
                messagebox.showerror("Duplicate Course", f"A course named '{dlg.result.name}' already exists.")
                return
            self.courses.append(dlg.result)
            self._refresh_course_list_ui()
            self.set_status_message(f"Added course: '{dlg.result.name}'")

    def _on_edit_course_dialog(self) -> None:
        selected = self.tree_courses.selection()
        if not selected:
            messagebox.showinfo("Select Course", "Please select a course from the list to edit.")
            return

        c_name = self.tree_courses.item(selected[0], "values")[0]
        match = [c for c in self.courses if c.name == c_name]
        if not match:
            return
        target_course = match[0]
        idx = self.courses.index(target_course)

        dlg = CourseDialog(self, title=f"Edit {target_course.name}", course=target_course, palette_index=idx)
        self.wait_window(dlg)
        if dlg.result:
            self.courses[idx] = dlg.result
            self._refresh_course_list_ui()
            self.set_status_message(f"Updated course: '{dlg.result.name}'")

    def _on_delete_course(self) -> None:
        selected = self.tree_courses.selection()
        if not selected:
            messagebox.showinfo("Select Course", "Please select a course from the list to remove.")
            return

        c_name = self.tree_courses.item(selected[0], "values")[0]
        if messagebox.askyesno("Confirm Delete", f"Remove '{c_name}' from your semester plan?"):
            self.courses = [c for c in self.courses if c.name != c_name]
            self._refresh_course_list_ui()
            self.set_status_message(f"Removed course: '{c_name}'")

    def _load_sample_courses(self, auto_generate: bool = True) -> None:
        """Loads a realistic 3-course university semester preset."""
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
                color=COURSE_PALETTE[0]["primary"],
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
                color=COURSE_PALETTE[1]["primary"],
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
                color=COURSE_PALETTE[2]["primary"],
            ),
        ]
        self._refresh_course_list_ui()
        if auto_generate:
            self._on_generate_schedule()
        self.set_status_message("Loaded standard 3-course semester sample plan.")

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
                f"Generated plan: {len(df)} milestones across {len(self.courses)} courses ({summary['total_study_hours']} total hrs)"
            )

        except Exception as e:
            messagebox.showerror("Generation Error", str(e))

    def _on_adaptive_replan(self) -> None:
        self._run_reschedule_engine(show_toast=True, source_reason="Manual Adaptive Replan")

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

            # Find and highlight rescheduled row in Treeview
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
                        f"🔄 Adaptive Rescheduling Complete!\n\n"
                        f"• Reason: {source_reason}\n"
                        f"• Rescheduled Tasks: {stats['total_rescheduled_count']} task(s) adjusted\n"
                        f"• Earliest Adjustment: {first.get('date', '--')} [{first.get('course', '')}: {first.get('topic', '')}]\n"
                        f"• Visual Indicator: Highlighted in PURPLE in the schedule table below!\n\n"
                        f"• Peak Combined Pace: {stats['max_daily_pace']} hrs/day\n"
                        f"• Average Combined Pace: {stats['avg_daily_pace']} hrs/day"
                    )
                    if stats["is_over_cap"]:
                        msg += f"\n\n⚠️ Caution: Planned pace exceeds your limit ({cap:.1f} hrs/day) on {stats['over_cap_days_count']} day(s)!"
                        messagebox.showwarning("Tasks Rescheduled (Capacity Alert)", msg)
                    else:
                        messagebox.showinfo("Tasks Rescheduled", msg)
                else:
                    msg = (
                        f"🔄 Adaptive Replan Complete!\n\n"
                        f"• All tasks are currently on track.\n"
                        f"• Peak Combined Pace: {stats['max_daily_pace']} hrs/day\n"
                        f"• Average Pace: {stats['avg_daily_pace']} hrs/day"
                    )
                    messagebox.showinfo("Adaptive Replan", msg)

            self.set_status_message(
                f"Rescheduled {stats['total_rescheduled_count']} task(s) • Peak pace: {stats['max_daily_pace']} h/d"
            )

        except Exception as e:
            messagebox.showerror("Adaptive Reschedule Error", str(e))

    def _auto_check_missed_past_tasks(self) -> None:
        """Detects any past uncompleted calendar tasks and automatically adapts remaining schedule."""
        if self.df_schedule.empty:
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
        past_uncompleted = (date_series < today_d) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))

        if past_uncompleted.any():
            num_past = int(past_uncompleted.sum())
            self._run_reschedule_engine(
                show_toast=True,
                source_reason=f"Detected {num_past} past uncompleted session(s) without 'Done Studying'",
            )

    # -----------------------------------------------------------------------
    # Today's Study Check-in Handlers
    # -----------------------------------------------------------------------
    def _mark_all_today_done(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = self.df_schedule["Date"] == today_str
        if not mask.any():
            messagebox.showinfo("No Tasks Today", f"No study sessions are scheduled for today ({today_str}).")
            return

        self.df_schedule.loc[mask, "Status"] = "Completed"
        self._refresh_all_views()
        self.set_status_message(f"🎉 Great job! Marked all {mask.sum()} milestone(s) for today as Done Studying!")
        messagebox.showinfo("All Done! 🎉", f"Awesome work! You have marked all study tasks for today ({today_str}) as Done Studying.")

    def _mark_all_today_missed(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        mask = (self.df_schedule["Date"] == today_str) & (self.df_schedule["Status"] != "Completed")
        if not mask.any():
            messagebox.showinfo("No Pending Tasks", "No pending tasks to mark as missed today.")
            return

        self.df_schedule.loc[mask, "Status"] = "Missed"
        self._run_reschedule_engine(show_toast=True, source_reason=f"Missed Today's Sessions ({today_str})")

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
            self._run_reschedule_engine(show_toast=True, source_reason=f"Missed {course_name} on {today_str}")
        else:
            if next_status == "Pending":
                self.df_schedule.loc[mask, "Rescheduled_From"] = ""
            self._refresh_all_views()
            self.set_status_message(f"{course_name} status: {next_status}")

    # -----------------------------------------------------------------------
    # Table Selection & Interaction
    # -----------------------------------------------------------------------
    def _set_selected_status(self, new_status: str) -> None:
        selected_items = self.tree_schedule.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one row in the schedule table.")
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
            self.set_status_message(f"Updated {len(selected_items)} study session(s) to {new_status}")

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

                # Reconstruct baseline hours
                self.course_baseline_hours = {}
                for c_name in df["Course"].unique():
                    self.course_baseline_hours[c_name] = float(df[df["Course"] == c_name]["Target Hours"].sum())

                self._refresh_course_list_ui()
                self._refresh_all_views()
                self._auto_check_missed_past_tasks()
                self.set_status_message(f"Loaded plan with {len(courses)} course(s) from {os.path.basename(path)}")
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
                self.set_status_message(f"Saved plan to {path}")
                messagebox.showinfo("Saved", f"Plan and course outlines saved successfully to:\n{path}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

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
        """Dynamically populates today's study card with all courses scheduled today."""
        for child in self.today_tasks_container.winfo_children():
            child.destroy()

        if self.df_schedule.empty:
            tk.Label(
                self.today_tasks_container,
                text="No active plan loaded.",
                font=("Helvetica Neue", 9),
                fg=TEXT_MUTED,
                bg=BG_CARD,
            ).pack(anchor="w")
            self.card_checkin.config(highlightbackground=BORDER_COLOR)
            return

        today_str = date.today().strftime("%Y-%m-%d")
        today_rows = self.df_schedule[self.df_schedule["Date"] == today_str]

        if today_rows.empty:
            self.card_checkin.config(highlightbackground=BORDER_COLOR)
            date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
            today_d = date.today()
            if today_d < date_series.iloc[0]:
                msg = f"Upcoming plan starts on {date_series.iloc[0]}"
            else:
                msg = "Semester exams concluded"
            tk.Label(
                self.today_tasks_container,
                text=msg,
                font=("Helvetica Neue", 9, "bold"),
                fg=TEXT_MUTED,
                bg=BG_CARD,
            ).pack(anchor="w")
            return

        # Check if all completed or any missed
        all_completed = bool((today_rows["Status"] == "Completed").all())
        has_missed = bool((today_rows["Status"] == "Missed").any())
        has_resched = bool((today_rows["Status"] == "Rescheduled").any())

        if all_completed:
            self.card_checkin.config(highlightbackground=COLOR_SUCCESS)
        elif has_missed:
            self.card_checkin.config(highlightbackground=COLOR_DANGER)
        elif has_resched:
            self.card_checkin.config(highlightbackground=COLOR_RESCHEDULED)
        else:
            self.card_checkin.config(highlightbackground=COLOR_PRIMARY)

        # Render each course row for today
        for _, row in today_rows.iterrows():
            c_name = row["Course"]
            topic = row["Topic"]
            topic_day = row["Topic Day"]
            hrs = row["Target Hours"]
            status = row["Status"]
            resched_from = str(row.get("Rescheduled_From", "") or "")

            item_frame = tk.Frame(self.today_tasks_container, bg="#f8fafc", highlightthickness=1, highlightbackground=BORDER_COLOR, padx=8, pady=5)
            item_frame.pack(fill="x", pady=2)

            left_info = tk.Frame(item_frame, bg="#f8fafc")
            left_info.pack(side="left", fill="x", expand=True)

            # Course tag label
            lbl_course = tk.Label(
                left_info,
                text=f"{c_name}",
                font=("Helvetica Neue", 9, "bold"),
                fg=COLOR_PRIMARY,
                bg="#f8fafc",
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
                bg="#f8fafc",
                anchor="w",
            )
            lbl_sub.pack(fill="x")

            # Quick status button
            if status == "Completed":
                btn_txt = "✅ Done"
                btn_bg = COLOR_SUCCESS_BG
                btn_fg = COLOR_SUCCESS_TEXT
            elif status == "Missed":
                btn_txt = "❌ Missed"
                btn_bg = COLOR_DANGER_BG
                btn_fg = COLOR_DANGER_TEXT
            elif status == "Rescheduled":
                btn_txt = "🔄 Resched"
                btn_bg = COLOR_RESCHEDULED_BG
                btn_fg = COLOR_RESCHEDULED_TEXT
            else:
                btn_txt = "⏳ Pending"
                btn_bg = "#ffffff"
                btn_fg = TEXT_MAIN

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
            self.card_courses.update_card("0 Courses", "Configured in semester")
            self.card_nearest_exam.update_card("--", "Countdown")
            self.card_total_hours.update_card("--", "Total semester work")
            self.card_target.update_card("--", "Daily pace")
            self.card_progress.update_card("0%", "0 completed")
            self.card_feasibility.update_card("Ready", "Cap: 5.0h/day", COLOR_SUCCESS)
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date

        # 1. Courses count
        unique_courses = self.df_schedule["Course"].unique().tolist()
        self.card_courses.update_card(
            f"{len(unique_courses)} Courses",
            ", ".join(unique_courses[:3]) + ("..." if len(unique_courses) > 3 else ""),
        )

        # 2. Nearest Exam
        exam_dates = []
        for c in self.courses:
            exam_dates.append((c.exam_date, c.name))
        if not exam_dates:
            # derive from df
            for c_name in unique_courses:
                last_d = date_series[self.df_schedule["Course"] == c_name].iloc[-1]
                exam_dates.append((last_d, c_name))

        future_exams = [(d, n) for d, n in exam_dates if d >= today_d]
        if future_exams:
            min_d, min_name = min(future_exams, key=lambda x: x[0])
            days_left = (min_d - today_d).days
            self.card_nearest_exam.update_card(
                f"{days_left} Days Left",
                f"Next: {min_name[:14]} ({min_d.strftime('%b %d')})",
            )
        else:
            self.card_nearest_exam.update_card("Exams Done", "All dates reached")

        # 3. Total study hours
        total_hours = float(self.df_schedule["Target Hours"].sum())
        total_ch = sum(c.credit_hours for c in self.courses) if self.courses else 0.0
        self.card_total_hours.update_card(
            f"{total_hours:.1f} hrs",
            f"{total_ch:.1f} Total Credit Hours",
        )

        # 4. Today's target pace
        today_str = today_d.strftime("%Y-%m-%d")
        today_rows = self.df_schedule[self.df_schedule["Date"] == today_str]
        if not today_rows.empty:
            today_target = float(today_rows["Target Hours"].sum())
        else:
            # next available day
            future_slots = self.df_schedule[(date_series >= today_d) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))]
            if not future_slots.empty:
                next_date = future_slots["Date"].iloc[0]
                today_target = float(future_slots[future_slots["Date"] == next_date]["Target Hours"].sum())
            else:
                today_target = 0.0

        self.card_target.update_card(
            f"{today_target:.2f} h/d",
            "Across scheduled courses",
        )

        # 5. Study Progress
        total_milestones = len(self.df_schedule)
        completed_m = int((self.df_schedule["Status"] == "Completed").sum())
        missed_m = int((self.df_schedule["Status"] == "Missed").sum())
        resched_m = int((self.df_schedule["Status"] == "Rescheduled").sum())
        pct = round((completed_m / total_milestones) * 100, 1) if total_milestones else 0.0
        self.card_progress.update_card(
            f"{pct}%",
            f"{completed_m} Done • {missed_m} Missed • {resched_m} Resched",
        )

        # 6. Feasibility check
        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 5.0

        # Check future daily pace
        future_mask = date_series >= today_d
        future_df = self.df_schedule[future_mask & self.df_schedule["Status"].isin(["Pending", "Rescheduled"])]
        daily_sums = future_df.groupby("Date")["Target Hours"].sum()
        max_pace = float(daily_sums.max()) if not daily_sums.empty else 0.0
        is_over = max_pace > cap

        if is_over:
            self.card_feasibility.update_card(
                "⚠️ Over Cap",
                f"Peak {max_pace:.2f} > {cap:.1f}h/day limit",
                val_color=COLOR_DANGER,
            )
        else:
            self.card_feasibility.update_card(
                "✅ Feasible",
                f"Peak: {max_pace:.2f} ≤ {cap:.1f}h/day",
                val_color=COLOR_SUCCESS,
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

            # Tag determination
            if status == "Completed":
                tag = "completed"
                status_icon = "✅ Done"
            elif status == "Missed":
                tag = "missed"
                status_icon = "❌ Missed"
            elif is_resched:
                tag = "rescheduled"
                status_icon = "🔄 Rescheduled"
            elif row_date == today_str:
                tag = "today"
                status_icon = "📌 Today"
            else:
                tag = "pending"
                status_icon = "⏳ Pending"

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

        self.lbl_table_count.config(text=f"Showing {displayed} of {len(self.df_schedule)} milestones")

    def _refresh_courses_tab_view(self) -> None:
        for item in self.tree_course_summary.get_children():
            self.tree_course_summary.delete(item)

        if self.df_schedule.empty:
            return

        today_d = date.today()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date

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

            self.tree_course_summary.insert(
                "",
                "end",
                values=(
                    c.name,
                    f"{c.credit_hours:.1f}",
                    c.exam_date.strftime("%Y-%m-%d"),
                    f"{days_left}d",
                    f"{total_hrs:.1f}h",
                    f"{daily_pace:.2f} h/d",
                    f"{completed_tasks}/{total_tasks}",
                    f"{pct}%",
                ),
            )

        self._refresh_topic_periods_table()

    def _on_course_summary_select(self, event) -> None:
        selected = self.tree_course_summary.selection()
        if not selected:
            return
        c_name = self.tree_course_summary.item(selected[0], "values")[0]
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

        # Group by Date
        grouped = self.df_schedule.groupby("Date", sort=False)
        for date_str, group in grouped:
            day_num = group["Day"].iloc[0]
            weekday = group["Weekday"].iloc[0]
            active_courses = ", ".join(group["Course"].unique())
            total_target = float(group["Target Hours"].sum())
            completed_hours = float(group[group["Status"] == "Completed"]["Target Hours"].sum())

            # Status summary
            c_cnt = int((group["Status"] == "Completed").sum())
            m_cnt = int((group["Status"] == "Missed").sum())
            r_cnt = int((group["Status"] == "Rescheduled").sum())
            p_cnt = int((group["Status"] == "Pending").sum())
            summary_str = f"{c_cnt} Done • {p_cnt + r_cnt} Left"
            if m_cnt:
                summary_str += f" ({m_cnt} Missed)"

            is_over = total_target > cap and (p_cnt + r_cnt) > 0
            if is_over:
                tag = "overcap"
                flag = f"⚠️ Over Cap (+{total_target - cap:.2f}h)"
            elif date_str == today_str:
                tag = "today"
                flag = "📌 Today"
            else:
                tag = "feasible"
                flag = "✅ Realistic"

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
                    flag,
                ),
                tags=(tag,),
            )

    def _refresh_insights_view(self) -> None:
        if self.df_schedule.empty:
            self.txt_insights.delete("1.0", tk.END)
            self.txt_insights.insert("1.0", "Generate or load a study plan to see analytics and diagnostic reports.")
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
            self.banner_feasibility.config(bg=COLOR_DANGER_BG, highlightbackground="#fecaca")
            self.lbl_feasibility_text.config(
                text=f"⚠️ CAPACITY ALERT: Daily study pace peaks at {max_daily_pace:.2f} hrs/day, exceeding your {cap:.1f} hrs/day limit on {len(over_cap_days)} day(s)!",
                fg=COLOR_DANGER_TEXT,
                bg=COLOR_DANGER_BG,
            )
        else:
            self.banner_feasibility.config(bg=COLOR_SUCCESS_BG, highlightbackground="#bbf7d0")
            self.lbl_feasibility_text.config(
                text=f"✅ FEASIBILITY STATUS: Multi-course plan is sustainable (peak {max_daily_pace:.2f} hrs/day within {cap:.1f} hrs/day limit).",
                fg=COLOR_SUCCESS_TEXT,
                bg=COLOR_SUCCESS_BG,
            )

        report = []
        report.append("=" * 74)
        report.append("🎓 REPLAN v1 — MULTI-COURSE SEMESTER ANALYTICS & FEASIBILITY REPORT")
        report.append("=" * 74)
        report.append(f"• Total Enrolled Courses:     {len(self.courses)} courses")
        report.append(f"• Combined Semester Workload: {float(self.df_schedule['Target Hours'].sum()):.1f} study hours")
        report.append(f"• Peak Combined Pace:         {max_daily_pace:.2f} hrs/day (Your Capacity Limit: {cap:.1f} hrs/day)")
        report.append(f"• Average Future Daily Pace:  {avg_daily_pace:.2f} hrs/day")
        report.append("")

        report.append("-" * 74)
        report.append("📚 COURSE-BY-COURSE BREAKDOWN & EXAM COUNTDOWN:")
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

            report.append(f"▶ {c.name.upper()} ({c.credit_hours} CH)")
            report.append(f"   • Exam Date:         {c.exam_date.strftime('%Y-%m-%d')} ({days_left} calendar days left)")
            report.append(f"   • Study Pace:        {pace:.2f} hrs/day across {rem_days} remaining sessions")
            report.append(f"   • Workload Progress: {comp_h:.1f}/{total_h:.1f} hrs ({comp_days} sessions completed, {miss_h:.1f} hrs missed)")
            report.append(f"   • Topics Outlined:   {', '.join(c.topics[:3])}{'...' if len(c.topics) > 3 else ''}")
            report.append("")

        report.append("-" * 74)
        report.append("🛡️ CAPACITY & FEASIBILITY ASSESSMENT:")
        report.append("-" * 74)
        if is_over:
            report.append(f"🚨 Workload overload detected on {len(over_cap_days)} date(s):")
            for d_str, pace_val in list(over_cap_days.items())[:5]:
                report.append(f"   • {d_str}: {pace_val:.2f} hrs planned (+{pace_val - cap:.2f} hrs over limit)")
            report.append("\n  Suggested Remediation Steps:")
            report.append(f"  1. Increase daily capacity cap to {max_daily_pace:.2f} hrs/day.")
            report.append("  2. Extend upcoming course exam dates if permitted by academic calendar.")
            report.append("  3. Prune or prioritize high-yield modules in heavy course outlines.")
        else:
            buffer = round(cap - max_daily_pace, 2)
            report.append(f"✨ Excellent pace! You have a safety buffer of at least {buffer} hrs/day below your")
            report.append(f"   maximum capacity of {cap:.1f} hrs/day. Complete your daily milestones to stay ahead!")

        report.append("")
        report.append("-" * 74)
        report.append("🔄 ADAPTIVE REPLAN LOG (Session Adjustments):")
        report.append("-" * 74)
        if not self.replan_history:
            report.append("No replanning events recorded yet in this session.")
        else:
            for idx, h in enumerate(reversed(self.replan_history), 1):
                report.append(
                    f"[{h['timestamp']}] Replan #{len(self.replan_history) - idx + 1}: "
                    f"Peak Pace {h['max_daily_pace']} h/d | Rescheduled {h.get('total_rescheduled_count', 0)} task(s)."
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
            "RePlan v1 — Adaptive Multi-Course Semester Planner 🎓\n\n"
            "Calculates realistic day-by-day study milestones across multiple courses,\n"
            "each with its own outline, credit hours, and distinct exam dates.\n\n"
            "Key v1 Enhancements:\n"
            "• Multi-Course Scheduling: Enter any number of courses, outlines & exam dates.\n"
            "• Daily Multi-Task Allocation: Daily milestones allocated across concurrent courses.\n"
            "• Individual Course Rescheduling: Missed sessions are adaptively redistributed\n"
            "  strictly before each course's own exam date and highlighted in PURPLE!\n"
            "• Today's Check-in Hero Box: Check off tasks for today across courses with 1 click!\n"
            "• Daily Workload Feasibility: Identifies overloaded days exceeding daily study cap.\n"
            "• Portable Persistence: Saves and restores full multi-course plans and outlines.\n\n"
            "Based on Replan Adaptive Planner."
        )
        messagebox.showinfo("About RePlan v1", msg)


# ---------------------------------------------------------------------------
# CLI / Main Entrypoint
# ---------------------------------------------------------------------------
def main():
    app = ReplanV1App()
    app.mainloop()


if __name__ == "__main__":
    main()
