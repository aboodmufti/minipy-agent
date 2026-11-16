import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tally.cli import main

EXAMPLE = str(Path(__file__).resolve().parent.parent / "examples" / "household.journal")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def test_balance(self):
        code, out, _ = run("balance", EXAMPLE)
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            "checking         3,756.30 USD\n"
            "groceries          243.70 USD\n"
            "savings          2,169.00 USD\n"
            "-----------------------------\n"
            "Total            6,169.00 USD\n",
        )

    def test_balance_as_of_in_euros(self):
        code, out, _ = run("balance", EXAMPLE, "--as-of", "2026-03-01", "--currency", "EUR")
        self.assertEqual(code, 0)
        self.assertIn("savings          1,881.82 EUR\n", out)

    def test_register(self):
        code, out, _ = run("register", EXAMPLE, "--account", "savings")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            [
                "2026-01-01  savings                  1,000.00 EUR      1,080.00 USD  opening balance",
                "2026-03-01  savings                    900.00 EUR      2,070.00 USD  bonus",
                "2026-03-20  savings                     90.00 EUR      2,169.00 USD  interest",
            ],
        )

    def test_missing_file(self):
        code, _, err = run("balance", "/nonexistent.journal")
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("tally: error:"))
