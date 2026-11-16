"""Command line: ``python -m tally balance|register JOURNAL [options]``."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

from . import __version__
from .journal import JournalError, load
from .ledger import Ledger
from .money import format_amount
from .rates import NoRateError


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tally", description="Plain-text ledger.")
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    balance = commands.add_parser("balance", help="account balances")
    balance.add_argument("journal")
    balance.add_argument("--as-of", type=_date, help="include transactions up to DATE")
    balance.add_argument("--currency", help="report in this currency")

    register = commands.add_parser("register", help="transactions with running totals")
    register.add_argument("journal")
    register.add_argument("--account", help="only this account")
    register.add_argument("--as-of", type=_date, help="include transactions up to DATE")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ledger = Ledger(load(args.journal))
        if args.command == "balance":
            _print_balance(ledger, args.as_of, args.currency)
        else:
            _print_register(ledger, args.account, args.as_of)
    except (JournalError, NoRateError, OSError) as error:
        print(f"tally: error: {error}", file=sys.stderr)
        return 1
    return 0


def _print_balance(ledger: Ledger, as_of: date | None, currency: str | None) -> None:
    unit = currency or ledger.base
    balances = ledger.balances(as_of, currency)
    width = max([len(account) for account in balances] + [len("Total")])
    for account, value in balances.items():
        print(f"{account:<{width}}  {format_amount(value):>14} {unit}")
    print("-" * (width + 17 + len(unit)))
    total = sum(balances.values(), Decimal(0))
    print(f"{'Total':<{width}}  {format_amount(total):>14} {unit}")


def _print_register(ledger: Ledger, account: str | None, as_of: date | None) -> None:
    for row in ledger.register(account, as_of):
        line = (
            f"{row.date.isoformat()}  {row.account:<20} "
            f"{format_amount(row.amount):>12} {row.currency}  "
            f"{format_amount(row.running):>12} {ledger.base}  {row.memo}"
        )
        print(line.rstrip())
