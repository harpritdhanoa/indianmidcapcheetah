"""
Build actual_nav.json — the real, marked-to-market NAV of the funded portfolio,
from the entry date forward. Additive step: does NOT touch any existing builder.

Churn-log aware by design so future rebalances are a data append, not a code change:
- If actual_churns.json exists, it is an append-only list of dated books:
    [ {"churn_date":"YYYY-MM-DD","holdings":[{"tkr","qty","avg_price"}],"cash_in":0,"cash_out":0}, ... ]
- Otherwise it falls back to the single entry in actual_holdings.json.

Between churn dates, value(t) = Σ held-lots · close(t). At each churn date the lot set
swaps; value carries continuously across the swap (a churn re-slices the same pot).

Fails loudly (leaves any prior actual_nav.json in place) if a holding is missing from prices.
"""
import json, os, sys
import pandas as pd

PX = 'prices_raw.parquet'
OUT = 'actual_nav.json'

px = pd.read_parquet(PX)

# ---- assemble the churn log (list of dated lot-sets) ----
if os.path.exists('actual_churns.json'):
    churns = json.load(open('actual_churns.json'))
else:
    h = json.load(open('actual_holdings.json'))
    churns = [{
        'churn_date': h['entry_date'],
        'holdings': [{'tkr': x['tkr'], 'qty': x['qty'], 'avg_price': x['avg_price']}
                     for x in h['holdings']],
        'cash_in': 0, 'cash_out': 0,
    }]
churns = sorted(churns, key=lambda c: c['churn_date'])
entry_date = churns[0]['churn_date']
cost_basis = round(sum(x['qty'] * x['avg_price'] for x in churns[0]['holdings']), 2)

# validate tickers exist
for c in churns:
    for x in c['holdings']:
        col = x['tkr'] + '.NS'
        if col not in px.columns:
            sys.exit(f"ABORT: {col} not in {PX}; leaving {OUT} untouched.")

# ---- walk the trading days from entry forward, swapping lot-set at each churn ----
dates = [d for d in px.index if d >= pd.Timestamp(entry_date)]
vals = []
ci = 0
for d in dates:
    while ci + 1 < len(churns) and d >= pd.Timestamp(churns[ci + 1]['churn_date']):
        ci += 1
    lots = churns[ci]['holdings']
    v = 0.0
    for x in lots:
        p = px.loc[d, x['tkr'] + '.NS']
        if pd.isna(p):
            p = px[x['tkr'] + '.NS'].loc[:d].ffill().iloc[-1]  # last good close
        v += x['qty'] * float(p)
    vals.append(round(v, 2))

# ---- per-holding current price + profit%, for the active lot set as of the last date ----
# (keyed by ticker so build_live_ladder.py can join it onto actual_holdings.json's display rows;
# generalises across a future churn since it uses whichever lot set is active on the last date)
last_d = dates[-1]
holdings_now = []
for x in churns[ci]['holdings']:
    col = x['tkr'] + '.NS'
    p = px.loc[last_d, col]
    if pd.isna(p):
        p = px[col].loc[:last_d].ffill().iloc[-1]
    p = float(p)
    holdings_now.append({
        'tkr': x['tkr'],
        'current_price': round(p, 2),
        'profit_pct': round((p / x['avg_price'] - 1) * 100, 2),
    })

out = {
    'entry_date': entry_date,
    'cost_basis': cost_basis,
    'dates': [d.strftime('%Y-%m-%d') for d in dates],
    'value': vals,
    'holdings_now': holdings_now,
}
json.dump(out, open(OUT, 'w'), indent=2)
print(f"{OUT}: {len(dates)} pts, entry {entry_date}, cost_basis {cost_basis:,.0f}, "
      f"value[0] {vals[0]:,.0f}, value[-1] {vals[-1]:,.0f}")
