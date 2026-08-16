import os, json, datetime, requests

REPO = "kinvestapp/Daily-MF-Posts"
BRANCH = "main"

def main():
    date_str = datetime.date.today().isoformat()
    with open(f"public/posts/{date_str}.json") as f:
        data = json.load(f)

    image_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/public/posts/{date_str}.png"
    caption = data["caption"] + "\n\nARN-366802 | AMFI-registered Mutual Fund Distributor | www.assetplus.in/mfd/ARN-366802 | Mutual Fund investments are subject to market risks, read all scheme related documents carefully"

    access_token = os.environ["META_ACCESS_TOKEN"]
    page_id = os.environ["META_PAGE_ID"]
    ig_user_id = os.environ["META_IG_USER_ID"]

    # --- Instagram: create container, then publish ---
    container = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": access_token}
    ).json()
    print("IG container:", container)

    ig_result = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
        data={"creation_id": container["id"], "access_token": access_token}
    ).json()
    print("IG publish result:", ig_result)

    # --- Facebook Page ---
    fb_result = requests.post(
        f"https://graph.facebook.com/v21.0/{page_id}/photos",
        data={"url": image_url, "caption": caption, "access_token": access_token}
    ).json()
    print("FB publish result:", fb_result)

if __name__ == "__main__":
    main()
