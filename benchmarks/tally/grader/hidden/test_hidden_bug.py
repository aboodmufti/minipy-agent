"""Hidden tests for the exchange-rate bug (docs/FORMAT.md, "Prices")."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from decimal import Decimal

from tally.cli import main
from tally.journal import parse
from tally.ledger import Ledger
from tally.rates import NoRateError, RateTable


def table(*prices):
    t = RateTable("USD")
    for day, currency, rate in prices:
        t.add(day, currency, Decimal(rate))
    return t


def cli(text, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".journal", delete=False) as f:
        f.write(text)
    try:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([*args[:1], f.name, *args[1:]])
        return code, out.getvalue(), err.getvalue()
    finally:
        os.unlink(f.name)


class RateLookupTest(unittest.TestCase):
    def test_between_prices_uses_earlier(self):
        t = table((date(2026, 1, 1), "EUR", "1.10"), (date(2026, 2, 1), "EUR", "1.20"))
        self.assertEqual(t.rate("EUR", date(2026, 1, 15)), Decimal("1.10"))
        self.assertEqual(t.rate("EUR", date(2026, 1, 31)), Decimal("1.10"))

    def test_many_prices(self):
        t = table(*[(date(2026, m, 1), "GBP", f"1.{m:02d}") for m in range(1, 13)])
        for m in range(1, 13):
            self.assertEqual(t.rate("GBP", date(2026, m, 20)), Decimal(f"1.{m:02d}"))

    def test_before_first_price_is_an_error(self):
        t = table((date(2026, 1, 1), "EUR", "1.10"))
        with self.assertRaises(NoRateError):
            t.rate("EUR", date(2025, 12, 31))

    def test_same_day_later_price_wins(self):
        t = table(
            (date(2026, 1, 1), "EUR", "1.30"),
            (date(2026, 1, 1), "EUR", "1.10"),
        )
        self.assertEqual(t.rate("EUR", date(2026, 1, 1)), Decimal("1.10"))
        self.assertEqual(t.rate("EUR", date(2026, 1, 9)), Decimal("1.10"))

    def test_prices_added_out_of_order(self):
        t = table(
            (date(2026, 3, 1), "EUR", "1.30"),
            (date(2026, 1, 1), "EUR", "1.10"),
            (date(2026, 2, 1), "EUR", "1.20"),
        )
        self.assertEqual(t.rate("EUR", date(2026, 2, 14)), Decimal("1.20"))
        self.assertEqual(t.rate("EUR", date(2026, 3, 14)), Decimal("1.30"))

    def test_price_added_after_lookup(self):
        t = table((date(2026, 1, 1), "EUR", "1.10"))
        self.assertEqual(t.rate("EUR", date(2026, 2, 10)), Decimal("1.10"))
        t.add(date(2026, 2, 1), "EUR", Decimal("1.20"))
        self.assertEqual(t.rate("EUR", date(2026, 2, 10)), Decimal("1.20"))


class LedgerConversionTest(unittest.TestCase):
    def test_transaction_between_prices(self):
        ledger = Ledger(
            parse(
                "P 2026-02-01 EUR 1.20\n"
                "P 2026-01-01 EUR 1.10\n"
                "2026-01-20 travel 100.00 EUR\n"
                "2026-02-20 travel 100.00 EUR\n"
            )
        )
        self.assertEqual(ledger.balances(), {"travel": Decimal("230.00")})

    def test_report_currency_uses_rate_on_report_date(self):
        ledger = Ledger(
            parse(
                "P 2026-01-01 EUR 1.25\n"
                "P 2026-02-01 EUR 1.60\n"
                "2026-01-01 bank 100.00 USD\n"
            )
        )
        self.assertEqual(
            ledger.balances(as_of=date(2026, 1, 31), currency="EUR"),
            {"bank": Decimal("80.00")},
        )

    def test_transaction_before_first_price_fails(self):
        ledger = Ledger(parse("P 2026-02-01 EUR 1.20\n2026-01-20 travel 5.00 EUR\n"))
        with self.assertRaises(NoRateError):
            ledger.balances()

    def test_cli_reports_missing_rate(self):
        code, out, err = cli("P 2026-02-01 EUR 1.20\n2026-01-20 travel 5.00 EUR\n", "balance")
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("tally: error:"))
        self.assertIn("EUR", err)
