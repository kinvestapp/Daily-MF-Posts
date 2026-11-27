"""Agent v2 daily pipeline: pick hook/topic -> write -> lint -> render -> QA -> save.

Usage:
  python -m agent_v2.pipeline              # real run (needs ANTHROPIC_API_KEY)
  python -m agent_v2.pipeline --sample     # offline: render the fixture post (no API calls)
"""
import argparse
import datetime
import glob
import json
import os
import shutil
from pathlib import Path

from .content import generate_post
from .post_queue import next_item, remaining
from .hooks import pick_hook, pick_topic
from .reel import build_reel
from .experiments import choose_theme
from .render import render_slides

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "posts_v2"
CAPTION_FOOTER = (
    "\n\nARN-366802 | AMFI-registered Mutual Fund Distributor | www.assetplus.in/mfd/ARN-366802 | "
    "Mutual Fund investments are subject to market risks, read all scheme related documents carefully"
)
MAX_RENDER_ATTEMPTS = 3


def load_history():
    hooks, topics = [], []
    for f in sorted(glob.glob(str(OUT / "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
            hooks.append(d.get("hook"))
            topics.append(d.get("topic"))
        except (OSError, json.JSONDecodeError):
            continue
    return hooks, topics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    date_str = args.date
    day_dir = OUT / date_str
    if day_dir.exists():
        shutil.rmtree(day_dir)

    hook_hist, topic_hist = load_history()
    hook_key = pick_hook(hook_hist)
    topic, segment = pick_topic(topic_hist)

    theme = choose_theme(date_str)
    print(f"[pipeline] theme: {theme}")

    # CONTENT_SOURCE: "queue" = only pre-written posts (no API calls, no credits);
    #                 "auto"  = queue first, then the Claude API if a key is set; "api" = API only.
    source = os.environ.get("CONTENT_SOURCE", "auto")
    queued = None
    if not args.sample and source in ("queue", "auto"):
        queued = next_item(exclude_date=date_str)
        if queued is None and source == "queue":
            raise RuntimeError("Content queue is empty. Add posts to content_queue/ (or set CONTENT_SOURCE=api).")
        if queued is not None:
            print(f"[queue] using {queued['queue_id']} ({len(remaining(date_str)) - 1} left after this one)")

    post, paths, issues = None, [], ["not started"]
    for attempt in range(1, MAX_RENDER_ATTEMPTS + 1):
        if args.sample:
            post = json.load(open(ROOT / "agent_v2" / "fixtures" / "sample_post.json", encoding="utf-8"))
        elif queued is not None:
            post = queued
        else:
            post = generate_post(topic, hook_key, segment)
        paths, issues = render_slides(post, day_dir, date_str, theme=theme)
        if not issues:
            break
        print(f"[qa] attempt {attempt} failed: {issues}")
        shutil.rmtree(day_dir, ignore_errors=True)
        if queued is not None:   # a queued post cannot be regenerated; fail loudly instead of publishing it broken
            break
    if issues:
        raise RuntimeError(f"Quality gate failed after {MAX_RENDER_ATTEMPTS} attempts: {issues}")

    rel = [str(Path(p).relative_to(ROOT)) for p in paths]
    reel_rel, reel_audio = None, None
    try:
        reel_abs, reel_audio = build_reel(paths, day_dir / "reel.mp4")
        reel_rel = str(Path(reel_abs).relative_to(ROOT))
    except Exception as e:  # a failed Reel must never block the carousel
        print(f"[reel] skipped: {e}")
    meta = {
        "date": date_str,
        "hook": post.get("hook", hook_key),
        "topic": post.get("topic", topic),
        "segment": post.get("segment", segment),
        "queue_id": post.get("queue_id"),
        "slides": post["slides"],
        "caption": post["caption"],
        "caption_full": post["caption"] + CAPTION_FOOTER,
        "images": rel,
        "format": "carousel_3",
        "theme": theme,
        "reel": reel_rel,
        "reel_audio": reel_audio,
        "published": {},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    prev = OUT / f"{date_str}.json"
    if prev.exists():   # a re-run on the same day must remember what was already published
        try:
            meta["published"] = json.load(open(prev, encoding="utf-8")).get("published", {}) or {}
        except (ValueError, OSError):
            pass
    with open(OUT / f"{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(rel)} slides for {date_str} (hook={meta['hook']}): {rel}")


if __name__ == "__main__":
    main()
