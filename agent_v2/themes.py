"""Visual themes as DATA (colour tokens), so the agent can invent and test looks without touching code.

A theme is themes/<name>.json: {"name", "status": "champion"|"challenger"|"retired", "colors": {...}, "why": "..."}.
Required colour keys: bg1, bg2, bg3 (dark background gradient), accent, accent_light, accent_lightest.
bg2 doubles as the dark ink used on accent buttons, so it must contrast with both accent_light and accent.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "themes"
KEYS = ["bg1", "bg2", "bg3", "accent", "accent_light", "accent_lightest"]
BASE = {"bg1": "#0E2250", "bg2": "#0B1B3F", "bg3": "#08122B",
        "accent": "#D4A24C", "accent_light": "#F2C879", "accent_lightest": "#F7D58E"}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def validate(colors):
    """Return a list of problems (empty = usable). Guards readability, never taste."""
    probs = []
    for k in KEYS:
        if not HEX.match(str(colors.get(k, ""))):
            probs.append(f"{k} missing or not #RRGGBB")
    if probs:
        return probs
    if contrast(colors["accent_light"], colors["bg2"]) < 4.5:
        probs.append("accent_light on bg2 contrast < 4.5")
    if contrast(colors["bg2"], colors["accent"]) < 4.5:
        probs.append("dark ink on accent button contrast < 4.5")
    if contrast("#FFFFFF", colors["bg1"]) < 7 or contrast("#FFFFFF", colors["bg3"]) < 7:
        probs.append("white text on background contrast < 7")
    if _lum(colors["bg2"]) > 0.08:
        probs.append("background not dark enough")
    return probs


def load_all():
    out = {}
    for f in sorted(THEME_DIR.glob("*.json")):
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
            out[t["name"]] = t
        except (OSError, ValueError, KeyError):
            continue
    return out


def colors_of(name):
    t = load_all().get(name)
    return {**BASE, **(t["colors"] if t else {})}


def apply(html, name):
    """Swap the base colour tokens in rendered HTML/CSS for the named theme's colours."""
    if not name or name == "midnight_gold":
        return html
    c = colors_of(name)
    for key in KEYS:
        html = re.sub(re.escape(BASE[key]), c[key], html, flags=re.I)
    rgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
    html = html.replace("242,200,121", rgb(c["accent_light"])).replace("212,162,76", rgb(c["accent"]))
    return html
