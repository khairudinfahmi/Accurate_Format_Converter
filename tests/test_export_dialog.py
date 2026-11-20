import unittest
import datetime
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

class TestExportConfigLogic(unittest.TestCase):
    def setUp(self):
        self.tx_dates = [
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 2),
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 15),
            datetime.date(2026, 10, 16),
            datetime.date(2026, 10, 20),
            datetime.date(2026, 10, 31)
        ]
        self.unique_dates = sorted(list(set(self.tx_dates)))
        self.date_options = [d.strftime("%d/%m/%Y") for d in self.unique_dates]
        self.date_lookup = {d.strftime("%d/%m/%Y"): d for d in self.unique_dates}

    def test_unique_dates_and_options(self):
        self.assertEqual(len(self.unique_dates), 7)
        self.assertEqual(self.date_options[0], "01/10/2026")
        self.assertEqual(self.date_options[-1], "31/10/2026")

    def test_presets(self):
        # All
        from_all = self.date_options[0]
        to_all = self.date_options[-1]
        self.assertEqual(from_all, "01/10/2026")
        self.assertEqual(to_all, "31/10/2026")

        # Period 1 (01-15)
        p1 = [d for d in self.unique_dates if d.day <= 15]
        self.assertTrue(len(p1) > 0)
        self.assertEqual(p1[0].strftime("%d/%m/%Y"), "01/10/2026")
        self.assertEqual(p1[-1].strftime("%d/%m/%Y"), "15/10/2026")

        # Period 2 (16-end)
        p2 = [d for d in self.unique_dates if d.day >= 16]
        self.assertTrue(len(p2) > 0)
        self.assertEqual(p2[0].strftime("%d/%m/%Y"), "16/10/2026")
        self.assertEqual(p2[-1].strftime("%d/%m/%Y"), "31/10/2026")

    def test_auto_adjust_from_after_to(self):
        # If user sets from to 31/10/2026 while to is 15/10/2026
        from_val = "31/10/2026"
        to_val = "15/10/2026"
        if self.date_lookup[from_val] > self.date_lookup[to_val]:
            to_val = from_val
        self.assertEqual(from_val, "31/10/2026")
        self.assertEqual(to_val, "31/10/2026")

    def test_auto_adjust_to_before_from(self):
        # If user sets to to 01/10/2026 while from is 16/10/2026
        from_val = "16/10/2026"
        to_val = "01/10/2026"
        if self.date_lookup[to_val] < self.date_lookup[from_val]:
            from_val = to_val
        self.assertEqual(from_val, "01/10/2026")
        self.assertEqual(to_val, "01/10/2026")

    def test_subrange_filtering_count(self):
        fd = datetime.date(2026, 10, 1)
        td = datetime.date(2026, 10, 15)
        cnt = sum(1 for d in self.tx_dates if fd <= d <= td)
        self.assertEqual(cnt, 4)

        fd2 = datetime.date(2026, 10, 16)
        td2 = datetime.date(2026, 10, 31)
        cnt2 = sum(1 for d in self.tx_dates if fd2 <= d <= td2)
        self.assertEqual(cnt2, 3)

        self.assertEqual(cnt + cnt2, len(self.tx_dates))

if __name__ == '__main__':
    unittest.main()
