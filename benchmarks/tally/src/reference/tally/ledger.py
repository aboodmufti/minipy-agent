"""Balances and registers computed from a journal."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .journal import Journal, Transaction
from .money import quantize
from .rates import RateTable
from .recurring import occurrences


@dataclass(frozen=True)
class RegisterRow:
    date: date
    account: str
    amount: Decimal
    currency: str
    memo: str
    running: Decimal  # running balance of the account, in the base currency


class Ledger:
    def __init__(self, journal: Journal):
        self.journal = journal
        self.rates = RateTable(journal.base)
        for price in journal.prices:
            self.rates.add(price.date, price.currency, price.rate)

    @property
    def base(self) -> str:
        return self.journal.base

    def end_date(self) -> date | None:
        """The latest date of any transaction, price or recurring rule start.

        None for an empty journal.
        """
        dates = [t.date for t in self.journal.transactions]
        dates += [p.date for p in self.journal.prices]
        dates += [rule.start for rule in self.journal.recurring]
        return max(dates) if dates else None

    def transactions(self, as_of: date | None = None) -> list[Transaction]:
        """Transactions dated on or before ``as_of`` (the end date if None).

        Includes the occurrences of recurring rules. Sorted by date; transactions on
        the same date keep their journal order (an occurrence uses its rule's line).
        """
        through = as_of if as_of is not None else self.end_date()
        if through is None:
            return []
        selected = [t for t in self.journal.transactions if t.date <= through]
        for rule in self.journal.recurring:
            selected.extend(
                Transaction(day, rule.account, rule.amount, rule.currency, rule.memo, rule.line)
                for day in occurrences(rule, through)
            )
        return sorted(selected, key=lambda t: (t.date, t.line))

    def balances(
        self, as_of: date | None = None, currency: str | None = None
    ) -> dict[str, Decimal]:
        """Balance of each account, sorted by account name, rounded to cents.

        Each transaction is converted to the base currency at the rate in effect on
        its own date. If ``currency`` is another currency, each base-currency total is
        then converted at that currency's rate on ``as_of`` (or on the end date).
        """
        totals: dict[str, Decimal] = defaultdict(Decimal)
        for t in self.transactions(as_of):
            totals[t.account] += self.rates.convert(t.amount, t.currency, t.date)
        target = currency or self.base
        if target != self.base and totals:
            on = as_of or self.end_date()
            rate = self.rates.rate(target, on)
            totals = {account: value / rate for account, value in totals.items()}
        return {account: quantize(totals[account]) for account in sorted(totals)}

    def register(
        self, account: str | None = None, as_of: date | None = None
    ) -> list[RegisterRow]:
        """Transactions with a running balance per account (in the base currency)."""
        rows = []
        running: dict[str, Decimal] = defaultdict(Decimal)
        for t in self.transactions(as_of):
            if account is not None and t.account != account:
                continue
            running[t.account] += self.rates.convert(t.amount, t.currency, t.date)
            rows.append(
                RegisterRow(
                    t.date,
                    t.account,
                    t.amount,
                    t.currency,
                    t.memo,
                    quantize(running[t.account]),
                )
            )
        return rows
