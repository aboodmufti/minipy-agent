import unittest
from datetime import date
from decimal import Decimal

from tally.journal import JournalError, parse

SAMPLE = """\
# a comment
option base EUR

P 2026-01-01 USD 0.92   ; dollars
2026-01-02 assets:bank 1,200.00 EUR salary for December
2026-01-03 expenses:food (12.30) EUR
"""


class ParseTest(unittest.TestCase):
    def test_sample(self):
        journal = parse(SAMPLE)
        self.assertEqual(journal.base, "EUR")
        self.assertEqual(len(journal.prices), 1)
        self.assertEqual(journal.prices[0].rate, Decimal("0.92"))
        first, second = journal.transactions
        self.assertEqual(first.date, date(2026, 1, 2))
        self.assertEqual(first.account, "assets:bank")
        self.assertEqual(first.amount, Decimal("1200.00"))
        self.assertEqual(first.memo, "salary for December")
        self.assertEqual(first.line, 5)
        self.assertEqual(second.amount, Decimal("-12.30"))
        self.assertEqual(second.memo, "")

    def test_default_base_is_usd(self):
        self.assertEqual(parse("").base, "USD")

    def test_errors_carry_line_numbers(self):
        cases = {
            "2026-01-01 bank 1.00 USD\nnonsense here\n": 2,
            "\n\n2026-13-01 bank 1.00 USD\n": 3,
            "2026-01-01 bank 1.00x USD\n": 1,
            "P 2026-01-01 EUR -1.00\n": 1,
        }
        for text, line in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(JournalError) as caught:
                    parse(text)
                self.assertEqual(caught.exception.line, line)
                self.assertTrue(str(caught.exception).startswith(f"line {line}:"))
