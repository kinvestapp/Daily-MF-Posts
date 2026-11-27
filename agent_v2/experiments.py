"""A/B testing of visual themes. Assignment is deterministic by date; judging is free (no API calls).

Rules (the agent cannot change these; only the data they act on):
- one challenger at a time gets CHALLENGER_SHARE of posts; the champion gets the rest
- judged on score_per_1k_reach once both sides have MIN_N scored posts
- challenger >= PROMOTE_RATIO x champion  -> becomes champion (old champion retired)
- challenger <= RETIRE_RATIO x champion   -> retired
"""
import hashlib
import json
from pathlib import Path

from . import themes
from .strategist import load_scores

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "experiments.json"
CHALLENGER_SHARE = 4      # one post in four
MIN_N = 4
PROMOTE_RATIO = 1.15
RETIRE_RATIO = 0.85


def _by_status(status):
    return [t for t in themes.load_all().values() if t.get("status") == status]


def champion():
    c = _by_status("champion")
    return c[0]["name"] if c else "midnight_gold"


def choose_theme(date_str):
    ch = _by_status("challenger")
    if ch and int(hashlib.sha256(date_str.encode()).hexdigest(), 16) % CHALLENGER_SHARE == 0:
        return ch[0]["name"]
    return champion()


def theme_table():
    rows = load_scores()
    agg = {}
    for r in rows.values():
        t = r.get("theme") or "midnight_gold"
        agg.setdefault(t, []).append(r["score_per_1k_reach"])
    return {k: {"n": len(v), "mean": round(sum(v) / len(v), 2)} for k, v in agg.items()}


def _set_status(name, status):
    f = themes.THEME_DIR / f"{name}.json"
    t = json.loads(f.read_text(encoding="utf-8"))
    t["status"] = status
    f.write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def judge():
    """Apply the promote/retire rules. Returns a list of human-readable decisions."""
    tbl = theme_table()
    champ = champion()
    decisions = []
    for t in _by_status("challenger"):
        a, b = tbl.get(t["name"]), tbl.get(champ)
        if not a or not b or a["n"] < MIN_N or b["n"] < MIN_N or b["mean"] <= 0:
            decisions.append(f"{t['name']}: still testing ({(a or {}).get('n', 0)} vs {(b or {}).get('n', 0)} scored posts, need {MIN_N} each)")
            continue
        ratio = a["mean"] / b["mean"]
        if ratio >= PROMOTE_RATIO:
            _set_status(champ, "retired"); _set_status(t["name"], "champion")
            decisions.append(f"{t['name']} PROMOTED to champion ({ratio:.2f}x vs {champ})")
        elif ratio <= RETIRE_RATIO:
            _set_status(t["name"], "retired")
            decisions.append(f"{t['name']} RETIRED ({ratio:.2f}x vs {champ})")
        else:
            decisions.append(f"{t['name']}: inconclusive ({ratio:.2f}x), keep testing")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"themes": tbl, "champion": champion(), "decisions": decisions}, indent=2) + "\n", encoding="utf-8")
    return decisions
