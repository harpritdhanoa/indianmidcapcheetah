import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, pickle, json
from engine import px, asof

with open('weights_history.pkl', 'rb') as f:
    weights_history = pickle.load(f)

ref_dates = sorted(weights_history.keys())
TCOST_ONEWAY = 0.0025
daily_records = []
base_nav = 1.0
prev_w = None

for i, rd in enumerate(ref_dates):
    w = weights_history[rd]
    start = asof(px.index, rd)
    end = asof(px.index, ref_dates[i+1]) if i+1 < len(ref_dates) else px.index.max()
    sub = px.loc[start:end, list(w.index)].copy()
    sub = sub.ffill()
    rel = sub / sub.iloc[0]  # growth of 1 rupee per stock from period start
    port_rel = (rel * w).sum(axis=1)  # portfolio value relative to 1 at period start (pre-cost)
    if prev_w is not None:
        all_names = set(w.index) | set(prev_w.index)
        turnover = sum(abs(w.get(t, 0) - prev_w.get(t, 0)) for t in all_names) / 2
    else:
        turnover = 1.0
    cost = turnover * TCOST_ONEWAY * 2
    port_rel_net = port_rel.copy()
    port_rel_net.iloc[0] = port_rel_net.iloc[0] * (1 - cost)  # apply cost at rebalance
    # renormalize so it starts exactly at (1-cost) then grows
    scale = (1 - cost) / port_rel.iloc[0]
    port_rel_net = port_rel * scale
    nav_series = base_nav * port_rel_net
    for dt, v in nav_series.items():
        daily_records.append({'date': dt, 'nav': v})
    base_nav = nav_series.iloc[-1]
    prev_w = w

nav_df = pd.DataFrame(daily_records).drop_duplicates(subset='date', keep='last').set_index('date').sort_index()
nav_df.to_csv('daily_nav.csv')

navv = nav_df['nav']
rets = navv.pct_change().dropna()
ann_vol = rets.std() * np.sqrt(252) * 100
peak = navv.cummax()
dd = (navv/peak - 1)
max_dd = dd.min() * 100
n_years = (navv.index[-1] - navv.index[0]).days / 365.25
cagr = (navv.iloc[-1]/navv.iloc[0]) ** (1/n_years) - 1
print(f"Daily NAV: {navv.index[0].date()} -> {navv.index[-1].date()}, {n_years:.1f}y")
print(f"Final growth of 1: {navv.iloc[-1]:.3f}  CAGR: {cagr*100:.2f}%")
print(f"Annualized vol (daily): {ann_vol:.2f}%")
print(f"Max drawdown (daily): {max_dd:.2f}%  on {dd.idxmin().date()}")
print(f"Return/risk: {cagr*100/ann_vol:.2f}")

# calendar year returns
cy = navv.resample('YE').last()
cy_ret = cy.pct_change()
cy_ret.iloc[0] = cy.iloc[0]/navv.iloc[0] - 1
print("\nCalendar year returns:")
print((cy_ret*100).round(2))
