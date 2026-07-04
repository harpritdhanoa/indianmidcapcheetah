# Midcap Cheetah — Live Portfolio Monitor

A live, self-updating monitor for an SPMO-style (12-1 risk-adjusted momentum) strategy
run on the Nifty Midcap 150 universe: 30 holdings, semi-annual rebalance, 20% buffer,
10% single-stock cap, plus a fundamental quality screen (negative net worth, persistent
losses, weak interest coverage) that excludes distressed names from the candidate pool
regardless of momentum.

**This is a research/monitoring tool, not investment advice.**

## How it stays live

`index.html` is a static page — GitHub Pages just serves whatever is currently
committed. The "live" part comes from `.github/workflows/daily-refresh.yml`, a
GitHub Actions workflow that runs once a day (10:30 UTC / 4:00 PM IST, plus you can
trigger it manually from the Actions tab):

1. `refresh_prices.py` — tops up `prices_raw.parquet` with the latest close via yfinance
   for the ~150-name universe.
2. `daily_nav.py` — recomputes the full since-inception daily NAV curve from the
   actual rebalance weight history.
3. `build_fund_nav_json.py` — repacks that curve for the chart.
4. `build_ladder_data.py` — rebuilds today's momentum ranks, what the quality screen
   excludes, what "if the rebalance happened today" would drop/add versus the real
   last-churn holdings, and each position's drifted weight.
5. `build_live_ladder.py` — rebuilds `index.html` from the above.

If anything changed, the workflow commits and pushes it back to this repo. GitHub
Pages then serves the new version automatically — no server to run, no always-on
process required, and it keeps working whether or not any particular machine (or
Claude session) is open. If a step fails (most likely: yfinance/network hiccup, or
an unexpected data gap), the workflow's log shows exactly which step and why, and
the previous good `index.html` is simply left in place until the next successful run.

## One-time setup (after cloning/pushing this folder to GitHub)

1. Push this folder to a new GitHub repo (see commands below).
2. In the repo: **Settings → Pages** → Source: "Deploy from a branch" → Branch: `main`, folder: `/ (root)`.
3. In the repo: **Settings → Actions → General** → make sure "Allow all actions and
   reusable workflows" is selected (this is the default for personal repos).
4. That's it — the workflow will run on its own daily schedule from here on. You can
   also click **Actions → Daily refresh → Run workflow** any time for an on-demand refresh.

## Running it locally

```
pip install -r requirements.txt
python daily_refresh.py
```

Regenerates `prices_raw.parquet`, `daily_nav.csv`, `fund_nav_since_inception.json`,
`live_ladder_data.json`, and `index.html` in place.

## What's NOT automated here

- The actual portfolio holdings only change on a **real** semi-annual rebalance
  (last one: 2026-05-29, tracked in `weights_history.pkl`). This pipeline never
  executes trades or auto-rebalances — it only monitors the existing holdings
  against today's ranks and flags what a rebalance *would* do if run today.
- Shares outstanding (used for market-cap weighting) are not refreshed daily —
  they change slowly and aren't part of this pipeline; re-run `fetch_networth.py`/
  equivalent share-count refresh manually on a slower cadence if needed.
