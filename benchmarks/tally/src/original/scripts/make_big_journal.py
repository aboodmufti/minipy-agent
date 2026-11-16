"""Write a large, realistic journal for performance testing.

Usage: python scripts/make_big_journal.py [PATH]   (default: /tmp/big.journal)

The output is deterministic: the same file every time.
"""

import random
import sys
from datetime import date, timedelta

TRANSACTIONS = 200_000
FIRST_DAY = date(2021, 1, 1)
LAST_DAY = date(2026, 12, 31)
CURRENCIES = {"EUR": 1.08, "GBP": 1.27, "JPY": 0.0068}
ACCOUNTS = [
    f"{kind}:{name}"
    for kind in ("assets", "expenses", "income", "liabilities")
    for name in ("bank", "cash", "card", "travel", "food", "rent", "salary", "loan", "gifts", "fees")
]


def main(path: str) -> None:
    rng = random.Random(2026)
    days = (LAST_DAY - FIRST_DAY).days + 1
    lines = ["option base USD", ""]

    prices = []
    for currency, level in CURRENCIES.items():
        rate = level
        for offset in range(days):
            if offset and rng.random() < 0.1:
                continue  # no price that day
            rate *= 1 + rng.uniform(-0.004, 0.004)
            day = FIRST_DAY + timedelta(days=offset)
            prices.append(f"P {day.isoformat()} {currency} {rate:.6f}")
    # Prices are imported from several feeds, so they are not in date order.
    rng.shuffle(prices)
    lines += prices
    lines.append("")

    currencies = ["USD", "USD", *CURRENCIES]
    for _ in range(TRANSACTIONS):
        day = FIRST_DAY + timedelta(days=rng.randrange(1, days))
        account = rng.choice(ACCOUNTS)
        currency = rng.choice(currencies)
        amount = rng.randint(-250_000, 250_000) / 100
        if currency == "JPY":
            amount = round(amount * 150)
        lines.append(f"{day.isoformat()} {account} {amount:,.2f} {currency} txn")

    with open(path, "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    print(f"wrote {path}: {TRANSACTIONS} transactions")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/big.journal")
