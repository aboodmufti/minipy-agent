"""Recurring transactions. Specification: docs/recurring.md."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

FREQUENCIES = ("daily", "weekly", "monthly", "yearly")


@dataclass(frozen=True)
class RecurringRule:
    freq: str  # one of FREQUENCIES
    interval: int  # every N periods; 1 for plain "monthly" etc.
    start: date
    account: str
    amount: Decimal
    currency: str
    memo: str = ""
    until: date | None = None  # inclusive
    line: int = 0


def _add_months(start: date, months: int) -> date:
    """``start`` moved by ``months``, clamped to the last day of a shorter month."""
    year, month_index = divmod(start.month - 1 + months, 12)
    year += start.year
    month = month_index + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _occurrence(rule: RecurringRule, k: int) -> date:
    """Occurrence number ``k`` (0 is the start), always computed from the start."""
    n = k * rule.interval
    if rule.freq == "daily":
        return rule.start + timedelta(days=n)
    if rule.freq == "weekly":
        return rule.start + timedelta(weeks=n)
    if rule.freq == "monthly":
        return _add_months(rule.start, n)
    if rule.freq == "yearly":
        return _add_months(rule.start, 12 * n)
    raise ValueError(f"unknown frequency {rule.freq!r}")


def occurrences(rule: RecurringRule, through: date) -> list[date]:
    """Every occurrence date of ``rule`` from its start through ``through``.

    Both ends are inclusive, and ``rule.until`` (if set) also limits the result.
    Dates are returned in ascending order.
    """
    if rule.freq not in FREQUENCIES:
        raise ValueError(f"unknown frequency {rule.freq!r}")
    last = through if rule.until is None else min(through, rule.until)
    result = []
    k = 0
    while True:
        try:
            day = _occurrence(rule, k)
        except (OverflowError, ValueError):
            break  # past the last date Python can represent (9999-12-31)
        if day > last:
            break
        result.append(day)
        k += 1
    return result
