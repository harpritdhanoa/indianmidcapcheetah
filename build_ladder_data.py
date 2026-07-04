"""
Rebuild live_ladder_data.json fresh, as of the latest date in prices_raw.parquet.

Reconstructs: today's full-universe momentum rank, rank 1 week ago and 1 month
ago (for the delta columns), what the quality screen excludes today, what
"if the rebalance happened today" would drop/add versus the actual last-churn
holdings, and each held position's weight (target-at-last-churn vs. drifted
current, per the same renormalization used when the weight columns were first
added to the dashboard).

Consumed by build_live_ladder.py.
"""
import json
import pickle
import warnings
warnings.filterwarnings('ignore')

import pandas as pd

from engine import px, momentum_scores, select_with_buffer, TARGET_N, BUFFER, asof
from quality_screen import eligible_universe

names_df = pd.read_csv('midcap150_current.csv')
NAME_MAP = {row['Symbol'] + '.NS': row['Company Name'] for _, row in names_df.iterrows()}


def tkr_of(t_ns):
    return t_ns.replace('.NS', '')


def name_of(t_ns):
    return NAME_MAP.get(t_ns, tkr_of(t_ns))


with open('weights_history.pkl', 'rb') as f:
    weights_history = pickle.load(f)
last_churn = max(weights_history.keys())
w0 = weights_history[last_churn]
held = set(w0.index)

as_of = px.index.max()

scored_now = momentum_scores(px, as_of)
if scored_now is None:
    raise SystemExit(f"momentum_scores returned None for as_of={as_of}; aborting ladder rebuild "
                      f"(leaving previous live_ladder_data.json in place).")
rank_now = scored_now['rank'].to_dict()


def safe_rank(d):
    s = momentum_scores(px, d)
    return s['rank'].to_dict() if s is not None else {}


rank_1wk = safe_rank(pd.Timestamp(as_of) - pd.DateOffset(weeks=1))
rank_1mo = safe_rank(pd.Timestamp(as_of) - pd.DateOffset(months=1))

screen_log = []
eligible_rank_map = eligible_universe(rank_now, as_of, log=screen_log)
screened_tkrs = {e['ticker'] for e in screen_log}

sel, retained, adds = select_with_buffer(eligible_rank_map, held, N=TARGET_N, buffer=BUFFER)
dropped = held - sel
added = sel - held

# Drifted weight: target weight at last churn x price return since then, renormalized
# across the held names (same calc used when weight columns were first added).
price_then_d = asof(px.index, last_churn)
price_now_d = asof(px.index, as_of)
p_then = px.loc[price_then_d, list(held)]
p_now = px.loc[price_now_d, list(held)]
value_now = w0 * (p_now / p_then)
w_now = value_now / value_now.sum()

universe = set(rank_now.keys()) | held
ladder = []
for t in universe:
    r = rank_now.get(t)
    if r is None:
        continue  # missing from today's scoreable universe entirely (e.g. data gap) - can't rank it
    if r > 50 and t not in held:
        continue  # only show top 50 + any fallen holdings, matching the page's stated scope
    tag = None
    if t in screened_tkrs:
        tag = 'screened'
    elif t in dropped:
        tag = 'at_risk'
    elif t in added:
        tag = 'would_enter'
    ladder.append({
        'tkr': tkr_of(t),
        'name': name_of(t),
        'rank_now': r,
        'd1w': (rank_1wk[t] - r) if (t in rank_1wk and t in rank_now) else None,
        'd1m': (rank_1mo[t] - r) if (t in rank_1mo and t in rank_now) else None,
        'held': t in held,
        'tag': tag,
        'w_target_pct': round(float(w0[t]) * 100, 2) if t in held else None,
        'w_now_pct': round(float(w_now[t]) * 100, 2) if t in held else None,
    })
ladder.sort(key=lambda r: r['rank_now'])


def name_rank_row(t):
    return {'tkr': tkr_of(t), 'name': name_of(t), 'rank': rank_now.get(t)}


rank_key = lambda r: r['rank'] if r['rank'] is not None else 10 ** 9
dropped_today = sorted([name_rank_row(t) for t in dropped], key=rank_key)
added_today = sorted([name_rank_row(t) for t in added], key=rank_key)
screened_out = sorted(
    [{'tkr': tkr_of(e['ticker']), 'name': name_of(e['ticker']),
      'rank': rank_now.get(e['ticker']), 'reasons': e['reasons']} for e in screen_log],
    key=rank_key,
)

data = {
    'as_of': str(pd.Timestamp(as_of).date()),
    'last_churn': str(pd.Timestamp(last_churn).date()),
    'target_n': TARGET_N,
    'buffer_line': int(round((1 + BUFFER) * TARGET_N)),
    'portfolio_size': len(held),
    'dropped_today': dropped_today,
    'added_today': added_today,
    'screened_out': screened_out,
    'ladder': ladder,
}
json.dump(data, open('live_ladder_data.json', 'w'), indent=2)
print(f"live_ladder_data.json rebuilt: as_of={data['as_of']}, {len(ladder)} ladder rows, "
      f"{len(dropped_today)} dropped, {len(added_today)} added, {len(screened_out)} screened out.")
