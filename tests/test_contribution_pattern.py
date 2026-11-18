import calendar
import importlib
import io
import random
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from unittest.mock import Mock, mock_open, patch

from chinese_calendar import is_workday

from contribution_pattern import LEVELS, generate_pattern, validate_calendar_range


MODULES = ("main", "main_cn", "main_month", "main_month_cn")


class PatternTests(unittest.TestCase):
    def test_holidays_weekends_and_makeup_workdays(self):
        rng = Mock()
        rng.choices.return_value = [4]
        rng.random.return_value = 0.1
        with patch("contribution_pattern.random.SystemRandom", return_value=rng):
            self.assertEqual(generate_pattern(date(2024, 1, 1), 7),
                             [0, 4, 4, 4, 4, 0, 0])
            # Spring Festival includes weekdays; Sunday Feb 18 is a makeup workday.
            self.assertEqual(generate_pattern(date(2024, 2, 10), 9),
                             [0] * 8 + [4])

    def test_rest_day_probability_boundary(self):
        rng = Mock()
        rng.random.side_effect = [0.0, 0.099999, 0.1, 0.999999]
        with patch("contribution_pattern.random.SystemRandom", return_value=rng):
            self.assertEqual(generate_pattern(date(2024, 2, 10), 4), [1, 1, 0, 0])
        rng.choices.assert_not_called()

    def test_leap_month_and_cross_year_dates(self):
        rng = Mock()
        rng.choices.return_value = [4]
        rng.random.return_value = 0.9
        with patch("contribution_pattern.random.SystemRandom", return_value=rng):
            february = generate_pattern(date(2024, 2, 1), 29)
            self.assertEqual(len(february), 29)
            self.assertEqual(february[-1], 4)
            self.assertEqual(generate_pattern(date(2023, 12, 29), 5), [4, 0, 0, 0, 4])

    def test_rest_day_volume_is_significantly_lower(self):
        rng = random.Random(2024)
        workday_counts = []
        rest_day_counts = []
        with patch("contribution_pattern.random.SystemRandom", return_value=rng):
            for _ in range(50):
                for offset, level in enumerate(generate_pattern(date(2024, 1, 1), 366)):
                    current = date(2024, 1, 1) + timedelta(days=offset)
                    counts = workday_counts if is_workday(current) else rest_day_counts
                    counts.append(LEVELS[str(level)])
        workday_mean = sum(workday_counts) / len(workday_counts)
        rest_day_mean = sum(rest_day_counts) / len(rest_day_counts)
        self.assertTrue(all(count in (0, 1) for count in rest_day_counts))
        self.assertGreater(rest_day_mean, 0.08)
        self.assertLess(rest_day_mean, 0.12)
        self.assertGreater(workday_mean, 3.8)
        self.assertLess(workday_mean, 4.3)
        self.assertLess(rest_day_mean, workday_mean * 0.05)

    def test_unsupported_range_fails_before_sampling(self):
        with patch("contribution_pattern.random.SystemRandom") as rng:
            with self.assertRaises(NotImplementedError):
                validate_calendar_range(date(2024, 1, 1), date(9998, 12, 31))
            with self.assertRaises(NotImplementedError):
                generate_pattern(date(2003, 12, 31), 2)
        rng.assert_not_called()


class ScriptTests(unittest.TestCase):
    def test_all_builders_use_actual_commit_dates(self):
        for name in MODULES:
            with self.subTest(script=name):
                module = importlib.import_module(name)
                monthly = "month" in name
                start = date(2024, 2, 1) if monthly else date(2024, 1, 1)
                days = calendar.monthrange(2024, 2)[1] if monthly else 366
                rng = Mock()
                rng.choices.return_value = [1]
                rng.random.return_value = 0.9
                with patch("contribution_pattern.random.SystemRandom", return_value=rng), \
                        patch.object(module, "run_cmd", return_value=True) as command, \
                        patch.object(module.os.path, "isfile", return_value=False), \
                        patch("builtins.open", mock_open()), redirect_stdout(io.StringIO()):
                    if monthly:
                        result = module.build_month_in_repo(
                            2024, 2, "unused", "user", "email", push_monthly=True)
                    else:
                        result = module.build_year_in_repo(2024, "unused", "user", "email")
                self.assertTrue(result)
                expected_dates = [
                    start + timedelta(days=offset) for offset in range(days)
                    if is_workday(start + timedelta(days=offset))
                ]
                commit_calls = [call for call in command.call_args_list
                                if call[0][0].startswith("git commit ")]
                actual_dates = [
                    datetime.fromisoformat(call[0][2]["GIT_AUTHOR_DATE"]).date()
                    for call in commit_calls
                ]
                self.assertEqual(actual_dates, expected_dates)
                for call in commit_calls:
                    self.assertEqual(call[0][2]["GIT_AUTHOR_DATE"],
                                     call[0][2]["GIT_COMMITTER_DATE"])
                if monthly:
                    self.assertEqual(command.call_args[0][0], "git push -u origin main")

    def test_unsupported_year_aborts_before_repository_operations(self):
        for name in MODULES:
            with self.subTest(script=name):
                module = importlib.import_module(name)
                start = datetime(2024, 1, 1) if "month" in name else 2024
                end = datetime(9998, 12, 1) if "month" in name else 9998
                answers = ["user", "email", start, end, "remote"]
                with patch.object(module, "ask", side_effect=answers), \
                        patch.object(module.os.path, "exists") as exists, \
                        patch.object(module, "run_cmd") as command, \
                        self.assertLogs(level="ERROR") as logs, \
                        redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        module.main()
                self.assertEqual(error.exception.code, 1)
                self.assertIn("9998", logs.output[0])
                exists.assert_not_called()
                command.assert_not_called()

    def test_empty_month_is_still_not_pushed(self):
        for name in ("main_month", "main_month_cn"):
            with self.subTest(script=name):
                module = importlib.import_module(name)
                rng = Mock()
                rng.choices.return_value = [0]
                rng.random.return_value = 0.9
                with patch("contribution_pattern.random.SystemRandom", return_value=rng), \
                        patch.object(module, "run_cmd") as command, \
                        patch.object(module.os.path, "isfile", return_value=False), \
                        redirect_stdout(io.StringIO()):
                    self.assertTrue(module.build_month_in_repo(
                        2024, 2, "unused", "user", "email", push_monthly=True))
                command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
