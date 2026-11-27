"""Compliance linter. The agent can never relax these rules (see redesign plan)."""
import re

# Carried over from the v1 pipeline.
BANNED_PATTERNS = [
    r"\bNAV\b",
    r"\bguaranteed?\b",
    r"\bassured returns?\b",
    r"\bfinancial plan(?:ning)?\b",
    r"\bfinancial advis[eo]r\b",
    r"\bbest fund\b",
    r"\btop schemes?\b",
    r"\d+(\.\d+)?%\s*(p\.?a\.?|per annum|returns?|growth|gains?|cagr|yield|profit|appreciation)",
    r"(returns?|growth|gains?|cagr|yield|profit|appreciation|grew|grow)\s+(of|by|was|is|at)?\s*\d+(\.\d+)?%",
    # New in v2: hard-sell / fear / greed language that regulators and ethics rule out.
    r"\bsure[- ]?shot\b",
    r"\brisk[- ]?free\b",
    r"\bno risk\b",
    r"\bdouble your money\b",
    r"\bget rich\b",
    r"\bact now\b",
    r"\bhurry\b",
    r"\blimited (units|period|time offer)\b",
    r"\bcrash(es|ed|ing)? (is |are )?(coming|imminent)\b",
    r"\bdon'?t miss out\b",
    r"\bbanks? (are )?(robbing|cheating|looting)\b",
    r"\bbeat the market\b",
    r"\bhigh returns?\b",
    r"\bmultibagger\b",
    # Regulatory / trust claims the distributor cannot make.
    r"\bcompliant (with|to)\b",
    r"\b(sebi|amfi|rbi)[- ]?(approved|endorsed|recommended|certified|guaranteed)\b",
    r"\b(approved|endorsed|regulated|certified) by (sebi|amfi|rbi|the government)\b",
    r"\btrusted (platform|partner|advis|choice)",
    r"\b(100%|completely|totally) (safe|secure)\b",
    r"\bpermanent\b",
    # House style: no em or en dashes (they render awkwardly in headlines).
    r"[\u2014\u2013]",
]

REQUIRED_FOOTER = [
    "ARN-366802",
    "Mutual Fund investments are subject to market risks, read all scheme related documents carefully",
]


def lint_text(text):
    """Return a list of violated patterns (empty list = clean)."""
    return [p for p in BANNED_PATTERNS if re.search(p, text, re.IGNORECASE)]


def lint_post(post):
    """`post` is the structured content dict from content.py. Returns list of issues."""
    chunks = [post.get("caption", "")]
    for slide in post.get("slides", []):
        for key in ("kicker", "headline", "subhead", "title", "cta", "footnote"):
            if slide.get(key):
                chunks.append(str(slide[key]))
        for point in slide.get("points", []) or []:
            chunks.append(str(point.get("title", "")))
            chunks.append(str(point.get("text", "")))
    return lint_text(" \n".join(chunks))


def check_footer_present(rendered_text):
    """The CTA slide must carry the ARN and the market-risk disclaimer."""
    return [req for req in REQUIRED_FOOTER if req not in rendered_text]
