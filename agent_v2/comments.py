"""Reply to new Instagram comments on recent posts (conversation is a strong engagement signal).

Safe by design:
- needs the instagram_manage_comments permission; without it, it says so and exits cleanly
- one cheap model call per run, and only when there are new comments
- every reply passes the compliance linter; advice questions get an invitation to message, never advice
- spam, abuse and our own comments are never answered; each comment is answered at most once
"""
import datetime
import glob
import json
import os
from pathlib import Path

import requests

from . import llm
from .compliance import lint_text

API = "https://graph.facebook.com/v21.0"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "replied_comments.json"
DAYS = 10

SYSTEM = """You reply to Instagram comments for K-Invest.app, an AMFI-registered Mutual Fund Distributor in Chennai.
For each comment return a reply, or an empty string to skip.
- Warm, short (max 25 words), human. Match the commenter's language: English, or Tanglish (Tamil in English letters,
  respectful 'neenga' forms) if they wrote that way. No Hindi words unless they wrote Hindi.
- Answer the feeling or share a tiny general fact. If they ask what to buy, which fund, how much, returns or anything
  personal: do not advise; invite them to send a DM so the team can explain options.
- Never mention returns, guarantees, safety, scheme names or 'best'. No em or en dashes. At most one emoji.
- Skip (empty string): spam, abuse, emoji-only reactions you cannot add to, links, other businesses promoting.
Respond ONLY with raw JSON: {"replies": [{"id": "<comment id>", "reply": "..."}]}"""


def _get(path, token, **params):
    r = requests.get(f"{API}/{path}", params={**params, "access_token": token}, timeout=30).json()
    if "error" in r:
        raise PermissionError(r["error"].get("message", str(r["error"])))
    return r


def recent_media():
    cutoff = (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()
    out = []
    for f in sorted(glob.glob(str(ROOT / "public" / "posts_v2" / "*.json"))):
        if Path(f).stem < cutoff:
            continue
        meta = json.load(open(f, encoding="utf-8"))
        pub = meta.get("published", {})
        for key in ("instagram_media_id", "instagram_reel_id"):
            if pub.get(key):
                out.append((pub[key], meta))
    return out


def main():
    token, ig_id = os.environ["META_ACCESS_TOKEN"], os.environ["META_IG_USER_ID"]
    done = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    try:
        me = _get(ig_id, token, fields="username")["username"]
        pending = []
        for media_id, meta in recent_media():
            data = _get(f"{media_id}/comments", token, fields="id,text,username,replies{username}", limit=50).get("data", [])
            for c in data:
                ours = any(r.get("username") == me for r in c.get("replies", {}).get("data", []))
                if c["id"] in done or c.get("username") == me or ours or not c.get("text", "").strip():
                    continue
                pending.append({"id": c["id"], "text": c["text"][:300], "post_headline": meta["slides"][0]["headline"]})
    except PermissionError as e:
        print(f"[comments] cannot read comments yet (add instagram_manage_comments to the token): {e}")
        return
    if not pending:
        print("[comments] no new comments")
        return
    pending = pending[:25]
    text = llm.call(llm.WRITER_MODELS, SYSTEM, [{"role": "user", "content": json.dumps(pending, ensure_ascii=False)}],
                    max_tokens=2500, purpose="comment-replies")
    s, e = text.find("{"), text.rfind("}")
    replies = {r["id"]: r.get("reply", "").strip() for r in json.loads(text[s:e + 1]).get("replies", [])}
    sent = 0
    for c in pending:
        reply = replies.get(c["id"], "")
        if reply and not lint_text(reply) and len(reply.split()) <= 30:
            r = requests.post(f"{API}/{c['id']}/replies", data={"message": reply, "access_token": token}, timeout=30).json()
            if "id" in r:
                sent += 1
            else:
                print(f"[comments] reply failed for {c['id']}: {r}")
                continue
        elif reply:
            print(f"[comments] reply blocked by linter or length: {reply!r}")
        done.add(c["id"])
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(done)) + "\n")
    print(f"[comments] {len(pending)} new, {sent} replied")


if __name__ == "__main__":
    main()
