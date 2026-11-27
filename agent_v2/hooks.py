"""Positive-framed engagement hook library for K-Invest.app.

Every hook is written so that it is usable by an AMFI-registered MFD:
no guaranteed returns, no panic, no attacks on named institutions.
Lust is intentionally excluded. Hard fear / hard anger / greed are excluded;
their positive reframings are included under safer names.
"""
import random

HOOKS = {
    "belief": {
        "angle": "Identity and values: disciplined, patient, long-term investors; 'this is who we are'.",
        "example": "Wealth is built in the boring months nobody posts about.",
    },
    "hope": {
        "angle": "Aspiration through small steady steps; future self; time in the market.",
        "example": "Your future self is quietly grateful for today's SIP.",
    },
    "curiosity": {
        "angle": "Information gap: tease a useful insight the reader will want to open the carousel for.",
        "example": "The one SIP habit that matters more than the amount.",
    },
    "awe": {
        "angle": "A surprising but factual illustration of compounding or time (arithmetic only, no return %).",
        "example": "Rs 5,000 a month for 20 years is Rs 12 lakh of your own money invested.",
    },
    "humor": {
        "angle": "Light, kind humor about procrastination or money habits. Never mock the reader.",
        "example": "'I'll start my SIP next month' (said every month).",
    },
    "empathy": {
        "angle": "Acknowledge real money worries families share (rising costs, EMIs, school fees, parents' health) and show a calm first step. Normalise it.",
        "example": "Juggling EMIs, school fees and savings is hard. Starting small is still starting.",
    },
    "belonging": {
        "angle": "Families across Tamil Nadu and India building wealth patiently, one SIP at a time. No fake numbers or testimonials.",
        "example": "Families across India invest a little every month. You can too.",
    },
    "nostalgia": {
        "angle": "Our parents' savings habits, and what today's options add on top.",
        "example": "Our parents saved in gold, chits and FDs. Our generation can add patient investing.",
    },
    "pride": {
        "angle": "Pride in building for your family: your first salary, your first SIP, your first goal.",
        "example": "Your first salary, your first SIP, your first goal: all yours.",
    },
    "authority": {
        "angle": "Plain-language expert explanation of how something works; credibility through clarity.",
        "example": "Expense ratio explained in 20 seconds.",
    },
    "relief": {
        "angle": "Remove a pain: paperwork, jargon, uncertainty. Show how simple the first step is (KYC, SIP set-up).",
        "example": "KYC and SIP set-up, explained without the jargon.",
    },
    "start_early": {
        "angle": "Soft FOMO: the cost of starting late versus early, shown as a neutral illustration.",
        "example": "Starting at 25 vs 35: what ten extra years of time can do.",
    },
    "myth_buster": {
        "angle": "Contrarian but kind: gently correct a common misconception. Never attack named AMCs or competitors.",
        "example": "Myth: you need a lot of money to start. Reality: you need a habit.",
    },
    "surprise_fact": {
        "angle": "A factual 'did you know' that is relevant and verifiable. No alarmism.",
        "example": "Did you know inflation quietly reduces what idle savings can buy?",
    },
    "scarcity_of_time": {
        "angle": "Time is the scarce resource, not money. Positive nudge to start, never urgency about a fund.",
        "example": "You cannot buy back time in the market. You can start using it today.",
    },
}

# Audience segments, in the owner's priority order. The weight is the share of posts aimed at each.
# Content is mainly for domestic investors; NRIs are welcome but secondary.
SEGMENTS = {
    "chennai_tn": {"weight": 35, "notes": "Chennai and Tamil Nadu families: salaried professionals, small business owners, first-time investors. Relatable local life (family goals, school and college fees, weddings, house, festivals like Pongal and Deepavali, traditional savings such as gold, chit funds, FDs, LIC). Warm, respectful, never stereotyping."},
    "south_india": {"weight": 25, "notes": "South India (Karnataka, Kerala, Andhra, Telangana): similar family-goal framing, neutral language, no region-specific stereotypes."},
    "north_india": {"weight": 25, "notes": "North India: family goals, business families, festival and wedding-season planning (Diwali, weddings), neutral language."},
    "nri": {"weight": 15, "notes": "NRIs and overseas Indians (including Nordics, Gulf, US, UK) investing in India. KYC and FATCA basics, investing from abroad. Only explain the process; never claim legal or regulatory approval."},
}

# (topic, segment). Education only, never scheme specific.
TOPICS = [
    ("SIP basics: what a SIP is and why monthly habits matter", "chennai_tn"),
    ("Starting small: Rs 500 or Rs 1,000 a month", "chennai_tn"),
    ("Goal-based investing: child's education, house, wedding, retirement", "chennai_tn"),
    ("Pongal and Deepavali season: planning festival spending without derailing your SIP", "chennai_tn"),
    ("Traditional savings (gold, chits, FDs, LIC) and where mutual funds can fit, explained neutrally", "chennai_tn"),
    ("First salary: a calm 3-step money routine (emergency fund, SIP, insurance review)", "chennai_tn"),
    ("Rupee cost averaging in plain words", "south_india"),
    ("Expense ratio and why costs matter", "south_india"),
    ("Active vs passive funds, explained simply", "south_india"),
    ("Staying invested through market ups and downs", "south_india"),
    ("Small business owners: separating business cash from personal investing", "south_india"),
    ("Wedding and festival season: goal-based saving for family events", "north_india"),
    ("Common mutual fund myths", "north_india"),
    ("Emergency fund before investing", "north_india"),
    ("Asset allocation in one minute", "north_india"),
    ("Review vs react: how to check your portfolio calmly", "north_india"),
    ("NRI basics: KYC and investing in India from abroad", "nri"),
    ("NRI basics: what FATCA means in plain words", "nri"),
]


def pick_hook(history=None, rng=None):
    """Pick a hook. Phase 1 = least-recently-used rotation.

    `history` is a list of previously used hook keys (oldest first).
    Phase 3 will replace this with the performance-weighted strategist.
    """
    rng = rng or random.Random()
    history = history or []
    recent = history[-len(HOOKS) // 2:] if history else []
    pool = [k for k in HOOKS if k not in recent] or list(HOOKS)
    return rng.choice(pool)


def pick_topic(history=None, rng=None):
    """Weighted by audience segment, avoiding recently used topics. Returns (topic, segment)."""
    rng = rng or random.Random()
    history = history or []
    recent = set(history[-8:])
    seg_names = list(SEGMENTS)
    seg = rng.choices(seg_names, weights=[SEGMENTS[s]["weight"] for s in seg_names])[0]
    pool = [t for t, s in TOPICS if s == seg and t not in recent] or [t for t, s in TOPICS if s == seg]
    return rng.choice(pool), seg
