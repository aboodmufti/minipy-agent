"""Parser for the plain-text journal format described in docs/FORMAT.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from .money import parse_amount


class JournalError(ValueError):
    """An invalid journal line. ``str(error)`` starts with ``line N:``."""

    def __init__(self, line: int, message: str):
        super().__init__(f"line {line}: {message}")
        self.line = line


@dataclass(frozen=True)
class Transaction:
    date: date
    account: str
    amount: Decimal
    currency: str
    memo: str = ""
    line: int = 0


@dataclass(frozen=True)
class Price:
    """One unit of ``currency`` is worth ``rate`` units of the base currency."""

    date: date
    currency: str
    rate: Decimal
    line: int = 0


@dataclass
class Journal:
    base: str = "USD"
    transactions: list[Transaction] = field(default_factory=list)
    prices: list[Price] = field(default_factory=list)


_DATE = r"\d{4}-\d{2}-\d{2}"
_ACCOUNT = r"[A-Za-z][\w:-]*"
_CURRENCY = r"[A-Z]{3}"
_TRANSACTION = re.compile(
    rf"^({_DATE})\s+({_ACCOUNT})\s+(\S+)\s+({_CURRENCY})(?:\s+(.*))?$"
)
_PRICE = re.compile(rf"^P\s+({_DATE})\s+({_CURRENCY})\s+(\S+)$")
_BASE = re.compile(rf"^option\s+base\s+({_CURRENCY})$")


def parse_date(text: str, line: int) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise JournalError(line, f"invalid date {text!r}") from None


def _amount(text: str, line: int) -> Decimal:
    try:
        return parse_amount(text)
    except ValueError as error:
        raise JournalError(line, str(error)) from None


def _strip_comment(raw: str) -> str:
    """Remove a ``;`` comment anywhere on the line, or a ``#`` comment line."""
    text = raw.split(";", 1)[0].strip()
    return "" if text.startswith("#") else text


def parse(text: str) -> Journal:
    """Parse journal text. Raises ``JournalError`` for the first invalid line."""
    journal = Journal()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw)
        if not line:
            continue
        if match := _TRANSACTION.match(line):
            journal.transactions.append(
                Transaction(
                    date=parse_date(match[1], number),
                    account=match[2],
                    amount=_amount(match[3], number),
                    currency=match[4],
                    memo=(match[5] or "").strip(),
                    line=number,
                )
            )
        elif match := _PRICE.match(line):
            rate = _amount(match[3], number)
            if rate <= 0:
                raise JournalError(number, f"rate must be positive, got {match[3]}")
            journal.prices.append(
                Price(parse_date(match[1], number), match[2], rate, number)
            )
        elif match := _BASE.match(line):
            journal.base = match[1]
        else:
            raise JournalError(number, f"cannot parse {line!r}")
    return journal


def load(path: str | Path) -> Journal:
    return parse(Path(path).read_text(encoding="utf-8"))
