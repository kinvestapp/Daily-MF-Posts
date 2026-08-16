import os, json, datetime, re, base64
from anthropic import Anthropic

THEMES = [
    "SIP fundamentals: power of compounding, rupee cost averaging",
    "Goal-based investing: education, retirement, home, wedding funds",
    "Young investor / first-timer: starting early, small amounts, ₹500/month",
    "Personal finance basics: emergency fund, 50/30/20 budgeting, good vs bad debt",
    "Mutual fund literacy: what is an expense ratio, active vs passive, fund categories",
    "Behavioural finance: volatility ≠ loss, avoiding panic selling, staying invested",
    "Myth-busting: common misconceptions about mutual funds, addressed simply",
]

BANNED_PATTERNS = [
    r"\d+%", r"NAV", r"guaranteed", r"assured return", r"financial plan",
    r"financial advisor", r"best fund", r"top scheme"
]

def get_theme():
    day_index = datetime.date.today().weekday()  # 0=Mon
    return THEMES[day_index % len(THEMES)]

def generate_content(theme):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = (
        "You write short, compliant social media content for an Indian AMFI-registered "
        "Mutual Fund Distributor (MFD). Rules: no NAV or return percentages, no scheme names, "
        "no performance predictions or guarantees, no use of the words 'financial planning' or "
        "'financial advisor'. Content must be purely educational/conceptual, never scheme-specific "
        "advice. Respond with ONLY a raw JSON object, no markdown code fences, no preamble, no "
        "explanation, no backticks. The response must start with { and end with }. Shape: "
        '{"headline": "...", "body": "...", "caption": "..."}. '
        "headline: max 8 words. body: max 25 words. caption: 2-3 sentences plus 4-5 relevant hashtags."
    )
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Today's theme: {theme}"}]
    )
    text = message.content[0].text.strip()
    print(f"Raw Claude response: {text}")  # visible in Actions log if it fails again

    # Strip markdown code fences if present, despite instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    # Extract just the {...} portion in case of any stray text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in Claude response: {text}")
    text = text[start:end+1]

    data = json.loads(text)

    combined_check = (data["headline"] + " " + data["body"] + " " + data["caption"]).lower()
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, combined_check, re.IGNORECASE):
            raise ValueError(f"Content failed compliance check on pattern: {pattern}. Raw: {data}")

    return data
    
def render_image(data, date_str):
    from playwright.sync_api import sync_playwright

    with open("assets/logo.png", "rb") as logo_file:
        logo_base64 = base64.b64encode(logo_file.read()).decode("utf-8")
    logo_data_uri = f"data:image/png;base64,{logo_base64}"

    with open("template.html") as f:
        html = f.read()
    html = (html
            .replace("{{LOGO_PATH}}", logo_data_uri)
            .replace("{{HEADLINE}}", data["headline"])
            .replace("{{BODY}}", data["body"]))

    os.makedirs("public/posts", exist_ok=True)
    temp_html_path = f"public/posts/{date_str}.html"
    with open(temp_html_path, "w") as f:
        f.write(html)

    png_path = f"public/posts/{date_str}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        page.goto(f"file://{os.path.abspath(temp_html_path)}")
        page.wait_for_function(
            "document.querySelector('img.logo').complete && document.querySelector('img.logo').naturalWidth > 0"
        )
        page.screenshot(path=png_path)
        browser.close()

    os.remove(temp_html_path)
    return png_path
    
def main():
    date_str = datetime.date.today().isoformat()
    theme = get_theme()
    data = generate_content(theme)
    png_path = render_image(data, date_str)

    with open(f"public/posts/{date_str}.json", "w") as f:
        json.dump({"date": date_str, "theme": theme, **data, "image": png_path}, f, indent=2)

    print(f"Generated: {png_path}")

if __name__ == "__main__":
    main()
