import os, json, datetime, requests, time

REPO = "kinvestapp/Daily-MF-Posts"
BRANCH = "main"

def wait_for_image_url(image_url, max_attempts=6, delay_seconds=5):
    for attempt in range(max_attempts):
        try:
            response = requests.get(image_url, timeout=10, stream=True)
            if response.status_code == 200:
                print(f"Image URL confirmed reachable after {attempt + 1} attempt(s).")
                response.close()
                return True
            print(f"Got status {response.status_code} (attempt {attempt + 1}/{max_attempts})")
        except requests.RequestException as e:
            print(f"Request failed (attempt {attempt + 1}/{max_attempts}): {e}")
        time.sleep(delay_seconds)
    return False

def wait_for_container_ready(container_id, access_token, max_attempts=8, delay_seconds=3):
    """Poll Instagram's container status until it's FINISHED and ready to publish."""
    for attempt in range(max_attempts):
        status = requests.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": access_token}
        ).json()
        code = status.get("status_code")
        print(f"Container status (attempt {attempt + 1}/{max_attempts}): {code}")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            raise RuntimeError(f"Instagram container processing failed: {status}")
        time.sleep(delay_seconds)
    return False

def main():
    date_str = datetime.date.today().isoformat()
    with open(f"public/posts/{date_str}.json") as f:
        data = json.load(f)

    image_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/public/posts/{date_str}.png?v={int(time.time())}"
    caption = data["caption"] + "\n\nARN-366802 | AMFI-registered Mutual Fund Distributor | www.assetplus.in/mfd/ARN-366802 | Mutual Fund investments are subject to market risks, read all scheme related documents carefully"

    access_token = os.environ["META_ACCESS_TOKEN"]
    page_id = os.environ["META_PAGE_ID"]
    ig_user_id = os.environ["META_IG_USER_ID"]

    if not wait_for_image_url(image_url):
        raise RuntimeError(f"Image URL never became reachable: {image_url}")

    # --- Instagram: create container, wait until ready, then publish ---
    container = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": access_token}
    ).json()
    print("IG container:", container)

    if "id" not in container:
        raise RuntimeError(f"Instagram container creation failed: {container}")

    if not wait_for_container_ready(container["id"], access_token):
        raise RuntimeError("Instagram container never finished processing.")

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
