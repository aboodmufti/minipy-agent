#!/bin/bash
# Reference solution: copy the changed and added files over /app.
set -euo pipefail
cp -r /solution/overlay/. /app/
