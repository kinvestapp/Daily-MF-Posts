import os, json, datetime, re, base64

THEMES = [
    ("SIP fundamentals: power of compounding, rupee cost averaging", "k_mascot"),
    ("Goal-based investing: education, retirement, home, wedding funds", "girl"),
    ("Young investor / first-timer: starting early, small amounts, ₹500/month", "girl"),
    ("Personal finance basics: emergency fund, 50/30/20 budgeting, good vs bad debt", "k_mascot"),
    ("Mutual fund literacy: what is an expense ratio, active vs passive, fund categories", "k_mascot"),
    ("Behavioural finance: volatility ≠ loss, avoiding panic selling, staying invested", "girl"),
    ("Myth-busting: common misconceptions about mutual funds, addressed simply", "girl"),
]

CHARACTER_FILES = {
    "k_mascot": "assets/characters/k_mascot_reference.png",
    "girl": "assets/characters/girl_character_reference.png",
}

CHARACTER_DESCRIPTIONS = {
    "k_mascot": "the K mascot character shown in the reference image: a friendly cartoon character shaped like the letter K, warm beige/tan material, small green rupee-symbol necktie, big expressive eyes, hand-drawn notebook/sketchbook ink illustration style",
    "girl": "the South Indian girl character shown in the reference image: warm brown skin tone, black hair in a ponytail, friendly expressive eyes, detailed color pencil illustration style",
}

BANNED_PATTERNS = [
    r"\d+%", r"NAV", r"guaranteed", r"assured return", r"financial plan",
    r"financial advisor", r"best fund", r"top scheme"
]

def get_theme_and_character():
    day_index = datetime.date.today().weekday()
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
    print(f"Raw Claude response: {text}")

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

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

def generate_illustration(theme, character_key):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ref_path = CHARACTER_FILES[character_key]
    char_desc = CHARACTER_DESCRIPTIONS[character_key]

    uploaded_file = client.files.upload(file=ref_path)

    prompt = (
        f"Using {char_desc}, illustrate ONE single new scene about: {theme}, drawn as if it's a page "
        "in a spiral-bound notebook — the entire 1080x1080 image should look like one continuous "
        "notebook page with faint ruled horizontal lines across the whole page, a black rounded card "
        "border framing the whole page, and a spiral binding running down the far left edge. "
        "Show the character only ONCE in a single clear pose or moment, positioned in the upper half "
        "of the page — not multiple repeated instances of the character. "
        "CRITICAL: the character must be completely plain and unbranded — no logo, no letters, no "
        "brand mark, no text of any kind on the character's tie, body, or anywhere on them. Do not "
        "attempt to draw any version of a company logo anywhere in the image. "
        "IMPORTANT: leave the top-right corner (roughly the top 180px and right 260px) as completely "
        "plain, unmarked notebook paper with no illustration elements there — this area is reserved "
        "for a logo overlay. "
        "IMPORTANT: leave the bottom quarter of the page as lightly-ruled but otherwise empty notebook "
        "paper, with no illustration elements there — this space is reserved for text overlay. "
        "IMPORTANT: keep all four outer edges of the image (roughly the outer 50px margin on every "
        "side) free of important illustration details, since edges may sit close to UI overlays on "
        "social media apps. "
        "Keep the exact same character design, art style, and color palette as the reference image. "
        "CRITICAL: Do not include any text, letters, numbers, words, or labels anywhere in the image — "
        "purely visual/pictorial illustration only, no lettering of any kind, not even small or "
        "background text. "
        "Warm, optimistic, approachable mood suitable for an Indian personal finance social media post."
    )
    
    generation_config = {
        'temperature': 1,
        'max_output_tokens': 65536,
        'top_p': 0.95,
        'thinking_level': 'minimal',
        'image_config': {'image_size': '1K'},
    }

    interaction = client.interactions.create(
        model='models/gemini-3.1-flash-lite-image',
        input=[
            {"type": "text", "text": prompt},
            {"type": "image", "uri": uploaded_file.uri, "mime_type": uploaded_file.mime_type},
        ],
        generation_config=generation_config,
        response_modalities=['image', 'text'],
    )

    image_b64 = None
    for step in interaction.steps:
        if step.type == 'model_output' and step.content:
            for part in step.content:
                if part.type == 'image':
                    image_b64 = part.data

    if not image_b64:
        raise RuntimeError(f"No image returned from Gemini. Full interaction: {interaction}")

    return f"data:image/png;base64,{image_b64}"

def render_image(data, illustration_data_uri, date_str):
    from playwright.sync_api import sync_playwright

    with open("assets/logo.png", "rb") as logo_file:
        logo_base64 = base64.b64encode(logo_file.read()).decode("utf-8")
    logo_data_uri = f"data:image/png;base64,{logo_base64}"

    with open("template_illustrated.html") as f:
        html = f.read()
    html = (html
            .replace("{{LOGO_PATH}}", logo_data_uri)
            .replace("{{ILLUSTRATION_PATH}}", illustration_data_uri)
            .replace("{{HEADLINE}}", data["headline"])
            .replace("{{BODY}}", data["body"]))

    os.makedirs("public/posts_test", exist_ok=True)
    temp_html_path = f"public/posts_test/{date_str}-illustrated.html"
    with open(temp_html_path, "w") as f:
        f.write(html)

    png_path = f"public/posts_test/{date_str}-illustrated.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        page.goto(f"file://{os.path.abspath(temp_html_path)}")
        page.wait_for_function(
            "document.querySelectorAll('img').length === 2 && "
            "Array.from(document.querySelectorAll('img')).every(img => img.complete && img.naturalWidth > 0)"
        )
        page.screenshot(path=png_path)
        browser.close()

    os.remove(temp_html_path)
    return png_path

def main():
    date_str = datetime.date.today().isoformat()
    theme, character_key = get_theme_and_character()
    data = generate_content(theme)
    illustration_data_uri = generate_illustration(theme, character_key)
    png_path = render_image(data, illustration_data_uri, date_str)
    print(f"Generated (TEST, not published): {png_path} (character: {character_key})")

if __name__ == "__main__":
    main()
