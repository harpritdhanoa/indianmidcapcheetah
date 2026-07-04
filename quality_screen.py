"""
Formal, config-driven distress/quality screen. Applied automatically to every
rebalance (backtest AND live) via engine.eligible_universe() -- not an ad hoc,
case-by-case decision. All four rules are point-in-time honest: a fiscal year's
data is only used once it would have actually been public (FY end + 60-day
SEBI filing deadline <= the as-of date).

Free-data limitation: Yahoo Finance only carries ~4-5 years of annual financials
for Indian mid-caps, so these rules can only be evaluated from roughly FY2022
onward. Rules silently pass (do not exclude) a stock with insufficient history
rather than penalizing it for a data gap.

Known gaps NOT covered here (no free structured data): auditor going-concern /
qualified opinions, promoter share-pledge percentage, related-party red flags.
"""
import pickle
import pandas as pd

FILING_LAG_DAYS = 60  # SEBI LODR Reg. 33: annual results due within 60 days of FY end

QUALITY_RULES = {
    'negative_net_worth':   {'enabled': True},
    'persistent_losses':    {'enabled': True, 'lookback_years': 3, 'min_negative_years': 2},
    'weak_interest_cover':  {'enabled': True, 'min_coverage': 1.0},
    # Disabled by default: tested and found to over-fire on banks/NBFCs/insurers (operating
    # cash flow reflects loan/deposit/investment book changes, not distress) and on
    # capex-heavy growth-phase names (power generation, realty, some pharma capacity
    # build-outs) -- e.g. it flagged Glenmark, Laurus Labs, Voltas, and ~10 financial-sector
    # names alongside genuinely distressed ones. A workable version would need sector-aware
    # gating and/or magnitude-relative-to-market-cap thresholds; not reliable enough as-is
    # to run with "no exceptions". Left here, off, rather than silently dropped.
    'negative_fcf':         {'enabled': False, 'lookback_years': 3, 'min_negative_years': 2},
}

with open('networth_partial.pkl', 'rb') as f:
    _nw_raw = pickle.load(f)
with open('fundamentals_partial.pkl', 'rb') as f:
    _fund_raw = pickle.load(f)

def _series(d):
    if not d:
        return None
    s = pd.Series(d).sort_index()
    return s[s.notna()]

_NET_WORTH = {t: _series(d) for t, d in _nw_raw.items() if d and '_error' not in d}
_NET_INCOME = {t: _series(d.get('net_income', {})) for t, d in _fund_raw.items()}
_EBIT = {t: _series(d.get('ebit', {})) for t, d in _fund_raw.items()}
_INTEREST = {t: _series(d.get('interest_expense', {})) for t, d in _fund_raw.items()}
_FCF = {}
for t, d in _fund_raw.items():
    fcf = d.get('free_cf', {})
    if not fcf and 'operating_cf' in d and 'capex' in d:
        ocf, capex = pd.Series(d['operating_cf']), pd.Series(d['capex'])
        fcf = (ocf + capex).to_dict()  # capex already stored as negative outflow
    _FCF[t] = _series(fcf)

def _known_as_of(series, asof_date, lag_days=FILING_LAG_DAYS):
    """Values whose fiscal year end + filing lag was already public by asof_date, oldest->newest."""
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)
    cutoff = pd.Timestamp(asof_date)
    return series[series.index + pd.Timedelta(days=lag_days) <= cutoff]

def is_eligible(ticker, asof_date, rules=QUALITY_RULES):
    """Returns (eligible: bool, reasons: list[str]). A stock fails if ANY enabled
    rule fails. Missing/insufficient data never triggers a failure (it just means
    that rule can't be evaluated yet for this name)."""
    reasons = []

    if rules['negative_net_worth']['enabled']:
        s = _known_as_of(_NET_WORTH.get(ticker), asof_date)
        if len(s) > 0 and s.iloc[-1] < 0:
            reasons.append(f"negative net worth ({s.iloc[-1]/1e7:.0f} Cr as of FY{s.index[-1].date()})")

    if rules['persistent_losses']['enabled']:
        cfg = rules['persistent_losses']
        s = _known_as_of(_NET_INCOME.get(ticker), asof_date).tail(cfg['lookback_years'])
        if len(s) >= 2:
            n_neg = (s < 0).sum()
            if n_neg >= cfg['min_negative_years']:
                reasons.append(f"net losses in {n_neg}/{len(s)} of last fiscal years")

    if rules['weak_interest_cover']['enabled']:
        e = _known_as_of(_EBIT.get(ticker), asof_date)
        i = _known_as_of(_INTEREST.get(ticker), asof_date)
        if len(e) > 0 and len(i) > 0 and i.iloc[-1] > 0:
            cover = e.iloc[-1] / i.iloc[-1]
            if cover < rules['weak_interest_cover']['min_coverage']:
                reasons.append(f"interest coverage {cover:.2f}x (EBIT/interest, FY{e.index[-1].date()})")

    if rules['negative_fcf']['enabled']:
        cfg = rules['negative_fcf']
        s = _known_as_of(_FCF.get(ticker), asof_date).tail(cfg['lookback_years'])
        if len(s) >= 2:
            n_neg = (s < 0).sum()
            if n_neg >= cfg['min_negative_years']:
                reasons.append(f"negative free cash flow in {n_neg}/{len(s)} of last fiscal years")

    return (len(reasons) == 0), reasons

def eligible_universe(rank_by_ticker, asof_date, rules=QUALITY_RULES, log=None):
    """Filters a {ticker: rank} dict down to quality-screen-eligible names.
    If `log` (a list) is passed, appends an entry per excluded ticker with reasons."""
    out = {}
    for t, r in rank_by_ticker.items():
        ok, reasons = is_eligible(t, asof_date, rules)
        if ok:
            out[t] = r
        elif log is not None:
            log.append({'ticker': t, 'rank': r, 'as_of': str(pd.Timestamp(asof_date).date()), 'reasons': reasons})
    return out

if __name__ == '__main__':
    ok, reasons = is_eligible('IDEA.NS', '2026-07-01')
    print('IDEA.NS eligible:', ok, reasons)
    ok, reasons = is_eligible('NATIONALUM.NS', '2026-07-01')
    print('NATIONALUM.NS eligible:', ok, reasons)
