import json

DATA = json.load(open('live_ladder_data.json'))
FUND_NAV = json.load(open('fund_nav_since_inception.json'))

_nav = FUND_NAV['nav']
_dates = FUND_NAV['dates']
_cagr_years = (__import__('datetime').date.fromisoformat(_dates[-1]) - __import__('datetime').date.fromisoformat(_dates[0])).days / 365.25
_cagr = (_nav[-1] / _nav[0]) ** (1 / _cagr_years) - 1
_roll_max = []
_m = -1e9
for v in _nav:
    _m = max(_m, v)
    _roll_max.append(_m)
_max_dd = min((v / m - 1) for v, m in zip(_nav, _roll_max))

DATA['fund_nav'] = {
    'dates': _dates,
    'nav': _nav,
    'inception': _dates[0],
    'as_of': _dates[-1],
    'cagr_pct': round(_cagr * 100, 2),
    'max_dd_pct': round(_max_dd * 100, 2),
    'growth_of_1': round(_nav[-1] / _nav[0], 3),
}
# Benchmark comparison: rebase Nifty Midcap 150 onto the strategy NAV at the
# first overlapping date, so both curves are in "growth of Rs 1" units.
try:
    _bm = json.load(open('benchmark_series.json'))
    _nav_by_date = dict(zip(_dates, _nav))
    _bm_pairs = [(d, c) for d, c in zip(_bm['dates'], _bm['close']) if d in _nav_by_date]
    if len(_bm_pairs) >= 100:
        _d0, _c0 = _bm_pairs[0]
        _factor = _nav_by_date[_d0] / _c0
        DATA['benchmark'] = {
            'name': _bm['name'],
            'from': _d0,
            'dates': [d for d, _ in _bm_pairs],
            'values': [round(c * _factor, 4) for _, c in _bm_pairs],
        }
except FileNotFoundError:
    pass

# Actual funded portfolio (tracked from entry_date forward, alongside the paper strategy).
try:
    _ah = json.load(open('actual_holdings.json'))
    _an = json.load(open('actual_nav.json'))
    DATA['actual'] = {
        'entry_date': _an['entry_date'],
        'cost_basis': _an['cost_basis'],
        'dates': _an['dates'],
        'value': _an['value'],
        'n_holdings': _ah['n_holdings'],
        'holdings': _ah['holdings'],
    }
except FileNotFoundError:
    pass

DATA_JSON = json.dumps(DATA)

html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Live Portfolio Monitor — 30 Holdings vs. Challengers</title>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
  :root {
    --bg: #0f1117; --panel: #171a23; --panel2: #1d2130; --border: #2a2f3f;
    --text: #e6e8ef; --muted: #9099ac; --accent: #5b8def; --good: #3ecf8e;
    --bad: #ef5b6a; --amber: #e8b84b;
  }
  * { box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 32px 24px 64px; }
  .wrap { max-width: 1080px; margin: 0 auto; }
  .title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  .refresh-btn { display: inline-flex; align-items: center; gap: 6px; background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 7px 14px; font-size: 13px; text-decoration: none; white-space: nowrap; cursor: pointer; font-family: inherit; }
  .refresh-btn:hover { background: var(--border); }
  .calc-link { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; text-decoration: none; white-space: nowrap; }
  .calc-link:hover { color: var(--text); }
  .header-links { display: flex; align-items: center; gap: 14px; }
  .sub { color: var(--muted); font-size: 14px; margin-bottom: 28px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px 22px; margin-bottom: 24px; }
  .panel h2 { font-size: 16px; margin: 0 0 4px; }
  .panel .desc { color: var(--muted); font-size: 13px; margin-bottom: 14px; }
  .stat-grid { display:flex; gap: 16px; flex-wrap: wrap; margin-bottom: 6px; }
  .stat { background: var(--panel2); border-radius: 8px; padding: 10px 16px; min-width: 150px; }
  .stat .v { font-size: 20px; font-weight: 700; }
  .stat .l { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }

  .verdict-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 700px) { .verdict-grid { grid-template-columns: 1fr; } }
  .verdict-box { border-radius: 10px; padding: 14px 16px; }
  .verdict-box.drop { background: rgba(239,91,106,0.08); border: 1px solid rgba(239,91,106,0.35); }
  .verdict-box.add { background: rgba(62,207,142,0.08); border: 1px solid rgba(62,207,142,0.35); }
  .verdict-box h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: .03em; }
  .verdict-box.drop h3 { color: var(--bad); }
  .verdict-box.add h3 { color: var(--good); }
  .verdict-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 13.5px; }
  .verdict-row:last-child { border-bottom: none; }
  .verdict-row .name { color: var(--muted); font-size: 12px; }
  .verdict-empty { color: var(--muted); font-size: 13px; font-style: italic; }

  table.ladder { width: 100%; border-collapse: collapse; font-size: 13px; }
  table.ladder th, table.ladder td { padding: 7px 10px; text-align: right; border-bottom: 1px solid var(--border); }
  table.ladder th:nth-child(1), table.ladder td:nth-child(1) { text-align: center; width: 40px; }
  table.ladder th:nth-child(2), table.ladder td:nth-child(2),
  table.ladder th:nth-child(3), table.ladder td:nth-child(3) { text-align: left; }
  table.ladder th { color: var(--muted); font-weight: 600; font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; }
  table.ladder td.tkr { font-weight: 600; }
  table.ladder td.cname { color: var(--muted); font-size: 12px; }
  table.ladder td.wt { font-variant-numeric: tabular-nums; }
  table.ladder td.wt-dash { color: var(--muted); }
  table.ladder td.wt-up { color: var(--good); }
  table.ladder td.wt-down { color: var(--bad); }
  tr.divider-30 td { border-bottom: 2px solid var(--good); }
  tr.divider-36 td { border-bottom: 2px dashed var(--amber); }
  tr.row-at-risk { background: rgba(239,91,106,0.08); }
  tr.row-would-enter { background: rgba(62,207,142,0.08); }
  .badge { display: inline-block; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; padding: 2px 7px; border-radius: 10px; }
  .badge-held { background: var(--panel2); color: var(--muted); }
  .badge-challenger { background: var(--panel2); color: var(--muted); }
  .badge-at-risk { background: rgba(239,91,106,0.2); color: var(--bad); }
  .badge-would-enter { background: rgba(62,207,142,0.2); color: var(--good); }
  .badge-screened { background: rgba(200,120,255,0.18); color: #c87dff; }
  tr.row-screened { background: rgba(200,120,255,0.06); }
  tr.row-screened td.tkr, tr.row-screened td.cname { text-decoration: line-through; opacity: 0.7; }
  .screen-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
  .screen-row:last-child { border-bottom: none; }
  .screen-row .reasons { color: var(--muted); font-size: 11.5px; text-align: right; max-width: 60%; }
  .up { color: var(--good); }
  .down { color: var(--bad); }
  .flat { color: var(--muted); }
  table.holdings { width: 100%; border-collapse: collapse; font-size: 13px; }
  table.holdings th, table.holdings td { padding: 7px 10px; text-align: right; border-bottom: 1px solid var(--border); }
  table.holdings th:nth-child(1), table.holdings td:nth-child(1) { text-align: center; width: 40px; color: var(--muted); }
  table.holdings th:nth-child(2), table.holdings td:nth-child(2) { text-align: left; font-weight: 600; }
  table.holdings th { color: var(--muted); font-weight: 600; font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; }
  .legend-note { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12px; color: var(--muted); margin-top: 12px; }
  .legend-note span.dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; vertical-align:middle; }
  .callout { border-left: 3px solid var(--accent); background: var(--panel2); padding: 10px 14px; border-radius: 6px; font-size: 13px; color: var(--muted); margin-top: 14px; }
  .chart-wrap { position: relative; height: 320px; margin-top: 4px; }
  .chart-toolbar { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 8px; }
  .chart-toolbar button { background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 5px 12px; font-size: 12px; cursor: pointer; }
  .chart-toolbar button:hover { background: var(--border); }
  .draw-toolbar { justify-content: space-between; flex-wrap: wrap; }
  .tool-group { display: flex; gap: 6px; align-items: center; }
  .tool-btn { background: var(--panel2); color: var(--muted); border: 1px solid var(--border); border-radius: 6px; padding: 5px 12px; font-size: 12px; cursor: pointer; }
  .tool-btn:hover { background: var(--border); color: var(--text); }
  .tool-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .tool-group select { background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 12px; }
  .tool-group label { color: var(--muted); font-size: 12px; }
  footer { color: var(--muted); font-size: 12px; text-align: center; margin-top: 30px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="title-row">
    <h1>Live Portfolio Monitor</h1>
    <div class="header-links">
      <a class="calc-link" href="calculation_14jul.html">How the selection is computed (14 Jul)</a>
      <button class="refresh-btn" id="refreshBtn" title="Trigger the GitHub Action that refreshes prices and rebuilds this page">↻ Refresh</button>
    </div>
  </div>
  <div class="sub" id="subline"></div>

  <div class="panel">
    <div class="stat-grid">
      <div class="stat"><div class="v" id="s-portsize"></div><div class="l">Current holdings</div></div>
      <div class="stat"><div class="v" id="s-asof"></div><div class="l">Ranks as of</div></div>
      <div class="stat"><div class="v" id="s-lastchurn"></div><div class="l">Bought at last churn</div></div>
      <div class="stat"><div class="v" id="s-atrisk"></div><div class="l">Holdings at risk today</div></div>
      <div class="stat"><div class="v" id="s-wtatrisk"></div><div class="l">Portfolio weight at risk</div></div>
    </div>
  </div>

  <div class="panel">
    <h2>Fund performance since inception</h2>
    <div class="desc" id="fundDesc"></div>
    <div class="stat-grid">
      <div class="stat"><div class="v" id="f-cagr"></div><div class="l">CAGR since inception</div></div>
      <div class="stat"><div class="v" id="f-growth"></div><div class="l">Growth of ₹1</div></div>
      <div class="stat"><div class="v" id="f-maxdd"></div><div class="l">Max drawdown (daily)</div></div>
    </div>
    <div class="chart-toolbar draw-toolbar" style="margin-top:12px">
      <div class="tool-group">
        <span style="font-size:12px"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);margin-right:5px;vertical-align:middle"></span>Strategy (paper)</span>
        <span style="font-size:12px;color:var(--amber)" id="bmLegend"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--amber);margin-right:5px;vertical-align:middle"></span>Nifty Midcap 150 (rebased)</span>
        <span style="font-size:12px;color:var(--good);display:none" id="actualLegend"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--good);margin-right:5px;vertical-align:middle"></span>Your portfolio (actual)</span>
      </div>
      <div class="tool-group">
        <button class="tool-btn active" id="bmToggle">vs Midcap 150: ON</button>
        <button class="tool-btn" id="scaleToggle">Log scale</button>
        <button class="tool-btn" data-range="1">1Y</button>
        <button class="tool-btn" data-range="3">3Y</button>
        <button class="tool-btn" data-range="5">5Y</button>
        <button class="tool-btn" data-range="0">All</button>
      </div>
    </div>
    <div class="chart-toolbar draw-toolbar" style="margin-top:6px">
      <div class="tool-group">
        <label style="color:var(--muted);font-size:12px">Align both at: <input type="date" id="anchorDate" style="background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:12px;font-family:inherit"></label>
        <button class="tool-btn" id="anchorApply">Set start point</button>
        <span style="color:var(--muted);font-size:12px">— or just click any point on the chart</span>
      </div>
      <div class="tool-group">
        <button class="tool-btn active" id="modeNav">₹ NAV view</button>
      </div>
    </div>
    <div id="cmpChart" style="height:340px"></div>
    <div class="callout">Net of the same 0.25% one-way transaction cost and semi-annual rebalance/buffer/cap rules as the live selection above. Max drawdown is measured on the actual daily NAV path, not just at rebalance dates. The amber line is the real Nifty Midcap 150 index (Yahoo carries it from Jan 2019). The paper strategy line turns faint/dashed after the live-entry marker — it keeps running as the theoretical benchmark to measure real execution against, while the green line is your actual funded book, marked to market daily. <b>Compare from any start point:</b> click a point on the chart, or pick a date and press "Set start point" — all curves re-anchor to 0% at that date, TradingView-style, so the separation after it is the out/under-performance from exactly that moment. "₹ NAV view" returns to the growth-of-₹1 view.</div>
  </div>

  <div class="panel" id="actualPanel" style="display:none">
    <h2>Your actual portfolio</h2>
    <div class="desc" id="actualDesc"></div>
    <div class="stat-grid">
      <div class="stat"><div class="v" id="a-cost"></div><div class="l">Cost basis</div></div>
      <div class="stat"><div class="v" id="a-value"></div><div class="l">Value today</div></div>
      <div class="stat"><div class="v" id="a-return"></div><div class="l">Return since entry</div></div>
      <div class="stat"><div class="v" id="a-holdings"></div><div class="l">Holdings</div></div>
    </div>
    <h3 style="margin:22px 0 8px;font-size:14px" id="holdingsTitle">Holdings as bought</h3>
    <table class="holdings" id="holdingsTable"></table>
  </div>

  <div class="panel">
    <h2>Midcap benchmark — daily (TradingView)</h2>
    <div class="desc">The universe benchmark on a full TradingView chart — switch line/candles, add indicators, draw, change ranges, go fullscreen. Shows the <b>BSE 150 MidCap index</b> (near-identical universe to the Nifty Midcap 150; NSE index data isn't licensed for free TradingView embeds). Use the symbol box to compare — <b>BSE:SBIMIDMOM</b> is a Nifty Midcap 150 Momentum 50 ETF, the closest listed analogue to this strategy, and <b>BSE:MID150BEES</b> tracks the Nifty Midcap 150 itself.</div>
    <div style="height:520px; border:1px solid var(--border); border-radius:10px; overflow:hidden">
      <div class="tradingview-widget-container" style="height:100%; width:100%">
        <div class="tradingview-widget-container__widget" style="height:100%; width:100%"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
        {
          "autosize": true,
          "symbol": "BSE:MID150",
          "interval": "D",
          "range": "ALL",
          "style": "2",
          "timezone": "Asia/Kolkata",
          "theme": "dark",
          "locale": "en",
          "backgroundColor": "rgba(23, 26, 35, 1)",
          "gridColor": "rgba(42, 47, 63, 0.4)",
          "withdateranges": true,
          "allow_symbol_change": true,
          "details": false,
          "hide_side_toolbar": false,
          "save_image": true,
          "calendar": false,
          "support_host": "https://www.tradingview.com"
        }
        </script>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>If the rebalance happened today</h2>
    <div class="desc">This runs the real selection rule (top 30, 20% buffer) against today's ranks, using your actual 30 holdings as the starting point — not a hypothetical.</div>
    <div class="verdict-grid">
      <div class="verdict-box drop">
        <h3>Would be dropped</h3>
        <div id="dropList"></div>
      </div>
      <div class="verdict-box add">
        <h3>Would be added</h3>
        <div id="addList"></div>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>Quality screen — automatically excluded, every rebalance</h2>
    <div class="desc">A permanent, config-driven rule set (not a case-by-case judgment call): any stock with negative net worth, net losses in 2 of the last 3 fiscal years, or interest coverage below 1x is removed from the candidate pool before selection runs — win or lose on momentum, it never gets in. Point-in-time honest: only uses annual results that would actually have been public by each date.</div>
    <div id="screenList"></div>
  </div>

  <div class="panel">
    <h2>The live ladder — your 30 holdings and everyone challenging them</h2>
    <div class="desc">Every stock ranked in the top 50 today, plus any of your holdings that have fallen further. Green divider = the rank-30 selection line. Amber dashed divider = the rank-36 buffer edge — a held stock below this line would actually lose its seat; a challenger above it is a real threat, not just noise.</div>
    <table class="ladder" id="ladderTable"></table>
    <div class="legend-note">
      <span><span class="dot" style="background:var(--bad)"></span>Held, ranked past the buffer — at risk</span>
      <span><span class="dot" style="background:var(--good)"></span>Not held, inside the buffer — would enter</span>
    </div>
    <div class="callout" id="ladderCallout"></div>
  </div>

  <footer id="footerNote"></footer>
</div>

<script>
const DATA = __DATA_JSON__;

document.getElementById('subline').textContent =
  `Your 30 holdings from the last churn, checked against today's momentum ranks (${DATA.as_of}) — who's slipping toward the exit, and who outside the portfolio is closing in.`;
document.getElementById('s-portsize').textContent = DATA.portfolio_size;
document.getElementById('s-asof').textContent = DATA.as_of;
document.getElementById('s-lastchurn').textContent = DATA.last_churn;
document.getElementById('ladderCallout').textContent =
  `Δ columns show rank change vs. 1 week ago and 1 month ago. Positive = climbing (moving toward #1). Weight columns: "Target" = each holding's actual entry weight (bought ${DATA.last_churn}); "Now" = exact current weight from real share counts × today's close, renormalized across the 30 positions — i.e. what the position is actually worth today, not what it was sized to. Challengers and screened-out names carry no weight (not held).`;
document.getElementById('footerNote').textContent =
  `Portfolio = your actual holdings, bought ${DATA.last_churn}. Simulation uses the same 12-1 momentum score, buffer, and selection rule as the semi-annual backtest, with a permanent quality screen applied ahead of ranking. Not investment advice.`;
document.getElementById('s-atrisk').textContent = DATA.dropped_today.length;

const dropTkrs = new Set(DATA.dropped_today.map(r => r.tkr));
const wtAtRisk = DATA.ladder
  .filter(r => dropTkrs.has(r.tkr) && r.w_now_pct != null)
  .reduce((sum, r) => sum + r.w_now_pct, 0);
document.getElementById('s-wtatrisk').textContent = wtAtRisk.toFixed(1) + '%';

// --- Fund NAV since inception ---
const FUND = DATA.fund_nav;
document.getElementById('fundDesc').textContent =
  `Daily growth of ₹1 invested at inception (${FUND.inception}) through ${FUND.as_of}, following the same 12-1 momentum score, semi-annual rebalance, 20% buffer, and 10% issuer cap as the live portfolio above.`;
document.getElementById('f-cagr').textContent = FUND.cagr_pct.toFixed(2) + '%';
document.getElementById('f-growth').textContent = FUND.growth_of_1.toFixed(2) + 'x';
document.getElementById('f-maxdd').textContent = FUND.max_dd_pct.toFixed(2) + '%';

function fmtDateLabel(iso) {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${months[m - 1]} ${y}`;
}

// --- Your actual portfolio (funded book, marked to market daily) ---
if (DATA.actual) {
  const A = DATA.actual;
  document.getElementById('actualPanel').style.display = '';
  document.getElementById('actualLegend').style.display = '';
  document.getElementById('actualDesc').textContent =
    `Funded ${fmtDateLabel(A.entry_date)} — marked to market daily on real closes, alongside the paper strategy and Nifty Midcap 150 above.`;
  document.getElementById('a-cost').textContent = '₹' + (A.cost_basis / 100000).toFixed(2) + 'L';
  const lastVal = A.value[A.value.length - 1];
  document.getElementById('a-value').textContent = '₹' + (lastVal / 100000).toFixed(2) + 'L';
  const ret = (lastVal / A.cost_basis - 1) * 100;
  const retEl = document.getElementById('a-return');
  retEl.textContent = (ret >= 0 ? '+' : '') + ret.toFixed(2) + '%';
  retEl.classList.add(ret > 0 ? 'up' : (ret < 0 ? 'down' : 'flat'));
  document.getElementById('a-holdings').textContent = A.n_holdings;
  document.getElementById('holdingsTitle').textContent = `Holdings as bought — ${fmtDateLabel(A.entry_date)}`;

  let hh = '<tr><th>#</th><th>Ticker</th><th>Qty</th><th>Avg price</th><th>Cost ₹</th><th>Weight</th></tr>';
  A.holdings.forEach((r, i) => {
    hh += `<tr><td>${i + 1}</td><td>${r.tkr}</td><td>${r.qty}</td>` +
      `<td>${r.avg_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>` +
      `<td>${r.cost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>` +
      `<td>${r.weight_pct.toFixed(2)}%</td></tr>`;
  });
  document.getElementById('holdingsTable').innerHTML = hh;
}

// --- Cheetah vs Midcap 150 comparison chart (TradingView Lightweight Charts) ---
// Two modes: '₹ NAV' (growth of ₹1 since inception) and '% from anchor' — click any
// point on the chart (or set a date) and BOTH series re-anchor to 0% at that date,
// exactly like TradingView's compare mode.
(function () {
  const el = document.getElementById('cmpChart');
  const css = getComputedStyle(document.documentElement);
  const chart = LightweightCharts.createChart(el, {
    layout: { background: { color: 'transparent' }, textColor: css.getPropertyValue('--muted').trim() },
    grid: { vertLines: { color: 'rgba(42,47,63,0.5)' }, horzLines: { color: 'rgba(42,47,63,0.5)' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: 'rgba(42,47,63,0.8)' },
    timeScale: { borderColor: 'rgba(42,47,63,0.8)' },
    autoSize: true,
  });
  const rsFmt = v => '₹' + v.toFixed(2);
  const pctFmt = v => (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
  const navSeries = chart.addAreaSeries({
    lineColor: css.getPropertyValue('--accent').trim(), lineWidth: 2,
    topColor: 'rgba(91,141,239,0.25)', bottomColor: 'rgba(91,141,239,0.02)',
    priceFormat: { type: 'custom', formatter: rsFmt },
  });
  const NAV_RAW = FUND.dates.map((d, i) => ({ time: d, value: FUND.nav[i] }));

  // Paper strategy: solid up to (and including) the live-entry date, then faint/dashed after
  // — it keeps running as the theoretical benchmark to measure real execution against.
  const entryIdx = DATA.actual ? FUND.dates.indexOf(DATA.actual.entry_date) : -1;
  const paperPre = entryIdx > -1 ? NAV_RAW.slice(0, entryIdx + 1) : NAV_RAW;
  navSeries.setData(paperPre);

  let paperFadeSeries = null, PAPER_FADE_RAW = null;
  if (entryIdx > -1 && entryIdx < NAV_RAW.length - 1) {
    PAPER_FADE_RAW = NAV_RAW.slice(entryIdx); // starts at the entry point so it connects, no gap
    paperFadeSeries = chart.addLineSeries({
      color: 'rgba(91,141,239,0.4)', lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceFormat: { type: 'custom', formatter: rsFmt },
    });
    paperFadeSeries.setData(PAPER_FADE_RAW);
  }

  let bmSeries = null, BM_RAW = null;
  if (DATA.benchmark) {
    bmSeries = chart.addLineSeries({
      color: css.getPropertyValue('--amber').trim(), lineWidth: 2,
      priceFormat: { type: 'custom', formatter: rsFmt },
    });
    BM_RAW = DATA.benchmark.dates.map((d, i) => ({ time: d, value: DATA.benchmark.values[i] }));
    bmSeries.setData(BM_RAW);
  } else {
    document.getElementById('bmLegend').style.display = 'none';
    document.getElementById('bmToggle').style.display = 'none';
  }

  // Actual funded portfolio: rebased onto the same "growth of ₹1" scale as the paper strategy,
  // anchored so it starts exactly on the paper curve at entry (your book IS the strategy realised
  // on day one) and diverges from there as real fills/slippage/cash drag play out.
  let actualSeries = null, ACTUAL_RAW = null, actualEntryMarker = null;
  if (DATA.actual) {
    const A = DATA.actual;
    const navByDate = {};
    FUND.dates.forEach((d, i) => { navByDate[d] = FUND.nav[i]; });
    let entryNav = navByDate[A.entry_date];
    if (entryNav == null) {
      for (const d of FUND.dates) { if (d <= A.entry_date) entryNav = navByDate[d]; else break; }
    }
    const v0 = A.value[0];
    ACTUAL_RAW = A.dates.map((d, i) => ({ time: d, value: entryNav * (A.value[i] / v0) }));
    actualSeries = chart.addLineSeries({
      color: css.getPropertyValue('--good').trim(), lineWidth: 2.5,
      priceFormat: { type: 'custom', formatter: rsFmt },
      pointMarkersVisible: true,
    });
    actualSeries.setData(ACTUAL_RAW);
    actualEntryMarker = {
      time: A.entry_date, position: 'aboveBar', color: css.getPropertyValue('--good').trim(),
      shape: 'circle',
      text: `● Live entry — ${fmtDateLabel(A.entry_date)} · ₹${(A.cost_basis / 100000).toFixed(2)}L · ${A.n_holdings} holdings`,
    };
    actualSeries.setMarkers([actualEntryMarker]);
  }

  chart.timeScale().fitContent();

  // ---- anchor / mode machinery ----
  const anchorInput = document.getElementById('anchorDate');
  const bmStart = BM_RAW ? BM_RAW[0].time : FUND.dates[0];
  anchorInput.min = bmStart;
  anchorInput.max = FUND.dates[FUND.dates.length - 1];
  anchorInput.value = bmStart;

  function valueOnOrBefore(arr, t) {
    // arr sorted by time asc; return last value with time <= t
    let v = null;
    for (const p of arr) { if (p.time <= t) v = p.value; else break; }
    return v;
  }
  function timeToStr(t) {
    return typeof t === 'string' ? t
      : t.year + '-' + String(t.month).padStart(2, '0') + '-' + String(t.day).padStart(2, '0');
  }

  let mode = 'nav';
  let logOn = false;
  const scaleBtn = document.getElementById('scaleToggle');
  function setLog(on) {
    logOn = on;
    chart.priceScale('right').applyOptions({ mode: on ? LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal });
    scaleBtn.classList.toggle('active', on);
  }

  function applyAnchor(t) {
    if (!BM_RAW) return;
    // clamp anchor into the benchmark's date range so both series have a value
    if (t < bmStart) t = bmStart;
    const a0 = valueOnOrBefore(NAV_RAW, t), b0 = valueOnOrBefore(BM_RAW, t);
    if (!a0 || !b0) return;
    mode = 'pct';
    if (logOn) setLog(false); // % scale can be negative; log is meaningless here
    navSeries.applyOptions({ priceFormat: { type: 'custom', formatter: pctFmt },
      topColor: 'rgba(91,141,239,0.18)', bottomColor: 'rgba(91,141,239,0.0)' });
    bmSeries.applyOptions({ priceFormat: { type: 'custom', formatter: pctFmt } });
    navSeries.setData(paperPre.map(p => ({ time: p.time, value: (p.value / a0 - 1) * 100 })));
    bmSeries.setData(BM_RAW.map(p => ({ time: p.time, value: (p.value / b0 - 1) * 100 })));
    if (paperFadeSeries) {
      paperFadeSeries.applyOptions({ priceFormat: { type: 'custom', formatter: pctFmt } });
      paperFadeSeries.setData(PAPER_FADE_RAW.map(p => ({ time: p.time, value: (p.value / a0 - 1) * 100 })));
    }
    if (actualSeries) {
      const aa0 = valueOnOrBefore(ACTUAL_RAW, t);
      actualSeries.applyOptions({ priceFormat: { type: 'custom', formatter: pctFmt } });
      actualSeries.setData(aa0 == null ? [] : ACTUAL_RAW.map(p => ({ time: p.time, value: (p.value / aa0 - 1) * 100 })));
      actualSeries.setMarkers([]);
    }
    const mk = [{ time: t, position: 'inBar', color: '#ffffff', shape: 'circle', text: 'start' }];
    navSeries.setMarkers(mk); bmSeries.setMarkers([]);
    anchorInput.value = t;
    document.getElementById('modeNav').classList.remove('active');
    document.getElementById('anchorApply').classList.add('active');
  }

  function backToNav() {
    mode = 'nav';
    navSeries.applyOptions({ priceFormat: { type: 'custom', formatter: rsFmt },
      topColor: 'rgba(91,141,239,0.25)', bottomColor: 'rgba(91,141,239,0.02)' });
    navSeries.setData(paperPre); navSeries.setMarkers([]);
    if (bmSeries) { bmSeries.applyOptions({ priceFormat: { type: 'custom', formatter: rsFmt } }); bmSeries.setData(BM_RAW); bmSeries.setMarkers([]); }
    if (paperFadeSeries) { paperFadeSeries.applyOptions({ priceFormat: { type: 'custom', formatter: rsFmt } }); paperFadeSeries.setData(PAPER_FADE_RAW); }
    if (actualSeries) {
      actualSeries.applyOptions({ priceFormat: { type: 'custom', formatter: rsFmt } });
      actualSeries.setData(ACTUAL_RAW);
      actualSeries.setMarkers([actualEntryMarker]);
    }
    document.getElementById('modeNav').classList.add('active');
    document.getElementById('anchorApply').classList.remove('active');
  }

  chart.subscribeClick(param => { if (param.time) applyAnchor(timeToStr(param.time)); });
  document.getElementById('anchorApply').addEventListener('click', () => applyAnchor(anchorInput.value));
  document.getElementById('modeNav').addEventListener('click', backToNav);

  // benchmark on/off
  let bmOn = true;
  document.getElementById('bmToggle').addEventListener('click', (e) => {
    if (!bmSeries) return;
    bmOn = !bmOn;
    bmSeries.applyOptions({ visible: bmOn });
    document.getElementById('bmLegend').style.opacity = bmOn ? 1 : 0.35;
    e.target.textContent = 'vs Midcap 150: ' + (bmOn ? 'ON' : 'OFF');
    e.target.classList.toggle('active', bmOn);
  });

  scaleBtn.addEventListener('click', () => { if (mode === 'pct') return; setLog(!logOn); });

  // range buttons
  document.querySelectorAll('[data-range]').forEach(btn => btn.addEventListener('click', () => {
    const yrs = +btn.dataset.range;
    if (!yrs) { chart.timeScale().fitContent(); return; }
    const last = FUND.dates[FUND.dates.length - 1];
    const from = new Date(last); from.setFullYear(from.getFullYear() - yrs);
    chart.timeScale().setVisibleRange({ from: from.toISOString().slice(0, 10), to: last });
  }));

  // Default view: re-anchor to the live-entry date so actual-vs-paper-vs-benchmark reads
  // cleanly from day one, exactly like pressing "Set start point" at the entry marker, and
  // zoom to a window around it — the full 10Y history rebased to a near-today anchor is
  // technically correct but visually useless at "All" zoom.
  if (DATA.actual && BM_RAW) {
    applyAnchor(DATA.actual.entry_date);
    const zoomFrom = new Date(DATA.actual.entry_date); zoomFrom.setDate(zoomFrom.getDate() - 90);
    chart.timeScale().setVisibleRange({
      from: zoomFrom.toISOString().slice(0, 10),
      to: FUND.dates[FUND.dates.length - 1],
    });
  }
})();

const weightByTkr = {};
DATA.ladder.forEach(r => { weightByTkr[r.tkr] = r.w_now_pct; });

function verdictRows(list, showWeight) {
  if (list.length === 0) return '<div class="verdict-empty">None right now.</div>';
  return list.map(r => {
    const w = showWeight ? weightByTkr[r.tkr] : null;
    const wTag = (w != null) ? ` <span class="name">(${w.toFixed(2)}%)</span>` : '';
    return `<div class="verdict-row"><span>${r.tkr} <span class="name">${r.name}</span>${wTag}</span><span>#${r.rank}</span></div>`;
  }).join('');
}
document.getElementById('dropList').innerHTML = verdictRows(DATA.dropped_today, true);
document.getElementById('addList').innerHTML = verdictRows(DATA.added_today, false);

function deltaCell(v) {
  if (v === null || v === undefined) return '<td class="flat">—</td>';
  const cls = v > 0 ? 'up' : (v < 0 ? 'down' : 'flat');
  const sign = v > 0 ? '+' : '';
  return `<td class="${cls}">${sign}${v}</td>`;
}

function badge(r) {
  if (r.tag === 'screened') return '<span class="badge badge-screened">Screened out</span>';
  if (r.tag === 'at_risk') return '<span class="badge badge-at-risk">At risk</span>';
  if (r.tag === 'would_enter') return '<span class="badge badge-would-enter">Would enter</span>';
  if (r.held) return '<span class="badge badge-held">Held</span>';
  return '<span class="badge badge-challenger">Challenger</span>';
}

if (DATA.screened_out.length === 0) {
  document.getElementById('screenList').innerHTML = '<div class="verdict-empty">Nothing excluded right now.</div>';
} else {
  document.getElementById('screenList').innerHTML = DATA.screened_out.map(r =>
    `<div class="screen-row"><span>${r.tkr} <span class="name" style="color:var(--muted);font-size:12px;">${r.name}</span> — rank #${r.rank}</span><span class="reasons">${r.reasons.join('; ')}</span></div>`
  ).join('');
}

function weightCells(r) {
  if (r.w_target_pct == null || r.w_now_pct == null) {
    return '<td class="wt wt-dash">—</td><td class="wt wt-dash">—</td>';
  }
  const drift = r.w_now_pct - r.w_target_pct;
  const driftCls = drift > 0.005 ? 'wt-up' : (drift < -0.005 ? 'wt-down' : 'wt-dash');
  return `<td class="wt wt-dash">${r.w_target_pct.toFixed(2)}%</td><td class="wt ${driftCls}">${r.w_now_pct.toFixed(2)}%</td>`;
}

let h = '<tr><th>#</th><th>Ticker</th><th>Company</th><th>Status</th><th>Wt. target</th><th>Wt. now</th><th>Δ 1wk</th><th>Δ 1mo</th></tr>';
DATA.ladder.forEach(r => {
  let rowCls = '';
  if (r.tag === 'screened') rowCls = 'row-screened';
  if (r.tag === 'at_risk') rowCls = 'row-at-risk';
  if (r.tag === 'would_enter') rowCls = 'row-would-enter';
  h += `<tr class="${rowCls}"><td>${r.rank_now}</td><td class="tkr">${r.tkr}</td><td class="cname">${r.name}</td><td>${badge(r)}</td>${weightCells(r)}${deltaCell(r.d1w)}${deltaCell(r.d1m)}</tr>`;
});
document.getElementById('ladderTable').innerHTML = h;

// Post-process: add divider classes to the row AT rank 30 and rank 36 (bottom border under that row)
const trs = document.querySelectorAll('#ladderTable tr');
trs.forEach((tr, i) => {
  if (i === 0) return;
  const rank = DATA.ladder[i-1].rank_now;
  if (rank === DATA.target_n) tr.classList.add('divider-30');
  if (rank === DATA.buffer_line) tr.classList.add('divider-36');
});

// --- One-click manual refresh (GitHub Actions workflow_dispatch) ---
const GH_ACTIONS_PAGE = 'https://github.com/harpritdhanoa/indianmidcapcheetah/actions/workflows/daily-refresh.yml';
const GH_DISPATCH_API = 'https://api.github.com/repos/harpritdhanoa/indianmidcapcheetah/actions/workflows/daily-refresh.yml/dispatches';
document.getElementById('refreshBtn').addEventListener('click', async () => {
  const btn = document.getElementById('refreshBtn');
  let tok = localStorage.getItem('gh_pat_cheetah');
  if (!tok) {
    tok = prompt('One-time setup for one-click refresh:\\n\\nPaste a GitHub fine-grained personal access token with "Actions: Read and write" permission on the indianmidcapcheetah repo.\\n(github.com \\u2192 Settings \\u2192 Developer settings \\u2192 Fine-grained tokens)\\n\\nStored only in this browser. Press Cancel to just open the Actions page instead.');
    if (!tok) { window.open(GH_ACTIONS_PAGE, '_blank'); return; }
    localStorage.setItem('gh_pat_cheetah', tok.trim());
  }
  btn.disabled = true; btn.textContent = '\\u21bb Triggering\\u2026';
  try {
    const r = await fetch(GH_DISPATCH_API, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + localStorage.getItem('gh_pat_cheetah'),
                 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28' },
      body: JSON.stringify({ ref: 'main' })
    });
    if (r.status === 204) {
      btn.textContent = '\\u2713 Refresh started \\u2014 page updates in ~3 min';
      setTimeout(() => { btn.textContent = '\\u21bb Refresh'; btn.disabled = false; }, 12000);
    } else {
      if (r.status === 401 || r.status === 403) localStorage.removeItem('gh_pat_cheetah'); // bad/expired token: re-prompt next click
      btn.textContent = '\\u2717 Failed (' + r.status + ') \\u2014 opening Actions page';
      window.open(GH_ACTIONS_PAGE, '_blank');
      setTimeout(() => { btn.textContent = '\\u21bb Refresh'; btn.disabled = false; }, 4000);
    }
  } catch (e) {
    btn.textContent = '\\u2717 Network error \\u2014 opening Actions page';
    window.open(GH_ACTIONS_PAGE, '_blank');
    setTimeout(() => { btn.textContent = '\\u21bb Refresh'; btn.disabled = false; }, 4000);
  }
});
</script>
</body>
</html>
"""

html = html.replace('__DATA_JSON__', DATA_JSON)

out_path = 'index.html'
with open(out_path, 'w') as f:
    f.write(html)
print("Written:", out_path, len(html), "bytes")
