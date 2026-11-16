"""Hidden tests for recurring transactions (docs/recurring.md)."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from decimal import Decimal

from tally.cli import main
from tally.journal import JournalError, parse
from tally.ledger import Ledger
from tally.recurring import RecurringRule, occurrences


def rule(freq, start, interval=1, until=None):
    return RecurringRule(
        freq=freq,
        interval=interval,
        start=start,
        account="bank",
        amount=Decimal("-1.00"),
        currency="USD",
        until=until,
    )


def dates(*items):
    return [date.fromisoformat(item) for item in items]


def cli(text, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".journal", delete=False) as f:
        f.write(text)
    try:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([args[0], f.name, *args[1:]])
        return code, out.getvalue(), err.getvalue()
    finally:
        os.unlink(f.name)


class OccurrenceDatesTest(unittest.TestCase):
    def test_daily(self):
        self.assertEqual(
            occurrences(rule("daily", date(2026, 2, 26)), date(2026, 3, 2)),
            dates("2026-02-26", "2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"),
        )

    def test_daily_every_seven_equals_weekly(self):
        start, through = date(2026, 1, 3), date(2026, 6, 30)
        self.assertEqual(
            occurrences(rule("daily", start, 7), through),
            occurrences(rule("weekly", start), through),
        )

    def test_weekly_every_three_weeks(self):
        self.assertEqual(
            occurrences(rule("weekly", date(2026, 12, 18), 3), date(2027, 1, 29)),
            dates("2026-12-18", "2027-01-08", "2027-01-29"),
        )

    def test_monthly_from_31st_in_common_year(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2027, 1, 31)), date(2027, 7, 31)),
            dates(
                "2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30",
                "2027-05-31", "2027-06-30", "2027-07-31",
            ),
        )

    def test_monthly_from_29th_in_leap_and_common_years(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2027, 12, 29)), date(2028, 3, 29)),
            dates("2027-12-29", "2028-01-29", "2028-02-29", "2028-03-29"),
        )
        self.assertEqual(
            occurrences(rule("monthly", date(2026, 1, 29)), date(2026, 3, 29)),
            dates("2026-01-29", "2026-02-28", "2026-03-29"),
        )

    def test_monthly_from_30th(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2026, 1, 30)), date(2026, 4, 30)),
            dates("2026-01-30", "2026-02-28", "2026-03-30", "2026-04-30"),
        )

    def test_quarterly_across_years(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2026, 8, 31), 3), date(2027, 6, 1)),
            dates("2026-08-31", "2026-11-30", "2027-02-28", "2027-05-31"),
        )

    def test_every_twelve_months_equals_yearly(self):
        start, through = date(2024, 2, 29), date(2033, 1, 1)
        self.assertEqual(
            occurrences(rule("monthly", start, 12), through),
            occurrences(rule("yearly", start), through),
        )

    def test_yearly_from_leap_day(self):
        self.assertEqual(
            occurrences(rule("yearly", date(2028, 2, 29)), date(2032, 12, 31)),
            dates("2028-02-29", "2029-02-28", "2030-02-28", "2031-02-28", "2032-02-29"),
        )

    def test_every_other_year(self):
        self.assertEqual(
            occurrences(rule("yearly", date(2026, 7, 4), 2), date(2032, 7, 3)),
            dates("2026-07-04", "2028-07-04", "2030-07-04"),
        )

    def test_until_inclusive_and_earlier_than_through(self):
        self.assertEqual(
            occurrences(
                rule("weekly", date(2026, 1, 5), until=date(2026, 1, 26)), date(2026, 12, 31)
            ),
            dates("2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26"),
        )

    def test_through_earlier_than_until(self):
        self.assertEqual(
            occurrences(
                rule("monthly", date(2026, 1, 10), until=date(2026, 12, 31)), date(2026, 3, 10)
            ),
            dates("2026-01-10", "2026-02-10", "2026-03-10"),
        )

    def test_through_before_start(self):
        self.assertEqual(occurrences(rule("monthly", date(2026, 5, 1)), date(2026, 4, 30)), [])

    def test_through_on_start(self):
        self.assertEqual(
            occurrences(rule("yearly", date(2026, 5, 1)), date(2026, 5, 1)), dates("2026-05-01")
        )

    def test_until_on_start(self):
        self.assertEqual(
            occurrences(
                rule("daily", date(2026, 5, 1), until=date(2026, 5, 1)), date(2027, 1, 1)
            ),
            dates("2026-05-01"),
        )

    def test_through_last_representable_date(self):
        result = occurrences(rule("yearly", date(9990, 3, 15)), date.max)
        self.assertEqual(result[0], date(9990, 3, 15))
        self.assertEqual(result[-1], date(9999, 3, 15))
        self.assertEqual(len(result), 10)
        self.assertEqual(
            occurrences(rule("weekly", date(9999, 12, 1)), date.max)[-1], date(9999, 12, 29)
        )

    def test_ten_years_daily(self):
        start, through = date(2026, 1, 1), date(2035, 12, 31)
        result = occurrences(rule("daily", start), through)
        self.assertEqual(len(result), (through - start).days + 1)
        self.assertEqual(result[-1], through)
        self.assertTrue(all(b - a == timedelta(days=1) for a, b in zip(result, result[1:])))


class ParseRuleTest(unittest.TestCase):
    def test_minimal_rule(self):
        journal = parse("\n# rent\n~ monthly 2026-01-31 checking -1,450.00 USD\n")
        (r,) = journal.recurring
        self.assertIsInstance(r, RecurringRule)
        self.assertEqual(
            (r.freq, r.interval, r.start, r.until, r.account, r.amount, r.currency, r.memo, r.line),
            ("monthly", 1, date(2026, 1, 31), None, "checking", Decimal("-1450.00"), "USD", "", 3),
        )

    def test_full_rule_with_comment(self):
        (r,) = parse(
            "~ weekly/2 2026-01-02 until 2026-06-30 assets:bank (40.00) EUR the cleaner ; cash\n"
        ).recurring
        self.assertEqual(
            (r.freq, r.interval, r.until, r.account, r.amount, r.currency, r.memo),
            ("weekly", 2, date(2026, 6, 30), "assets:bank", Decimal("-40.00"), "EUR", "the cleaner"),
        )

    def test_rules_in_file_order_alongside_other_entries(self):
        journal = parse(
            "option base EUR\n"
            "~ yearly 2024-02-29 savings 100.00 EUR leap\n"
            "P 2026-01-01 USD 0.90\n"
            "2026-01-02 bank 5.00 EUR\n"
            "~ daily/3 2026-01-01 bank -0.50 EUR coffee\n"
        )
        self.assertEqual([(r.freq, r.line) for r in journal.recurring], [("yearly", 2), ("daily", 5)])
        self.assertEqual(journal.recurring[1].interval, 3)
        self.assertEqual(len(journal.transactions), 1)
        self.assertEqual(len(journal.prices), 1)
        self.assertEqual(journal.base, "EUR")

    def test_invalid_rules_report_their_line(self):
        bad = {
            "unknown frequency": "~ biweekly 2026-01-01 bank -1.00 USD",
            "zero interval": "~ weekly/0 2026-01-01 bank -1.00 USD",
            "negative interval": "~ weekly/-2 2026-01-01 bank -1.00 USD",
            "non-numeric interval": "~ weekly/two 2026-01-01 bank -1.00 USD",
            "bad start": "~ weekly 2026-13-01 bank -1.00 USD",
            "bad until": "~ weekly 2026-01-01 until 2026-02-30 bank -1.00 USD",
            "until before start": "~ weekly 2026-01-08 until 2026-01-07 bank -1.00 USD",
            "bad amount": "~ weekly 2026-01-01 bank 1.2.3 USD",
        }
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(JournalError) as caught:
                parse("2026-01-01 bank 1.00 USD\n\n" + text + "\n")
            self.assertEqual(caught.exception.line, 3, name)
            self.assertTrue(str(caught.exception).startswith("line 3:"), name)


class LedgerWithRulesTest(unittest.TestCase):
    JOURNAL = (
        "option base USD\n"
        "P 2026-01-01 EUR 1.10\n"
        "P 2026-02-01 EUR 1.20\n"
        "P 2026-03-01 EUR 1.50\n"
        "2026-01-01 checking 5,000.00 USD opening\n"
        "~ monthly 2026-01-31 checking -1,000.00 USD rent\n"
        "~ monthly 2026-01-01 until 2026-02-01 travel 100.00 EUR pass\n"
        "2026-03-31 checking 0.00 USD check\n"
    )

    def setUp(self):
        self.ledger = Ledger(parse(self.JOURNAL))

    def test_balances_as_of(self):
        self.assertEqual(
            self.ledger.balances(as_of=date(2026, 3, 30)),
            {"checking": Decimal("3000.00"), "travel": Decimal("230.00")},
        )

    def test_balances_through_end_date(self):
        self.assertEqual(self.ledger.end_date(), date(2026, 3, 31))
        self.assertEqual(
            self.ledger.balances(),
            {"checking": Decimal("2000.00"), "travel": Decimal("230.00")},
        )

    def test_report_currency_with_rules(self):
        self.assertEqual(
            self.ledger.balances(as_of=date(2026, 3, 1), currency="EUR"),
            {"checking": Decimal("2000.00"), "travel": Decimal("153.33")},
        )

    def test_register_includes_occurrences_in_order(self):
        rows = self.ledger.register(account="checking", as_of=date(2026, 3, 31))
        self.assertEqual(
            [(row.date, row.memo, row.running) for row in rows],
            [
                (date(2026, 1, 1), "opening", Decimal("5000.00")),
                (date(2026, 1, 31), "rent", Decimal("4000.00")),
                (date(2026, 2, 28), "rent", Decimal("3000.00")),
                (date(2026, 3, 31), "rent", Decimal("2000.00")),
                (date(2026, 3, 31), "check", Decimal("2000.00")),
            ],
        )

    def test_end_date_counts_rule_start(self):
        ledger = Ledger(parse("2026-01-01 bank 1.00 USD\n~ yearly 2026-06-01 bank 2.00 USD\n"))
        self.assertEqual(ledger.end_date(), date(2026, 6, 1))
        self.assertEqual(ledger.balances(), {"bank": Decimal("3.00")})

    def test_only_rules(self):
        ledger = Ledger(parse("~ weekly 2026-06-01 bank 2.00 USD\n"))
        self.assertEqual(ledger.end_date(), date(2026, 6, 1))
        self.assertEqual(ledger.balances(as_of=date(2026, 6, 22)), {"bank": Decimal("8.00")})

    def test_as_of_first_day(self):
        self.assertEqual(
            self.ledger.balances(as_of=date(2026, 1, 1)),
            {"checking": Decimal("5000.00"), "travel": Decimal("110.00")},
        )


class CliWithRulesTest(unittest.TestCase):
    TEXT = (
        "2026-01-01 checking 1,000.00 USD opening\n"
        "~ weekly/2 2026-01-02 until 2026-01-30 checking -40.00 USD cleaner\n"
        "~ monthly 2026-01-31 checking -500.00 USD rent\n"
    )

    def test_balance(self):
        code, out, _ = cli(self.TEXT, "balance", "--as-of", "2026-02-28")
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            "checking         -120.00 USD\n"
            "----------------------------\n"
            "Total            -120.00 USD\n",
        )

    def test_register(self):
        code, out, _ = cli(self.TEXT, "register", "--as-of", "2026-01-31")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            [
                "2026-01-01  checking                 1,000.00 USD      1,000.00 USD  opening",
                "2026-01-02  checking                   -40.00 USD        960.00 USD  cleaner",
                "2026-01-16  checking                   -40.00 USD        920.00 USD  cleaner",
                "2026-01-30  checking                   -40.00 USD        880.00 USD  cleaner",
                "2026-01-31  checking                  -500.00 USD        380.00 USD  rent",
            ],
        )

    def test_invalid_rule_is_reported(self):
        code, _, err = cli("~ hourly 2026-01-01 bank 1.00 USD\n", "balance")
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("tally: error: line 1:"))
