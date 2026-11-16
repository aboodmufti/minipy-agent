import unittest
from decimal import Decimal

from tally.money import format_amount, parse_amount, quantize


class ParseAmountTest(unittest.TestCase):
    def test_plain_and_negative(self):
        self.assertEqual(parse_amount("12.50"), Decimal("12.50"))
        self.assertEqual(parse_amount("-3"), Decimal("-3"))

    def test_thousands_separator(self):
        self.assertEqual(parse_amount("1,234,567.89"), Decimal("1234567.89"))

    def test_parentheses_are_negative(self):
        self.assertEqual(parse_amount("(12.50)"), Decimal("-12.50"))

    def test_invalid(self):
        for text in ("", "abc", "1.2.3", "NaN", "Infinity"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_amount(text)


class FormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_amount(Decimal("1234.5")), "1,234.50")
        self.assertEqual(format_amount(Decimal("-0.004")), "0.00")
        self.assertEqual(format_amount(Decimal("-1234567.891")), "-1,234,567.89")

    def test_quantize_half_even(self):
        self.assertEqual(quantize(Decimal("0.125")), Decimal("0.12"))
        self.assertEqual(quantize(Decimal("0.135")), Decimal("0.14"))
