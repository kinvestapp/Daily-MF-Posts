"""Twice a month (1st and 15th): pick the post most worth boosting and ask the owner, via a GitHub issue, to boost it.

The owner approved two paid boosts a month. The agent never spends money itself: it picks and explains, the owner
presses Boost. Free: no model calls.
"""
import datetime
import glob
import json
import os
from pathlib import Path

import requests

from .strategist import load_scores

ROOT = Path(__file__).resolve().parent.parent
API = "https://graph.facebook.com/v21.0"
WINDOW_DAYS = 14


def candidates():
    cutoff = (datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    scores = {r["media_id"]: r for r in load_scores().values()}
    out = []
    for f in sorted(glob.glob(str(ROOT / "public" / "posts_v2" / "*.json"))):
        if Path(f).stem < cutoff:
            continue
        meta = json.load(open(f, encoding="utf-8"))
        mid = meta.get("published", {}).get("instagram_media_id")
        if not mid or meta.get("segment") == "nri":
            continue
        row = scores.get(mid)
        # measured engagement first; the editor's hook score breaks ties and covers posts without data yet
        out.append(((row or {}).get("score_per_1k_reach", -1), meta.get("hook_score") or 0, meta, mid, row))
    return sorted(out, key=lambda x: (x[0], x[1]), reverse=True)


def permalink(mid):
    tok = os.environ.get("META_ACCESS_TOKEN")
    if not tok:
        return None
    r = requests.get(f"{API}/{mid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json()
    return r.get("permalink")


def issue_body(meta, mid, row, link):
    seg = meta.get("segment", "chennai_tn")
    place = "Chennai (+25 km)" if seg == "chennai_tn" else "Tamil Nadu, Karnataka, Kerala, Andhra Pradesh, Telangana" if seg == "south_india" else "India"
    if row:
        why = f"measured {row['score_per_1k_reach']} engagement points per 1,000 reached, the best of the last two weeks"
    elif meta.get("hook_score"):
        why = f"no engagement data yet; the editor scored its hook {meta['hook_score']}/10, the strongest available"
    else:
        why = "no engagement data yet; the most recent eligible post"
    return f"""The agent picked this post for one of this month's two boosts.

**Post:** {meta['slides'][0]['headline']} ({meta['date']}, {meta.get('series', '')}, {meta.get('lang', 'en')})
**Link:** {link or 'open Instagram and find the post from ' + meta['date']}
**Why this one:** {why}

### How to boost (about 2 minutes)
1. Open the post in the Instagram app and tap **Boost post**.
2. Goal: **More profile visits**.
3. Audience: **Create your own**. Location: **{place}**. Age **25-45**. Interests: personal finance, investment, savings.
4. Budget: **Rs 300-500 total over 3 days**.
5. Confirm the **beneficiary and payer** as K-Invest.app when Meta asks (Indian rules for investment ads).

When the boost ends, the agent will see the extra reach in its daily insights and learn from it.
Close this issue once boosted.
"""


def main():
    today = datetime.date.today()
    if today.day not in (1, 15) and os.environ.get("FORCE") != "1":
        print("[boost] not a boost day")
        return
    cands = candidates()
    if not cands:
        print("[boost] no eligible post in the last two weeks")
        return
    _, _, meta, mid, row = cands[0]
    title = f"Boost pick for {today.isoformat()}: {meta['slides'][0]['headline']}"
    body = issue_body(meta, mid, row, permalink(mid))
    repo, gh = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    r = requests.post(f"https://api.github.com/repos/{repo}/issues",
                      headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"},
                      json={"title": title, "body": body}, timeout=30)
    print(f"[boost] issue: {r.status_code} {r.json().get('html_url')}")


if __name__ == "__main__":
    main()
