"""
Top up prices_raw.parquet with any new daily bars since its last recorded date,
for the full Nifty Midcap 150 universe (midcap150_current.csv). Run before
daily_nav.py / build_ladder_data.py so both see today's close once it exists.

Safe to run multiple times a day / on non-trading days: if there's nothing new,
it's a no-op.
"""
import sys
import pandas as pd
import yfinance as yf

PARQUET = 'prices_raw.parquet'

px_old = pd.read_parquet(PARQUET)
last_date = px_old.index.max()
today = pd.Timestamp.today().normalize()

if last_date >= today:
    print(f"prices_raw.parquet already current through {last_date.date()} (today is {today.date()}). Nothing to do.")
    sys.exit(0)

# small overlap window so yfinance can correct/backfill a recently-revised close
start = (last_date - pd.Timedelta(days=5)).strftime('%Y-%m-%d')

symbols = pd.read_csv('midcap150_current.csv')['Symbol'].tolist()
tickers = [s + '.NS' for s in symbols]

print(f"Fetching {len(tickers)} tickers from {start} through today...")
all_new = {}
failed = []
CHUNK = 25
for i in range(0, len(tickers), CHUNK):
    chunk = tickers[i:i + CHUNK]
    try:
        d = yf.download(chunk, start=start, auto_adjust=True, progress=False, threads=True, group_by='ticker')
        for t in chunk:
            try:
                s = d['Close'] if len(chunk) == 1 else d[t]['Close']
                if not s.dropna().empty:
                    all_new[t] = s
                else:
                    failed.append(t)
            except Exception:
                failed.append(t)
    except Exception as e:
        print(f"  chunk {i} failed: {e}")
        failed.extend(chunk)
    print(f"  done {i + len(chunk)}/{len(tickers)}, failed so far: {len(failed)}")

if not all_new:
    print("No new data returned by yfinance for any ticker (market holiday, or a network/access problem). Leaving prices_raw.parquet untouched.")
    sys.exit(1)

px_new = pd.DataFrame(all_new)
px_new.index = pd.to_datetime([
    d.tz_localize(None) if hasattr(d, 'tzinfo') and d.tzinfo else d for d in px_new.index
])

combined = px_old.combine_first(px_new)  # union of index/columns, old values kept where new is missing
combined.update(px_new)                   # prefer freshly-fetched values on overlapping dates
combined = combined.sort_index()

combined.to_parquet(PARQUET)
print(f"Updated: {px_old.shape} -> {combined.shape}, now through {combined.index.max().date()}")
if failed:
    shown = failed[:10]
    print(f"Failed to fetch ({len(failed)}): {shown}{'...' if len(failed) > 10 else ''}")
