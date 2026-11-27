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
        "angle": "Acknowledge the real complexity NRIs face: two countries, taxes, paperwork. Normalise it.",
        "example": "Sending money home and juggling two tax systems is confusing. That is normal.",
    },
    "belonging": {
        "angle": "Community of Indians in the Nordics building wealth patiently. No fake numbers or testimonials.",
        "example": "Thousands of Indians abroad invest a little every month. You can too.",
    },
    "nostalgia": {
        "angle": "Our parents' savings habits, and what today's options add on top.",
        "example": "Our parents saved. Our generation can invest, patiently.",
    },
    "pride": {
        "angle": "You built a life abroad; let your savings grow back home too.",
        "example": "You built a life abroad. Your savings can grow back home too.",
    },
    "authority": {
        "angle": "Plain-language expert explanation of how something works; credibility through clarity.",
        "example": "Expense ratio explained in 20 seconds.",
    },
    "relief": {
        "angle": "Remove a pain: paperwork, jargon, uncertainty. Show how simple the first step is.",
        "example": "KYC, FATCA and SIP set-up without the paperwork maze.",
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

# Topics the content engine can rotate through (education only, never scheme specific).
TOPICS = [
    "SIP basics and the power of compounding",
    "Rupee cost averaging in plain words",
    "Goal-based investing: education, home, retirement, wedding",
    "Starting small: Rs 500 or Rs 1,000 a month",
    "Emergency fund before investing",
    "Expense ratio and why costs matter",
    "Active vs passive funds, explained simply",
    "Staying invested through market ups and downs",
    "Common mutual fund myths",
    "NRI basics: KYC, FATCA and investing from the Nordics",
    "Asset allocation in one minute",
    "Review vs react: how to check your portfolio calmly",
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
    rng = rng or random.Random()
    history = history or []
    recent = history[-6:]
    pool = [t for t in TOPICS if t not in recent] or TOPICS
    return rng.choice(pool)
