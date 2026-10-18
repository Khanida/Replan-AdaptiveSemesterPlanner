"""
Automated Test Suite for RePlan v1.1 Cozy & Friendly Multi-Course Scheduler 🌸
"""

import os
from datetime import date, timedelta
import unittest
import pandas as pd

from replanv1_1 import (
    CourseConfig,
    TopicPeriod,
    MultiCourseReplanEngine,
    STUDY_HOURS_PER_CH,
)


class TestReplanV11Engine(unittest.TestCase):
    def setUp(self):
        self.today = date.today()
        self.courses = [
            CourseConfig(
                name="Programming",
                credit_hours=4.0,
                exam_date=self.today + timedelta(days=90),
                topics=["Syntax", "OOP", "Data Structures", "Projects"],
                color="#7c3aed",
                icon="💻",
            ),
            CourseConfig(
                name="Calculus",
                credit_hours=3.0,
                exam_date=self.today + timedelta(days=60),
                topics=["Limits", "Derivatives", "Integrals"],
                color="#059669",
                icon="📐",
            ),
            CourseConfig(
                name="Networks",
                credit_hours=3.0,
                exam_date=self.today + timedelta(days=75),
                topics=["OSI", "IP Routing", "TCP/UDP"],
                color="#ea580c",
                icon="🌐",
            ),
        ]

    def test_multi_course_generation(self):
        df, periods, summary = MultiCourseReplanEngine.generate_multi_course_schedule(
            courses=self.courses,
            start_date=self.today,
        )

        self.assertFalse(df.empty)
        expected_cols = [
            "Day", "Date", "Weekday", "Course", "Topic Day", "Topic", "Target Hours", "Status", "Rescheduled_From"
        ]
        for col in expected_cols:
            self.assertIn(col, df.columns)

        self.assertEqual(summary["total_courses"], 3)
        self.assertEqual(summary["total_credit_hours"], 10.0)
        self.assertAlmostEqual(summary["total_study_hours"], 450.0)

        for c in self.courses:
            course_df = df[df["Course"] == c.name]
            self.assertFalse(course_df.empty)
            dates = pd.to_datetime(course_df["Date"]).dt.date
            self.assertTrue((dates < c.exam_date).all())

            c_periods = [p for p in periods if p.course_name == c.name]
            self.assertEqual(len(c_periods), len(c.topics))

    def test_adaptive_rescheduling_and_highlighting(self):
        df, periods, summary = MultiCourseReplanEngine.generate_multi_course_schedule(
            courses=self.courses,
            start_date=self.today,
        )

        day1_str = self.today.strftime("%Y-%m-%d")

        # Simulate user completed Calculus on Day 1, missed Programming, left Networks pending
        df.loc[(df["Date"] == day1_str) & (df["Course"] == "Calculus"), "Status"] = "Completed"
        df.loc[(df["Date"] == day1_str) & (df["Course"] == "Programming"), "Status"] = "Missed"

        tomorrow = self.today + timedelta(days=1)
        replan_df, stats = MultiCourseReplanEngine.reschedule_missed_tasks(
            df=df,
            today_date=tomorrow,
            max_daily_cap=5.0,
        )

        # Networks on Day 1 was past uncompleted -> should now be marked Missed
        day1_net = replan_df[(replan_df["Date"] == day1_str) & (replan_df["Course"] == "Networks")]
        self.assertEqual(day1_net["Status"].iloc[0], "Missed")

        # Both Programming and Networks missed tasks should be rescheduled forward
        rescheduled_rows = replan_df[replan_df["Status"] == "Rescheduled"]
        self.assertGreaterEqual(len(rescheduled_rows), 2)

        for _, row in rescheduled_rows.iterrows():
            self.assertTrue(bool(row["Rescheduled_From"]))

        prog_stats = stats["course_stats"]["Programming"]
        self.assertGreater(prog_stats["new_daily_hours"], prog_stats["prev_target"])

    def test_save_and_load_persistence(self):
        df, periods, summary = MultiCourseReplanEngine.generate_multi_course_schedule(
            courses=self.courses,
            start_date=self.today,
        )

        test_csv_path = "test_cozy_plan.csv"
        try:
            MultiCourseReplanEngine.save_csv(df, test_csv_path, self.courses)
            self.assertTrue(os.path.exists(test_csv_path))
            self.assertTrue(os.path.exists(test_csv_path + ".meta.json"))

            loaded_df, loaded_courses = MultiCourseReplanEngine.load_csv(test_csv_path)
            self.assertEqual(len(loaded_df), len(df))
            self.assertEqual(len(loaded_courses), len(self.courses))

            loaded_names = [c.name for c in loaded_courses]
            for c in self.courses:
                self.assertIn(c.name, loaded_names)
        finally:
            if os.path.exists(test_csv_path):
                os.remove(test_csv_path)
            if os.path.exists(test_csv_path + ".meta.json"):
                os.remove(test_csv_path + ".meta.json")

    def test_google_calendar_manager(self):
        from replanv1_1 import GoogleCalendarSyncManager
        df, periods, summary = MultiCourseReplanEngine.generate_multi_course_schedule(
            courses=self.courses,
            start_date=self.today,
        )
        milestones = df.head(5).to_dict("records")
        courses_by_name = {c.name: c for c in self.courses}

        ics_content = GoogleCalendarSyncManager.generate_ics_content(
            milestones=milestones,
            courses_by_name=courses_by_name,
            preferred_hour=18,
            all_day=False,
        )

        self.assertIn("BEGIN:VCALENDAR", ics_content)
        self.assertIn("END:VCALENDAR", ics_content)
        self.assertIn("BEGIN:VEVENT", ics_content)
        self.assertIn("END:VEVENT", ics_content)
        self.assertIn("SUMMARY:", ics_content)
        self.assertIn("Programming", ics_content)


if __name__ == "__main__":
    unittest.main()
