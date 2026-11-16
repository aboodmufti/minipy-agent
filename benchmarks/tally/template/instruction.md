The repository in `/app` is `tally`, a small plain-text ledger tool (Python 3.12, standard library only). Start by reading `README.md` and `docs/`.

Please complete these three items, as you would for a pull request:

1. **Bug:** currency conversion uses the wrong exchange rate. One test fails; run `python -m unittest` in `/app` to see it. Fix the cause, not just that case. `docs/FORMAT.md` describes the intended behavior.

2. **Performance:** `balance` is far too slow on large journals. `python scripts/make_big_journal.py` writes a realistic one to `/tmp/big.journal` (200,000 transactions). `python -m tally balance /tmp/big.journal --as-of 2026-06-30 --currency EUR` should finish in a couple of seconds.

3. **Feature:** implement recurring transactions as specified in `docs/recurring.md`: parsing, `tally.recurring.occurrences`, and their effect on `balance` and `register`. Write tests for it in `tests/test_recurring.py`. In those tests, use only the interface described in `docs/recurring.md` (`tally.journal.parse`, `tally.recurring`, `tally.ledger.Ledger`, `tally.cli.main`): they will also be run against other implementations, including deliberately broken ones, so make them thorough.

Also:

- Add entries for your changes to `CHANGELOG.md` under "Unreleased".
- Use only the standard library. Do not change the existing tests in `tests/`.
- Leave the repository clean: no scratch files or generated data in `/app`.
- Make sure `python -m unittest` passes before you finish.
