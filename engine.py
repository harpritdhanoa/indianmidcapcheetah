"""
SPMO-recipe momentum engine adapted for Nifty Midcap 150 (India).
Same math as the validated SPMO replication: 12-1 risk-adjusted momentum ->
winsorized z -> score -> 20% buffer -> issuer cap. See SPMO.md for the original.

Adaptations for India:
- Universe: current Nifty Midcap 150 constituents (150 names) - STATIC (survivorship-biased
  proxy; true point-in-time NSE constituent history isn't freely reconstructable - flagged).
- Weight proxy: price x shares-outstanding (yfinance get_shares_full), NOT float-adjusted
  (same simplification the SPMO case study used: full market cap, not float-adjusted IWF).
- Target N = 30 (20% of 150, same selection RATIO as SPMO's ~100/500), buffer 20%,
  single-stock cap 10% (same as SPMO). No dual-class issuer merging needed (not present
  in this universe).
- Rebalance cadence: semi-annual, reference dates = last trading day of May / November
  (matches the cadence NSE itself uses for its own Nifty Midcap150 Momentum 50 index,
  for a fair apples-to-apples comparison).
"""
import pickle, numpy as np, pandas as pd

LOOKBACK_M, LAG_M = 12, 1
BLEND_6M = 0.0
VOL_YEARS = 3
WINSOR = 3.0
TARGET_N = 30
BUFFER = 0.20
SINGLE_CAP = 0.10

px = pd.read_parquet('prices_raw.parquet')
with open('shares_raw.pkl', 'rb') as f:
    shares_raw = pickle.load(f)

# Build daily shares-outstanding (forward-filled, back-filled for dates before first record)
shares_df = pd.DataFrame(index=px.index)
for t, s in shares_raw.items():
    s = s.copy()
    s.index = pd.to_datetime([d.tz_localize(None) if hasattr(d, 'tz_localize') and d.tzinfo else d for d in s.index])
    s = s[~s.index.duplicated(keep='last')].sort_index()
    shares_df[t] = s.reindex(px.index).ffill().bfill()

mktcap = px * shares_df  # approx full market cap (not float-adjusted), INR

def asof(idx, d):
    sub = idx[idx <= pd.Timestamp(d)]
    return sub[-1] if len(sub) else None

def momentum_scores(px, ref_date, lookback_m=LOOKBACK_M, lag_m=LAG_M,
                     blend_6m=BLEND_6M, vol_years=VOL_YEARS, winsor=WINSOR):
    ref = asof(px.index, ref_date)
    if ref is None:
        return None
    end_m = asof(px.index, pd.Timestamp(ref) - pd.DateOffset(months=lag_m))
    s12 = asof(px.index, pd.Timestamp(end_m) - pd.DateOffset(months=lookback_m))
    if s12 is None:
        return None
    # require the stock to have priced continuously (no huge gaps) over the lookback+vol window
    window = px.loc[s12:ref]
    min_needed = int(0.90 * len(window))
    valid_cols = window.count()[window.count() >= min_needed].index
    raw12 = px.loc[end_m, valid_cols] / px.loc[s12, valid_cols] - 1
    wk = px.loc[:ref, valid_cols].resample('W-FRI').last()
    wk = wk.loc[wk.index >= pd.Timestamp(ref) - pd.DateOffset(years=vol_years)]
    vol = wk.pct_change(fill_method=None).std() * np.sqrt(52)
    df = pd.DataFrame({'ram12': raw12 / vol}).dropna()
    df = df[np.isfinite(df['ram12'])]
    if len(df) < 10:
        return None
    z = (df['ram12'] - df['ram12'].mean()) / df['ram12'].std()
    z = z.clip(-winsor, winsor)
    df['z'] = z
    df['score'] = np.where(df['z'] >= 0, 1 + df['z'], 1 / (1 - df['z']))
    return df.sort_values('score', ascending=False).assign(rank=lambda x: range(1, len(x) + 1))

def select_with_buffer(rank_by_ticker, incumbents, N=TARGET_N, buffer=BUFFER):
    buf = int(round((1 + buffer) * N))
    retained = sorted([t for t in incumbents if rank_by_ticker.get(t, 10**9) <= buf],
                       key=lambda t: rank_by_ticker[t])
    newcomers = [t for t in sorted(rank_by_ticker, key=rank_by_ticker.get) if t not in incumbents]
    adds = newcomers[:max(0, N - len(retained))]
    sel = (set(retained) | set(adds))
    if len(sel) > N:
        sel = set(sorted(sel, key=lambda t: rank_by_ticker[t])[:N])
    return sel, set(retained) & sel, set(adds) & sel

def capped_weights(mc_x_score, cap=SINGLE_CAP):
    w = (mc_x_score / mc_x_score.sum()).astype(float)
    for _ in range(300):
        over = w > cap + 1e-12
        if not over.any():
            break
        exc = (w[over] - cap).sum()
        w[over] = cap
        und = ~over
        w[und] += exc * w[und] / w[und].sum()
    return w

if __name__ == '__main__':
    # quick sanity test on latest date
    scored = momentum_scores(px, '2026-05-29')
    print(scored.head(15))
