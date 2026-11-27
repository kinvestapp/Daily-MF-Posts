"""Publish the day's 3-slide carousel to Instagram (carousel) and Facebook (multi-photo post).

Writes the resulting media ids back into public/posts_v2/<date>.json so the Phase 2
insights collector can attach performance data to the right post / hook / topic.
"""
import datetime
import json
import os
import time

import requests

API = "https://graph.facebook.com/v21.0"


def wait_for_url(url, tries=8, delay=5):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=15, stream=True)
            r.close()
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(delay)
    return False


def wait_ready(container_id, token, tries=20, delay=3):
    for _ in range(tries):
        s = requests.get(f"{API}/{container_id}", params={"fields": "status_code", "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            return True
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"container {container_id} failed: {s}")
        time.sleep(delay)
    return False


def publish_reel(ig_id, token, path, caption):
    """Resumable upload: no public video URL needed. Reel stays out of the main feed grid by default."""
    share = os.environ.get("REEL_SHARE_TO_FEED", "false")
    c = requests.post(f"{API}/{ig_id}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": share, "access_token": token}).json()
    if "id" not in c or "uri" not in c:
        raise RuntimeError(f"Reel container failed: {c}")
    with open(path, "rb") as f:
        up = requests.post(c["uri"], headers={"Authorization": f"OAuth {token}", "offset": "0",
                                              "file_size": str(os.path.getsize(path))}, data=f).json()
    if not up.get("success", True) and "error" in up:
        raise RuntimeError(f"Reel upload failed: {up}")
    if not wait_ready(c["id"], token, tries=48, delay=5):
        raise RuntimeError("Reel never finished processing")
    pub = requests.post(f"{API}/{ig_id}/media_publish", data={"creation_id": c["id"], "access_token": token}).json()
    if "id" not in pub:
        raise RuntimeError(f"Reel publish failed: {pub}")
    return pub["id"]


def main():
    date_str = os.environ.get("POST_DATE", datetime.date.today().isoformat())
    meta_path = f"public/posts_v2/{date_str}.json"
    meta = json.load(open(meta_path, encoding="utf-8"))
    repo = os.environ.get("GITHUB_REPOSITORY", "kinvestapp/Daily-MF-Posts")
    branch = os.environ.get("PUBLISH_BRANCH", "main")
    token = os.environ["META_ACCESS_TOKEN"]
    page_id, ig_id = os.environ["META_PAGE_ID"], os.environ["META_IG_USER_ID"]
    caption = meta["caption_full"]

    stamp = int(time.time())
    urls = [f"https://raw.githubusercontent.com/{repo}/{branch}/{p}?v={stamp}" for p in meta["images"]]
    for u in urls:
        if not wait_for_url(u):
            raise RuntimeError(f"image not reachable: {u}")

    # --- Instagram carousel ---
    children = []
    for u in urls:
        r = requests.post(f"{API}/{ig_id}/media", data={"image_url": u, "is_carousel_item": "true", "access_token": token}).json()
        if "id" not in r:
            raise RuntimeError(f"IG child container failed: {r}")
        children.append(r["id"])
    for c in children:
        if not wait_ready(c, token):
            raise RuntimeError(f"IG child {c} never finished")
    parent = requests.post(f"{API}/{ig_id}/media", data={
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption, "access_token": token}).json()
    if "id" not in parent:
        raise RuntimeError(f"IG carousel container failed: {parent}")
    if not wait_ready(parent["id"], token):
        raise RuntimeError("IG carousel never finished")
    ig = requests.post(f"{API}/{ig_id}/media_publish", data={"creation_id": parent["id"], "access_token": token}).json()
    print("IG:", ig)
    meta["published"]["instagram_media_id"] = ig.get("id")

    # --- Facebook multi-photo post ---
    photo_ids = []
    for u in urls:
        r = requests.post(f"{API}/{page_id}/photos", data={"url": u, "published": "false", "access_token": token}).json()
        if "id" not in r:
            raise RuntimeError(f"FB photo upload failed: {r}")
        photo_ids.append(r["id"])
    payload = {"message": caption, "access_token": token}
    for i, pid in enumerate(photo_ids):
        payload[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    fb = requests.post(f"{API}/{page_id}/feed", data=payload).json()
    print("FB:", fb)
    meta["published"]["facebook_post_id"] = fb.get("id")

    meta["published"]["published_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(meta_path, "w", encoding="utf-8") as f:   # save carousel ids before attempting the Reel
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # --- Instagram Reel (a failure here must not undo the carousel) ---
    reel = meta.get("reel")
    if reel and os.path.exists(reel) and os.environ.get("PUBLISH_REEL", "1") == "1":
        try:
            meta["published"]["instagram_reel_id"] = publish_reel(ig_id, token, reel, caption)
            print("Reel:", meta["published"]["instagram_reel_id"])
        except Exception as e:
            print("Reel failed:", e)
            meta["published"]["reel_error"] = str(e)[:300]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
