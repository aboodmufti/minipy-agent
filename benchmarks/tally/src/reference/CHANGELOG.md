# Changelog

## Unreleased

- Recurring transactions (`~` lines): daily, weekly, monthly and yearly rules with
  an optional interval and end date. See docs/recurring.md.
- Fix: currency conversion used the next price after a transaction's date instead
  of the price in effect on that date, and dates before a currency's first price
  were silently converted instead of raising an error.
- `balance` and `register` are much faster on journals with many prices: rate
  lookups use a sorted index and binary search.

## 0.3.0 (2026-09-14)

- `register` command with running balances per account.
- `--currency` option for `balance`.

## 0.2.0 (2026-06-02)

- Prices (`P` lines) and conversion to a base currency.
- `option base` directive.

## 0.1.0 (2026-04-20)

- First release: transactions and `balance`.
