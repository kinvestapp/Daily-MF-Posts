"""One guarded door to the Anthropic API: usage log, per-run call cap, monthly budget cap, model fallback.

Costs are ESTIMATES from the token counts the API reports and the price table below
(USD per million tokens, input/output). Unknown models are priced like Sonnet, to stay on the safe side.
Check real prices and balance in the Anthropic Console.
"""
import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "data" / "api_usage.jsonl"
PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (15.0, 75.0)}

# Writer: Haiku (no extended thinking, cheap, predictable length). Reviewer: stronger model, judged on short output.
# Override with WRITER_MODEL / REVIEW_MODEL. Models that think before answering need a generous max_tokens.
WRITER_MODELS = [os.environ.get("WRITER_MODEL", "claude-haiku-4-5-20251001")]
REVIEW_MODELS = [os.environ.get("REVIEW_MODEL", "claude-sonnet-5-5"), "claude-haiku-4-5-20251001"]

_calls_this_run = 0
_client = None
_thinking_off = True


class BudgetExceeded(RuntimeError):
    pass


class Truncated(RuntimeError):
    """The reply hit max_tokens (often because the model spent them thinking), so the text is incomplete."""


def _price(model):
    for key, val in PRICES.items():
        if key in model:
            return val
    return PRICES["sonnet"]


def month_spend(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    prefix = now.strftime("%Y-%m")
    total = 0.0
    if USAGE.exists():
        for line in USAGE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row["ts"].startswith(prefix):
                    total += row["est_usd"]
    return round(total, 4)


def _check_limits():
    cap_calls = int(os.environ.get("MAX_API_CALLS_PER_RUN", "4"))
    cap_usd = float(os.environ.get("MONTHLY_BUDGET_USD", "6"))
    if _calls_this_run >= cap_calls:
        raise BudgetExceeded(f"per-run API call cap reached ({cap_calls})")
    spent = month_spend()
    if spent >= cap_usd:
        raise BudgetExceeded(f"monthly API budget reached (estimated ${spent:.2f} of ${cap_usd:.2f})")


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _log(model, purpose, tin, tout):
    pin, pout = _price(model)
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "model": model, "purpose": purpose,
           "input_tokens": tin, "output_tokens": tout, "est_usd": round(tin * pin / 1e6 + tout * pout / 1e6, 5)}
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


_rejects_thinking_off = set()


def _send(**kwargs):
    """Stream the reply: the SDK refuses large non-streaming requests (over about 21k max_tokens)."""
    with _get_client().messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def call(models, system, messages, max_tokens, purpose):
    """Call the first model that exists. Returns the response text."""
    global _calls_this_run
    last = None
    for model in models:
        _check_limits()
        kwargs = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
        if _thinking_off and model not in _rejects_thinking_off:
            kwargs["thinking"] = {"type": "disabled"}   # plain writing/review tasks: do not pay for extended thinking
        try:
            try:
                msg = _send(**kwargs)
            except Exception as e:
                if "thinking" in kwargs and getattr(e, "status_code", None) == 400 and "thinking" in str(e).lower():
                    print("[llm] model does not accept thinking=disabled; retrying without it")
                    kwargs.pop("thinking")
                    _rejects_thinking_off.add(model)
                    msg = _send(**kwargs)
                else:
                    raise
        except Exception as e:  # unknown model id -> try the next one; anything else is a real error
            if getattr(e, "status_code", None) == 404:
                print(f"[llm] model {model} not available, trying next")
                last = e
                continue
            raise
        _calls_this_run += 1
        row = _log(model, purpose, msg.usage.input_tokens, msg.usage.output_tokens)
        print(f"[llm] {purpose}: {model} in={row['input_tokens']} out={row['output_tokens']} ~${row['est_usd']:.4f} (month ~${month_spend():.2f})")
        if getattr(msg, "stop_reason", None) == "max_tokens":
            raise Truncated(f"{purpose}: reply cut off at max_tokens={max_tokens} (output tokens {row['output_tokens']})")
        # newer models may return thinking blocks first: keep only the text blocks
        return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "text") == "text")
    raise RuntimeError(f"no usable model among {models}: {last}")
