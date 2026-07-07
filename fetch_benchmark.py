"""
Fetch the Nifty Midcap 150 index daily closes (Yahoo: NIFTYMIDCAP150.NS,
available from Jan 2019) for the strategy-vs-benchmark comparison chart.

Resilient by design: if the download fails but a previously committed
benchmark_series.json exists, keep the stale file and exit 0 so a flaky
Yahoo day never aborts the whole daily refresh.
"""
import json
import os
import sys

OUT = "benchmark_series.json"
SYMBOL = "NIFTYMIDCAP150.NS"

try:
    import yfinance as yf
    h = yf.download(SYMBOL, start="2018-12-01", auto_adjust=True, progress=False)["Close"]
    if hasattr(h, "columns"):  # yfinance may return a 1-col DataFrame
        h = h[SYMBOL]
    h = h.dropna()
    if len(h) < 100:
        raise RuntimeError(f"suspiciously short benchmark series: {len(h)} rows")
    out = {
        "symbol": SYMBOL,
        "name": "Nifty Midcap 150",
        "dates": [d.strftime("%Y-%m-%d") for d in h.index],
        "close": [round(float(v), 2) for v in h],
    }
    with open(OUT, "w") as f:
        json.dump(out, f)
    print(f"Benchmark refreshed: {len(h)} rows, {out['dates'][0]} -> {out['dates'][-1]}")
except Exception as e:
    if os.path.exists(OUT):
        print(f"WARNING: benchmark fetch failed ({e}); keeping existing {OUT}")
        sys.exit(0)
    print(f"ERROR: benchmark fetch failed and no cached {OUT} exists: {e}")
    sys.exit(1)
