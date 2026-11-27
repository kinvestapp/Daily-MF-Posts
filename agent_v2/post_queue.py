"""Content queue: pre-written posts (no API calls, no credits).

Each file in content_queue/ is one post in the same shape content.py produces:
  {"hook", "topic", "segment", "slides": [hook, value, cta], "caption"}
Files are used in filename order. A post counts as used once a published-or-dry-run
metadata file in public/posts_v2/ carries its queue_id (today's own file is ignored so
a same-day re-run picks the same post again).
"""
import glob
import json
from pathlib import Path

from .compliance import lint_post
from .content import validate_shape

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content_queue"
POSTS = ROOT / "public" / "posts_v2"


def used_ids(exclude_date=None):
    ids = set()
    for f in glob.glob(str(POSTS / "*.json")):
        if exclude_date and Path(f).stem == exclude_date:
            continue
        try:
            qid = json.load(open(f, encoding="utf-8")).get("queue_id")
        except (OSError, json.JSONDecodeError):
            continue
        if qid:
            ids.add(qid)
    return ids


def next_item(exclude_date=None):
    """Return the first valid unused queue post (with 'queue_id'), or None."""
    used = used_ids(exclude_date)
    for f in sorted(glob.glob(str(QUEUE / "*.json"))):
        qid = Path(f).stem
        if qid in used:
            continue
        post = json.load(open(f, encoding="utf-8"))
        try:
            validate_shape(post)
            issues = lint_post(post)
            if issues:
                raise ValueError(f"compliance patterns matched: {issues}")
        except (ValueError, KeyError) as e:
            print(f"[queue] skipping {qid}: {e}")
            continue
        post["queue_id"] = qid
        return post
    return None


def remaining(exclude_date=None):
    used = used_ids(exclude_date)
    return [Path(f).stem for f in sorted(glob.glob(str(QUEUE / "*.json"))) if Path(f).stem not in used]
