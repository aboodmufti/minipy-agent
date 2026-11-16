# Journal format

A journal is a UTF-8 text file with one entry per line. Blank lines are ignored.

## Comments

- A line whose first non-space character is `#` is a comment.
- `;` starts a comment anywhere on a line; the rest of the line is ignored.

## Base currency

```
option base USD
```

All balances are computed in the base currency. The default is `USD`.

## Transactions

```
DATE ACCOUNT AMOUNT CURRENCY [MEMO]
2026-03-02 checking -45.20 USD groceries
2026-03-02 savings 1,000.00 EUR transfer from checking
2026-03-03 checking (12.50) USD refund reversed
```

- `DATE` is an ISO date, `YYYY-MM-DD`.
- `ACCOUNT` starts with a letter and may contain letters, digits, `_`, `-` and `:`
  (for example `assets:checking`).
- `AMOUNT` may use `,` as a thousands separator. A negative amount is written with
  a leading `-` or in parentheses: `(12.50)`.
- `CURRENCY` is a three-letter uppercase code.
- `MEMO` is the rest of the line, trimmed. It may be empty.

## Prices

```
P DATE CURRENCY RATE
P 2026-03-01 EUR 1.0850
```

One unit of `CURRENCY` is worth `RATE` units of the base currency on and after
`DATE`. `RATE` must be positive.

The rate in effect on a date is the most recent price for that currency dated on
or before that date. If a currency has several prices on the same date, the one
later in the file wins. Converting an amount dated before a currency's first price
is an error.

## Balances

Each transaction is converted to the base currency at the rate in effect on its
own date. A balance reported in another currency (`--currency`) converts each
base-currency total at that currency's rate on the report date (`--as-of`, or
the journal's last date).

## Recurring transactions

Planned; see [recurring.md](recurring.md).
