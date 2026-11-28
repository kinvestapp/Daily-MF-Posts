"""Strategist: decides WHAT to write next, in plain code (no API calls).

Reads data/metrics.jsonl (Phase 2 collector), ranks hooks by score per 1,000 accounts reached,
and plans the next batch: ~70% of slots exploit the best hooks, ~30% explore the least-tested ones.
Until there is enough data (MIN_SCORED posts) it rotates hooks evenly. Audience mix follows SEGMENTS weights.
"""
import glob
import json
import random
from pathlib import Path

from .hooks import HOOK_PRIOR, HOOKS, SEGMENTS, TOPICS

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "data" / "metrics.jsonl"
MIN_SCORED = 6
EXPLORE_SHARE = 0.3
TANGLISH_SHARE = 1 / 3


def load_scores():
    """Latest snapshot per carousel post: {media_id: row}, preferring 72h > 24h > 7d."""
    pref = {"72h": 3, "7d": 2, "24h": 1}
    best = {}
    if METRICS.exists():
        for line in METRICS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("format") != "carousel" or r.get("score_per_1k_reach") is None:
                continue
            cur = best.get(r["media_id"])
            if cur is None or pref.get(r["window"], 0) > pref.get(cur["window"], 0):
                best[r["media_id"]] = r
    return best


def table(rows, key):
    agg = {}
    for r in rows.values():
        k = r.get(key)
        if k:
            agg.setdefault(k, []).append(r["score_per_1k_reach"])
    return {k: {"n": len(v), "mean": round(sum(v) / len(v), 2)} for k, v in agg.items()}


def segment_quota(n):
    """Largest-remainder split of n posts across audience segments by weight."""
    total = sum(s["weight"] for s in SEGMENTS.values())
    raw = {k: n * s["weight"] / total for k, s in SEGMENTS.items()}
    quota = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - quota[k], reverse=True)[: n - sum(quota.values())]:
        quota[k] += 1
    return quota


def nri_recent(days=30):
    """Owner rule: at most one NRI post a month. True if one was published in the last `days` or is still queued."""
    import datetime
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    for f in glob.glob(str(ROOT / "public" / "posts_v2" / "*.json")):
        if Path(f).stem >= cutoff:
            try:
                if json.load(open(f, encoding="utf-8")).get("segment") == "nri":
                    return True
            except (OSError, json.JSONDecodeError):
                pass
    used = set()
    for f in glob.glob(str(ROOT / "public" / "posts_v2" / "*.json")):
        try:
            used.add(json.load(open(f, encoding="utf-8")).get("queue_id"))
        except (OSError, json.JSONDecodeError):
            pass
    for f in glob.glob(str(ROOT / "content_queue" / "*.json")):
        if Path(f).stem not in used:
            try:
                if json.load(open(f, encoding="utf-8")).get("segment") == "nri":
                    return True
            except (OSError, json.JSONDecodeError):
                pass
    return False


def plan(n, recent_hooks, recent_topics, rng=None):
    """Return (assignments, hook_table). assignments = [{hook, segment, topic, mode}]."""
    rng = rng or random.Random()
    rows = load_scores()
    htable = table(rows, "hook")
    cold = len(rows) < MIN_SCORED
    quota = segment_quota(n)
    if quota.get("nri", 0) and nri_recent():
        quota["chennai_tn"] += quota.pop("nri")
    elif quota.get("nri", 0) > 1:
        quota["chennai_tn"] += quota["nri"] - 1
        quota["nri"] = 1
    slots = [seg for seg, q in quota.items() for _ in range(q)]
    rng.shuffle(slots)

    # Exploit only hooks with at least 2 results (when any qualify) that score within 60% of the best one.
    proven = [h for h in htable if htable[h]["n"] >= 2] or list(htable)
    ranked = sorted(proven, key=lambda h: htable[h]["mean"], reverse=True)
    best = htable[ranked[0]]["mean"] if ranked else 0
    top = [h for h in ranked[:3] if htable[h]["mean"] >= 0.6 * best] or ranked[:1]
    seen_count = {h: htable.get(h, {}).get("n", 0) for h in HOOKS}
    used_hooks, used_topics, out = list(recent_hooks), set(recent_topics), []
    chennai_seen = rng.randrange(3)   # random phase so Tanglish does not always land on the same weekday
    for seg in slots:
        if cold:
            pool = [h for h in HOOKS if h not in used_hooks[-3:]] or list(HOOKS)
            hook, mode = rng.choices(pool, weights=[HOOK_PRIOR.get(x, 1) for x in pool])[0], "rotate"
        elif rng.random() < EXPLORE_SHARE:
            least = min(seen_count[h] for h in HOOKS if h not in used_hooks[-3:] or len(HOOKS) < 5)
            pool = [h for h in HOOKS if seen_count[h] == least and h not in used_hooks[-3:]] or list(HOOKS)
            hook, mode = rng.choices(pool, weights=[HOOK_PRIOR.get(x, 1) for x in pool])[0], "explore"
        else:
            pool = [h for h in top if h not in used_hooks[-2:]] or top
            hook, mode = rng.choice(pool), "exploit"
        topics = [t for t, s in TOPICS if s == seg and t not in used_topics] or [t for t, s in TOPICS if s == seg]
        topic = rng.choice(topics)
        used_hooks.append(hook)
        used_topics.add(topic)
        # Owner-approved language test: every third Chennai post gets a Tanglish hook.
        lang = "en"
        if seg == "chennai_tn":
            chennai_seen += 1
            if chennai_seen % round(1 / TANGLISH_SHARE) == 0:
                lang = "tanglish"
        out.append({"hook": hook, "segment": seg, "topic": topic, "mode": mode, "lang": lang})
    return out, htable


def history():
    """Hooks and topics already used or queued (oldest first by filename)."""
    hooks, topics = [], []
    for f in sorted(glob.glob(str(ROOT / "public" / "posts_v2" / "*.json"))) + sorted(glob.glob(str(ROOT / "content_queue" / "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("hook"):
            hooks.append(d["hook"])
        if d.get("topic"):
            topics.append(d["topic"])
    return hooks, topics
