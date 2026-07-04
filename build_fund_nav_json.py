"""
Regenerate fund_nav_since_inception.json from daily_nav.csv (produced by
daily_nav.py). Consumed by build_live_ladder.py for the "Fund performance
since inception" chart.
"""
import json
import pandas as pd

nav = pd.read_csv('daily_nav.csv', parse_dates=['date']).sort_values('date')
chart = {
    'dates': nav['date'].dt.strftime('%Y-%m-%d').tolist(),
    'nav': [round(float(x), 4) for x in nav['nav']],
}
json.dump(chart, open('fund_nav_since_inception.json', 'w'))
print(f"fund_nav_since_inception.json: {len(chart['dates'])} points, "
      f"{chart['dates'][0]} -> {chart['dates'][-1]}, last nav={chart['nav'][-1]}")
