# Recurring transactions

Status: specified, not implemented yet.

A recurring rule is a transaction that repeats on a schedule. Rules live in the
journal next to ordinary transactions.

## Syntax

```
~ FREQUENCY START [until END] ACCOUNT AMOUNT CURRENCY [MEMO]
```

- `FREQUENCY` is `daily`, `weekly`, `monthly` or `yearly`, optionally followed by
  `/N` to repeat every N periods: `monthly/3` is quarterly. N must be a positive
  integer. Without `/N` the interval is 1.
- `START` and `END` are ISO dates. `END` is inclusive. `END` before `START` is an
  error.
- `ACCOUNT`, `AMOUNT`, `CURRENCY` and `MEMO` follow the same rules as for an
  ordinary transaction (see [FORMAT.md](FORMAT.md)). Comments work as on any line.

Examples:

```
~ monthly 2026-01-31 checking -1,450.00 USD rent
~ weekly/2 2026-01-02 until 2026-06-30 checking -40.00 USD cleaner
~ yearly 2024-02-29 savings 100.00 USD leap-day bonus
```

## Occurrence dates

Occurrence k (k = 0, 1, 2, ...) of a rule with interval N falls on:

- `daily`: START + k·N days.
- `weekly`: START + 7·k·N days.
- `monthly`: the month k·N months after START's month, on START's day of the
  month. If that month is shorter, the occurrence is on the month's last day.
  The day always comes from START, never from the previous occurrence: a rule
  starting on January 31 occurs on January 31, February 28 (29 in a leap year),
  March 31, April 30, and so on.
- `yearly`: k·N years after START, on the same month and day. A rule starting on
  February 29 occurs on February 28 in years that are not leap years.

The first occurrence (k = 0) is START itself.

## Python interface

- `tally.journal.parse` returns the rules in `Journal.recurring`, a list of
  `tally.recurring.RecurringRule` in file order, with `line` set to the rule's
  line number.
- An invalid rule line raises `tally.journal.JournalError` with that line number,
  like any other invalid line. Invalid includes: an unknown frequency, an interval
  that is not a positive integer, an invalid date, END before START, and an
  invalid amount.
- `tally.recurring.occurrences(rule, through)` returns the occurrence dates `d`
  with `START <= d <= through`, and `d <= END` if the rule has an END, in
  ascending order. It returns an empty list if `through` is before START.

## Balances and registers

- Each occurrence counts exactly like an ordinary transaction on its date: same
  account, amount, currency and memo, converted at the rate in effect on the
  occurrence's date.
- With `--as-of DATE` (`as_of=` in `tally.ledger.Ledger`), rules are expanded
  through DATE. Without it, rules are expanded through the journal's end date: the
  latest date of any ordinary transaction, price or rule START
  (`Ledger.end_date()`).
- Transactions are listed by date. Transactions on the same date are listed in the
  order of their lines in the journal; an occurrence uses its rule's line.
