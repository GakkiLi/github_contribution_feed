"""Date-aware contribution levels using the mainland China work calendar."""

import random
from datetime import date, timedelta
from typing import List

from chinese_calendar import is_workday

WEIGHTS = (30, 20, 15, 15, 5)
LEVELS = {"0": 0, "1": 1, "2": 5, "3": 10, "4": 20}


def validate_calendar_range(start_date: date, end_date: date) -> None:
    """Reject unsupported years before any repository changes."""
    is_workday(start_date)
    is_workday(end_date)


def generate_pattern(start_date: date, days: int) -> List[int]:
    """Keep workday weights; rest days have a 10% chance of one commit."""
    validate_calendar_range(start_date, start_date + timedelta(days=days - 1))
    rng = random.SystemRandom()
    pattern = []
    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        if is_workday(current_date):
            level = rng.choices([0, 1, 2, 3, 4], weights=WEIGHTS, k=1)[0]
        else:
            level = 1 if rng.random() < 0.1 else 0
        pattern.append(level)
    return pattern
