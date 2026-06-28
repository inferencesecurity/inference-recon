"""
eval/providers.py — Direct vendor SDK adapters for multi-provider model calls.

No intermediary libraries. Each provider routes to its own official SDK,
which is as trusted as the API endpoint itself.

── Tier aliases ──────────────────────────────────────────────────────────────

Use tier names instead of versioned model IDs everywhere except this file:

    haiku     Anthropic's lightweight tier   — fast, cheap
    sonnet    Anthropic's balanced tier      — speed + intelligence
    opus      Anthropic's flagship tier      — maximum capability

    --model haiku                   resolves to current haiku model
    --model anthropic/haiku         same, explicit provider
    --model anthropic/claude-opus-4-7   explicit version — passes through unchanged

Versioned IDs are pinned in TIERS below. When Anthropic ships a new model,
set `next` and `promote_after`; resolve_model() auto-promotes on that date.
See TIERS for the promotion workflow.

── Explicit model strings ────────────────────────────────────────────────────

Pass a full provider/model string to bypass tier resolution entirely:

    anthropic/claude-sonnet-4-6
    openai/gpt-4o-mini
    google/gemini-2.0-flash

Provider can be omitted if the model name is unambiguous:
    claude-sonnet-4-6    →  inferred as anthropic
    gpt-4o-mini          →  inferred as openai
    gemini-2.0-flash     →  inferred as google

── API keys ──────────────────────────────────────────────────────────────────

    ANTHROPIC_API_KEY   — Anthropic
    OPENAI_API_KEY      — OpenAI
    GEMINI_API_KEY      — Google (AI Studio); falls back to GOOGLE_API_KEY
"""

import os
import re
import time
from dataclasses import dataclass
from datetime import date


# ── Tier definitions ──────────────────────────────────────────────────────────
#
# Promotion workflow when Anthropic ships a new model:
#   1. Run VAmPI benchmark with the new model — recall should hold at 1.00
#   2. Set next = "<new-model-id>" and promote_after = "YYYY-MM-DD" (days/weeks out)
#   3. resolve_model() auto-switches on that date; no further action needed
#   4. Once promotion has stabilised: fold next into current, clear both fields
#
# Never write versioned model IDs outside this dict (except historical records
# in the DB, triage scripts, and corpus run logs).

TIERS: dict[str, dict] = {
    "haiku": {
        "current":       "claude-haiku-4-5-20251001",
        "next":          None,
        "promote_after": None,   # "YYYY-MM-DD" — set when staging a promotion
    },
    "sonnet": {
        "current":       "claude-sonnet-4-6",
        "next":          None,
        "promote_after": None,
    },
    "opus": {
        "current":       "claude-opus-4-7",
        "next":          None,
        "promote_after": None,
    },
}

DEFAULT_PROVIDER = "anthropic"


def resolve_model(model: str) -> str:
    """
    Resolve a tier alias to a full provider/model string.

    haiku            → anthropic/claude-haiku-4-5-20251001  (current)
    anthropic/sonnet → anthropic/claude-sonnet-4-6
    anthropic/claude-opus-4-7 → unchanged (explicit version passthrough)

    If a tier has a pending promotion and today >= promote_after, the next
    model is returned instead of current.
    """
    provider_prefix = DEFAULT_PROVIDER
    name = model

    if "/" in model:
        provider_prefix, _, name = model.partition("/")

    tier = TIERS.get(name.lower())
    if tier is None:
        return model  # not a tier alias — pass through unchanged

    target = tier["current"]
    if tier["next"] and tier["promote_after"]:
        try:
            if date.today() >= date.fromisoformat(tier["promote_after"]):
                target = tier["next"]
        except ValueError:
            pass  # malformed date — stay on current

    return f"{provider_prefix}/{target}"


@dataclass
class ModelResponse:
    text:                   str
    input_tokens:           int
    output_tokens:          int
    model:                  str   # identifier returned by the provider
    cache_creation_tokens:  int   = 0   # tokens written to prompt cache (Anthropic only)
    cache_read_tokens:      int   = 0   # tokens read from prompt cache (Anthropic only)


# ── Provider dispatch ─────────────────────────────────────────────────────────

def call(model: str, system: str, user: str, max_tokens: int = 16384) -> ModelResponse:
    """
    Call any supported model. Tier aliases are resolved before dispatch.
    Raises on API or network error.

    Provider SDKs are imported lazily so the module loads without all three
    installed (useful for --dry-run or single-vendor setups).
    """
    resolved = resolve_model(model)
    provider, model_name = _parse_model(resolved)

    if provider == "anthropic":
        return _call_anthropic(model_name, system, user, max_tokens)
    if provider == "openai":
        return _call_openai(model_name, system, user, max_tokens)
    if provider == "google":
        return _call_google(model_name, system, user, max_tokens)

    raise ValueError(
        f"Unknown provider {provider!r}. "
        "Use a tier alias (haiku/sonnet/opus) or anthropic/<model>, "
        "openai/<model>, google/<model>."
    )


def provider_from_model(model: str) -> str:
    """Map a model string (or tier alias) to an ingest --tool identifier."""
    resolved = resolve_model(model)
    provider, _ = _parse_model(resolved)
    return f"api-{provider}" if provider in ("anthropic", "openai", "google") else "api-other"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_model(model: str) -> tuple[str, str]:
    """Return (provider, model_name), inferring provider if omitted."""
    if "/" in model:
        provider, _, model_name = model.partition("/")
        return provider.lower(), model_name

    m = model.lower()
    if "claude" in m:
        return "anthropic", model
    if "gemini" in m:
        return "google", model
    if "gpt" in m or re.match(r"o\d[\d-]", m):
        return "openai", model

    raise ValueError(
        f"Cannot infer provider from {model!r}. "
        "Use a tier alias (haiku/sonnet/opus) or prefix with provider, "
        "e.g. anthropic/claude-haiku-4-5-20251001"
    )


_RETRY_WAITS = [90, 120, 180]   # seconds — sized for tier-1 30K tokens/min limit

def _call_anthropic(model_name: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    import anthropic  # noqa: PLC0415
    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY

    for attempt, wait in enumerate([0] + _RETRY_WAITS):
        if wait:
            print(f"    [rate limit] waiting {wait}s (attempt {attempt + 1}/{1 + len(_RETRY_WAITS)})...")
            time.sleep(wait)
        try:
            msg = client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": user,
                     "cache_control": {"type": "ephemeral"}}
                ]}],
            )
            usage = msg.usage
            return ModelResponse(
                text=msg.content[0].text,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                model=msg.model,
                cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            )
        except anthropic.RateLimitError:
            if attempt == len(_RETRY_WAITS):
                raise


def _call_openai(model_name: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    import openai  # noqa: PLC0415
    client = openai.OpenAI()         # reads OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=model_name,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return ModelResponse(
        text=resp.choices[0].message.content or "",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        model=resp.model,
    )


def _call_google(model_name: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    import google.generativeai as genai  # noqa: PLC0415
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Set GEMINI_API_KEY or GOOGLE_API_KEY for Google models")
    genai.configure(api_key=api_key)
    gmodel = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
    )
    resp = gmodel.generate_content(user)
    return ModelResponse(
        text=resp.text,
        input_tokens=resp.usage_metadata.prompt_token_count,
        output_tokens=resp.usage_metadata.candidates_token_count,
        model=model_name,
    )
