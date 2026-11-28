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
        "example": "Chennai's quiet savers never post about it. They just never skip the 5th.",
    },
    "hope": {
        "angle": "Aspiration through small steady steps; future self; time in the market.",
        "example": "Her college fee is 15 Junes away. One small envelope a month.",
    },
    "curiosity": {
        "angle": "Information gap: tease a useful insight the reader will want to open the carousel for.",
        "example": "The salary-day habit Chennai parents rarely talk about.",
    },
    "awe": {
        "angle": "A surprising but factual illustration of compounding or time (arithmetic only, no return %).",
        "example": "Rs 3,000 a month from first job to 60 is Rs 12.6 lakh of your own savings.",
    },
    "humor": {
        "angle": "Light, kind humor about procrastination or money habits. Never mock the reader.",
        "example": "Me every 1st: SIP from next month. Me every 30th: same.",
    },
    "empathy": {
        "angle": "Acknowledge real money worries families share (rising costs, EMIs, school fees, parents' health) and show a calm first step. Normalise it.",
        "example": "Rent, school fees, Amma's medicines. And still, Rs 500 a month counts.",
    },
    "belonging": {
        "angle": "Families across Tamil Nadu and India building wealth patiently, one SIP at a time. No fake numbers or testimonials.",
        "example": "Velachery to Tambaram, families are quietly fixing a SIP date.",
    },
    "nostalgia": {
        "angle": "Our parents' savings habits, and what today's options add on top.",
        "example": "Amma saved in gold. Appa saved in FDs. What will your kids say you saved in?",
    },
    "pride": {
        "angle": "Pride in building for your family: your first salary, your first SIP, your first goal.",
        "example": "Your first salary bought sweets for everyone. Your second can start your SIP.",
    },
    "authority": {
        "angle": "Plain-language expert explanation of how something works; credibility through clarity.",
        "example": "Expense ratio, explained before your filter coffee cools.",
    },
    "relief": {
        "angle": "Remove a pain: paperwork, jargon, uncertainty. Show how simple the first step is (KYC, SIP set-up).",
        "example": "KYC sounds scary. It is mostly one form.",
    },
    "start_early": {
        "angle": "Soft FOMO: the cost of starting late versus early, shown as a neutral illustration.",
        "example": "Two friends, same salary. One started at 25, one at 35.",
    },
    "community_fomo": {
        "angle": "Positive FOMO through belonging: neighbours, colleagues and families in your city already keep a small monthly habit, and the door is open to join them. Invitation, never pressure: no urgency, no 'you are falling behind', no invented numbers or testimonials.",
        "example": "Chennai families are quietly building a monthly habit. Your seat is open.",
    },
    "myth_buster": {
        "angle": "Contrarian but kind: gently correct a common misconception. Never attack named AMCs or competitors.",
        "example": "Myth: SIPs are for rich people. Fact: they can start small.",
    },
    "surprise_fact": {
        "angle": "A factual 'did you know' that is relevant and verifiable. No alarmism.",
        "example": "Prices rise quietly every year. Idle cash notices first.",
    },
    "scarcity_of_time": {
        "angle": "Time is the scarce resource, not money. Positive nudge to start, never urgency about a fund.",
        "example": "You cannot buy back the years. You can use this one.",
    },
}

# Owner priority: emotional hooks of belonging and (positive) FOMO get the most airtime until real data says otherwise.
# Used as sampling weights when the strategist is rotating or exploring; exploitation is driven by measured results.
HOOK_PRIOR = {"community_fomo": 6, "belonging": 6, "start_early": 3, "hope": 2, "empathy": 2, "pride": 2, "nostalgia": 2}

# Audience segments, in the owner's priority order. The weight is the share of posts aimed at each.
# Content is mainly for domestic investors; NRIs are welcome but secondary.
SEGMENTS = {
    "chennai_tn": {"weight": 70, "notes": "Chennai and Tamil Nadu families: salaried professionals, small business owners, first-time investors. Relatable local life (family goals, school and college fees, weddings, house, festivals like Pongal and Deepavali, traditional savings such as gold, chit funds, FDs, LIC). Warm, respectful, never stereotyping."},
    "south_india": {"weight": 12, "notes": "South India (Karnataka, Kerala, Andhra, Telangana): similar family-goal framing, neutral language, no region-specific stereotypes."},
    "north_india": {"weight": 14, "notes": "North India: family goals, business families, festival and wedding-season planning (Diwali, weddings), neutral language."},
    "nri": {"weight": 4, "notes": "NRIs and overseas Indians (including Nordics, Gulf, US, UK) investing in India. KYC and FATCA basics, investing from abroad. Only explain the process; never claim legal or regulatory approval."},
}

# (topic, segment). Education only, never scheme specific.
TOPICS = [
    ("SIP basics: what a SIP is and why monthly habits matter", "chennai_tn"),
    ("Starting small: Rs 500 or Rs 1,000 a month", "chennai_tn"),
    ("Goal-based investing: child's education, house, wedding, retirement", "chennai_tn"),
    ("Pongal and Deepavali season: planning festival spending without derailing your SIP", "chennai_tn"),
    ("Traditional savings (gold, chits, FDs, LIC) and where mutual funds can fit, explained neutrally", "chennai_tn"),
    ("First salary: a calm 3-step money routine (emergency fund, SIP, insurance review)", "chennai_tn"),
    ("Neighbourhood habits: how Chennai families keep a small monthly SIP going alongside rent, school fees and EMIs", "chennai_tn"),
    ("Salaried in OMR, Guindy or Ambattur: a simple monthly money routine on payday", "chennai_tn"),
    ("Women of the family leading household money goals, explained respectfully", "chennai_tn"),
    ("Planning a child's college admission and fees years ahead, goal by goal", "chennai_tn"),
    ("Small shop and business owners in Chennai: keeping a personal SIP separate from business cash", "chennai_tn"),
    ("Parents' health and retirement: building a calm plan step by step", "chennai_tn"),
    ("June school fee season: planning next year's fees from this year", "chennai_tn"),
    ("A wedding in the family in 3 years: a goal-based monthly plan", "chennai_tn"),
    ("Freelancers and gig workers in Chennai: keeping a SIP with irregular income", "chennai_tn"),
    ("Couples in Chennai: setting one shared money goal", "chennai_tn"),
    ("Gold and SIPs: why many Tamil families keep both, explained neutrally", "chennai_tn"),
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


# Named recurring series (the slide-1 kicker) so followers recognise and come back for a format.
SERIES = {
    "community_fomo": "NAMMA CHENNAI SAVES", "belonging": "NAMMA CHENNAI SAVES", "empathy": "NAMMA CHENNAI SAVES",
    "pride": "NAMMA CHENNAI SAVES", "nostalgia": "AMMA'S WAY, OUR WAY", "myth_buster": "MYTH OR FACT",
    "authority": "60-SECOND MONEY", "relief": "60-SECOND MONEY", "curiosity": "60-SECOND MONEY",
    "surprise_fact": "60-SECOND MONEY", "awe": "60-SECOND MONEY",
}


def series_for(hook, segment):
    s = SERIES.get(hook, "SALARY DAY")
    if s == "NAMMA CHENNAI SAVES" and segment != "chennai_tn":
        s = "FAMILIES LIKE YOURS"
    return s


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
