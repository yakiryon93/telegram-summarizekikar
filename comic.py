"""Comic-style picture of a brief: each section of the Telegram text becomes a
panel (title, short lines, a speech bubble), rendered to PNG with Playwright.

Built from the finished message text, so the picture always says the same
thing as the message. Any failure returns None and the text is sent alone."""

import html
import os
import re

PALETTE = ['#b8f2c9', '#ffd23f', '#ffc4c4', '#e0c3fc', '#bde0fe', '#ffd6a5', '#c7f9cc', '#ffe5ec']
LINE_MAX = 150
LINES_PER_PANEL = 5

NUM = re.compile(r'((?:(?<!\w)[+\-−])?\$?\d{1,2}:\d{2}|(?:(?<!\w)[+\-−])?\$?\d[\d,]*(?:\.\d+)?[%KMB]?)')
EMOJI_START = re.compile(r'^([^\w\s"\'(*]{1,3})\s*')


def _clean(t):
    return t.replace('**', '').replace('‎', '').replace('‏', '').strip()


def _short(t):
    """First sentence(s) up to LINE_MAX characters."""
    if len(t) <= LINE_MAX:
        return t
    cut = t[:LINE_MAX]
    for sep in ('. ', '; ', ' — ', ', '):
        i = cut.rfind(sep)
        if i > 60:
            return cut[:i].rstrip(' .;,—') + '.'
    return cut.rsplit(' ', 1)[0] + '…'


def _fmt(t):
    """Escape and color the numbers (green up, red down), each kept LTR."""
    out = []
    for part in NUM.split(html.escape(t, quote=False)):
        if NUM.fullmatch(part) and any(ch.isdigit() for ch in part):
            cls = 'up' if part.startswith('+') else 'dn' if part[0] in '-−' else ''
            if ':' in part:
                cls = ''
            out.append(f'<span class="n {cls}">{part}</span>')
        else:
            out.append(part)
    return ''.join(out)


def panels_from_message(message):
    """[(title, emoji, lines, bubble)] from the brief's sections."""
    sections = [s.strip() for s in message.split('\n\n') if s.strip()]
    title = _clean(sections[0].split('\n')[0]).replace('📅', '🗞️') if sections else ''
    panels = []
    for sec in sections[1:]:
        rows = [r for r in sec.split('\n') if r.strip()]
        if not rows or 'nditzik.github.io' in rows[0]:
            continue
        head = _clean(rows[0])
        m = EMOJI_START.match(head)
        emoji = m.group(1) if m else ''
        head = head[m.end():] if m else head
        lines, bubble = [], None
        # "🏢 **דוחות היום** · לפני: ..." — the rest of the header line is content
        bold = re.match(r'^\S*\s*\*\*(.+?)\*\*\s*(.*)$', rows[0])
        if bold:
            head = _clean(bold.group(1))
            rest = bold.group(2).strip().lstrip('·:').strip()
            if rest:
                lines.append(_clean(rest))
        for r in rows[1:]:
            r = _clean(r)
            if not r or r.startswith('⚠️') and 'דילגתי' in r:
                continue
            if r.startswith('🎯'):
                bubble = r.lstrip('🎯').strip()
            elif bubble is None and not lines and not r.startswith(('•', '✦', '⚠️')) and not re.match(r'^\d', r):
                bubble = r
            else:
                lines.append(r.lstrip('•').strip())
        lines = [_short(re.sub(r'^\d️⃣\s*', '', l)) for l in lines if l][:LINES_PER_PANEL]
        if bubble:
            bubble = _short(bubble)
        if lines or bubble:
            panels.append((head, emoji, lines, bubble))
    return title, panels


def render_html(title, panels, footer='nditzik.github.io/nidam-markets · תיק וירטואלי, לא המלצה'):
    cells = []
    for i, (head, emoji, lines, bubble) in enumerate(panels):
        wide = ' wide' if (i == len(panels) - 1 and len(panels) % 2) else ''
        body = ''.join(f'<li>{_fmt(l)}</li>' for l in lines)
        bub = f'<div class="bub">{_fmt(bubble)}</div>' if bubble else ''
        cells.append(f'<div class="p{wide}" style="background-color:{PALETTE[i % len(PALETTE)]}">'
                     f'<h2>{html.escape(emoji)} {html.escape(head)}</h2>'
                     f'{bub}<ul>{body}</ul></div>')
    return f'''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Secular+One&family=Rubik:wght@400;600;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:720px;background:#fff7d6;font-family:Rubik,sans-serif;color:#111;padding:18px}}
.title{{background:#111;color:#ffd23f;font-family:'Secular One',Rubik,sans-serif;font-size:27px;text-align:center;padding:10px 8px;border-radius:6px;transform:rotate(-1deg);box-shadow:5px 5px 0 #e63946;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.p{{border:4px solid #111;border-radius:6px;padding:12px;box-shadow:6px 6px 0 #111;
   background-image:radial-gradient(rgba(0,0,0,.08) 1.2px,transparent 1.3px);background-size:9px 9px}}
.p.wide{{grid-column:1 / span 2}}
.p h2{{font-family:'Secular One',Rubik,sans-serif;font-size:20px;display:inline-block;background:#111;color:#fff;padding:2px 10px;border-radius:4px;margin-bottom:8px}}
.bub{{background:#fff;border:3px solid #111;border-radius:18px;padding:8px 11px;font-size:15px;line-height:1.45;position:relative;margin:4px 0 14px;font-weight:600}}
.bub:after{{content:"";position:absolute;bottom:-13px;right:26px;border:10px solid transparent;border-top-color:#111}}
ul{{list-style:none}}li{{font-size:15px;font-weight:600;line-height:1.5;margin-bottom:3px}}
.n{{font-weight:800;direction:ltr;unicode-bidi:isolate}}.up{{color:#0a8a3a}}.dn{{color:#d62828}}
.foot{{margin-top:16px;text-align:center;font-size:13px;font-weight:600}}
</style></head><body>
<div class="title">{html.escape(title)}</div>
<div class="grid">{''.join(cells)}</div>
<div class="foot">{html.escape(footer)}</div>
</body></html>'''


def render_comic(message, path):
    """Writes a PNG of the message to `path`. Returns path or None."""
    try:
        title, panels = panels_from_message(message)
        if not panels:
            return None
        page_html = render_html(title, panels)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = os.getenv('CHROMIUM_PATH') or None
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            page = browser.new_page(viewport={'width': 720, 'height': 300}, device_scale_factor=2)
            page.set_content(page_html, wait_until='networkidle', timeout=30000)
            page.evaluate('document.fonts.ready')
            page.screenshot(path=path, full_page=True)
            browser.close()
        return path
    except Exception as e:
        print(f'Comic failed: {type(e).__name__}: {e}')
        return None
