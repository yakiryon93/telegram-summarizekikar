"""Replay the virtual portfolio over the last N editions of the picks ledger.

Needs a clone of nditzik/nidam-markets with enough git history to recover the
picks.json of each edition (targets live only there):
  git clone https://github.com/nditzik/nidam-markets.git
  git -C nidam-markets fetch --shallow-since=<date before the first edition>
  python tools/simulate_portfolio.py /path/to/nidam-markets [N]
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

repo = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
os.environ['BRIEF_DATA_DIR'] = os.path.join(repo, 'data')
import morning_brief as mb  # noqa: E402  (reads BRIEF_DATA_DIR at import)


def git(*a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, check=True).stdout


# picks.json as it was at the end of each edition day (last rebuild wins)
snap = {}
for h in reversed(git('log', '--format=%H', '--', 'data/picks.json').split()):
    try:
        p = json.loads(git('show', f'{h}:data/picks.json'))
    except Exception:
        continue
    if p.get('date'):
        snap[p['date']] = p

ledger, _ = mb.load_json('picks_ledger.json')
last_eds = ledger['editions'][-n:]
editions = []
for e in last_eds:
    one = {'editions': [e]}
    editions += mb.editions_from_sources(snap.get(e['date']), one)
    print(f"edition {e['date']}: picks.json snapshot {'found' if e['date'] in snap else 'MISSING (no targets)'}")

spy_days = [d for d, _ in mb.load_bars('SPY')]
pf = mb.new_portfolio()
pf['last_day'] = max(d for d in spy_days if d < editions[0]['date'])
pf['start_date'] = editions[0]['date']

for day in [d for d in spy_days if d >= editions[0]['date']]:
    bought, sold = mb.run_portfolio(pf, editions, spy_days, upto=day)
    print(f'\n=== {day} ===')
    for b in bought:
        if b.get('skipped'):
            print(f"  SKIP {b['sym']}: {b['skipped']}")
        else:
            print(f"  BUY  {b['sym']:5} entry {b['entry']:>9.2f} stop {b['stop']} target {b['target']}  shares {b['shares']:.3f}")
    for s in sold:
        print(f"  SELL {s['sym']:5} close {s['exit']:>9.2f} ({s['reason']}, {s['days']}d) "
              f"stop {s['stop']} target {s['target']}  ret {s['ret']:+.2f}%  pnl {s['pnl']:+.2f}")
    for p in pf['positions']:
        c = mb.close_on(p['sym'], day)
        print(f"  hold {p['sym']:5} close {c} stop {p['stop']} target {p['target']}")
    # value as of `day`, not the latest bar
    val = pf['cash'] + sum(p['shares'] * (mb.close_on(p['sym'], day) or p['entry']) for p in pf['positions'])
    print(f"  cash {pf['cash']:.2f}  positions {len(pf['positions'])}  value {val:.2f}")

print('\n--- brief section as of the latest bar ---')
print('\n'.join(mb.portfolio_section(pf, [], [])))
