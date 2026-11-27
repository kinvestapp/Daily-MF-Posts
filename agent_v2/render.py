"""Render the 3 carousel slides (modern fintech theme) with Playwright.

All text is drawn by HTML/CSS (never by an image model), so rupee signs, dashes
and the compliance footer are always exact. Output is 1440x1800 JPEG (4:5), which is
Instagram's native maximum width for feed images and the only format the Graph API accepts.
"""
import base64
import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
LOGO = ROOT / "assets" / "logo.png"

W, H = 1080, 1350
SCALE = 4 / 3  # 1080 -> 1440 px wide
MARGIN = 64

FOOTER_ID = "ARN-366802 | AMFI-registered Mutual Fund Distributor | www.assetplus.in/mfd/ARN-366802"
FOOTER_RISK = "Mutual Fund investments are subject to market risks, read all scheme related documents carefully"

ICON_PATHS = {
    "growth": '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.2 8.2-8 9-4.8-.8-8-4.5-8-9V6l8-3z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "cap": '<path d="M2 9l10-5 10 5-10 5-10-5z"/><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5"/><path d="M22 9v6"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M9 8h6M9 11h6M10 8c3 0 4.5 1.5 4.5 3s-1.5 3-4.5 3l4 4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.7 3 2.7 15 0 18M12 3c-2.7 3-2.7 15 0 18"/>',
    "handshake": '<path d="M2 12l5-4 4 2 3-2 6 4"/><path d="M4 14l5 5 2-1.5M9 13l4 4 2-1.5M13 11l4.5 4.5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "bookmark": '<path d="M6 3h12v18l-6-4.5L6 21V3z"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}


def icon(name, size=64, stroke="#0B1B3F", width=1.7):
    path = ICON_PATHS.get(name, ICON_PATHS["growth"])
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{path}</svg>')


def esc(s):
    return html.escape(str(s or ""), quote=True)


def _font_face():
    rules = []
    ranges = {
        "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
    }
    for weight in (500, 700, 800):
        for subset, urange in ranges.items():
            f = FONT_DIR / f"inter-{subset}-{weight}-normal.woff2"
            b64 = base64.b64encode(f.read_bytes()).decode()
            rules.append(
                "@font-face{font-family:'InterK';font-style:normal;font-weight:%d;font-display:block;"
                "src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}" % (weight, b64, urange)
            )
    return "\n".join(rules)


def _logo_uri():
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(W)dpx;height:%(H)dpx;background:#0B1B3F;font-family:'InterK',-apple-system,'Segoe UI',Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.frame{position:relative;width:%(W)dpx;height:%(H)dpx;overflow:hidden;color:#fff;
  background:
   radial-gradient(900px 700px at 100%% 0%%, rgba(212,162,76,.22), transparent 60%%),
   radial-gradient(800px 800px at 0%% 100%%, rgba(56,189,248,.14), transparent 60%%),
   linear-gradient(160deg,#0E2250 0%%,#0B1B3F 55%%,#08122B 100%%)}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:54px 54px;
  -webkit-mask-image:radial-gradient(circle at 70%% 30%%,#000 0%%,transparent 70%%);mask-image:radial-gradient(circle at 70%% 30%%,#000 0%%,transparent 70%%)}
.top{position:absolute;left:%(M)dpx;right:%(M)dpx;top:56px;display:flex;justify-content:space-between;align-items:center}
.pager{display:flex;gap:10px;align-items:center}
.dot{width:12px;height:12px;border-radius:99px;background:rgba(255,255,255,.28)}
.dot.on{width:44px;background:#D4A24C}
.badge{background:#fff;border-radius:18px;padding:10px 16px;display:flex;align-items:center}
.badge img{height:58px;display:block}
.main{position:absolute;left:%(M)dpx;right:%(M)dpx;top:190px;bottom:170px;display:flex;flex-direction:column}
.kicker{align-self:flex-start;font-weight:700;font-size:26px;letter-spacing:.14em;text-transform:uppercase;color:#F2C879;border:2px solid rgba(242,200,121,.55);border-radius:99px;padding:12px 26px}
.h1{text-wrap:balance;font-weight:800;letter-spacing:-.025em;line-height:1.04;margin-top:44px;font-size:104px;color:#fff}
.h1 em{font-style:normal;color:#F2C879}
.sub{margin-top:34px;font-weight:500;font-size:36px;line-height:1.35;color:rgba(255,255,255,.78);max-width:880px}
.hero{position:absolute;right:-40px;bottom:150px;width:520px;height:520px;display:flex;align-items:center;justify-content:center}
.ring{position:absolute;border-radius:50%%;border:2px solid rgba(255,255,255,.10)}
.orb{position:relative;width:220px;height:220px;border-radius:50%%;background:linear-gradient(145deg,#F7D58E,#D4A24C);display:flex;align-items:center;justify-content:center;box-shadow:0 30px 80px rgba(212,162,76,.35)}
.swipe{position:absolute;left:%(M)dpx;bottom:200px;display:flex;align-items:center;gap:14px;font-weight:700;font-size:28px;color:#F2C879}
.title{text-wrap:balance;font-weight:800;font-size:68px;line-height:1.08;letter-spacing:-.02em;margin-top:6px}
.cards{margin-top:46px;display:flex;flex-direction:column;gap:26px}
.card{display:flex;gap:30px;align-items:flex-start;background:linear-gradient(135deg,rgba(255,255,255,.10),rgba(255,255,255,.04));border:1.5px solid rgba(255,255,255,.14);border-radius:36px;padding:38px 40px}
.num{flex:none;width:84px;height:84px;border-radius:26px;background:linear-gradient(145deg,#F7D58E,#D4A24C);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:42px;color:#0B1B3F}
.ct{font-weight:800;font-size:40px;letter-spacing:-.01em;line-height:1.15}
.cx{margin-top:10px;font-weight:500;font-size:31px;line-height:1.38;color:rgba(255,255,255,.80)}
.corner{position:absolute;right:%(M)dpx;top:190px;width:110px;height:110px;border-radius:32px;background:linear-gradient(145deg,#F7D58E,#D4A24C);display:flex;align-items:center;justify-content:center}
.cta-wrap{justify-content:center}
.cta-orb{width:150px;height:150px;border-radius:50%%;margin-bottom:54px;background:linear-gradient(145deg,#F7D58E,#D4A24C);display:flex;align-items:center;justify-content:center;box-shadow:0 30px 80px rgba(212,162,76,.30)}
.cta-btn{margin-top:54px;align-self:flex-start;display:flex;align-items:center;gap:20px;background:linear-gradient(145deg,#F7D58E,#D4A24C);color:#0B1B3F;font-weight:800;font-size:38px;border-radius:99px;padding:28px 48px;line-height:1.15}
.foot-note{margin-top:34px;font-weight:500;font-size:26px;color:rgba(255,255,255,.62);max-width:860px;line-height:1.4}
.web{margin-top:26px;font-weight:700;font-size:28px;color:#F2C879}
.footer{position:absolute;left:%(M)dpx;right:%(M)dpx;bottom:44px;padding-top:22px;border-top:1.5px solid rgba(255,255,255,.16);color:rgba(255,255,255,.72)}
.f1{font-weight:700;font-size:18.5px;letter-spacing:0;white-space:nowrap}
.f2{margin-top:6px;font-weight:500;font-size:18.5px;color:rgba(255,255,255,.62);white-space:nowrap}
""" % {"W": W, "H": H, "M": MARGIN}

FIT_JS = """
() => {
  // shrink headline-type text until it fits its max line count
  document.querySelectorAll('[data-maxlines]').forEach(el => {
    const max = parseInt(el.dataset.maxlines, 10);
    let size = parseFloat(getComputedStyle(el).fontSize);
    const min = parseFloat(el.dataset.minsize || '48');
    const lines = () => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight));
    while (lines() > max && size > min) { size -= 2; el.style.fontSize = size + 'px'; }
  });
}
"""

QA_JS = """
() => {
  const issues = [];
  const frame = document.querySelector('.frame').getBoundingClientRect();
  const M = %(M)d - 2;
  document.querySelectorAll('[data-safe]').forEach(el => {
    const r = el.getBoundingClientRect();
    const name = el.dataset.safe;
    if (r.left < frame.left + M || r.right > frame.right - M) issues.push(name + ': horizontal overflow');
    if (r.top < frame.top + 40) issues.push(name + ': too close to top');
  });
  const main = document.querySelector('.main');
  const footer = document.querySelector('.footer');
  if (main && footer) {
    let bottom = 0;
    main.querySelectorAll('*').forEach(c => { const r = c.getBoundingClientRect(); if (r.height > 0) bottom = Math.max(bottom, r.bottom); });
    if (bottom > footer.getBoundingClientRect().top - 16) issues.push('content collides with footer');
  }
  if (footer) {
    const fr = footer.getBoundingClientRect();
    if (fr.bottom > frame.bottom - 24) issues.push('footer clipped at bottom');
  }
  if (footer) {
    const ft = footer.getBoundingClientRect().top;
    document.querySelectorAll('[data-above-footer]').forEach(el => {
      const ring = el.querySelector('.orb') || el;
      if (ring.getBoundingClientRect().bottom > ft - 12) issues.push(el.dataset.aboveFooter + ' overlaps footer');
    });
    const f1 = document.querySelector('.f1'); const f2 = document.querySelector('.f2');
    if (f1.scrollWidth > f1.clientWidth + 1 || f1.getBoundingClientRect().height > 30) issues.push('footer line 1 wraps');
    if (f2.getBoundingClientRect().height > 30) issues.push('footer line 2 wraps');
  }
  const bad = [];
  document.querySelectorAll('.h1,.title,.ct,.cx,.sub,.kicker').forEach(el => { if (el.scrollWidth > el.clientWidth + 1) bad.push(el.className); });
  if (bad.length) issues.push('text wider than container: ' + bad.join(','));
  return {issues, text: document.body.innerText};
}
""" % {"M": MARGIN}


def _top(index, total):
    dots = "".join(f'<div class="dot{" on" if i == index else ""}"></div>' for i in range(total))
    return (f'<div class="top"><div class="pager" data-safe="pager">{dots}</div>'
            f'<div class="badge" data-safe="logo"><img src="{_logo_uri()}"/></div></div>')


def _footer():
    return (f'<div class="footer" data-safe="footer"><div class="f1">{esc(FOOTER_ID)}</div>'
            f'<div class="f2">{esc(FOOTER_RISK)}</div></div>')


def _emphasis(headline):
    """Gold-highlight the last 2 words of the hook headline for visual rhythm."""
    words = esc(headline).split()
    if len(words) < 4:
        return " ".join(words)
    return " ".join(words[:-2]) + " <em>" + " ".join(words[-2:]) + "</em>"


def slide_html(slide, index, total):
    kind = slide["kind"]
    if kind == "hook":
        body = (
            f'<div class="main" data-safe="main"><div class="kicker">{esc(slide.get("kicker"))}</div>'
            f'<div class="h1" data-maxlines="5" data-minsize="64" data-safe="headline">{_emphasis(slide["headline"])}</div>'
            f'<div class="sub" data-safe="subhead">{esc(slide.get("subhead"))}</div></div>'
            f'<div class="hero" data-above-footer="hero"><div class="ring" style="width:520px;height:520px"></div>'
            f'<div class="ring" style="width:400px;height:400px"></div>'
            f'<div class="orb">{icon(slide.get("icon", "growth"), 110, "#0B1B3F", 1.6)}</div></div>'
            f'<div class="swipe" data-safe="swipe" data-above-footer="swipe">Swipe {icon("arrow", 34, "#F2C879", 2)}</div>'
        )
    elif kind == "value":
        cards = "".join(
            f'<div class="card" data-safe="card"><div class="num">{i + 1}</div><div>'
            f'<div class="ct">{esc(p["title"])}</div><div class="cx">{esc(p["text"])}</div></div></div>'
            for i, p in enumerate(slide["points"])
        )
        body = (
            f'<div class="main" data-safe="main"><div class="title" data-maxlines="3" data-minsize="48" data-safe="title">{esc(slide["title"])}</div>'
            f'<div class="cards">{cards}</div></div>'
        )
    else:  # cta
        body = (
            f'<div class="main cta-wrap" data-safe="main"><div class="cta-orb" data-above-footer="orb">{icon("target", 84, "#0B1B3F", 1.6)}</div><div class="h1" data-maxlines="4" data-minsize="64" data-safe="headline" style="font-size:92px;margin-top:0">{_emphasis(slide["headline"])}</div>'
            f'<div class="cta-btn" data-safe="cta">{icon("bookmark", 46, "#0B1B3F", 2)}<span>{esc(slide["cta"])}</span></div>'
            + (f'<div class="foot-note" data-safe="footnote">{esc(slide.get("footnote"))}</div>' if slide.get("footnote") else "")
            + '<div class="web" data-safe="web">www.assetplus.in/mfd/ARN-366802</div></div>'
        )
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><style>{_font_face()}{CSS}</style></head>'
            f'<body><div class="frame"><div class="grid"></div>{_top(index, total)}{body}{_footer()}</div></body></html>')


def render_slides(post, out_dir, stem):
    """Render all slides. Returns (paths, qa_issues). qa_issues is [] when everything passed."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = post["slides"]
    paths, all_issues = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        page = ctx.new_page()
        for i, slide in enumerate(slides):
            page.set_content(slide_html(slide, i, len(slides)), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.evaluate(FIT_JS)
            qa = page.evaluate(QA_JS)
            for issue in qa["issues"]:
                all_issues.append(f"slide {i + 1}: {issue}")
            if slide["kind"] == "cta":
                for req in ("ARN-366802", FOOTER_RISK):
                    if req not in qa["text"]:
                        all_issues.append(f"slide {i + 1}: missing required footer text {req!r}")
            path = out_dir / f"{stem}-{i + 1}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=92)
            paths.append(str(path))
        browser.close()
    return paths, all_issues
