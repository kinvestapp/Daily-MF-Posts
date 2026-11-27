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
from .content import SYSTEM, validate_shape
from .hooks import HOOKS, SEGMENTS
from .strategist import history, plan

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content_queue"
REPORT = ROOT / "data" / "weekly_report.md"
REFILL_BELOW = int(os.environ.get("REFILL_BELOW", "7"))

BATCH_SYSTEM = SYSTEM.replace("ONLY a raw JSON object", "ONLY a raw JSON array with one object per assignment, in the same order, each object").replace(
    "exactly this shape:", "exactly this shape (the array contains N of these):") + "\nYou receive N numbered assignments. Return the array in assignment order."

REVIEW_SYSTEM = """You are a strict compliance and accuracy reviewer for Indian mutual fund distributor social posts (AMFI/SEBI context).
For each numbered post decide ok=true/false. Flag a post if ANY of these is true:
- a factual statement about Indian mutual funds, SIPs, taxes, FATCA/CRS, KYC or liquidity is wrong or too absolute
- it promises or implies returns, safety, approval or regulatory endorsement
- a myth could be misread as a claim (myth/fact labels missing), or slide 1 and slide 2 are about different ideas
- tone is fear, urgency, greed or anger, or it attacks a named institution
- wording is confusing for a first-time investor
Respond ONLY with raw JSON: {"results": [{"id": <n>, "ok": true|false, "issues": ["short reason", ...]}]}. Keep issues short. Be strict but not pedantic."""


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
        lines.append(f"{i}. hook={a['hook']} ({HOOKS[a['hook']]['angle']}) | topic={a['topic']} | audience={a['segment']}: {SEGMENTS[a['segment']]['notes']}")
        if feedback and feedback.get(i):
            lines.append("   FIX THESE ISSUES FROM THE LAST DRAFT: " + "; ".join(feedback[i]))
    return "\n".join(lines)


def _clean(post, a):
    """Validate shape + linter. Returns (post, problem or None)."""
    try:
        validate_shape(post)
        issues = lint_post(post)
        if issues:
            return post, f"compliance patterns matched: {issues}"
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        return post, str(e)
    post.update({"hook": a["hook"], "topic": a["topic"], "segment": a["segment"]})
    return post, None


def write_batch(assignments, feedback=None):
    text = llm.call(llm.WRITER_MODELS, BATCH_SYSTEM, [{"role": "user", "content": _write_user(assignments, feedback)}],
                    max_tokens=1000 * len(assignments) + 500, purpose="planner-write")
    arr = _json(text, "[")
    if len(arr) != len(assignments):
        raise ValueError(f"expected {len(assignments)} posts, got {len(arr)}")
    return arr


def review(posts):
    payload = json.dumps([{"id": i, **{k: p[k] for k in ("slides", "caption")}} for i, p in enumerate(posts, 1)], ensure_ascii=False)
    text = llm.call(llm.REVIEW_MODELS, REVIEW_SYSTEM, [{"role": "user", "content": payload}], max_tokens=8000, purpose="planner-review")
    return {r["id"]: r.get("issues", []) for r in _json(text, "{")["results"] if not r.get("ok", False)}


def next_number():
    nums = [int(re.match(r"(\d+)", Path(f).name).group(1)) for f in glob.glob(str(QUEUE / "*.json")) if re.match(r"\d+", Path(f).name)]
    return (max(nums) if nums else 0) + 1


def save(post, n):
    slug = re.sub(r"[^a-z0-9]+", "-", post["topic"].lower())[:40].strip("-")
    path = QUEUE / f"{n:03d}-{post['hook']}-{slug}.json"
    json.dump({k: post[k] for k in ("hook", "topic", "segment", "slides", "caption")}, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
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

    drafts = write_batch(assignments)
    accepted, problems = {}, {}
    for i, (d, a) in enumerate(zip(drafts, assignments), 1):
        post, why = _clean(d, a)
        if why:
            problems[i] = [why]
        else:
            accepted[i] = post
    review_note = "reviewed"
    try:
        flagged = review([accepted[i] for i in sorted(accepted)]) if accepted else {}
    except (llm.Truncated, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"[planner] WARNING review unusable, continuing with code checks only: {e}")
        flagged, review_note = {}, f"REVIEW SKIPPED ({str(e)[:80]})"
    order = sorted(accepted)
    for pos, i in enumerate(order, 1):          # review ids are positions within the reviewed list
        if pos in flagged:
            problems[i] = flagged[pos]
            del accepted[i]

    if problems:
        redo = sorted(problems)
        print(f"[planner] rewriting {len(redo)} post(s): {problems}")
        try:
            fixed = write_batch([assignments[i - 1] for i in redo], {k + 1: problems[i] for k, i in enumerate(redo)})
            for i, d in zip(redo, fixed):
                post, why = _clean(d, assignments[i - 1])
                if why is None:
                    accepted[i] = post
                else:
                    print(f"[planner] dropped assignment {i}: {why}")
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"[planner] rewrite failed, dropping those posts: {e}")

    n = next_number()
    saved = []
    for i in sorted(accepted):
        saved.append(save(accepted[i], n))
        n += 1
    stamp = datetime.date.today().isoformat()
    lines = [f"# Weekly planner report ({stamp})", "", f"Queued {len(saved)} of {args.count} posts ({review_note}). Month-to-date API spend (estimate): ${llm.month_spend():.2f}", "",
             "## Hook performance (score per 1,000 reached)", ""]
    cap = float(os.environ.get("MONTHLY_BUDGET_USD", "3"))
    if llm.month_spend() >= 0.8 * cap:
        lines = lines[:1] + ["", f"**NEEDS OWNER APPROVAL: API spend is at {llm.month_spend()/cap:.0%} of the ${cap:.2f} monthly cap. Writing stops at the cap; raise MONTHLY_BUDGET_USD to continue.**"] + lines[1:]
    lines += [f"- {h}: mean {v['mean']} over {v['n']} post(s)" for h, v in sorted(htable.items(), key=lambda kv: -kv[1]['mean'])] or ["- no results collected yet (rotating hooks evenly)"]
    lines += ["", "## This batch", ""] + [f"- {s}" for s in saved]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(saved)} post(s): {saved}")
    if not saved:
        raise SystemExit("No post passed validation and review.")


if __name__ == "__main__":
    main()
