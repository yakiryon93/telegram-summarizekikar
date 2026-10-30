"""Daily morning brief for Kobi on Telegram (Mon–Fri, 09:00 Israel time).

Reads the JSON files of nidam-markets (https://nditzik.github.io/nidam-markets),
builds a short Hebrew brief, runs the virtual portfolio and sends it with the
same Telethon setup as summarizer.py.

Usage:
  python morning_brief.py                 # scheduled run: sends only at 09:xx Israel, once a day
  python morning_brief.py --test          # print the message, send nothing, save nothing
  python morning_brief.py --send-now      # manual send: ignores the hour, still once a day
  BRIEF_DATA_DIR=/path/to/nidam-markets/data python morning_brief.py --test
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

IL = ZoneInfo('Asia/Jerusalem')
SITE_DATA = 'https://nditzik.github.io/nidam-markets/data'
DATA_DIR = os.getenv('BRIEF_DATA_DIR', '').strip()
HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(HERE, 'portfolio.json')
STATE_FILE = os.path.join(HERE, 'brief_state.json')
MODEL = 'claude-opus-4-8'  # same model as summarizer.py
KOBI = '+972504501509'     # same recipient as summarizer.py

START_CASH = 10_000.0
POSITION_SIZE = 1_000.0
MAX_POSITIONS = 10
MAX_HOLD_DAYS = 20

DAY_NAMES = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']

# Hebrew names for large companies that show up in todayBig. Anything not here
# falls back to a cleaned-up English name.
HE_NAMES = {
    'AAPL': 'אפל', 'MSFT': 'מיקרוסופט', 'NVDA': 'אנבידיה', 'GOOGL': 'אלפבית (גוגל)', 'GOOG': 'אלפבית (גוגל)',
    'AMZN': 'אמזון', 'META': 'מטא', 'TSLA': 'טסלה', 'AVGO': 'ברודקום', 'BRK.A': 'ברקשייר האת\'ווי',
    'BRK.B': 'ברקשייר האת\'ווי', 'LLY': 'אלי לילי', 'JPM': 'ג\'יי.פי מורגן', 'V': 'ויזה', 'MA': 'מאסטרקארד',
    'XOM': 'אקסון מוביל', 'CVX': 'שברון', 'UNH': 'יונייטדהלת\'', 'JNJ': 'ג\'ונסון אנד ג\'ונסון',
    'WMT': 'וולמארט', 'PG': 'פרוקטר אנד גמבל', 'HD': 'הום דיפו', 'COST': 'קוסטקו', 'ORCL': 'אורקל',
    'ABBV': 'אבווי', 'MRK': 'מרק', 'PFE': 'פייזר', 'KO': 'קוקה-קולה', 'PEP': 'פפסיקו', 'BAC': 'בנק אוף אמריקה',
    'WFC': 'וולס פארגו', 'C': 'סיטיגרופ', 'GS': 'גולדמן זאקס', 'MS': 'מורגן סטנלי', 'BLK': 'בלאקרוק',
    'AXP': 'אמריקן אקספרס', 'SCHW': 'שוואב', 'NFLX': 'נטפליקס', 'DIS': 'דיסני', 'CMCSA': 'קומקאסט',
    'T': 'AT&T', 'VZ': 'וריזון', 'TMUS': 'טי-מובייל', 'AMD': 'AMD', 'INTC': 'אינטל', 'QCOM': 'קוואלקום',
    'TXN': 'טקסס אינסטרומנטס', 'MU': 'מיקרון', 'AMAT': 'אפלייד מטיריאלס', 'LRCX': 'לאם ריסרץ\'',
    'KLAC': 'KLA', 'ADI': 'אנלוג דיבייסס', 'ARM': 'ARM', 'TSM': 'TSMC', 'ASML': 'ASML', 'CSCO': 'סיסקו',
    'IBM': 'IBM', 'CRM': 'סיילספורס', 'ADBE': 'אדובי', 'NOW': 'סרוויס נאו', 'INTU': 'אינטואיט',
    'PLTR': 'פלנטיר', 'SHOP': 'שופיפיי', 'UBER': 'אובר', 'ABNB': 'Airbnb', 'PYPL': 'פייפאל',
    'SNOW': 'סנופלייק', 'CRWD': 'קראודסטרייק', 'PANW': 'פאלו אלטו', 'CHKP': 'צ\'ק פוינט', 'WIX': 'וויקס',
    'MBLY': 'מובילאיי', 'TEVA': 'טבע', 'NICE': 'נייס', 'CYBR': 'סייברארק', 'MNDY': 'מאנדיי', 'ESLT': 'אלביט מערכות',
    'TSEM': 'טאואר', 'ANET': 'אריסטה', 'DELL': 'דל', 'HPQ': 'HP', 'SBUX': 'סטארבקס', 'MCD': 'מקדונלד\'ס',
    'NKE': 'נייקי', 'BA': 'בואינג', 'LMT': 'לוקהיד מרטין', 'RTX': 'RTX (רייתיאון)', 'NOC': 'נורת\'רופ גראמן',
    'GD': 'ג\'נרל דיינמיקס', 'GE': 'GE אאירוספייס', 'CAT': 'קטרפילר', 'DE': 'דיר', 'HON': 'האניוול',
    'UPS': 'UPS', 'FDX': 'פדקס', 'MMM': '3M', 'F': 'פורד', 'GM': 'ג\'נרל מוטורס', 'AZN': 'אסטרהזניקה',
    'NVO': 'נובו נורדיסק', 'BMY': 'בריסטול מאיירס', 'AMGN': 'אמג\'ן', 'GILD': 'גיליאד', 'REGN': 'רג\'נרון',
    'VRTX': 'ורטקס', 'MRNA': 'מודרנה', 'ABT': 'אבוט', 'TMO': 'תרמו פישר', 'DHR': 'דנאהר', 'ISRG': 'אינטואיטיב סרג\'יקל',
    'MDT': 'מדטרוניק', 'SYK': 'סטרייקר', 'CVS': 'CVS', 'CI': 'סיגנה', 'ELV': 'אלבנס', 'HUM': 'יומנה',
    'BP': 'BP', 'SHEL': 'של', 'COP': 'קונוקו פיליפס', 'OXY': 'אוקסידנטל', 'SLB': 'שלומברז\'ה',
    'MNST': 'מונסטר', 'MDLZ': 'מונדלז', 'CL': 'קולגייט', 'PM': 'פיליפ מוריס', 'MO': 'אלטריה', 'KHC': 'קראפט היינץ',
    'MAR': 'מריוט', 'BKNG': 'בוקינג', 'SPOT': 'ספוטיפיי', 'ROKU': 'רוקו', 'EL': 'אסתי לאודר', 'SONY': 'סוני',
    'TM': 'טויוטה', 'BABA': 'עליבאבא', 'PDD': 'PDD (טמו)', 'JD': 'JD.com', 'NEE': 'נקסטרה אנרג\'י',
    'DUK': 'דיוק אנרג\'י', 'SO': 'סאות\'רן', 'D': 'דומיניון אנרג\'י', 'EXC': 'אקסלון', 'AMT': 'אמריקן טאוור',
    'PLD': 'פרולוג\'יס', 'O': 'ריאלטי אינקם', 'LIN': 'לינדה', 'SPGI': 'S&P גלובל', 'ICE': 'ICE', 'CME': 'CME',
    'COIN': 'קוינבייס', 'HOOD': 'רובינהוד', 'MSTR': 'מייקרוסטרטג\'י', 'SMCI': 'סופר מיקרו', 'ON': 'און סמיקונדקטור',
    'MRVL': 'מארוול', 'CCJ': 'קמקו', 'KVUE': 'קנוויו', 'CHD': 'צ\'רץ\' אנד דוויט', 'ETN': 'איטון',
    'MPC': 'מרתון פטרוליום', 'WMB': 'ויליאמס', 'FANG': 'דיימונדבק', 'CNI': 'הרכבת הקנדית', 'RYAAY': 'ריינאייר',
}

NAME_SUFFIXES = re.compile(
    r'(,?\s+(Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.?|Holdings?|PLC|plc|Ltd\.?|Limited|'
    r'N\.V\.|S\.A\.|SE|AG|Sponsored|ADR|Class [A-C]|Cl [A-C]|Common Stock|Group Inc\.?))+\s*$',
    re.I)


def company_name(sym, name=''):
    if sym in HE_NAMES:
        return HE_NAMES[sym]
    n = (name or '').strip()
    prev = None
    while n and n != prev:
        prev = n
        n = NAME_SUFFIXES.sub('', n).strip(' ,')
    return n or sym


# ---------- data loading ----------

def load_json(name):
    """Returns (data, None) or (None, reason). Never raises."""
    try:
        if DATA_DIR:
            with open(os.path.join(DATA_DIR, name), encoding='utf-8') as f:
                return json.load(f), None
        r = requests.get(f'{SITE_DATA}/{name}', timeout=20)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}'
        return r.json(), None
    except FileNotFoundError:
        return None, 'הקובץ חסר'
    except Exception as e:  # network / bad json
        return None, f'{type(e).__name__}'


_bars_cache = {}


def load_bars(sym):
    """[(date_str, close), ...] sorted, or None."""
    if sym not in _bars_cache:
        data, _ = load_json(f'bars/{sym}.json')
        bars = None
        if isinstance(data, dict) and data.get('bars'):
            bars = sorted((b[0], float(b[4])) for b in data['bars'] if b and b[4] is not None)
        _bars_cache[sym] = bars
    return _bars_cache[sym]


def parse_updated(meta):
    """'30/10/2026 12:31' (Israel time) -> aware datetime or None."""
    try:
        return datetime.strptime(meta['updatedAt'], '%d/%m/%Y %H:%M').replace(tzinfo=IL)
    except Exception:
        return None


def prev_weekday(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ---------- formatting helpers ----------

def pct(x, digits=2):
    if x is None:
        return '—'
    return f'{x:+.{digits}f}%'.replace('+-', '-')


def money(x):
    return f'${x:,.0f}'


def short_date(iso):
    d = date.fromisoformat(iso)
    return f'{d.day}.{d.month}'


def with_lrm(s):
    # Keeps "+1.2%" / tickers from flipping inside RTL lines in Telegram.
    return f'‎{s}‎'


# ---------- section 2: market ----------

NUM_RE = re.compile(r'\d+(?:[.,]\d+)*')


def numbers_in(text):
    return {n.replace(',', '') for n in NUM_RE.findall(text or '')}


def llm_market_sentences(analysis, facts_text):
    """2–3 Hebrew sentences from the daily analysis. Returns None on any failure
    or if the model wrote a number that is not in the source material."""
    key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    if not key:
        return None
    source = '\n'.join([
        f"כותרת: {analysis.get('headline', '')}",
        f"תקציר: {analysis.get('tldr', '')}",
        f"שורה תחתונה: {analysis.get('bottomline', '')}",
        f"מה לבדוק: {analysis.get('watchFor', '')}",
        'נתונים:',
        facts_text,
    ])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{
                'role': 'user',
                'content': f"""אתה כותב את פסקת השוק בבריף בוקר בטלגרם למשקיע פרטי.
כתוב 2 עד 3 משפטים קצרים בעברית: מה קרה אתמול בוול סטריט, איך נראים החוזים הבוקר, ומה המשמעות.

חוקים:
- התבסס אך ורק על החומר שלמטה. אל תוסיף עובדות, שמות או אירועים שלא מופיעים בו.
- אל תכתוב מספרים, אחוזים או רמות מחיר — הם מופיעים בשורות נפרדות מתחת לפסקה. כתוב במילים ("ירידה מתונה", "נפילה חדה").
- בלי כותרת, בלי תבליטים, בלי אימוג'י. רק המשפטים.

החומר:
{source}""",
            }],
        )
        text = response.content[0].text.strip()
    except Exception as e:
        print(f'LLM failed: {type(e).__name__}: {e}')
        return None
    invented = numbers_in(text) - numbers_in(source) - {'500'}
    if invented:
        print(f'LLM output rejected, numbers not in source: {invented}')
        return None
    if len(text) > 700:
        print('LLM output rejected: too long')
        return None
    return text


def market_section(analysis, market, last_session, now, use_llm=True):
    lines = ['📉 **השוק**']
    notes = []

    ana_ok = isinstance(analysis, dict) and analysis.get('date') and (
        last_session is None or analysis['date'] >= last_session.isoformat())
    if analysis is not None and not ana_ok:
        notes.append(f"הניתוח היומי ישן ({analysis.get('date', '?')})")

    mkt_items = {}
    mkt_ok = False
    if isinstance(market, dict):
        upd = parse_updated(market.get('_meta', {}))
        mkt_ok = upd is not None and now - upd <= timedelta(hours=12)
        if mkt_ok:
            mkt_items = {it['key']: it for it in market.get('items', [])}
        else:
            notes.append(f"נתוני השוק ישנים (עודכנו {market.get('_meta', {}).get('updatedAt', '?')})")

    facts = []
    if mkt_items:
        spy, qqq, iwm = mkt_items.get('spy'), mkt_items.get('qqq'), mkt_items.get('iwm')
        es, nq, vix = mkt_items.get('es'), mkt_items.get('nq'), mkt_items.get('vix')
        y = []
        if es and es.get('indexClose') and spy:
            y.append(f"S&P 500 (SPY) {pct(spy.get('chg'))}, סגירה {es['indexClose']:,.0f}")
        elif spy:
            y.append(f"S&P 500 (SPY) {pct(spy.get('chg'))}")
        if qqq:
            y.append(f"נאסד\"ק 100 (QQQ) {pct(qqq.get('chg'))}")
        if iwm:
            y.append(f"ראסל 2000 (IWM) {pct(iwm.get('chg'))}")
        if y:
            when = ''
            if es and es.get('indexCloseDate'):
                d = date.fromisoformat(es['indexCloseDate'])
                when = f" (יום {DAY_NAMES[d.weekday()]})"
            facts.append(f'• בסגירה{when}: ' + ' · '.join(y))
        f = []
        if es:
            f.append(f"S&P {pct(es.get('overnight', es.get('chg')))}")
        if nq:
            f.append(f"נאסד\"ק {pct(nq.get('overnight', nq.get('chg')))}")
        if f:
            facts.append('• החוזים הבוקר: ' + ' · '.join(f))
        vl = market.get('vixLight') or {}
        if vix or vl:
            v = vl.get('vix') or (vix or {}).get('price')
            light = {'green': '🟢 ירוק', 'yellow': '🟡 צהוב', 'red': '🔴 אדום'}.get(vl.get('state'), '')
            s = f'• VIX {v:.1f}' if v else '• VIX'
            if light:
                s += f' · רמזור {light}'
            if vl.get('ratio'):
                s += f" ({pct((vl['ratio'] - 1) * 100, 0)} מול ממוצע 50 יום)"
            if vl.get('spike'):
                s += ' · ⚠️ דיברגנס'
            facts.append(s)

    if not ana_ok and not mkt_items:
        why = '; '.join(notes) or 'הקבצים לא נטענו'
        return lines + [f'⚠️ אין נתוני שוק עדכניים ({why}) — החלק דולג.']

    prose = None
    if ana_ok:
        prose = llm_market_sentences(analysis, '\n'.join(facts)) if use_llm else None
        if not prose:
            prose = analysis.get('headline') or analysis.get('tldr', '')
    if prose:
        lines.append(prose)
    lines += facts
    if ana_ok and analysis.get('bottomline'):
        bl = re.sub(r'^\s*שורה תחתונה:\s*', '', analysis['bottomline'])
        lines.append(f'🎯 שורה תחתונה: {bl}')
    for n in notes:
        lines.append(f'⚠️ {n} — דילגתי עליו.')
    return lines


# ---------- section 3: earnings ----------

def earnings_section(earnings, today):
    lines = ['🏢 **מדווחות היום**']
    if not isinstance(earnings, dict):
        return lines + ['⚠️ לוח הדוחות לא נטען — החלק דולג.']
    if earnings.get('today') != today.isoformat():
        return lines + [f"⚠️ לוח הדוחות ישן (של {earnings.get('today', '?')}) — החלק דולג."]
    big = earnings.get('todayBig') or []
    if not big:
        return lines + ['אין היום דוחות של חברות גדולות.']
    when = {r.get('ticker'): r.get('when') for r in earnings.get('reporting') or []}
    tag = {'before': 'לפני הפתיחה', 'after': 'אחרי הסגירה'}
    groups = {}
    for c in big:
        groups.setdefault(tag.get(when.get(c['ticker']), 'שעה לא ידועה'), []).append(
            c['ticker'] if company_name(c['ticker'], c.get('name')) == c['ticker']
            else f"{company_name(c['ticker'], c.get('name'))} ({c['ticker']})")
    for label in ['לפני הפתיחה', 'אחרי הסגירה', 'שעה לא ידועה']:
        if label in groups:
            lines.append(f'• {label}: ' + ', '.join(groups[label]))
    total = earnings.get('todayCount')
    if total and total > len(big):
        lines.append(f'סה"כ {total} חברות מדווחות היום.')
    return lines


# ---------- section 4: macro ----------

def econ_section(econ, now):
    lines = ['🏛 **מאקרו**']
    if not isinstance(econ, dict):
        return lines + ['⚠️ יומן המאקרו לא נטען — החלק דולג.']
    upd = parse_updated(econ.get('_meta', {}))
    if upd is None or now - upd > timedelta(hours=72):
        return lines + [f"⚠️ יומן המאקרו ישן (עודכן {econ.get('_meta', {}).get('updatedAt', '?')}) — החלק דולג."]
    events = []
    for e in econ.get('events') or []:
        try:
            t = datetime.fromisoformat(e['date']).replace(tzinfo=ZoneInfo('UTC')).astimezone(IL)
        except Exception:
            continue
        events.append((t, e))
    events.sort(key=lambda x: x[0])

    def fmt(e):
        s = e.get('he', '')
        if e.get('period'):
            s += f" ({e['period']})"
        s += f" — צפי {e['forecast']}" if e.get('forecast') else ' — אין צפי'
        if e.get('previous'):
            s += f", קודם {e['previous']}"
        return s

    todays = [(t, e) for t, e in events if t.date() == now.date()]
    if todays:
        for t, e in todays:
            lines.append(f"• {t:%H:%M} {fmt(e)}")
        return lines
    lines.append('היום אין נתון מתוזמן.')
    upcoming = [(t, e) for t, e in events if t > now]
    if upcoming:
        t0 = upcoming[0][0]
        same = [e for t, e in upcoming if t == t0]
        names = ', '.join(e.get('he', '') for e in same)
        lines.append(f"הבא: יום {DAY_NAMES[t0.weekday()]} {t0.day}.{t0.month} ב-{t0:%H:%M} — {names}")
        for e in same:
            if e.get('forecast'):
                lines.append(f"  {e['he']}: צפי {e['forecast']}")
    return lines


# ---------- section 5: picks ----------

def picks_fresh(picks, today):
    return isinstance(picks, dict) and picks.get('date') and \
        date.fromisoformat(picks['date']) >= today - timedelta(days=5)


def picks_section(picks, today):
    lines = ['✦ **הנבחרות**']
    if not isinstance(picks, dict):
        return lines + ['⚠️ קובץ הנבחרות לא נטען — החלק דולג.']
    if not picks_fresh(picks, today):
        return lines + [f"⚠️ מהדורת הנבחרות ישנה ({picks.get('date', '?')}) — החלק דולג."]
    items = picks.get('picks') or []
    head = f"מהדורת {short_date(picks['date'])}"
    if picks.get('momOnly'):
        head += ' (מהמומנטום בלבד)'
    if not items:
        lines.append(f'{head}: אין מניות שקיבלו אישור מחיר.')
    else:
        new = [p for p in items if not p.get('since')]
        old = [p for p in items if p.get('since')]
        lines.append(f'{head}, {len(items)} מניות:')
        if new:
            lines.append('• חדשות: ' + ', '.join(p['sym'] for p in new))
        if old:
            lines.append('• ממשיכות: ' + ', '.join(f"{p['sym']} (מ-{short_date(p['since'])})" for p in old))
    gate = picks.get('gate') or {}
    if gate.get('label'):
        dot = {'green': '🟢', 'yellow': '🟠', 'neutral': '🟠', 'red': '🔴'}.get(gate.get('state'), '')
        g = f"מצב השוק: {dot} {gate['label']}".replace('  ', ' ')
        extra = [x for x in [f"עד {gate['maxPos']} פוזיציות" if gate.get('maxPos') else '', gate.get('sizing', '')] if x]
        if extra:
            g += f" ({', '.join(extra)})"
        lines.append(g)
    pend = picks.get('pending')
    if isinstance(pend, dict) and pend.get('waiting'):
        lines.append(f"⏳ המהדורה הבאה ממתינה ל{' ול'.join(pend['waiting'])}.")
    return lines


# ---------- section 6: virtual portfolio ----------

def new_portfolio():
    return {
        'note': 'תיק וירטואלי — סימולציה בלבד, בלי כסף אמיתי',
        'start_cash': START_CASH,
        'start_date': None,
        'spy_start': None,
        'cash': START_CASH,
        'last_day': None,
        'positions': [],
        'closed': [],
    }


def editions_from_sources(picks, ledger):
    """[{date, symbols:[{sym, entry, stop, target}]}] — the ledger gives every
    edition (so missed days are caught up); picks.json adds targets and the
    buy zone for the edition it holds."""
    by_sym = {}
    if isinstance(picks, dict):
        by_sym = {p['sym']: p for p in picks.get('picks') or []}
    eds = []
    if isinstance(ledger, dict) and ledger.get('editions'):
        for e in ledger['editions']:
            syms = []
            for s in e.get('symbols') or []:
                p = by_sym.get(s['sym']) if isinstance(picks, dict) and picks.get('date') == e['date'] else None
                syms.append({
                    'sym': s['sym'],
                    'entry': (p or {}).get('entry') or s.get('entry') or (p or {}).get('price'),
                    'stop': (p or {}).get('stop') or s.get('stop'),
                    'target': (p or {}).get('target'),
                })
            eds.append({'date': e['date'], 'symbols': syms})
    elif isinstance(picks, dict) and picks.get('date'):
        eds.append({'date': picks['date'], 'symbols': [
            {'sym': p['sym'], 'entry': p.get('entry') or p.get('price'), 'stop': p.get('stop'), 'target': p.get('target')}
            for p in picks.get('picks') or [] if not p.get('since')]})
    return sorted(eds, key=lambda e: e['date'])


def close_on(sym, day):
    bars = load_bars(sym)
    if not bars:
        return None
    for d, c in reversed(bars):
        if d == day:
            return c
        if d < day:
            return None
    return None


def last_close(sym):
    bars = load_bars(sym)
    return bars[-1][1] if bars else None


def run_portfolio(pf, editions, spy_days, upto=None):
    """Replays every trading day after pf['last_day'] (up to `upto`).
    Per day: sell on that day's close, then buy that day's edition at entry.
    Returns (bought, sold) lists for the message."""
    bought, sold = [], []
    if pf['last_day'] is None:
        if not editions:
            return bought, sold
        # First run: start with the latest edition.
        first = editions[-1]['date']
        pf['last_day'] = max([d for d in spy_days if d < first], default=None) or first
        pf['start_date'] = first
    days = [d for d in spy_days if d > pf['last_day'] and (upto is None or d <= upto)]
    for day in days:
        # sells
        keep = []
        for p in pf['positions']:
            c = close_on(p['sym'], day)
            if c is None or day <= p['bought']:
                keep.append(p)
                continue
            held = sum(1 for d in spy_days if p['bought'] < d <= day)
            reason = None
            if p.get('stop') and c < p['stop']:
                reason = 'סטופ'
            elif p.get('target') and c > p['target']:
                reason = 'יעד'
            elif held >= MAX_HOLD_DAYS:
                reason = f'{MAX_HOLD_DAYS} ימי מסחר'
            if reason:
                value = p['shares'] * c
                pf['cash'] += value
                rec = {**p, 'sold': day, 'exit': c, 'pnl': value - p['cost'],
                       'ret': (c / p['entry'] - 1) * 100, 'reason': reason, 'days': held}
                pf['closed'].append(rec)
                sold.append(rec)
            else:
                keep.append(p)
        pf['positions'] = keep
        # buys
        for ed in editions:
            if ed['date'] != day:
                continue
            for s in ed['symbols']:
                held_syms = {p['sym'] for p in pf['positions']}
                if s['sym'] in held_syms or not s.get('entry'):
                    continue
                if len(pf['positions']) >= MAX_POSITIONS or pf['cash'] < POSITION_SIZE - 1e-6:
                    bought.append({'sym': s['sym'], 'skipped': 'אין מזומן/מקום'})
                    continue
                pos = {'sym': s['sym'], 'entry': s['entry'], 'stop': s.get('stop'), 'target': s.get('target'),
                       'shares': POSITION_SIZE / s['entry'], 'cost': POSITION_SIZE, 'bought': day, 'edition': ed['date']}
                pf['cash'] -= POSITION_SIZE
                pf['positions'].append(pos)
                bought.append(pos)
        pf['last_day'] = day
        if pf['spy_start'] is None and day >= (pf['start_date'] or day):
            pf['spy_start'] = close_on('SPY', day)
            pf['start_date'] = day
    return bought, sold


def portfolio_value(pf):
    total = pf['cash']
    for p in pf['positions']:
        c = last_close(p['sym'])
        total += p['shares'] * (c if c is not None else p['entry'])
    return total


def portfolio_section(pf, bought, sold, note=None):
    lines = ['💼 **התיק שלנו** (וירטואלי, סימולציה)']
    if note:
        lines.append(f'⚠️ {note}')
    if pf.get('start_date') is None or pf.get('last_day') is None:
        return lines + ['התיק יתחיל ב-$10,000 עם מהדורת הנבחרות הראשונה שתיקרא.']
    buys = [b for b in bought if not b.get('skipped')]
    if buys:
        lines.append(f"• נקנו ({money(POSITION_SIZE)} כל אחת): " + ', '.join(f"{b['sym']} ${b['entry']:,.2f}" for b in buys))
    skipped = [b['sym'] for b in bought if b.get('skipped')]
    if skipped:
        lines.append(f"• לא נקנו (אין מזומן או מקום): {', '.join(skipped)}")
    for s in sold:
        lines.append(f"• נמכרה {s['sym']} ב-${s['exit']:,.2f}: {pct(s['ret'], 1)} "
                     f"({'+' if s['pnl'] >= 0 else '-'}{money(abs(s['pnl']))}) — {s['reason']}, אחרי {s['days']} ימים")
    if not bought and not sold:
        lines.append('• אין קניות או מכירות היום.')
    value = portfolio_value(pf)
    ret = (value / pf['start_cash'] - 1) * 100
    s = f"שווי התיק: {money(value)} ({pct(ret)} מההתחלה)"
    spy_now = last_close('SPY')
    if pf.get('spy_start') and spy_now:
        s += f" · SPY מאותו יום: {pct((spy_now / pf['spy_start'] - 1) * 100)}"
    lines.append(s)
    if pf['positions']:
        held = []
        for p in pf['positions']:
            c = last_close(p['sym'])
            held.append(f"{p['sym']} {pct((c / p['entry'] - 1) * 100, 1)}" if c else p['sym'])
        lines.append(f"פתוחות ({len(pf['positions'])}): " + ', '.join(held))
    lines.append(f"מזומן: {money(pf['cash'])} · התחלה {short_date(pf['start_date'])} עם {money(pf['start_cash'])}")
    return lines


# ---------- assembly ----------

def build_brief(now, pf, use_llm=True):
    """Returns (message, pf_changed)."""
    today = now.date()
    analysis, _ = load_json('claude_analysis.json')
    market, _ = load_json('market.json')
    econ, _ = load_json('econ.json')
    earnings, _ = load_json('earnings.json')
    picks, _ = load_json('picks.json')
    ledger, _ = load_json('picks_ledger.json')

    spy = load_bars('SPY')
    last_session = None
    if spy and date.fromisoformat(spy[-1][0]) >= today - timedelta(days=6):
        last_session = date.fromisoformat(spy[-1][0])
    elif not spy:
        last_session = prev_weekday(today)

    sections = [
        [f'☀️ **בריף בוקר · יום {DAY_NAMES[today.weekday()]} {today:%d.%m.%Y}**'],
        market_section(analysis, market, last_session, now, use_llm),
        earnings_section(earnings, today),
        econ_section(econ, now),
        picks_section(picks, today),
    ]

    pf_changed = False
    if not spy or last_session is None:
        sections.append(portfolio_section(pf, [], [], 'נתוני המחירים (bars) חסרים או ישנים — התיק לא עודכן היום.'))
    else:
        note = None
        if not (picks_fresh(picks, today) or isinstance(ledger, dict)):
            note = 'מהדורת הנבחרות חסרה או ישנה — רק מכירות נבדקו היום.'
            editions = []
        else:
            editions = editions_from_sources(picks if picks_fresh(picks, today) else None, ledger)
        bought, sold = run_portfolio(pf, editions, [d for d, _ in spy])
        pf_changed = True
        sections.append(portfolio_section(pf, bought, sold, note))

    sections.append(['nditzik.github.io/nidam-markets'])
    return '\n\n'.join('\n'.join(s) for s in sections), pf_changed


def read_json_file(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


async def send(message):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    session = os.getenv('TG_STRING_SESSION', '').strip()
    async with TelegramClient(StringSession(session) if session else 'session',
                              int(os.getenv('TG_API_ID')), os.getenv('TG_API_HASH')) as client:
        await client.send_message(KOBI, message)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true', help='print only: no send, nothing saved')
    ap.add_argument('--send-now', action='store_true', help='ignore the 09:00 check (still once a day)')
    ap.add_argument('--now', help='override current time (ISO, Israel time) for testing')
    ap.add_argument('--no-llm', action='store_true')
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now).replace(tzinfo=IL) if args.now else datetime.now(IL)
    state = read_json_file(STATE_FILE, {})

    if not args.test:
        if now.weekday() >= 5:
            print(f'{now:%Y-%m-%d %H:%M} Israel — weekend, not sending.')
            return
        if not args.send_now and now.hour != 9:
            print(f'{now:%Y-%m-%d %H:%M} Israel — not 09:xx, not sending.')
            return
        if state.get('last_sent') == now.date().isoformat():
            print(f'Already sent today ({state["last_sent"]}).')
            return

    pf = read_json_file(PORTFOLIO_FILE, None) or new_portfolio()
    message, pf_changed = build_brief(now, pf, use_llm=not args.no_llm)

    if args.test:
        print(message)
        print(f'\n--- test mode: not sent, nothing saved ({len(message)} chars) ---')
        return

    asyncio.run(send(message))
    print(f'Brief sent ({len(message)} chars).')
    if pf_changed:
        write_json_file(PORTFOLIO_FILE, pf)
    state['last_sent'] = now.date().isoformat()
    write_json_file(STATE_FILE, state)


if __name__ == '__main__':
    sys.exit(main())
