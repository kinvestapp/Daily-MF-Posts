"""Content generation: writing brief (rules + craft), shape validation, and the daily single-post fallback."""
import json

from .compliance import lint_post
from .hooks import HOOKS, SEGMENTS, series_for

ICONS = ["growth", "shield", "clock", "target", "home", "cap", "coin", "globe", "handshake", "calendar"]

RULES = """You write Instagram carousel copy for K-Invest.app, an AMFI-registered Mutual Fund Distributor.
Audience in priority order: Chennai and Tamil Nadu, rest of South India, North India, then NRIs. Most readers live in
India: salaried people in their late 20s to 40s, young parents, small business owners, first-time investors.

HARD RULES (never break):
- Educational and conceptual only. No scheme names, no NAV, no return percentages, no predictions, no guarantees,
  no 'best fund', no 'financial planning' / 'financial advisor'.
- Never imply returns, growth figures, safety or that money will multiply. Any number must be simple arithmetic of the
  reader's OWN contributions (5,000 x 12 x 10 = 6,00,000) and say 'For illustration only'.
- Positive emotions only. Tension is welcome (a contrast, a relatable confession, the cost of waiting shown as plain
  contribution arithmetic), but never fear, panic, shame, greed or urgency to buy. Never 'you are falling behind'.
- Never attack banks, AMCs, gold, chits, FDs, LIC or competitors. No testimonials, no invented people quoted as real,
  no invented statistics ('8 out of 10 families...').
- Never claim anything is 'compliant with', 'approved by', 'endorsed by' or 'regulated by' an authority. No words
  'trusted', 'safe', 'secure', 'permanent', 'risk-free'.
- Facts must be accurate for Indian mutual funds: open-ended funds can usually be redeemed on business days, some have
  exit loads, ELSS has a 3-year lock-in, KYC is needed before investing. FATCA is a US law; most countries use CRS.
- Myth posts label points 'Myth: ...' (title) and 'Fact: ...' (text).
- No em dashes or en dashes. Rupee sign for rupees, Indian grouping (6,00,000 or 6 lakh).
"""

CRAFT = """HOW TO WRITE A HOOK THAT STOPS THE SCROLL (this is the whole job; generic copy is a failure):
- Specific beats general. Name a real-feeling person, place or moment: an IT employee on OMR on salary day, a T. Nagar
  shop owner, a young couple in Velachery, Amma's gold chain, Paati's post office passbook, the school fee receipt in
  June, the Pongal bonus, the EMI date, the first salary.
- Build tension or a gap: a contrast (two friends, same salary, different habit), then vs now (what our parents saved
  in vs what we can add), a relatable confession ('I said next month for three years'), a small surprising truth, or a
  list the reader wants to check themselves against ('3 things Chennai parents do on fee day').
- Belonging and positive FOMO: show that people like the reader, in their city, already keep a small monthly habit,
  and the door is open. Invitation, never pressure.
- Sound like a friend talking, not a brochure. Banned brochure words: unlock, journey, empower, financial freedom,
  wealth creation, secure your future, smart investing, take control, dream big, game changer.
- Never open with 'Did you know'. No question that can be answered with a flat 'no'. The headline must make sense
  without the subhead.
- Slide 2 pays off the hook with three concrete, useful points (a tip someone could act on this week).
- Slide 3 CTA is a SHARE or SAVE prompt tied to the idea, e.g. 'Send this to the friend who always says next month'
  or 'Save this for the next salary day'. Never 'start today', never 'invest now'.
- Caption: line 1 is a fresh hook (max 12 words, different from the headline). Then 1-2 short lines. Then ONE easy
  question that invites a comment ('What did your Amma save in?'). Then 5-7 hashtags mixing local
  (#Chennai #NammaChennai #TamilNadu #ChennaiFamilies) and niche (#SIP #MutualFunds #MoneyHabits).

LANGUAGE:
- lang=en: simple Indian English.
- lang=tanglish: the hook headline, subhead and caption line 1 mix Tamil words written in ENGLISH LETTERS with English,
  the way people in Chennai type on Instagram ('Salary vandhachu. SIP date fix panniteengala?'). Natural, warm,
  respectful (use 'neenga' forms), never slangy or crude, no Tamil script. Slide 2 and slide 3 stay in simple English.
  Add an English translation of every Tanglish line in "translation_en".
"""

LIMITS = """LENGTH LIMITS: kicker max 4 words; hook headline max 9 words; subhead max 16 words; value title max 8 words;
each point title max 4 words and text max 16 words; cta headline max 8 words; cta max 10 words; footnote max 14
words (may be empty). Do not use double quotes inside string values. icon must be one of: """ + ", ".join(ICONS) + "."

SINGLE_SHAPE = """{
  "slides": [
    {"kind": "hook",  "kicker": "...", "headline": "...", "subhead": "...", "icon": "<icon>"},
    {"kind": "value", "title": "...", "points": [{"title": "...", "text": "..."}, {"title": "...", "text": "..."}, {"title": "...", "text": "..."}], "icon": "<icon>"},
    {"kind": "cta",   "headline": "...", "cta": "...", "footnote": "..."}
  ],
  "caption": "...",
  "translation_en": ""
}"""

SYSTEM = RULES + "\n" + CRAFT + "\n" + LIMITS + "\n\nOUTPUT: ONLY a raw JSON object (no markdown fences), exactly this shape:\n" + SINGLE_SHAPE


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


def validate_hook(h):
    for key, mx in (("kicker", 4), ("headline", 9), ("subhead", 16)):
        if _words(h.get(key, "")) > mx:
            raise ValueError(f"hook.{key} exceeds {mx} words")
    if not h.get("headline"):
        raise ValueError("hook headline missing")


def validate_shape(post):
    """Structural + length validation. Raises ValueError with a message the model can act on."""
    slides = post.get("slides")
    if not isinstance(slides, list) or [s.get("kind") for s in slides] != ["hook", "value", "cta"]:
        raise ValueError("slides must be exactly three objects with kind hook, value, cta in that order")
    hook, value, cta = slides
    validate_hook(hook)
    for slide, key, mx in ((value, "title", 8), (cta, "headline", 8), (cta, "cta", 10), (cta, "footnote", 14)):
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
    if "?" not in post["caption"]:
        raise ValueError("caption must end its body with one question that invites a comment")
    return post


def generate_post(topic, hook_key, segment="chennai_tn", max_attempts=2, lang="en"):
    """Daily fallback when the queue is empty: ONE post, at most 2 calls."""
    from . import llm
    hook = HOOKS[hook_key]
    user = (
        f"Topic: {topic}\nAudience segment: {segment}. {SEGMENTS[segment]['notes']}\n"
        f"Assigned hook: {hook_key}. Angle: {hook['angle']}\nStyle reference (do not copy): {hook['example']}\n"
        f"lang={lang}. Use kicker exactly: {series_for(hook_key, segment)}"
    )
    messages = [{"role": "user", "content": user}]
    last_error = None
    for _ in range(max_attempts):
        text = llm.call(llm.WRITER_MODELS, SYSTEM, messages, max_tokens=1500, purpose="daily-write")
        try:
            post = validate_shape(_parse(text))
            post["slides"][0]["kicker"] = series_for(hook_key, segment)
            issues = lint_post(post)
            if issues:
                raise ValueError(f"compliance patterns matched: {issues}")
            post.update({"hook": hook_key, "topic": topic, "segment": segment, "lang": lang})
            return post
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            last_error = e
            print(f"[content] rejected: {e}")
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Rejected: {e}. Fix it and return ONLY the raw JSON object."})
    raise RuntimeError(f"content generation failed after {max_attempts} attempts: {last_error}")
