"""
RePlan — Adaptive Semester Planner 🎓
GUI Desktop Application

Transforms semester dates, course outlines, credit hours, and personal capacity
into manageable daily study milestones. When a student misses a session
(or forgets to click "done studying"), RePlan adaptively reschedules the missed task
into the period between today and the exam date and highlights the rescheduled task.

Based on Replan.ipynb.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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

DEFAULT_CSV_PATH = "my_semester_plan.csv"
STUDY_HOURS_PER_CH = 45.0  # 1 CH = 45 study hours


# ---------------------------------------------------------------------------
# Core Engine & Domain Logic
# ---------------------------------------------------------------------------
@dataclass
class TopicPeriod:
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


class ReplanEngine:
    """Core scheduling and adaptive replanning engine."""

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
            raise ValueError(f"Unable to parse '{clean}' as a date. Use YYYY-MM-DD format.")

    @staticmethod
    def generate_schedule(
        exam_date: date,
        credit_hours: float,
        topics: List[str],
        start_date: Optional[date] = None,
        hours_per_ch: float = STUDY_HOURS_PER_CH,
    ) -> Tuple[pd.DataFrame, List[TopicPeriod], Dict[str, Any]]:
        """
        Generates day-by-day study schedule matching Replan.ipynb Steps 1-5.
        Distributes total credit hours (CH * 45) evenly across remaining days
        and splits days proportionally across topics.
        """
        curr_date = start_date or datetime.today().date()
        rem_days = (exam_date - curr_date).days

        if rem_days <= 0:
            raise ValueError(
                f"Exam date ({exam_date}) must be strictly after the start date ({curr_date}). "
                f"Remaining days: {rem_days}."
            )

        if credit_hours <= 0:
            raise ValueError("Credit hours must be greater than zero.")

        clean_topics = [t.strip() for t in topics if t.strip()]
        if not clean_topics:
            raise ValueError("At least one topic is required to build a schedule.")

        num_topics = len(clean_topics)
        total_study_hours = round(credit_hours * hours_per_ch, 2)
        daily_hours = round(total_study_hours / rem_days, 2)

        # Distribute available days evenly across topics (Cell 19 logic)
        base_days = rem_days // num_topics
        extra_days = rem_days % num_topics

        topic_durations: List[int] = []
        for i in range(num_topics):
            topic_durations.append(base_days + 1 if i < extra_days else base_days)

        schedule_rows = []
        topic_periods: List[TopicPeriod] = []
        day_counter = 0

        for idx, topic in enumerate(clean_topics):
            duration = topic_durations[idx]
            topic_start = curr_date + timedelta(days=day_counter)
            topic_end = curr_date + timedelta(days=day_counter + max(0, duration - 1))
            topic_hours = round(duration * daily_hours, 1)

            topic_periods.append(
                TopicPeriod(
                    topic_num=idx + 1,
                    topic=topic,
                    duration_days=duration,
                    total_hours=topic_hours,
                    start_date=topic_start.strftime("%Y-%m-%d"),
                    end_date=topic_end.strftime("%Y-%m-%d"),
                    pending_days=duration,
                )
            )

            for d in range(duration):
                day_date = curr_date + timedelta(days=day_counter)
                schedule_rows.append(
                    {
                        "Day": day_counter + 1,
                        "Date": day_date.strftime("%Y-%m-%d"),
                        "Weekday": day_date.strftime("%A"),
                        "Target Hours": daily_hours,
                        "Topic Day": f"{d + 1}/{duration}",
                        "Topic": topic,
                        "Status": "Pending",
                        "Rescheduled_From": "",
                    }
                )
                day_counter += 1

        df_schedule = pd.DataFrame(schedule_rows)
        meta = {
            "credit_hours": credit_hours,
            "total_study_hours": total_study_hours,
            "daily_hours": daily_hours,
            "days_left": rem_days,
            "num_topics": num_topics,
            "start_date": curr_date.strftime("%Y-%m-%d"),
            "exam_date": exam_date.strftime("%Y-%m-%d"),
        }
        return df_schedule, topic_periods, meta

    @staticmethod
    def compute_topic_periods_from_df(df: pd.DataFrame) -> List[TopicPeriod]:
        """Derives topic period metrics from any schedule DataFrame."""
        if df.empty or "Topic" not in df.columns:
            return []

        periods = []
        unique_topics: List[str] = []
        for t in df["Topic"]:
            clean_t = str(t).split(" • 🔄")[0].split(" (🔄")[0].strip()
            if not unique_topics or unique_topics[-1] != clean_t:
                unique_topics.append(clean_t)

        topic_counter = 1
        for topic in unique_topics:
            mask = df["Topic"].apply(lambda x: str(x).split(" • 🔄")[0].split(" (🔄")[0].strip() == topic)
            sub = df[mask]
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
        max_daily_cap: float = 4.0,
        baseline_total_hours: Optional[float] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Adaptive Rescheduling Engine:
        1. Automatically identifies any past days where user did not click 'Done Studying'
           and marks them as Missed.
        2. Redistributes all uncompleted/missed curriculum tasks across remaining available
           study days in the period between today and the exam date.
        3. Flags and highlights rescheduled tasks (Status: 'Rescheduled').
        4. Dynamically recalculates daily target hours to prevent falling behind.
        """
        if df.empty:
            raise ValueError("No schedule available to replan.")

        df = df.copy()
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""

        if today_date is None:
            today_date = datetime.today().date()

        date_series = pd.to_datetime(df["Date"]).dt.date

        # 1. Past days where user did not click 'Done Studying' are marked Missed
        past_uncompleted = (date_series < today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
        if past_uncompleted.any():
            df.loc[past_uncompleted, "Status"] = "Missed"

        # 2. Extract full curriculum sequence in original order
        curriculum = []
        for _, r in df.iterrows():
            clean_topic = str(r["Topic"]).split(" • 🔄")[0].split(" (🔄")[0].strip()
            clean_topic_day = str(r["Topic Day"]).strip()
            curriculum.append({"Topic": clean_topic, "Topic Day": clean_topic_day})

        # 3. Count completed tasks
        num_completed = int((df["Status"] == "Completed").sum())

        # 4. Available future days from today onwards
        avail_mask = (date_series >= today_date) & (df["Status"].isin(["Pending", "Rescheduled"]))
        avail_indices = df[avail_mask].index.tolist()
        num_available_days = len(avail_indices)

        if num_available_days == 0:
            raise ValueError("⚠️ No available study days remaining before the exam date!")

        prev_daily_target = float(df.loc[avail_indices[0], "Target Hours"])

        # 5. Missed days tracking
        missed_indices = df[df["Status"] == "Missed"].index.tolist()
        num_missed = len(missed_indices)

        rescheduled_days_count = 0
        first_rescheduled_date = None
        first_rescheduled_topic = None

        if num_missed > 0 and num_available_days > 0:
            for i, slot_idx in enumerate(avail_indices):
                curr_task_idx = num_completed + i
                if curr_task_idx < len(curriculum):
                    task = curriculum[curr_task_idx]
                    df.loc[slot_idx, "Topic"] = task["Topic"]
                    df.loc[slot_idx, "Topic Day"] = task["Topic Day"]

                # Slots receiving tasks delayed by missed sessions are highlighted
                if i < num_missed:
                    missed_idx = missed_indices[min(i, num_missed - 1)]
                    from_day = df.loc[missed_idx, "Day"]
                    from_date = df.loc[missed_idx, "Date"]
                    df.loc[slot_idx, "Status"] = "Rescheduled"
                    df.loc[slot_idx, "Rescheduled_From"] = f"Day {from_day} ({from_date})"
                    rescheduled_days_count += 1
                    if first_rescheduled_date is None:
                        first_rescheduled_date = str(df.loc[slot_idx, "Date"])
                        first_rescheduled_topic = f"{df.loc[slot_idx, 'Topic']} ({df.loc[slot_idx, 'Topic Day']})"
                else:
                    if df.loc[slot_idx, "Status"] == "Rescheduled":
                        df.loc[slot_idx, "Status"] = "Pending"
                        df.loc[slot_idx, "Rescheduled_From"] = ""
        else:
            for slot_idx in avail_indices:
                if df.loc[slot_idx, "Status"] == "Rescheduled":
                    df.loc[slot_idx, "Status"] = "Pending"
                    df.loc[slot_idx, "Rescheduled_From"] = ""

        # 6. Recalculate adaptive daily target hours
        completed_hours = float(df.loc[df["Status"] == "Completed", "Target Hours"].sum())
        if baseline_total_hours is not None and baseline_total_hours > 0:
            uncompleted_hours = max(0.0, baseline_total_hours - completed_hours)
        else:
            pending_or_missed = df[df["Status"].isin(["Pending", "Missed", "Rescheduled"])]
            uncompleted_hours = float(pending_or_missed["Target Hours"].sum())

        new_daily_hours = round(uncompleted_hours / num_available_days, 2)
        is_over_cap = new_daily_hours > max_daily_cap

        df.loc[avail_indices, "Target Hours"] = new_daily_hours

        stats = {
            "num_available_days": num_available_days,
            "uncompleted_hours": round(uncompleted_hours, 2),
            "completed_hours": round(completed_hours, 2),
            "prev_daily_target": round(prev_daily_target, 2),
            "new_daily_hours": new_daily_hours,
            "max_daily_cap": max_daily_cap,
            "is_over_cap": is_over_cap,
            "rate_change": round(new_daily_hours - prev_daily_target, 2),
            "rescheduled_days_count": rescheduled_days_count,
            "first_rescheduled_date": first_rescheduled_date,
            "first_rescheduled_topic": first_rescheduled_topic,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return df, stats

    @staticmethod
    def reschedule(
        df: pd.DataFrame,
        max_daily_cap: float = 4.0,
        baseline_total_hours: Optional[float] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Backwards-compatible wrapper calling reschedule_missed_tasks."""
        return ReplanEngine.reschedule_missed_tasks(
            df=df,
            today_date=datetime.today().date(),
            max_daily_cap=max_daily_cap,
            baseline_total_hours=baseline_total_hours,
        )

    @staticmethod
    def load_csv(filepath: str) -> pd.DataFrame:
        """Loads and validates a semester plan CSV."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        df = pd.read_csv(filepath)
        required_cols = ["Day", "Date", "Weekday", "Target Hours", "Topic Day", "Topic", "Status"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"CSV file is missing expected columns: {missing}")

        df["Day"] = pd.to_numeric(df["Day"], errors="coerce").fillna(0).astype(int)
        df["Target Hours"] = pd.to_numeric(df["Target Hours"], errors="coerce").fillna(0.0).round(2)
        df["Status"] = df["Status"].fillna("Pending").astype(str)
        if "Rescheduled_From" not in df.columns:
            df["Rescheduled_From"] = ""
        else:
            df["Rescheduled_From"] = df["Rescheduled_From"].fillna("").astype(str)
        return df

    @staticmethod
    def save_csv(df: pd.DataFrame, filepath: str) -> None:
        """Saves schedule DataFrame to CSV."""
        df.to_csv(filepath, index=False)


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
        super().__init__(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=14, pady=10, **kwargs)
        self.accent_color = accent_color

        top_row = tk.Frame(self, bg=BG_CARD)
        top_row.pack(fill="x", expand=True)

        self.lbl_icon = tk.Label(top_row, text=icon, font=("Helvetica Neue", 13), fg=accent_color, bg=BG_CARD)
        self.lbl_icon.pack(side="left")

        self.lbl_title = tk.Label(
            top_row,
            text=f" {title.upper()}",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        self.lbl_title.pack(side="left")

        self.lbl_val = tk.Label(
            self,
            text=initial_val,
            font=("Helvetica Neue", 17, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
            anchor="w",
        )
        self.lbl_val.pack(fill="x", pady=(4, 2))

        self.lbl_sub = tk.Label(
            self,
            text=subtitle,
            font=("Helvetica Neue", 9),
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
# Main GUI Window
# ---------------------------------------------------------------------------
class ReplanApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RePlan — Adaptive Semester Planner 🎓")
        self.geometry("1260x860")
        self.minsize(1040, 700)
        self.configure(bg=BG_LIGHT)

        # State
        self.current_file_path: Optional[str] = None
        self.df_schedule: pd.DataFrame = pd.DataFrame()
        self.topic_periods: List[TopicPeriod] = []
        self.baseline_total_hours: Optional[float] = None
        self.replan_history: List[Dict[str, Any]] = []

        self._init_styles()
        self._build_header()
        self._build_metric_ribbon()
        self._build_main_layout()
        self._build_status_bar()

        # Load initial data and run auto-detection
        self._auto_load_initial_data()

    def _init_styles(self) -> None:
        """Configures ttk styles and global Tk defaults for dark text visibility."""
        # Ensure all Tk entry and text inputs default to dark text on white bg across all OS themes
        self.option_add("*Entry.foreground", TEXT_MAIN)
        self.option_add("*Entry.background", "#ffffff")
        self.option_add("*Entry.insertBackground", TEXT_MAIN)
        self.option_add("*Entry.selectBackground", COLOR_PRIMARY)
        self.option_add("*Entry.selectForeground", "#ffffff")

        self.option_add("*Text.foreground", TEXT_MAIN)
        self.option_add("*Text.background", "#ffffff")
        self.option_add("*Text.insertBackground", TEXT_MAIN)
        self.option_add("*Text.selectBackground", COLOR_PRIMARY)
        self.option_add("*Text.selectForeground", "#ffffff")

        self.option_add("*TCombobox*Listbox.foreground", TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.background", "#ffffff")
        self.option_add("*TCombobox*Listbox.selectBackground", COLOR_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

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
            padding=[16, 8],
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
            rowheight=28,
            font=("Helvetica Neue", 10),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Helvetica Neue", 10, "bold"),
            background="#f1f5f9",
            foreground=TEXT_MAIN,
            relief="flat",
            padding=[6, 6],
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
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            foreground=[("readonly", TEXT_MAIN)],
            selectbackground=[("readonly", COLOR_PRIMARY)],
            selectforeground=[("readonly", "#ffffff")],
        )

        # Progressbar
        self.style.configure(
            "TProgressbar",
            troughcolor="#e2e8f0",
            background=COLOR_SUCCESS,
            thickness=6,
        )

    # -----------------------------------------------------------------------
    # Top Header
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        header_frame = tk.Frame(self, bg=BG_DARK, height=64, padx=20, pady=10)
        header_frame.pack(side="top", fill="x")

        brand_frame = tk.Frame(header_frame, bg=BG_DARK)
        brand_frame.pack(side="left", fill="y")

        lbl_logo = tk.Label(
            brand_frame,
            text="🎓 RePlan",
            font=("Helvetica Neue", 18, "bold"),
            fg="#ffffff",
            bg=BG_DARK,
        )
        lbl_logo.pack(side="left")

        lbl_tagline = tk.Label(
            brand_frame,
            text=" | Adaptive Semester Planner • Missed a day? RePlan adapts.",
            font=("Helvetica Neue", 10),
            fg="#94a3b8",
            bg=BG_DARK,
        )
        lbl_tagline.pack(side="left", padx=(6, 0))

        btn_bar = tk.Frame(header_frame, bg=BG_DARK)
        btn_bar.pack(side="right")

        self._create_header_btn(btn_bar, "📂 Open Plan", self._on_load_csv_dialog)
        self._create_header_btn(btn_bar, "💾 Save Plan", self._on_save_csv_dialog)
        self._create_header_btn(btn_bar, "✨ Load Sample", self._load_notebook_sample)
        self._create_header_btn(btn_bar, "ℹ️ Help", self._show_about_dialog)

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
            padx=12,
            pady=6,
            cursor="pointinghand",
        )
        btn.pack(side="left", padx=4)
        return btn

    # -----------------------------------------------------------------------
    # Metric Ribbon
    # -----------------------------------------------------------------------
    def _build_metric_ribbon(self) -> None:
        ribbon_frame = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=12)
        ribbon_frame.pack(side="top", fill="x")

        self.card_days = MetricCard(
            ribbon_frame,
            title="Days Left",
            initial_val="--",
            subtitle="To exam deadline",
            accent_color=COLOR_INFO,
            icon="📅",
        )
        self.card_days.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.card_total_hours = MetricCard(
            ribbon_frame,
            title="Total Study Hours",
            initial_val="--",
            subtitle="Required semester work",
            accent_color="#8b5cf6",
            icon="⏱️",
        )
        self.card_total_hours.pack(side="left", fill="x", expand=True, padx=4)

        self.card_target = MetricCard(
            ribbon_frame,
            title="Daily Target Pace",
            initial_val="--",
            subtitle="Adaptive hours / day",
            accent_color=COLOR_PRIMARY,
            icon="🎯",
        )
        self.card_target.pack(side="left", fill="x", expand=True, padx=4)

        self.card_progress = MetricCard(
            ribbon_frame,
            title="Study Progress",
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
            subtitle="Limit: 4.0h/day",
            accent_color=COLOR_SUCCESS,
            icon="🛡️",
        )
        self.card_feasibility.pack(side="left", fill="x", expand=True, padx=(8, 0))

    # -----------------------------------------------------------------------
    # Main Paned / Side-by-Side Layout
    # -----------------------------------------------------------------------
    def _build_main_layout(self) -> None:
        content_frame = tk.Frame(self, bg=BG_LIGHT, padx=20, pady=6)
        content_frame.pack(side="top", fill="both", expand=True)

        # Left Column: Controls (~375px)
        left_col = tk.Frame(content_frame, bg=BG_LIGHT, width=375)
        left_col.pack(side="left", fill="y", padx=(0, 14))
        left_col.pack_propagate(False)

        # Right Column: Tabbed Views
        right_col = tk.Frame(content_frame, bg=BG_LIGHT)
        right_col.pack(side="left", fill="both", expand=True)

        self._build_sidebar_controls(left_col)
        self._build_right_notebook(right_col)

    # -----------------------------------------------------------------------
    # Left Sidebar Controls (Check-in, Setup & Adaptive Replan)
    # -----------------------------------------------------------------------
    def _build_sidebar_controls(self, parent: tk.Frame) -> None:
        # Card 0: Prominent Daily Study Check-in Hero Box
        self.card_checkin = tk.Frame(
            parent,
            bg=BG_CARD,
            highlightthickness=2,
            highlightbackground=COLOR_PRIMARY,
            padx=14,
            pady=12,
        )
        self.card_checkin.pack(side="top", fill="x", pady=(0, 12))

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

        today_str = datetime.today().strftime("%Y-%m-%d")
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

        # Dynamic today's milestone summary
        self.lbl_today_topic = tk.Label(
            self.card_checkin,
            text="Topic: Loading plan...",
            font=("Helvetica Neue", 10, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
            anchor="w",
            wraplength=340,
            justify="left",
        )
        self.lbl_today_topic.pack(fill="x", pady=(6, 2))

        self.lbl_today_target = tk.Label(
            self.card_checkin,
            text="Target: -- hrs • Status: Pending",
            font=("Helvetica Neue", 9),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            anchor="w",
        )
        self.lbl_today_target.pack(fill="x", pady=(0, 10))

        # Big, Clear Study Status Buttons
        btn_done_today = tk.Button(
            self.card_checkin,
            text="✅ I Have Done Studying Today!",
            command=lambda: self._mark_today_status("Completed"),
            font=("Helvetica Neue", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="#ffffff",
            activebackground=COLOR_SUCCESS_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            pady=9,
            cursor="pointinghand",
        )
        btn_done_today.pack(fill="x", pady=(0, 6))

        checkin_row2 = tk.Frame(self.card_checkin, bg=BG_CARD)
        checkin_row2.pack(fill="x")

        btn_miss_today = tk.Button(
            checkin_row2,
            text="❌ I Missed Today's Session",
            command=lambda: self._mark_today_status("Missed"),
            font=("Helvetica Neue", 9, "bold"),
            bg=COLOR_DANGER_BG,
            fg=COLOR_DANGER_TEXT,
            activebackground="#fee2e2",
            activeforeground=COLOR_DANGER_TEXT,
            relief="flat",
            bd=0,
            pady=6,
            cursor="pointinghand",
        )
        btn_miss_today.pack(side="left", fill="x", expand=True, padx=(0, 3))

        btn_reset_today = tk.Button(
            checkin_row2,
            text="⏳ Reset to Pending",
            command=lambda: self._mark_today_status("Pending"),
            font=("Helvetica Neue", 9),
            bg="#f1f5f9",
            fg=TEXT_MAIN,
            activebackground="#e2e8f0",
            activeforeground=TEXT_MAIN,
            relief="flat",
            bd=0,
            pady=6,
            cursor="pointinghand",
        )
        btn_reset_today.pack(side="left", fill="x", expand=True, padx=(3, 0))

        # Card 1: Course & Semester Setup
        card_setup = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=14, pady=12)
        card_setup.pack(side="top", fill="x", pady=(0, 12))

        lbl_sec1 = tk.Label(
            card_setup,
            text="⚙️ SEMESTER SETUP",
            font=("Helvetica Neue", 10, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        lbl_sec1.pack(anchor="w", pady=(0, 8))

        # Course Name
        tk.Label(card_setup, text="Course Name", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w")
        self.entry_course = tk.Entry(
            card_setup,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
        )
        self.entry_course.insert(0, "Programming & Problem Solving")
        self.entry_course.pack(fill="x", pady=(2, 8))

        # Exam Date
        tk.Label(card_setup, text="Exam Date (YYYY-MM-DD)", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w")
        date_row = tk.Frame(card_setup, bg=BG_CARD)
        date_row.pack(fill="x", pady=(2, 4))

        self.entry_exam_date = tk.Entry(
            date_row,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
        )
        default_exam = (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")
        self.entry_exam_date.insert(0, default_exam)
        self.entry_exam_date.pack(side="left", fill="x", expand=True)

        quick_dates = tk.Frame(card_setup, bg=BG_CARD)
        quick_dates.pack(fill="x", pady=(0, 8))
        for d in [30, 60, 90, 120]:
            btn = tk.Button(
                quick_dates,
                text=f"+{d}d",
                font=("Helvetica Neue", 8),
                bg="#f1f5f9",
                fg=TEXT_MAIN,
                activebackground="#e2e8f0",
                activeforeground=TEXT_MAIN,
                relief="flat",
                command=lambda days=d: self._set_exam_days_ahead(days),
                padx=5,
                pady=1,
            )
            btn.pack(side="left", padx=1)

        # Credit Hours & Max Daily Cap
        param_row = tk.Frame(card_setup, bg=BG_CARD)
        param_row.pack(fill="x", pady=(0, 8))

        ch_col = tk.Frame(param_row, bg=BG_CARD)
        ch_col.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(ch_col, text="Credit Hours", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w")
        self.entry_ch = tk.Entry(
            ch_col,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
        )
        self.entry_ch.insert(0, "3.0")
        self.entry_ch.pack(fill="x", pady=(2, 0))

        cap_col = tk.Frame(param_row, bg=BG_CARD)
        cap_col.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(cap_col, text="Max Cap (hrs/d)", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w")
        self.entry_cap = tk.Entry(
            cap_col,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
        )
        self.entry_cap.insert(0, "4.0")
        self.entry_cap.pack(fill="x", pady=(2, 0))

        # Course Outline / Topics
        tk.Label(
            card_setup,
            text="Course Topics (Comma or Newline separated)",
            font=("Helvetica Neue", 9, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(4, 0))

        self.txt_topics = tk.Text(
            card_setup,
            height=3,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
            wrap="word",
        )
        default_topics = "Introduction & Syntax, Data Structures, OOP, File Handling, Project & Revision"
        self.txt_topics.insert("1.0", default_topics)
        self.txt_topics.pack(fill="x", pady=(2, 10))

        btn_generate = tk.Button(
            card_setup,
            text="🚀 Generate Study Schedule",
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
        card_replan = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=14, pady=12)
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
            text="Missed study sessions? RePlan automatically redistributes unfinished tasks and hours across remaining available study days.",
            font=("Helvetica Neue", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            wraplength=340,
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

        # Tab 1: Day-by-Day Schedule
        self.tab_schedule = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_schedule, text="  📋 Day-by-Day Schedule  ")
        self._build_schedule_tab(self.tab_schedule)

        # Tab 2: Topic Periods Breakdown
        self.tab_topics = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_topics, text="  📅 Topic Periods Breakdown  ")
        self._build_topics_tab(self.tab_topics)

        # Tab 3: Adaptive Insights & Replan Log
        self.tab_insights = tk.Frame(self.notebook, bg=BG_CARD)
        self.notebook.add(self.tab_insights, text="  📊 Adaptive Insights & Analytics  ")
        self._build_insights_tab(self.tab_insights)

    # -----------------------------------------------------------------------
    # Tab 1: Day-by-Day Schedule Table (With Highlighted Rescheduled Tasks)
    # -----------------------------------------------------------------------
    def _build_schedule_tab(self, parent: tk.Frame) -> None:
        # Top Action Bar: Buttons to select if user has done studying for selected day(s)
        action_bar = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground=BORDER_COLOR, padx=12, pady=8)
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
            padx=12,
            pady=5,
            cursor="pointinghand",
        )
        btn_done.pack(side="left", padx=(0, 6))

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
            padx=12,
            pady=5,
            cursor="pointinghand",
        )
        btn_miss.pack(side="left", padx=(0, 6))

        btn_pending = tk.Button(
            action_bar,
            text="⏳ Reset Pending",
            command=lambda: self._set_selected_status("Pending"),
            font=("Helvetica Neue", 9),
            bg="#e2e8f0",
            fg=TEXT_MAIN,
            activebackground="#cbd5e1",
            activeforeground=TEXT_MAIN,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
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

        # Filter & Search toolbar row
        filter_bar = tk.Frame(parent, bg=BG_CARD, padx=12, pady=6)
        filter_bar.pack(side="top", fill="x")

        tk.Label(filter_bar, text="Filter Status:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.combo_status_filter = ttk.Combobox(
            filter_bar,
            values=["All", "Pending", "Completed", "Missed", "Rescheduled"],
            state="readonly",
            width=13,
        )
        self.combo_status_filter.current(0)
        self.combo_status_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_schedule_view())
        self.combo_status_filter.pack(side="left", padx=(4, 14))

        tk.Label(filter_bar, text="Search Topic:", font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.entry_search = tk.Entry(
            filter_bar,
            font=("Helvetica Neue", 10),
            bg="#ffffff",
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
            width=18,
        )
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_schedule_view())
        self.entry_search.pack(side="left", padx=(4, 14))

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

        self.lbl_table_count = tk.Label(filter_bar, text="0 days scheduled", font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_CARD)
        self.lbl_table_count.pack(side="right")

        # Treeview with Scrollbars
        table_container = tk.Frame(parent, bg=BG_CARD)
        table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        columns = ("Day", "Date", "Weekday", "Target Hours", "Topic Day", "Topic", "Status")
        self.tree_schedule = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")

        col_configs = {
            "Day": (55, "center"),
            "Date": (95, "center"),
            "Weekday": (95, "w"),
            "Target Hours": (95, "center"),
            "Topic Day": (80, "center"),
            "Topic": (280, "w"),
            "Status": (125, "center"),
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
    # Tab 2: Topic Periods Breakdown Table
    # -----------------------------------------------------------------------
    def _build_topics_tab(self, parent: tk.Frame) -> None:
        hdr = tk.Frame(parent, bg=BG_CARD, padx=12, pady=10)
        hdr.pack(side="top", fill="x")

        tk.Label(
            hdr,
            text="📅 TOPIC STUDY PERIODS & TIMELINE ALLOCATION",
            font=("Helvetica Neue", 11, "bold"),
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(side="left")

        table_container = tk.Frame(parent, bg=BG_CARD)
        table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        columns = ("Topic #", "Topic", "Duration", "Total Hours", "Start Date", "End Date", "Completed", "Pending", "Progress")
        self.tree_topics = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")

        col_configs = {
            "Topic #": (65, "center"),
            "Topic": (260, "w"),
            "Duration": (95, "center"),
            "Total Hours": (95, "center"),
            "Start Date": (95, "center"),
            "End Date": (95, "center"),
            "Completed": (80, "center"),
            "Pending": (80, "center"),
            "Progress": (90, "center"),
        }

        for col, (width, anchor) in col_configs.items():
            self.tree_topics.heading(col, text=col)
            self.tree_topics.column(col, width=width, anchor=anchor)

        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_topics.yview)
        self.tree_topics.configure(yscrollcommand=v_scroll.set)

        self.tree_topics.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

    # -----------------------------------------------------------------------
    # Tab 3: Adaptive Insights & Replan Analytics
    # -----------------------------------------------------------------------
    def _build_insights_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_CARD, padx=16, pady=14)
        container.pack(fill="both", expand=True)

        self.banner_feasibility = tk.Frame(
            container,
            bg=COLOR_SUCCESS_BG,
            highlightthickness=1,
            highlightbackground="#bbf7d0",
            padx=14,
            pady=10,
        )
        self.banner_feasibility.pack(fill="x", pady=(0, 12))

        self.lbl_feasibility_text = tk.Label(
            self.banner_feasibility,
            text="✅ FEASIBILITY STATUS: Study plan is well-balanced within your daily study limit.",
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
            insertbackground=TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            relief="solid",
            bd=1,
            padx=10,
            pady=10,
        )
        self.txt_insights.pack(fill="both", expand=True, pady=(0, 10))

    # -----------------------------------------------------------------------
    # Bottom Status Bar
    # -----------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        self.status_bar = tk.Frame(self, bg="#f1f5f9", height=26, padx=14, pady=4)
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
    # Adaptive Rescheduling & Study Completion Handlers
    # -----------------------------------------------------------------------
    def _run_reschedule_engine(self, show_toast: bool = True, source_reason: str = "Adaptive Replan") -> None:
        """
        Executes ReplanEngine.reschedule_missed_tasks:
        Redistributes missed curriculum tasks into available study days between
        today and the exam date, highlights rescheduled tasks in purple, and updates views.
        """
        if self.df_schedule.empty:
            return

        try:
            try:
                cap = float(self.entry_cap.get().strip())
            except ValueError:
                cap = 4.0

            updated_df, stats = ReplanEngine.reschedule_missed_tasks(
                self.df_schedule,
                today_date=datetime.today().date(),
                max_daily_cap=cap,
                baseline_total_hours=self.baseline_total_hours,
            )

            self.df_schedule = updated_df
            self.topic_periods = ReplanEngine.compute_topic_periods_from_df(updated_df)
            self.replan_history.append(stats)

            self._refresh_all_views()

            # Find and highlight the first rescheduled row in Treeview
            resched_items = []
            for item_id in self.tree_schedule.get_children():
                tags = self.tree_schedule.item(item_id, "tags")
                if "rescheduled" in tags:
                    resched_items.append(item_id)

            if resched_items:
                self.tree_schedule.selection_set(resched_items[0])
                self.tree_schedule.see(resched_items[0])

            diff = stats["rate_change"]
            diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"

            if show_toast:
                if stats["rescheduled_days_count"] > 0:
                    msg = (
                        f"🔄 Study Task Rescheduled!\n\n"
                        f"• Reason: {source_reason}\n"
                        f"• Rescheduled To: {stats['first_rescheduled_date']}\n"
                        f"• Assigned Task: {stats['first_rescheduled_topic']}\n"
                        f"• Highlighting: Highlighted in PURPLE in the schedule table below!\n\n"
                        f"• Adjusted Daily Target: {stats['new_daily_hours']} hrs/day ({diff_str} hrs/day)\n"
                        f"• Available Study Days Left: {stats['num_available_days']} days\n"
                        f"• Total Uncompleted Work: {stats['uncompleted_hours']} hrs"
                    )
                    if stats["is_over_cap"]:
                        msg += f"\n\n⚠️ Caution: Required daily pace exceeds your limit ({stats['max_daily_cap']} hrs/day)!"
                        messagebox.showwarning("Task Rescheduled (Over Cap)", msg)
                    else:
                        messagebox.showinfo("Task Rescheduled", msg)
                else:
                    msg = (
                        f"🔄 Adaptive Replan Complete!\n\n"
                        f"• Daily Target: {stats['new_daily_hours']} hrs/day ({diff_str} hrs/day)\n"
                        f"• Available Days Left: {stats['num_available_days']} days\n"
                        f"• Uncompleted Hours: {stats['uncompleted_hours']} hrs"
                    )
                    messagebox.showinfo("Adaptive Replan", msg)

            self.set_status_message(
                f"Rescheduled {stats['rescheduled_days_count']} task(s) • Pace: {stats['new_daily_hours']} hrs/day"
            )

        except Exception as e:
            messagebox.showerror("Adaptive Reschedule Error", str(e))

    def _mark_today_status(self, new_status: str) -> None:
        """
        Handles marking today's study milestone as Completed, Missed, or Pending.
        Called directly by the prominent check-in buttons.
        """
        if self.df_schedule.empty:
            messagebox.showwarning("No Schedule", "Please generate or load a schedule first.")
            return

        today_str = datetime.today().strftime("%Y-%m-%d")
        mask = self.df_schedule["Date"] == today_str

        if not mask.any():
            date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
            today_date = datetime.today().date()
            if today_date < date_series.iloc[0]:
                target_row_idx = 0
                target_date = self.df_schedule.loc[0, "Date"]
                msg = f"Today ({today_str}) is before the plan starts ({target_date}). Would you like to mark Day 1 instead?"
                if messagebox.askyesno("Confirm Mark", msg):
                    self.df_schedule.loc[0, "Status"] = new_status
                else:
                    return
            elif today_date > date_series.iloc[-1]:
                messagebox.showinfo("Semester Ended", f"Today ({today_str}) is past the scheduled exam date ({date_series.iloc[-1]}).")
                return
            else:
                messagebox.showinfo("Date Not Found", f"Today ({today_str}) was not found in the schedule table.")
                return
        else:
            self.df_schedule.loc[mask, "Status"] = new_status

        if new_status == "Completed":
            self._refresh_all_views()
            self._jump_to_today()
            self.set_status_message(f"🎉 Great job! You have completed today's study session ({today_str})!")
            messagebox.showinfo(
                "Study Completed! 🎉",
                f"Awesome work! You have marked today ({today_str}) as Done Studying.\n\n"
                f"Your progress has been updated in the dashboard."
            )
        elif new_status == "Missed":
            self.set_status_message(f"Logged today ({today_str}) as Missed.")
            # Automatically reschedule the missed task to upcoming available days and highlight!
            self._run_reschedule_engine(show_toast=True, source_reason=f"Missed Today's Session ({today_str})")
        else:
            self.df_schedule.loc[mask, "Rescheduled_From"] = ""
            self._refresh_all_views()
            self._jump_to_today()
            self.set_status_message(f"Reset today ({today_str}) to Pending.")

    def _set_selected_status(self, new_status: str) -> None:
        """Sets status for all selected rows from the action bar or menu."""
        selected_items = self.tree_schedule.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one day in the schedule table.")
            return

        for item_id in selected_items:
            values = self.tree_schedule.item(item_id, "values")
            day_num = int(values[0])
            mask = self.df_schedule["Day"] == day_num
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
        """Double clicking a row cycles through: Pending -> Completed -> Missed -> Pending."""
        item_id = self.tree_schedule.identify_row(event.y)
        if not item_id:
            return

        values = self.tree_schedule.item(item_id, "values")
        day_num = int(values[0])
        current_status_str = str(values[6])

        if "Completed" in current_status_str or "Done" in current_status_str:
            next_status = "Missed"
        elif "Missed" in current_status_str:
            next_status = "Pending"
        else:
            next_status = "Completed"

        mask = self.df_schedule["Day"] == day_num
        if mask.any():
            self.df_schedule.loc[mask, "Status"] = next_status
            if next_status != "Rescheduled":
                self.df_schedule.loc[mask, "Rescheduled_From"] = ""

        if next_status == "Missed":
            self._run_reschedule_engine(show_toast=True, source_reason=f"Day {day_num} marked Missed")
        else:
            self._refresh_all_views()
            self.set_status_message(f"Day {day_num} status changed to {next_status}")

    def _on_tree_selection_change(self, event) -> None:
        """Updates the selection preview label when user clicks table row(s)."""
        selected = self.tree_schedule.selection()
        if not selected:
            self.lbl_selected_preview.config(text="Select row(s) below to mark completed/missed")
            return

        if len(selected) == 1:
            vals = self.tree_schedule.item(selected[0], "values")
            day_num, row_date, weekday, target_hrs, topic_day, topic, status = vals
            self.lbl_selected_preview.config(
                text=f"Selected: Day {day_num} ({row_date}) • {topic} • Current: {status}"
            )
        else:
            self.lbl_selected_preview.config(text=f"Selected {len(selected)} days for batch update")

    def _show_tree_context_menu(self, event) -> None:
        row_id = self.tree_schedule.identify_row(event.y)
        if row_id:
            if row_id not in self.tree_schedule.selection():
                self.tree_schedule.selection_set(row_id)
            self.tree_menu.post(event.x_root, event.y_root)

    def _jump_to_today(self) -> None:
        today_str = datetime.today().strftime("%Y-%m-%d")
        for item_id in self.tree_schedule.get_children():
            vals = self.tree_schedule.item(item_id, "values")
            if vals and vals[1] == today_str:
                self.tree_schedule.selection_set(item_id)
                self.tree_schedule.see(item_id)
                return

    def _auto_check_missed_past_tasks(self) -> None:
        """
        Auto-detection: Checks if any past calendar days were left uncompleted
        (user did not click 'Done Studying'). Automatically marks them as Missed
        and reschedules their tasks to today onwards with purple highlighting.
        """
        if self.df_schedule.empty:
            return

        today_date = datetime.today().date()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
        past_uncompleted = (date_series < today_date) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))

        if past_uncompleted.any():
            num_past = int(past_uncompleted.sum())
            self._run_reschedule_engine(
                show_toast=True,
                source_reason=f"Detected {num_past} past uncompleted session(s) without 'Done Studying'",
            )

    # -----------------------------------------------------------------------
    # Setup & General Actions
    # -----------------------------------------------------------------------
    def _set_exam_days_ahead(self, days: int) -> None:
        new_date = (datetime.today() + timedelta(days=days)).strftime("%Y-%m-%d")
        self.entry_exam_date.delete(0, tk.END)
        self.entry_exam_date.insert(0, new_date)

    def _auto_load_initial_data(self) -> None:
        if os.path.exists(DEFAULT_CSV_PATH):
            try:
                self._load_csv_file(DEFAULT_CSV_PATH)
                self.set_status_message(f"Auto-loaded plan from '{DEFAULT_CSV_PATH}'")
                return
            except Exception as e:
                print(f"Failed to auto-load {DEFAULT_CSV_PATH}: {e}")

        self._load_notebook_sample()

    def _load_notebook_sample(self) -> None:
        self.entry_course.delete(0, tk.END)
        self.entry_course.insert(0, "Programming & Problem Solving")

        self.entry_exam_date.delete(0, tk.END)
        sample_exam = (datetime.today() + timedelta(days=108)).strftime("%Y-%m-%d")
        self.entry_exam_date.insert(0, sample_exam)

        self.entry_ch.delete(0, tk.END)
        self.entry_ch.insert(0, "3.0")

        self.entry_cap.delete(0, tk.END)
        self.entry_cap.insert(0, "4.0")

        self.txt_topics.delete("1.0", tk.END)
        self.txt_topics.insert("1.0", "Introduction & Syntax, Data Structures, OOP, File Handling, Project & Revision")

        self._on_generate_schedule()
        self.set_status_message("Loaded standard RePlan notebook sample plan.")

    def _on_generate_schedule(self) -> None:
        try:
            exam_str = self.entry_exam_date.get()
            exam_date = ReplanEngine.parse_date(exam_str)

            try:
                ch = float(self.entry_ch.get().strip())
            except ValueError:
                raise ValueError("Credit Hours must be a valid number (e.g. 3.0)")

            topics_raw = self.txt_topics.get("1.0", tk.END)
            topics = [t.strip() for chunk in topics_raw.split("\n") for t in chunk.split(",") if t.strip()]

            df, periods, meta = ReplanEngine.generate_schedule(
                exam_date=exam_date,
                credit_hours=ch,
                topics=topics,
            )

            self.df_schedule = df
            self.topic_periods = periods
            self.baseline_total_hours = meta["total_study_hours"]
            self.current_file_path = DEFAULT_CSV_PATH

            self._refresh_all_views()
            self.set_status_message(f"Generated new schedule: {len(df)} study days ({meta['total_study_hours']} total hours)")

        except Exception as e:
            messagebox.showerror("Schedule Generation Error", str(e))

    def _on_adaptive_replan(self) -> None:
        self._run_reschedule_engine(show_toast=True, source_reason="Manual Adaptive Replan")

    # -----------------------------------------------------------------------
    # File I/O
    # -----------------------------------------------------------------------
    def _on_load_csv_dialog(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Open Semester Plan CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        if path:
            self._load_csv_file(path)

    def _load_csv_file(self, filepath: str) -> None:
        try:
            df = ReplanEngine.load_csv(filepath)
            self.df_schedule = df
            self.topic_periods = ReplanEngine.compute_topic_periods_from_df(df)
            self.current_file_path = filepath
            self.baseline_total_hours = float(df["Target Hours"].sum())

            if not df.empty:
                last_date = df["Date"].iloc[-1]
                self.entry_exam_date.delete(0, tk.END)
                self.entry_exam_date.insert(0, str(last_date))

                unique_topics = list(dict.fromkeys(df["Topic"].dropna()))
                clean_topics = [str(t).split(" • 🔄")[0].split(" (🔄")[0].strip() for t in unique_topics]
                self.txt_topics.delete("1.0", tk.END)
                self.txt_topics.insert("1.0", ", ".join(list(dict.fromkeys(clean_topics))))

            self._refresh_all_views()
            self._auto_check_missed_past_tasks()
            self.set_status_message(f"Loaded {len(df)} study sessions from {os.path.basename(filepath)}")
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
                ReplanEngine.save_csv(self.df_schedule, path)
                self.current_file_path = path
                self.lbl_status_file.config(text=f"Plan: {os.path.basename(path)}")
                self.set_status_message(f"Saved plan to {path}")
                messagebox.showinfo("Saved", f"Plan saved successfully to:\n{path}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    # -----------------------------------------------------------------------
    # View Refreshes & Metrics Calculation
    # -----------------------------------------------------------------------
    def _refresh_all_views(self) -> None:
        self._refresh_today_checkin_card()
        self._refresh_metric_ribbon()
        self._refresh_schedule_view()
        self._refresh_topics_view()
        self._refresh_insights_view()
        if self.current_file_path:
            self.lbl_status_file.config(text=f"Active Plan: {os.path.basename(self.current_file_path)}")

    def _refresh_today_checkin_card(self) -> None:
        """Updates the top check-in card with today's scheduled topic and status."""
        if self.df_schedule.empty:
            self.lbl_today_topic.config(text="No active study plan loaded")
            self.lbl_today_target.config(text="Generate a plan to see today's milestone")
            self.card_checkin.config(highlightbackground=COLOR_PRIMARY)
            return

        today_str = datetime.today().strftime("%Y-%m-%d")
        mask = self.df_schedule["Date"] == today_str

        if mask.any():
            row = self.df_schedule[mask].iloc[0]
            status = row["Status"]
            resched_from = str(row.get("Rescheduled_From", "") or "")
            is_rescheduled = status == "Rescheduled" or bool(resched_from)

            if status == "Completed":
                status_symbol = "✅ Done"
                self.card_checkin.config(highlightbackground=COLOR_SUCCESS)
            elif status == "Missed":
                status_symbol = "❌ Missed"
                self.card_checkin.config(highlightbackground=COLOR_DANGER)
            elif is_rescheduled:
                status_symbol = "🔄 Rescheduled"
                self.card_checkin.config(highlightbackground=COLOR_RESCHEDULED)
            else:
                status_symbol = "⏳ Pending"
                self.card_checkin.config(highlightbackground=COLOR_PRIMARY)

            topic_text = f"Day {row['Day']}: {row['Topic']} ({row['Topic Day']})"
            if is_rescheduled and resched_from:
                topic_text += f"\n🔄 (Rescheduled from {resched_from})"

            self.lbl_today_topic.config(text=topic_text)
            self.lbl_today_target.config(
                text=f"Target: {row['Target Hours']} hrs • Status: {status_symbol}"
            )
        else:
            self.card_checkin.config(highlightbackground=BORDER_COLOR)
            date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
            today_date = datetime.today().date()
            if today_date < date_series.iloc[0]:
                first_date = str(self.df_schedule["Date"].iloc[0])
                first_topic = str(self.df_schedule["Topic"].iloc[0])
                self.lbl_today_topic.config(text=f"Plan starts on {first_date}: {first_topic}")
                self.lbl_today_target.config(text="Upcoming semester plan (not yet started)")
            else:
                self.lbl_today_topic.config(text="Semester exam date has passed")
                self.lbl_today_target.config(text="All milestones reached")

    def _refresh_metric_ribbon(self) -> None:
        if self.df_schedule.empty:
            self.card_days.update_card("--", "No plan generated")
            self.card_total_hours.update_card("--", "Credit hours required")
            self.card_target.update_card("--", "Daily pace")
            self.card_progress.update_card("0%", "0 completed")
            self.card_feasibility.update_card("Ready", "Cap: 4.0h/day", COLOR_SUCCESS)
            return

        today = datetime.today().date()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
        exam_date = date_series.iloc[-1]
        days_left = max(0, (exam_date - today).days)

        total_days = len(self.df_schedule)
        completed_days = int((self.df_schedule["Status"] == "Completed").sum())
        missed_days = int((self.df_schedule["Status"] == "Missed").sum())
        rescheduled_days = int((self.df_schedule["Status"] == "Rescheduled").sum())
        pending_days = int((self.df_schedule["Status"] == "Pending").sum())

        total_workload = float(self.df_schedule["Target Hours"].sum())
        progress_pct = round((completed_days / total_days) * 100, 1) if total_days else 0.0

        avail_mask = (date_series >= today) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))
        if avail_mask.any():
            current_target = float(self.df_schedule.loc[avail_mask, "Target Hours"].iloc[0])
        else:
            current_target = float(self.df_schedule["Target Hours"].iloc[-1])

        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 4.0

        is_over_cap = current_target > cap

        self.card_days.update_card(
            f"{days_left} Days Left",
            f"Exam: {exam_date.strftime('%Y-%m-%d')}",
        )
        self.card_total_hours.update_card(
            f"{total_workload:.1f} hrs",
            f"{self.entry_ch.get()} CH × {STUDY_HOURS_PER_CH:.0f}h",
        )
        self.card_target.update_card(
            f"{current_target:.2f} h/d",
            "Adaptive daily target",
        )
        self.card_progress.update_card(
            f"{progress_pct}%",
            f"{completed_days} Done • {missed_days} Missed • {rescheduled_days} Resched",
        )

        if is_over_cap:
            self.card_feasibility.update_card(
                "⚠️ Over Cap",
                f"{current_target:.2f} > {cap:.1f}h/day limit!",
                val_color=COLOR_DANGER,
            )
        else:
            self.card_feasibility.update_card(
                "✅ Feasible",
                f"Within {cap:.1f}h/day cap",
                val_color=COLOR_SUCCESS,
            )

    def _refresh_schedule_view(self) -> None:
        for item in self.tree_schedule.get_children():
            self.tree_schedule.delete(item)

        if self.df_schedule.empty:
            self.lbl_table_count.config(text="0 days scheduled")
            return

        status_filter = self.combo_status_filter.get()
        search_query = self.entry_search.get().strip().lower()

        today_str = datetime.today().strftime("%Y-%m-%d")
        displayed_count = 0

        for _, row in self.df_schedule.iterrows():
            status = str(row["Status"])
            topic = str(row["Topic"])
            row_date = str(row["Date"])
            resched_from = str(row.get("Rescheduled_From", "") or "")
            is_rescheduled = status == "Rescheduled" or bool(resched_from)

            if status_filter != "All":
                if status_filter == "Rescheduled" and not is_rescheduled:
                    continue
                elif status_filter != "Rescheduled" and status != status_filter:
                    continue

            if search_query and search_query not in topic.lower() and search_query not in row_date:
                continue

            # Tag determination & Highlighting
            if status == "Completed":
                tag = "completed"
                status_icon = "✅ Done"
            elif status == "Missed":
                tag = "missed"
                status_icon = "❌ Missed"
            elif is_rescheduled:
                tag = "rescheduled"
                status_icon = "🔄 Rescheduled"
            elif row_date == today_str:
                tag = "today"
                status_icon = "📌 Today"
            else:
                tag = "pending"
                status_icon = "⏳ Pending"

            topic_display = topic
            if is_rescheduled and resched_from:
                topic_display = f"{topic} (🔄 from {resched_from})"

            self.tree_schedule.insert(
                "",
                "end",
                values=(
                    row["Day"],
                    row["Date"],
                    row["Weekday"],
                    f"{float(row['Target Hours']):.2f}",
                    row["Topic Day"],
                    topic_display,
                    status_icon,
                ),
                tags=(tag,),
            )
            displayed_count += 1

        self.lbl_table_count.config(text=f"Showing {displayed_count} of {len(self.df_schedule)} days")

    def _refresh_topics_view(self) -> None:
        for item in self.tree_topics.get_children():
            self.tree_topics.delete(item)

        if not self.topic_periods:
            self.topic_periods = ReplanEngine.compute_topic_periods_from_df(self.df_schedule)

        for p in self.topic_periods:
            self.tree_topics.insert(
                "",
                "end",
                values=(
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

    def _refresh_insights_view(self) -> None:
        if self.df_schedule.empty:
            self.txt_insights.delete("1.0", tk.END)
            self.txt_insights.insert("1.0", "Generate or load a study plan to see analytics and diagnostic reports.")
            return

        today = datetime.today().date()
        date_series = pd.to_datetime(self.df_schedule["Date"]).dt.date
        exam_date = date_series.iloc[-1]
        days_left = max(0, (exam_date - today).days)

        completed_mask = self.df_schedule["Status"] == "Completed"
        missed_mask = self.df_schedule["Status"] == "Missed"
        avail_mask = (date_series >= today) & (self.df_schedule["Status"].isin(["Pending", "Rescheduled"]))

        completed_hrs = float(self.df_schedule.loc[completed_mask, "Target Hours"].sum())
        missed_hrs = float(self.df_schedule.loc[missed_mask, "Target Hours"].sum())
        pending_hrs = float(self.df_schedule.loc[avail_mask, "Target Hours"].sum())
        total_hrs = completed_hrs + missed_hrs + pending_hrs

        available_days = int(avail_mask.sum())
        current_target = round(pending_hrs / available_days, 2) if available_days else 0.0

        try:
            cap = float(self.entry_cap.get().strip())
        except ValueError:
            cap = 4.0

        is_over_cap = current_target > cap

        if is_over_cap:
            self.banner_feasibility.config(bg=COLOR_DANGER_BG, highlightbackground="#fecaca")
            self.lbl_feasibility_text.config(
                text=f"⚠️ CAPACITY ALERT: Target pace of {current_target:.2f} hrs/day exceeds your limit ({cap:.1f} hrs/day)!",
                fg=COLOR_DANGER_TEXT,
                bg=COLOR_DANGER_BG,
            )
        else:
            self.banner_feasibility.config(bg=COLOR_SUCCESS_BG, highlightbackground="#bbf7d0")
            self.lbl_feasibility_text.config(
                text=f"✅ FEASIBILITY STATUS: Study plan is realistic ({current_target:.2f} hrs/day within {cap:.1f} hrs/day limit).",
                fg=COLOR_SUCCESS_TEXT,
                bg=COLOR_SUCCESS_BG,
            )

        report = []
        report.append("=" * 68)
        report.append(f"🎓 REPLAN ANALYTICS & FEASIBILITY REPORT — {self.entry_course.get()}")
        report.append("=" * 68)
        report.append(f"• Exam Date:                {exam_date.strftime('%Y-%m-%d')} ({days_left} calendar days remaining)")
        report.append(f"• Available Study Sessions: {available_days} sessions remaining")
        report.append(f"• Current Daily Study Rate: {current_target:.2f} hrs/day (User Limit: {cap:.1f} hrs/day)")
        report.append(f"• Total Planned Workload:   {total_hrs:.1f} study hours")
        report.append(f"  ├─ Completed Workload:    {completed_hrs:.1f} hrs ({int(completed_mask.sum())} days)")
        report.append(f"  ├─ Missed Workload:       {missed_hrs:.1f} hrs ({int(missed_mask.sum())} days)")
        report.append(f"  └─ Remaining Workload:    {pending_hrs:.1f} hrs ({available_days} days)")
        report.append("")

        if is_over_cap:
            shortfall = round((current_target - cap) * available_days, 1)
            days_extension_needed = int((pending_hrs / cap) - available_days) + 1
            report.append("🚨 CAPACITY OVERLOAD DIAGNOSTIC:")
            report.append(f"  Your current pace exceeds your daily ceiling by {current_target - cap:.2f} hrs/day.")
            report.append(f"  Total capacity deficit over remaining days: ~{shortfall} hours.")
            report.append("  Suggested Remediation Steps:")
            report.append(f"  1. Extend exam date by {days_extension_needed} days to restore {cap:.1f} hrs/day pace.")
            report.append(f"  2. Increase daily study cap to {current_target:.2f} hrs/day.")
            report.append("  3. Prune or prioritize high-yield topics in the course outline.")
        else:
            buffer_hrs = round((cap - current_target) * available_days, 1)
            report.append("✨ PACE ASSESSMENT:")
            report.append(f"  Your pace is sustainable. You have an estimated buffer of ~{buffer_hrs} hours")
            report.append("  below your maximum daily capacity. Keep following your daily milestones!")

        report.append("")
        report.append("=" * 68)
        report.append("🔄 ADAPTIVE REPLAN LOG (Recent Adjustments):")
        report.append("=" * 68)
        if not self.replan_history:
            report.append("No replanning events recorded yet in this session.")
        else:
            for idx, h in enumerate(reversed(self.replan_history), 1):
                report.append(
                    f"[{h['timestamp']}] Replan #{len(self.replan_history) - idx + 1}: "
                    f"Target {h['prev_daily_target']} -> {h['new_daily_hours']} h/d | "
                    f"Rescheduled {h.get('rescheduled_days_count', 0)} task(s) across {h['num_available_days']} days."
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
            "RePlan — Adaptive Semester Planner 🎓\n\n"
            "An adaptive study planner that turns semester dates, course credit hours, "
            "and syllabus outlines into realistic daily study milestones.\n\n"
            "Key Features:\n"
            "• Daily Study Check-in: Select if you've done studying with 1 click!\n"
            "• Smart Adaptive Rescheduling: When a session is missed (or forgotten),\n"
            "  RePlan automatically reschedules the missed task into an upcoming study day\n"
            "  and highlights it in PURPLE!\n"
            "• Dynamic pace adjustment so you never fall behind\n"
            "• Feasibility alerts when workload exceeds daily limits\n"
            "• Full CSV persistence and portability\n\n"
            "Created for students who need plans that adapt to real life."
        )
        messagebox.showinfo("About RePlan", msg)


# ---------------------------------------------------------------------------
# CLI / Main Entrypoint
# ---------------------------------------------------------------------------
def main():
    app = ReplanApp()
    app.mainloop()


if __name__ == "__main__":
    main()
