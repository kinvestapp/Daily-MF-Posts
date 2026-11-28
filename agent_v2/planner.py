"""Weekly planner: strategist (code) -> writer (1 call, N posts) -> reviewer (1 cheap call) -> fix (1 call, failures only).

At most 3 API calls per run. Daily publishing then uses content_queue/ with no API call at all.

  python -m agent_v2.planner --count 7            # refill only if the queue is running low
  python -m agent_v2.planner --count 7 --force    # always write a batch
  python -m agent_v2.planner --count 7 --dry      # show the plan, make no API calls
"""
import argparse
import datetime
import glob
import json
import os
import re
from pathlib import Path

from . import llm
from .compliance import lint_post
from .content import CRAFT, HARD, LIMITS, RULES, validate_hook, validate_shape
from .hooks import HOOKS, SEGMENTS, series_for
from .strategist import history, plan

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content_queue"
REPORT = ROOT / "data" / "weekly_report.md"
REFILL_BELOW = int(os.environ.get("REFILL_BELOW", "7"))

MIN_SCORE = 7          # judge score (1-10) a hook must reach before it is queued
CHUNK = 5              # posts per writer call (smaller batches write better)

BATCH_SHAPE = """{
  "hook_candidates": [{"headline": "...", "subhead": "..."}, ... six different candidates ...],
  "hook_icon": "<icon>",
  "slides": [
    {"kind": "value", "title": "...", "points": [{"title": "...", "text": "..."}, {"title": "...", "text": "..."}, {"title": "...", "text": "..."}], "icon": "<icon>"},
    {"kind": "cta", "headline": "...", "cta": "...", "footnote": "..."}
  ],
  "caption": "...",
  "translation_en": "English translation of every Tanglish line, or empty string for lang=en"
}"""

BATCH_SYSTEM = (RULES + "\n" + CRAFT + "\n" + LIMITS + """

You receive N numbered assignments. For EACH one write SIX genuinely different hook candidates (different angles:
a scene, a contrast, a confession, a number, an invitation, a then-vs-now) plus one shared slide 2, slide 3 and
caption that work with any of them. Do NOT write the kicker; the series label is added by code.
OUTPUT: ONLY a raw JSON array, one object per assignment in order, each exactly this shape:
""" + BATCH_SHAPE)

JUDGE_SYSTEM = """You are the creative director AND compliance reviewer for K-Invest.app's Instagram (Indian mutual fund
distributor, audience mainly Chennai). For each numbered post:
1. Pick the hook candidate most likely to make a 28-40 year old salaried Chennai parent stop scrolling. Score it 1-10:
   specificity (a real scene, person or moment), tension or curiosity gap, emotional pull (belonging, hope, pride,
   positive FOMO), instantly clear in one second, feels local, sounds like a person not a brochure.
   9-10 = you would screenshot it. 5 = generic AMC/bank copy. Be harsh: generic copy scores 5 or less.
2. If the best candidate scores below 8, write a better headline (max 9 words) and subhead (max 16 words) yourself,
   same idea and same language (Tanglish = Tamil words in English letters mixed with English, respectful 'neenga'
   forms, no Tamil script), and score that instead.
3. Optionally rewrite the caption's FIRST line (max 12 words) if it is weak. Keep it different from the headline.
4. Compliance/accuracy: ok=false if anything implies returns, safety, guarantees or approval; uses fear, shame or
   urgency to buy; attacks gold, FDs, chits, banks or AMCs; invents statistics or testimonials; states a wrong fact
   about Indian mutual funds, KYC, tax or liquidity; Tanglish is unnatural, disrespectful or its translation_en does
   not match. A weak hook is NOT a compliance issue; fix it with step 2 instead.
Respond ONLY with raw JSON:
{"results": [{"id": <n>, "best": <candidate index from 1>, "score": <1-10>, "headline": "<final headline>",
  "subhead": "<final subhead>", "caption_first_line": "<new first line or empty>", "why": "<one short reason>",
  "ok": true|false, "issues": ["short reason", ...]}]}"""


def _json(text, opener):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    closer = "]" if opener == "[" else "}"
    s, e = text.find(opener), text.rfind(closer)
    if s == -1 or e == -1:
        raise ValueError("no JSON found")
    return json.loads(text[s:e + 1])


def _write_user(assignments, feedback=None):
    lines = [f"N = {len(assignments)} assignments."]
    for i, a in enumerate(assignments, 1):
        h = HOOKS[a["hook"]]
        lines.append(f"{i}. lang={a.get('lang', 'en')} | hook={a['hook']}: {h['angle']} (style reference, do not copy: {h['example']})"
                     f" | topic={a['topic']} | audience={a['segment']}: {SEGMENTS[a['segment']]['notes']}")
        if feedback and feedback.get(i):
            lines.append("   FIX THESE ISSUES FROM THE LAST DRAFT: " + "; ".join(feedback[i]))
    return "\n".join(lines)


def write_batch(assignments, feedback=None):
    out = []
    for k in range(0, len(assignments), CHUNK):
        part = assignments[k:k + CHUNK]
        fb = {i - k: v for i, v in (feedback or {}).items() if k < i <= k + CHUNK}
        text = llm.call(llm.WRITER_MODELS, BATCH_SYSTEM, [{"role": "user", "content": _write_user(part, fb)}],
                        max_tokens=1800 * len(part) + 800, purpose="planner-write")
        arr = _json(text, "[")
        if len(arr) != len(part):
            raise ValueError(f"expected {len(part)} posts, got {len(arr)}")
        out += arr
    return out


JUDGE_CHUNK = 5
JUDGE_TOKENS = 24000   # the judge model reasons before answering; billed only for what it uses


def judge(drafts, assignments):
    """Pick/improve the hook, score it, and review compliance, JUDGE_CHUNK posts per call.
    Returns {position: result}; a chunk whose verdict is unusable gets no entry (those posts are retried)."""
    out = {}
    for k in range(0, len(drafts), JUDGE_CHUNK):
        payload = []
        for i, (d, a) in enumerate(zip(drafts[k:k + JUDGE_CHUNK], assignments[k:k + JUDGE_CHUNK]), k + 1):
            payload.append({"id": i, "lang": a.get("lang", "en"), "audience": a["segment"], "hook_type": a["hook"],
                            "candidates": d.get("hook_candidates", []), "slides": d.get("slides", []),
                            "caption": d.get("caption", ""), "translation_en": d.get("translation_en", "")})
        try:
            text = llm.call(llm.REVIEW_MODELS, JUDGE_SYSTEM,
                            [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                            max_tokens=JUDGE_TOKENS, purpose="planner-judge")
            out.update({int(r["id"]): r for r in _json(text, "{")["results"]})
        except (llm.Truncated, ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"[planner] judge chunk {k // JUDGE_CHUNK + 1} unusable: {e}")
    return out


LOCAL_TAGS = {"chennai_tn": "#Chennai #NammaChennai #TamilNadu #ChennaiFamilies #SIP #MutualFunds #MoneyHabits",
              "south_india": "#SouthIndia #Bengaluru #Kerala #Hyderabad #SIP #MutualFunds #MoneyHabits",
              "north_india": "#India #Delhi #FamilyGoals #SIP #MutualFunds #MoneyHabits",
              "nri": "#NRI #NRIInvesting #India #SIP #MutualFunds"}


def tidy_caption(caption, new_first="", segment="chennai_tn"):
    """Instagram shows about two lines before 'more': hook on line 1, body, question, then hashtags, each on its own line."""
    import re as _re
    text = " ".join(caption.split())
    tags = " ".join(t for t in text.split() if t.startswith("#"))
    body = " ".join(t for t in text.split() if not t.startswith("#"))
    sentences = _re.split(r"(?<=[.!?])\s+", body.strip())
    if new_first:
        sentences[0] = new_first.strip()
    qi = max([i for i, x in enumerate(sentences) if x.endswith("?") and i > 0], default=len(sentences))
    middle, ask = sentences[1:qi], sentences[qi:]
    lines = [sentences[0]] + ([" ".join(middle)] if middle else []) + ([" ".join(ask)] if ask else [])
    if not tags:
        tags = LOCAL_TAGS.get(segment, LOCAL_TAGS["chennai_tn"])
    return "\n\n".join(lines + [tags])


def assemble(d, a, j):
    """Build the final post from a draft and the judge's verdict. Returns (post, problem or None)."""
    try:
        cands = d["hook_candidates"]
        best = cands[max(0, min(len(cands) - 1, int(j.get("best", 1)) - 1))]
        hook = {"kind": "hook", "kicker": series_for(a["hook"], a["segment"]),
                "headline": j.get("headline") or best["headline"], "subhead": j.get("subhead") or best.get("subhead", ""),
                "icon": d.get("hook_icon", "growth")}
        validate_hook(hook)
        caption = tidy_caption(d["caption"], j.get("caption_first_line", ""), a["segment"])
        post = {"slides": [hook] + list(d["slides"]), "caption": caption, "translation_en": d.get("translation_en", "")}
        validate_shape(post)
        issues = lint_post(post) + lint_post({"caption": post["translation_en"]})
        if issues:
            return None, f"compliance patterns matched: {issues}"
    except (ValueError, KeyError, AttributeError, TypeError, IndexError) as e:
        return None, str(e)
    if not j:
        return None, "not judged (judge reply unusable); write it again"
    if not j.get("ok", False):
        return None, "; ".join(j.get("issues") or ["reviewer rejected"])
    if int(j.get("score", 0)) < MIN_SCORE:
        return None, f"hook too weak (score {j.get('score')}): {j.get('why', '')}. Write sharper, more specific candidates."
    post.update({"hook": a["hook"], "topic": a["topic"], "segment": a["segment"], "lang": a.get("lang", "en"),
                 "series": hook["kicker"], "hook_score": int(j["score"]), "judge_note": j.get("why", "")})
    return post, None


BODY_LIMITS = [("value", "title", HARD["value_title"]), ("cta", "headline", HARD["cta_headline"]),
               ("cta", "cta", HARD["cta"]), ("cta", "footnote", HARD["footnote"])]


def _n(t):
    return len(str(t).split())


def precheck(d):
    """Cheap code checks before the judge. Drops over-long hook candidates and returns exact, fixable problems."""
    problems = []
    cands = [c for c in d.get("hook_candidates") or [] if isinstance(c, dict) and c.get("headline")
             and _n(c["headline"]) <= HARD["headline"] and _n(c.get("subhead", "")) <= HARD["subhead"]]
    if len(cands) < 2:
        problems.append("hook candidates: headline max 9 words, subhead max 16 words; most of yours were longer")
    d["hook_candidates"] = cands
    slides = {s.get("kind"): s for s in d.get("slides") or [] if isinstance(s, dict)}
    if set(slides) != {"value", "cta"}:
        return problems + ["slides must be exactly one value object and one cta object"]
    for kind, key, mx in BODY_LIMITS:
        if _n(slides[kind].get(key, "")) > mx:
            problems.append(f"{kind}.{key} has {_n(slides[kind][key])} words (max {mx}): '{slides[kind][key]}'")
    pts = slides["value"].get("points") or []
    if len(pts) != 3:
        problems.append("value.points must have exactly 3 items")
    for p in pts:
        if _n(p.get("title", "")) > HARD["point_title"]:
            problems.append(f"point title has {_n(p.get('title'))} words (max 4): '{p.get('title')}'")
        if _n(p.get("text", "")) > HARD["point_text"]:
            problems.append(f"point text has {_n(p.get('text'))} words (max 16): '{p.get('text')}'")
    if "?" not in d.get("caption", ""):
        problems.append("caption needs one question inviting a comment")
    return problems


def run_round(assignments, feedback=None):
    drafts = write_batch(assignments, feedback)
    fix = {i: pr for i, d in enumerate(drafts, 1) if (pr := precheck(d))}
    if fix:
        print(f"[planner] fixing length/shape in {len(fix)} draft(s) before judging")
        order = sorted(fix)
        redone = write_batch([assignments[i - 1] for i in order], {k + 1: fix[i] for k, i in enumerate(order)})
        for i, d in zip(order, redone):
            if not (pr := precheck(d)):
                drafts[i - 1] = d
                del fix[i]
            else:
                fix[i] = pr
    good = [i for i in range(1, len(drafts) + 1) if i not in fix]
    verdicts = judge([drafts[i - 1] for i in good], [assignments[i - 1] for i in good])
    ok, bad = {}, {i: pr for i, pr in fix.items()}
    for pos, i in enumerate(good, 1):
        post, why = assemble(drafts[i - 1], assignments[i - 1], verdicts.get(pos, {}))
        if why:
            bad[i] = [why]
        else:
            ok[i] = post
    return ok, bad


def next_number():
    files = glob.glob(str(QUEUE / "*.json")) + glob.glob(str(QUEUE / "retired" / "*.json"))
    nums = [int(re.match(r"(\d+)", Path(f).name).group(1)) for f in files if re.match(r"\d+", Path(f).name)]
    return (max(nums) if nums else 0) + 1


def save(post, n):
    slug = re.sub(r"[^a-z0-9]+", "-", post["topic"].lower())[:40].strip("-")
    path = QUEUE / f"{n:03d}-{post['hook']}-{slug}.json"
    keep = ("hook", "topic", "segment", "lang", "series", "hook_score", "judge_note", "slides", "caption", "translation_en")
    json.dump({k: post[k] for k in keep if k in post}, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return path.name


def remaining_in_queue():
    used = set()
    for f in glob.glob(str(ROOT / "public" / "posts_v2" / "*.json")):
        try:
            q = json.load(open(f, encoding="utf-8")).get("queue_id")
        except (OSError, json.JSONDecodeError):
            continue
        if q:
            used.add(q)
    return [Path(f).stem for f in sorted(glob.glob(str(QUEUE / "*.json"))) if Path(f).stem not in used]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    left = remaining_in_queue()
    if len(left) >= REFILL_BELOW and not args.force and not args.dry:
        print(f"Queue has {len(left)} unused posts (refill below {REFILL_BELOW}). Nothing to do, no API calls made.")
        return
    hooks_hist, topics_hist = history()
    assignments, htable = plan(args.count, hooks_hist, topics_hist)
    for i, a in enumerate(assignments, 1):
        print(f"{i}. {a['segment']:11} {a['hook']:16} [{a['mode']}] {a['topic'][:60]}")
    if args.dry:
        return

    review_note = "judged"
    accepted, problems = run_round(assignments)
    if problems:
        redo = sorted(problems)
        print(f"[planner] rewriting {len(redo)} post(s): {problems}")
        try:
            fixed, still = run_round([assignments[i - 1] for i in redo], {k + 1: problems[i] for k, i in enumerate(redo)})
            for k, i in enumerate(redo, 1):
                if k in fixed:
                    accepted[i] = fixed[k]
                else:
                    print(f"[planner] dropped assignment {i}: {still.get(k)}")
        except (llm.BudgetExceeded, llm.Truncated, ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"[planner] rewrite round failed, dropping those posts: {e}")

    try:   # render every accepted post once so nothing reaches the queue that cannot be laid out
        import tempfile
        from .render import render_slides
        for i in sorted(accepted):
            _, qa = render_slides(accepted[i], tempfile.mkdtemp(), "check")
            if qa:
                print(f"[planner] dropped assignment {i}: layout check failed {qa}")
                del accepted[i]
    except ImportError:
        print("[planner] playwright not installed; skipping layout check")

    n = next_number()
    saved = []
    for i in sorted(accepted):
        saved.append(save(accepted[i], n))
        n += 1
    stamp = datetime.date.today().isoformat()
    lines = [f"# Weekly planner report ({stamp})", "", f"Queued {len(saved)} of {args.count} posts ({review_note}). Month-to-date API spend (estimate): ${llm.month_spend():.2f}", "",
             "## Hook performance (score per 1,000 reached)", ""]
    cap = float(os.environ.get("MONTHLY_BUDGET_USD", "6"))
    if llm.month_spend() >= 0.8 * cap:
        lines = lines[:1] + ["", f"**NEEDS OWNER APPROVAL: API spend is at {llm.month_spend()/cap:.0%} of the ${cap:.2f} monthly cap. Writing stops at the cap; raise MONTHLY_BUDGET_USD to continue.**"] + lines[1:]
    lines += [f"- {h}: mean {v['mean']} over {v['n']} post(s)" for h, v in sorted(htable.items(), key=lambda kv: -kv[1]['mean'])] or ["- no results collected yet (rotating hooks evenly)"]
    lines += ["", "## This batch (hook score / series / language)", ""]
    lines += [f"- {name}: {accepted[i]['hook_score']}/10, {accepted[i]['series']}, {accepted[i]['lang']}. Headline: {accepted[i]['slides'][0]['headline']}"
              for name, i in zip(saved, sorted(accepted))]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(saved)} post(s): {saved}")
    if not saved:
        raise SystemExit("No post passed validation and review.")


if __name__ == "__main__":
    main()
