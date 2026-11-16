# tally

A small plain-text ledger. Write transactions in a text file, get balances and
registers. Python 3.12, standard library only.

```
$ python -m tally balance examples/household.journal
checking         3,756.30 USD
groceries          243.70 USD
savings          2,169.00 USD
-----------------------------
Total            6,169.00 USD
```

## Commands

- `python -m tally balance JOURNAL [--as-of DATE] [--currency CUR]`: balance of
  each account.
- `python -m tally register JOURNAL [--account ACCOUNT] [--as-of DATE]`: each
  transaction with the account's running balance in the base currency.

## Journal format

See [docs/FORMAT.md](docs/FORMAT.md). Recurring transactions are specified in
[docs/recurring.md](docs/recurring.md).

## Development

```
python -m unittest
```

`scripts/make_big_journal.py` writes a large journal for performance testing.

## Layout

- `tally/journal.py`: parser.
- `tally/rates.py`: exchange-rate lookups.
- `tally/ledger.py`: balances and registers.
- `tally/recurring.py`: recurring rules.
- `tally/cli.py`: command line.
- `tally/money.py`: amount parsing and formatting.
