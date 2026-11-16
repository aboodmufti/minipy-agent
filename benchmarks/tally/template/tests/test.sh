#!/bin/bash
# Scores the work in /app. See grade.py for the scoring rules.
mkdir -p /logs/verifier
python3 /tests/grade.py --app /app --out /logs/verifier \
  || echo '{"reward": 0}' > /logs/verifier/reward.json
