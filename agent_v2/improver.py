"""Weekly self-improvement step: judge running experiments (free), then, if none is running, propose ONE new
visual theme challenger (one API call). Themes are data (colour tokens), validated for contrast; the agent never
edits code, compliance rules, the footer, credentials or budgets here."""
import datetime
import json
import re

from . import experiments, llm, themes
from .strategist import load_scores, table

MAX_THEMES = 8

PROMPT = """You art-direct Instagram carousels for K-Invest.app, a mutual fund distributor serving Chennai and Tamil Nadu first.
Propose ONE new colour theme to A/B test against the current champion. Goal: more saves, shares and reach from
Chennai and South India audiences. Dark backgrounds with light text only (the layout is fixed). Keep it professional
and modern-fintech, not garish. Reply with ONLY a raw JSON object:
{"name": "snake_case_name", "why": "one sentence on the audience reasoning", "colors": {
 "bg1": "#RRGGBB", "bg2": "#RRGGBB", "bg3": "#RRGGBB", "accent": "#RRGGBB", "accent_light": "#RRGGBB", "accent_lightest": "#RRGGBB"}}
Rules: bg1 > bg2 > bg3 in lightness but all dark; accent_light must be readable on bg2; bg2 is also the ink on accent
buttons so it must contrast with accent. Must differ clearly from every theme listed."""


def propose():
    existing = themes.load_all()
    if len(existing) >= MAX_THEMES:
        return "theme cap reached, no proposal"
    listing = {n: {"status": t["status"], "colors": t["colors"], "why": t.get("why", "")} for n, t in existing.items()}
    user = (f"Existing themes and status:\n{json.dumps(listing, indent=1)}\n\n"
            f"Theme results so far (score per 1k reach): {json.dumps(experiments.theme_table())}\n"
            f"Hook results so far: {json.dumps(table(load_scores(), 'hook'))}")
    text = llm.call(llm.REVIEW_MODELS, PROMPT, [{"role": "user", "content": user}], max_tokens=4000, purpose="improver-theme")
    s, e = text.find("{"), text.rfind("}")
    cand = json.loads(text[s:e + 1])
    name = re.sub(r"[^a-z0-9_]", "", str(cand["name"]).lower().replace(" ", "_"))[:32]
    if not name or name in existing:
        return f"rejected proposal: bad or duplicate name {cand.get('name')!r}"
    probs = themes.validate(cand["colors"])
    if probs:
        return f"rejected proposal {name}: {probs}"
    out = {"name": name, "status": "challenger", "why": str(cand.get("why", ""))[:300], "colors": cand["colors"]}
    (themes.THEME_DIR / f"{name}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return f"new challenger theme: {name}"


def main():
    notes = experiments.judge()
    if not any(t.get("status") == "challenger" for t in themes.load_all().values()):
        try:
            notes.append(propose())
        except (llm.BudgetExceeded, llm.Truncated, ValueError, KeyError, json.JSONDecodeError) as e:
            notes.append(f"no new proposal ({type(e).__name__}: {str(e)[:100]})")
    print("\n".join(f"[improver] {n}" for n in notes))
    log = experiments.ROOT / "data" / "improver_log.md"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.date.today().isoformat()}\n" + "\n".join(f"- {n}" for n in notes) + "\n")


if __name__ == "__main__":
    main()
