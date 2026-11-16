"""Exchange-rate lookups against the journal's base currency."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import Decimal


class NoRateError(LookupError):
    """No price is known for a currency on the requested date."""


class RateTable:
    """Prices of currencies in the base currency.

    The rate in effect on a date is the most recent price dated on or before that
    date. If a currency has several prices on the same date, the one added last
    wins. Asking for a date before a currency's first price is an error.
    """

    def __init__(self, base: str):
        self.base = base
        self._prices: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
        self._index: dict[str, tuple[list[date], list[Decimal]]] = {}

    def add(self, on: date, currency: str, rate: Decimal) -> None:
        self._prices[currency].append((on, rate))
        self._index.pop(currency, None)

    def _sorted(self, currency: str) -> tuple[list[date], list[Decimal]]:
        index = self._index.get(currency)
        if index is None:
            # A stable sort by date keeps same-day prices in the order they were added.
            entries = sorted(self._prices.get(currency, []), key=lambda entry: entry[0])
            index = ([day for day, _ in entries], [rate for _, rate in entries])
            self._index[currency] = index
        return index

    def rate(self, currency: str, on: date) -> Decimal:
        if currency == self.base:
            return Decimal(1)
        days, rates = self._sorted(currency)
        position = bisect_right(days, on)
        if position == 0:
            raise NoRateError(f"no {currency} rate on or before {on.isoformat()}")
        return rates[position - 1]

    def convert(self, amount: Decimal, currency: str, on: date) -> Decimal:
        """Convert ``amount`` of ``currency`` to the base currency at the rate on ``on``."""
        return amount * self.rate(currency, on)
