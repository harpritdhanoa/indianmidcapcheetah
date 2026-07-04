"""
Daily refresh orchestrator for Live_Portfolio_Monitor.html.

Runs, in order, stopping at the first failure so a broken step never
overwrites the previously-good HTML with half-updated data:
  1. refresh_prices.py       - top up prices_raw.parquet via yfinance
  2. daily_nav.py            - recompute the full since-inception NAV curve
  3. build_fund_nav_json.py  - repack it for the chart
  4. build_ladder_data.py    - rebuild today's ladder/dropped/added/screened/weights
  5. build_live_ladder.py    - rebuild Live_Portfolio_Monitor.html

Intended to be run once a day, after market close, via a scheduled task.
"""
import datetime
import subprocess
import sys

STEPS = [
    ("Refresh prices", [sys.executable, "refresh_prices.py"]),
    ("Recompute NAV history", [sys.executable, "daily_nav.py"]),
    ("Rebuild fund NAV chart data", [sys.executable, "build_fund_nav_json.py"]),
    ("Rebuild live ladder data", [sys.executable, "build_ladder_data.py"]),
    ("Rebuild HTML dashboard", [sys.executable, "build_live_ladder.py"]),
]

print(f"=== Daily refresh started {datetime.datetime.now().isoformat()} ===")
for label, cmd in STEPS:
    print(f"\n--- {label} ---")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        print(f"\nFAILED at step: {label} (exit {result.returncode}). "
              f"Aborting - earlier outputs are untouched, HTML was not overwritten.")
        sys.exit(1)

print(f"\n=== Daily refresh complete {datetime.datetime.now().isoformat()} ===")
