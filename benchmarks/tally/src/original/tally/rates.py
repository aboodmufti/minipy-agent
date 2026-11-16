"""Exchange-rate lookups against the journal's base currency."""

from __future__ import annotations

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

    def add(self, on: date, currency: str, rate: Decimal) -> None:
        self._prices[currency].append((on, rate))

    def rate(self, currency: str, on: date) -> Decimal:
        if currency == self.base:
            return Decimal(1)
        entries = sorted(self._prices.get(currency, []))
        for day, rate in entries:
            if day >= on:
                return rate
        if entries:
            return entries[-1][1]
        raise NoRateError(f"no {currency} rate on or before {on.isoformat()}")

    def convert(self, amount: Decimal, currency: str, on: date) -> Decimal:
        """Convert ``amount`` of ``currency`` to the base currency at the rate on ``on``."""
        return amount * self.rate(currency, on)
