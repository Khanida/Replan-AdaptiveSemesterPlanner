"""State-aware roast regression checks for the v1.2 planner."""
import unittest
from datetime import date
import pandas as pd
from replanv1_2 import study_roast


class RoastTests(unittest.TestCase):
    today = date(2026, 10, 19)

    def plan(self, status='Pending', day='2026-10-19', hours=1):
        return pd.DataFrame([{'Date': day, 'Status': status, 'Target Hours': hours,
                              'Course': 'Calculus', 'Topic': 'Limits'}])

    def test_empty_plan(self):
        self.assertIn('Add courses', study_roast(pd.DataFrame(), self.today))

    def test_completed_plan(self):
        self.assertIn('All scheduled work is complete', study_roast(self.plan('Completed'), self.today))

    def test_overdue_has_action(self):
        self.assertIn('Use Adaptive Replan', study_roast(self.plan(day='2026-10-18'), self.today))

    def test_overloaded_plan(self):
        self.assertIn('Review daily capacity', study_roast(self.plan(hours=8), self.today))

    def test_today_and_rescheduled(self):
        for status in ['Pending', 'Rescheduled']:
            self.assertIn('Calculus / Limits (1.0h)', study_roast(self.plan(status), self.today))

    def test_free_day_is_not_called_complete(self):
        text = study_roast(self.plan(day='2026-10-20'), self.today)
        self.assertIn('next scheduled date', text)
        self.assertNotIn('All scheduled work is complete', text)

    def test_intensity_and_variation(self):
        plan = self.plan()
        self.assertTrue(study_roast(plan, self.today, intensity='Off').startswith('Next:'))
        self.assertTrue(study_roast(plan, self.today, intensity='Mild').startswith('One session'))
        self.assertIn('Procrastination', study_roast(plan, self.today, intensity='Extra spicy'))
        self.assertNotEqual(study_roast(plan, self.today), study_roast(plan, self.today, variation=1))


if __name__ == '__main__':
    unittest.main()
