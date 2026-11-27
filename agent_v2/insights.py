"""Phase 2: collect performance of published posts and log it for the learner.

Snapshots are taken at 24h, 72h and 7d after publishing and appended to data/metrics.jsonl.
Read-only against Meta. Score weights live in SCORE_WEIGHTS so they are easy to tune.
"""
import datetime
import glob
import json
import os
from pathlib import Path

import requests

API = "https://graph.facebook.com/v21.0"
ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "public" / "posts_v2"
METRICS = ROOT / "data" / "metrics.jsonl"
WINDOWS = {"24h": 24, "72h": 72, "7d": 168}

IG_METRICS = ["reach", "views", "saved", "shares", "likes", "comments", "total_interactions", "follows", "profile_visits"]
REEL_EXTRA = ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
# What the agent is trying to maximise. Saves, shares and follows matter more than likes.
SCORE_WEIGHTS = {"saved": 5, "shares": 4, "follows": 8, "comments": 2, "likes": 1}


def score(metrics):
    """Weighted engagement score, plus a rate per 1,000 accounts reached."""
    raw = sum(metrics.get(k, 0) * w for k, w in SCORE_WEIGHTS.items())
    reach = metrics.get("reach") or 0
    return {"score": raw, "score_per_1k_reach": round(raw * 1000 / reach, 2) if reach else None}


def _get(url, params):
    r = requests.get(url, params=params, timeout=30)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def ig_insights(media_id, token, kind="carousel"):
    """Fetch insight metrics; if the combined call errors, retry metric by metric so one
    unsupported metric never loses the rest."""
    out = {}
    metric_list = IG_METRICS + (REEL_EXTRA if kind == "reel" else [])
    status, data = _get(f"{API}/{media_id}/insights", {"metric": ",".join(metric_list), "access_token": token})
    if status == 200 and "data" in data:
        for m in data["data"]:
            out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
        return out
    for metric in metric_list:
        status, data = _get(f"{API}/{media_id}/insights", {"metric": metric, "access_token": token})
        if status == 200 and data.get("data"):
            m = data["data"][0]
            out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
    return out


def fb_stats(post_id, token):
    status, data = _get(f"{API}/{post_id}", {
        "fields": "reactions.summary(true).limit(0),comments.summary(true).limit(0),shares",
        "access_token": token})
    if status != 200:
        return {}
    return {
        "fb_reactions": data.get("reactions", {}).get("summary", {}).get("total_count", 0),
        "fb_comments": data.get("comments", {}).get("summary", {}).get("total_count", 0),
        "fb_shares": data.get("shares", {}).get("count", 0),
    }


def load_existing():
    seen = set()
    if METRICS.exists():
        for line in METRICS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                seen.add((d["media_id"], d["window"]))
    return seen


def due_snapshots(now=None):
    """Yield (meta, window, media_id, kind) for every published item whose window has elapsed and is not logged."""
    now = now or datetime.datetime.utcnow()
    seen = load_existing()
    for f in sorted(glob.glob(str(POSTS / "*.json"))):
        meta = json.load(open(f, encoding="utf-8"))
        pub = meta.get("published", {})
        if not pub.get("published_at"):
            continue
        age_h = (now - datetime.datetime.fromisoformat(pub["published_at"].rstrip("Z"))).total_seconds() / 3600
        for kind, key in (("carousel", "instagram_media_id"), ("reel", "instagram_reel_id")):
            media_id = pub.get(key)
            if not media_id:
                continue
            for window, hours in WINDOWS.items():
                if age_h >= hours and (media_id, window) not in seen:
                    yield meta, window, media_id, kind


def main():
    token = os.environ["META_ACCESS_TOKEN"]
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with open(METRICS, "a", encoding="utf-8") as out:
        for meta, window, media_id, kind in due_snapshots():
            pub = meta["published"]
            metrics = ig_insights(media_id, token, kind)
            if kind == "carousel" and pub.get("facebook_post_id"):
                metrics.update(fb_stats(pub["facebook_post_id"], token))
            row = {
                "date": meta["date"], "media_id": media_id, "window": window,
                "hook": meta.get("hook"), "topic": meta.get("topic"), "segment": meta.get("segment"), "format": kind,
                "published_at": pub["published_at"],
                "collected_at": datetime.datetime.utcnow().isoformat() + "Z",
                "metrics": metrics, **score(metrics),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows += 1
            print(f"logged {meta['date']} {window}: score={row['score']} metrics={metrics}")
    print(f"{rows} snapshot(s) written")


if __name__ == "__main__":
    main()
