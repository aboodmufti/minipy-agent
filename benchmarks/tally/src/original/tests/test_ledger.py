import unittest
from datetime import date
from decimal import Decimal

from tally.journal import parse
from tally.ledger import Ledger

JOURNAL = """\
P 2026-01-01 EUR 1.10
P 2026-02-01 EUR 1.20
2026-01-01 bank 100.00 USD
2026-01-01 travel 10.00 EUR
2026-02-01 bank -40.00 USD
2026-02-03 travel 5.00 EUR
"""


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(parse(JOURNAL))

    def test_balances(self):
        self.assertEqual(
            self.ledger.balances(),
            {"bank": Decimal("60.00"), "travel": Decimal("17.00")},
        )

    def test_balances_as_of(self):
        self.assertEqual(
            self.ledger.balances(as_of=date(2026, 1, 31)),
            {"bank": Decimal("100.00"), "travel": Decimal("11.00")},
        )

    def test_balances_in_other_currency(self):
        # Base totals 60.00 and 17.00 USD, converted at the EUR rate on 2026-02-03 (1.20).
        self.assertEqual(
            self.ledger.balances(currency="EUR"),
            {"bank": Decimal("50.00"), "travel": Decimal("14.17")},
        )

    def test_converts_at_rate_in_effect_on_transaction_date(self):
        ledger = Ledger(
            parse(
                "P 2026-01-01 EUR 1.10\n"
                "P 2026-02-01 EUR 1.20\n"
                "2026-01-15 travel 100.00 EUR mid-January\n"
            )
        )
        self.assertEqual(ledger.balances(), {"travel": Decimal("110.00")})

    def test_register_running_balance(self):
        rows = self.ledger.register(account="travel")
        self.assertEqual([row.running for row in rows], [Decimal("11.00"), Decimal("17.00")])

    def test_end_date(self):
        self.assertEqual(self.ledger.end_date(), date(2026, 2, 3))
