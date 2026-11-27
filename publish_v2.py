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
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
