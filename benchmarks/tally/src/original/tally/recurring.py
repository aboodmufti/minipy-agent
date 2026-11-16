"""Recurring transactions. Specification: docs/recurring.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


def occurrences(rule: RecurringRule, through: date) -> list[date]:
    """Every occurrence date of ``rule`` from its start through ``through``.

    Both ends are inclusive, and ``rule.until`` (if set) also limits the result.
    Dates are returned in ascending order.
    """
    raise NotImplementedError("recurring transactions are not implemented yet")
