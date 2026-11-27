"""Content generation: one hook + one topic -> 3-slide carousel copy + caption."""
import json
import os

from .compliance import lint_post
from .hooks import HOOKS, SEGMENTS

ICONS = ["growth", "shield", "clock", "target", "home", "cap", "coin", "globe", "handshake", "calendar"]

MODEL = os.environ.get("CONTENT_MODEL", "claude-haiku-4-5-20251001")

SYSTEM = f"""You write compliant Instagram carousel copy for K-Invest.app, an AMFI-registered
Mutual Fund Distributor. Audience in priority order: Chennai and Tamil Nadu, rest of South India,
North India, then NRIs/overseas Indians. Most investors are domestic, so write for people living in India
unless the assignment says the NRI segment. Never mention Nordic countries.

HARD RULES (never break):
- Purely educational and conceptual. No scheme names, no NAV, no return percentages, no predictions,
  no guarantees, no 'best fund', no 'financial planning' / 'financial advisor'.
- No fear, panic, urgency, greed or anger framing. Every hook is POSITIVE: hopeful, curious,
  empathetic, proud, relieved, amused or inspired.
- Never attack banks, AMCs or competitors. No testimonials. No invented statistics.
- Any numeric example must be simple arithmetic of the user's OWN contributions (e.g. 5,000 x 12 x 10 = 6,00,000)
  and be labelled 'For illustration only'. Never show growth/return figures.
- Never claim that anything is 'compliant with', 'approved by', 'endorsed by' or 'regulated by' any authority except the plain
  fact 'AMFI-registered Mutual Fund Distributor'. No words like 'trusted', 'safe', 'secure', 'permanent' or 'risk-free'.
- Use the Indian rupee sign as the single character used for rupees, and Indian number grouping (6,00,000 or 6 lakh).

OUTPUT: ONLY a raw JSON object (no markdown fences, no commentary), exactly this shape:
{{
  "slides": [
    {{"kind": "hook",  "kicker": "...", "headline": "...", "subhead": "...", "icon": "<icon>"}},
    {{"kind": "value", "title": "...", "points": [{{"title": "...", "text": "..."}}, {{"title": "...", "text": "..."}}, {{"title": "...", "text": "..."}}], "icon": "<icon>"}},
    {{"kind": "cta",   "headline": "...", "cta": "...", "footnote": "..."}}
  ],
  "caption": "..."
}}
LENGTH LIMITS: kicker max 4 words (uppercase-friendly label like 'SIP BASICS'); hook headline max 9 words;
subhead max 16 words; value title max 8 words; each point title max 4 words and text max 16 words;
cta headline max 8 words; cta max 10 words (a soft next step such as 'Save this for your next SIP review' or
'Follow for one simple money idea a day'); footnote max 14 words (may be empty string);
caption 2-3 plain sentences then 4-5 hashtags inline. Do not use double quotes inside string values.
Slide 1 must stop the scroll using the assigned hook. Slide 2 delivers the value. Slide 3 invites a save/follow.
icon must be one of: {', '.join(ICONS)}.
"""


def _parse(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


def _words(s):
    return len(str(s).split())


def validate_shape(post):
    """Structural + length validation. Raises ValueError with a message the model can act on."""
    slides = post.get("slides")
    if not isinstance(slides, list) or [s.get("kind") for s in slides] != ["hook", "value", "cta"]:
        raise ValueError("slides must be exactly three objects with kind hook, value, cta in that order")
    hook, value, cta = slides
    limits = [
        (hook, "kicker", 4), (hook, "headline", 9), (hook, "subhead", 16),
        (value, "title", 8), (cta, "headline", 8), (cta, "cta", 10), (cta, "footnote", 14),
    ]
    for slide, key, mx in limits:
        if _words(slide.get(key, "")) > mx:
            raise ValueError(f"{slide['kind']}.{key} exceeds {mx} words")
    pts = value.get("points")
    if not isinstance(pts, list) or len(pts) != 3:
        raise ValueError("value.points must have exactly 3 items")
    for p in pts:
        if _words(p.get("title", "")) > 4 or _words(p.get("text", "")) > 16 or not p.get("title"):
            raise ValueError("a value point violates the title<=4 / text<=16 word limits")
    for s in (hook, value):
        if s.get("icon") not in ICONS:
            s["icon"] = "growth"
    if not post.get("caption"):
        raise ValueError("caption missing")
    return post


def generate_post(topic, hook_key, segment="chennai_tn", max_attempts=4):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    hook = HOOKS[hook_key]
    user = (
        f"Topic: {topic}\n"
        f"Audience segment: {segment}. {SEGMENTS[segment]['notes']}\n"
        f"Assigned hook: {hook_key}. Angle: {hook['angle']}\n"
        f"Style reference for the hook (do not copy): {hook['example']}"
    )
    messages = [{"role": "user", "content": user}]
    last_error = None
    for attempt in range(1, max_attempts + 1):
        msg = client.messages.create(model=MODEL, max_tokens=900, system=SYSTEM, messages=messages)
        text = msg.content[0].text
        print(f"[content] attempt {attempt}: {text[:200]!r}")
        try:
            post = validate_shape(_parse(text))
            issues = lint_post(post)
            if issues:
                raise ValueError(f"compliance patterns matched: {issues}")
            post["hook"] = hook_key
            post["topic"] = topic
            post["segment"] = segment
            return post
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            last_error = e
            print(f"[content] rejected: {e}")
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Rejected: {e}. Fix it and return ONLY the raw JSON object."})
    raise RuntimeError(f"content generation failed after {max_attempts} attempts: {last_error}")
