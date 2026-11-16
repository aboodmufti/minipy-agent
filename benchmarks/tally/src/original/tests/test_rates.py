import unittest
from datetime import date
from decimal import Decimal

from tally.rates import NoRateError, RateTable


class RateTableTest(unittest.TestCase):
    def setUp(self):
        self.table = RateTable("USD")
        self.table.add(date(2026, 1, 1), "EUR", Decimal("1.10"))
        self.table.add(date(2026, 2, 1), "EUR", Decimal("1.20"))

    def test_base_currency(self):
        self.assertEqual(self.table.rate("USD", date(2000, 1, 1)), Decimal(1))

    def test_on_price_date(self):
        self.assertEqual(self.table.rate("EUR", date(2026, 2, 1)), Decimal("1.20"))

    def test_after_last_price(self):
        self.assertEqual(self.table.rate("EUR", date(2026, 12, 31)), Decimal("1.20"))

    def test_unknown_currency(self):
        with self.assertRaises(NoRateError):
            self.table.rate("GBP", date(2026, 3, 1))

    def test_convert(self):
        self.assertEqual(
            self.table.convert(Decimal("10"), "EUR", date(2026, 2, 1)), Decimal("12.00")
        )
