"""Deliberately broken versions of the reference solution, for scoring the agent's tests.

Each mutant applies one text replacement to one file of the reference tree. A good
test suite for recurring transactions fails on every one of them. ``old`` must
occur exactly once in the file; build.py checks that.
"""

MUTANTS = [
    {
        "name": "monthly-drift",
        "why": "monthly day carried over from the previous (clamped) occurrence",
        "file": "tally/recurring.py",
        "old": '    if rule.freq == "monthly":\n        return _add_months(rule.start, n)\n',
        "new": (
            '    if rule.freq == "monthly":\n'
            "        day = rule.start\n"
            "        for _ in range(k):\n"
            "            day = _add_months(day, rule.interval)\n"
            "        return day\n"
        ),
    },
    {
        "name": "monthly-ignores-interval",
        "why": "monthly/N repeats every month",
        "file": "tally/recurring.py",
        "old": "        return _add_months(rule.start, n)\n",
        "new": "        return _add_months(rule.start, k)\n",
    },
    {
        "name": "weekly-as-days",
        "why": "weekly/N steps N days instead of N weeks",
        "file": "tally/recurring.py",
        "old": "timedelta(weeks=n)",
        "new": "timedelta(days=n)",
    },
    {
        "name": "february-always-28",
        "why": "short months ignore leap years",
        "file": "tally/recurring.py",
        "old": "    day = min(start.day, calendar.monthrange(year, month)[1])\n",
        "new": "    day = min(start.day, 28 if month == 2 else calendar.monthrange(year, month)[1])\n",
    },
    {
        "name": "leap-day-to-march",
        "why": "yearly rule from February 29 moves to March 1 in common years",
        "file": "tally/recurring.py",
        "old": '    if rule.freq == "yearly":\n        return _add_months(rule.start, 12 * n)\n',
        "new": (
            '    if rule.freq == "yearly":\n'
            "        try:\n"
            "            return rule.start.replace(year=rule.start.year + n)\n"
            "        except ValueError:\n"
            "            return date(rule.start.year + n, 3, 1)\n"
        ),
    },
    {
        "name": "until-exclusive",
        "why": "the until date itself is excluded",
        "file": "tally/recurring.py",
        "old": "min(through, rule.until)",
        "new": "min(through, rule.until - timedelta(days=1))",
    },
    {
        "name": "through-exclusive",
        "why": "an occurrence on the through date is excluded",
        "file": "tally/recurring.py",
        "old": "        if day > last:\n",
        "new": "        if day >= last:\n",
    },
    {
        "name": "skips-start",
        "why": "the first occurrence is one period after START",
        "file": "tally/recurring.py",
        "old": "    k = 0\n",
        "new": "    k = 1\n",
    },
    {
        "name": "interval-not-parsed",
        "why": "the /N interval is ignored when parsing",
        "file": "tally/journal.py",
        "old": "    interval = 1 if match[2] is None else _interval(match[2], line)\n",
        "new": "    interval = 1\n",
    },
    {
        "name": "until-not-parsed",
        "why": "the until date is ignored when parsing",
        "file": "tally/journal.py",
        "old": "    until = None if match[4] is None else parse_date(match[4], line)\n",
        "new": "    until = None\n",
    },
    {
        "name": "end-date-ignores-rules",
        "why": "Ledger.end_date() ignores rule start dates",
        "file": "tally/ledger.py",
        "old": "        dates += [rule.start for rule in self.journal.recurring]\n",
        "new": "",
    },
    {
        "name": "same-day-order",
        "why": "occurrences always come after ordinary transactions on the same date",
        "file": "tally/ledger.py",
        "old": "        return sorted(selected, key=lambda t: (t.date, t.line))",
        "new": "        return sorted(selected, key=lambda t: t.date)",
    },
    {
        "name": "rule-currency-ignored",
        "why": "occurrences are booked in the base currency",
        "file": "tally/ledger.py",
        "old": "rule.amount, rule.currency, rule.memo, rule.line",
        "new": "rule.amount, self.base, rule.memo, rule.line",
    },
]
