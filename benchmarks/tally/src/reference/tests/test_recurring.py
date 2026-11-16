import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
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
        amount=Decimal("-10.00"),
        currency="USD",
        until=until,
    )


class OccurrencesTest(unittest.TestCase):
    def test_daily_with_interval_includes_through(self):
        self.assertEqual(
            occurrences(rule("daily", date(2026, 1, 1), 3), date(2026, 1, 10)),
            [date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 7), date(2026, 1, 10)],
        )

    def test_weekly_every_two_weeks(self):
        self.assertEqual(
            occurrences(rule("weekly", date(2026, 1, 2), 2), date(2026, 2, 13)),
            [date(2026, 1, 2), date(2026, 1, 16), date(2026, 1, 30), date(2026, 2, 13)],
        )

    def test_monthly_from_31st_does_not_drift(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2026, 1, 31)), date(2026, 5, 31)),
            [
                date(2026, 1, 31),
                date(2026, 2, 28),
                date(2026, 3, 31),
                date(2026, 4, 30),
                date(2026, 5, 31),
            ],
        )

    def test_monthly_in_leap_february(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2024, 1, 31)), date(2024, 3, 31)),
            [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)],
        )

    def test_quarterly_across_year_end(self):
        self.assertEqual(
            occurrences(rule("monthly", date(2025, 11, 30), 3), date(2026, 8, 31)),
            [date(2025, 11, 30), date(2026, 2, 28), date(2026, 5, 30), date(2026, 8, 30)],
        )

    def test_yearly_from_leap_day(self):
        self.assertEqual(
            occurrences(rule("yearly", date(2024, 2, 29)), date(2028, 3, 1)),
            [
                date(2024, 2, 29),
                date(2025, 2, 28),
                date(2026, 2, 28),
                date(2027, 2, 28),
                date(2028, 2, 29),
            ],
        )

    def test_until_is_inclusive(self):
        r = rule("monthly", date(2026, 1, 15), until=date(2026, 3, 15))
        self.assertEqual(
            occurrences(r, date(2026, 12, 31)),
            [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
        )

    def test_through_last_representable_date(self):
        self.assertEqual(
            occurrences(rule("monthly", date(9999, 10, 31)), date.max),
            [date(9999, 10, 31), date(9999, 11, 30), date(9999, 12, 31)],
        )

    def test_boundaries_at_start(self):
        start = date(2026, 5, 5)
        self.assertEqual(occurrences(rule("weekly", start), start), [start])
        self.assertEqual(occurrences(rule("weekly", start), date(2026, 5, 4)), [])


class ParseTest(unittest.TestCase):
    def test_full_rule(self):
        journal = parse(
            "2026-01-01 bank 5.00 USD\n"
            "~ weekly/2 2026-01-02 until 2026-06-30 bank -1,040.00 EUR cleaner ; note\n"
        )
        (r,) = journal.recurring
        self.assertEqual(r.freq, "weekly")
        self.assertEqual(r.interval, 2)
        self.assertEqual(r.start, date(2026, 1, 2))
        self.assertEqual(r.until, date(2026, 6, 30))
        self.assertEqual(r.account, "bank")
        self.assertEqual(r.amount, Decimal("-1040.00"))
        self.assertEqual(r.currency, "EUR")
        self.assertEqual(r.memo, "cleaner")
        self.assertEqual(r.line, 2)
        self.assertEqual(len(journal.transactions), 1)

    def test_defaults(self):
        (r,) = parse("~ monthly 2026-01-31 bank -1.00 USD\n").recurring
        self.assertEqual((r.interval, r.until, r.memo), (1, None, ""))

    def test_invalid_rules(self):
        bad = [
            "~ fortnightly 2026-01-01 bank -1.00 USD",
            "~ monthly/0 2026-01-01 bank -1.00 USD",
            "~ monthly/x 2026-01-01 bank -1.00 USD",
            "~ monthly 2026-02-30 bank -1.00 USD",
            "~ monthly 2026-03-01 until 2026-02-01 bank -1.00 USD",
            "~ monthly 2026-03-01 bank -1.0.0 USD",
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(JournalError) as caught:
                parse("2026-01-01 bank 1.00 USD\n" + text + "\n")
            self.assertEqual(caught.exception.line, 2)


class LedgerTest(unittest.TestCase):
    def test_foreign_rule_converted_on_each_date(self):
        ledger = Ledger(
            parse(
                "P 2026-01-01 EUR 1.10\n"
                "P 2026-02-01 EUR 1.20\n"
                "~ monthly 2026-01-01 travel 100.00 EUR\n"
            )
        )
        self.assertEqual(
            ledger.balances(as_of=date(2026, 2, 1)), {"travel": Decimal("230.00")}
        )

    def test_same_day_order_follows_lines(self):
        ledger = Ledger(
            parse(
                "~ monthly 2026-01-01 bank -30.00 USD rent\n"
                "2026-01-01 bank 100.00 USD salary\n"
            )
        )
        rows = ledger.register(as_of=date(2026, 1, 1))
        self.assertEqual([row.memo for row in rows], ["rent", "salary"])
        self.assertEqual([row.running for row in rows], [Decimal("-30.00"), Decimal("70.00")])

    def test_empty_journal_in_other_currency(self):
        self.assertEqual(Ledger(parse("")).balances(currency="EUR"), {})

    def test_end_date_includes_rule_start(self):
        ledger = Ledger(
            parse("2026-01-01 bank 10.00 USD\n~ monthly 2026-03-01 bank -1.00 USD\n")
        )
        self.assertEqual(ledger.end_date(), date(2026, 3, 1))
        self.assertEqual(ledger.balances(), {"bank": Decimal("9.00")})

    def test_cli_register(self):
        with tempfile.NamedTemporaryFile("w", suffix=".journal", delete=False) as f:
            f.write("2026-01-01 bank 100.00 USD\n~ monthly/2 2026-01-31 bank -10.00 USD fee\n")
        self.addCleanup(os.unlink, f.name)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["register", f.name, "--as-of", "2026-05-31"])
        self.assertEqual(code, 0)
        self.assertEqual(
            [line.split()[0] for line in out.getvalue().splitlines()],
            ["2026-01-01", "2026-01-31", "2026-03-31", "2026-05-31"],
        )
