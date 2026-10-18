"""Model adapters. The agent loop only needs: text in, text out, token counts.

The loop uses a plain JSON "action" protocol (see agent.py) instead of each vendor's
native tool-calling, so the same loop and the same traces work with any provider.
"""

import json
import os
from dataclasses import dataclass


@dataclass
class LLMOutput:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


def load_env(path=".env"):
    """Tiny .env reader so no extra dependency is needed."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cost_of(out: LLMOutput) -> float:
    """Dollar cost of one model call. Set PRICE_IN_PER_M / PRICE_OUT_PER_M in .env
    to your model's current price per million tokens; unset means 0.0."""
    p_in = float(os.getenv("PRICE_IN_PER_M", "0") or 0)
    p_out = float(os.getenv("PRICE_OUT_PER_M", "0") or 0)
    return (out.tokens_in * p_in + out.tokens_out * p_out) / 1_000_000


class ScriptedLLM:
    """Offline stand-in used by the tests: replays a fixed list of actions.
    If the list runs out it repeats the last one."""

    def __init__(self, actions):
        self.actions = list(actions)
        self.i = 0

    def complete(self, system, messages):
        a = self.actions[min(self.i, len(self.actions) - 1)]
        self.i += 1
        return LLMOutput(text=a if isinstance(a, str) else json.dumps(a))


class AnthropicLLM:
    def __init__(self, model=None):
        import anthropic  # pip install anthropic

        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model or os.getenv("MODEL", "claude-sonnet-5-5")

    def complete(self, system, messages):
        r = self.client.messages.create(
            model=self.model, max_tokens=800, system=system, messages=messages
        )
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return LLMOutput(text, r.usage.input_tokens, r.usage.output_tokens)


class GeminiLLM:
    def __init__(self, model=None):
        from google import genai  # pip install google-genai

        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=key)
        self.model = model or os.getenv("MODEL", "gemini-2.5-flash")

    def complete(self, system, messages):
        from google.genai import types

        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        r = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0),
        )
        u = r.usage_metadata
        return LLMOutput(
            r.text or "",
            getattr(u, "prompt_token_count", 0) or 0,
            getattr(u, "candidates_token_count", 0) or 0,
        )


class GroqLLM:
    """Groq uses an OpenAI-style chat API: the system prompt is just the first message."""

    def __init__(self, model=None):
        import groq
        from groq import Groq  # pip install groq

        self.BadRequestError = groq.BadRequestError
        self.client = Groq()  # reads GROQ_API_KEY
        self.model = model or os.getenv("MODEL", "llama-3.3-70b-versatile")
        # JSON mode makes the model return a valid JSON object every time.
        # Set GROQ_JSON_MODE=0 in .env if your chosen model does not support it.
        self.json_mode = os.getenv("GROQ_JSON_MODE", "1") != "0"
        # Reasoning models spend tokens thinking before they answer, so allow plenty.
        self.max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "4000"))

    def complete(self, system, messages):
        kwargs = {}
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}] + messages,
                temperature=0,
                max_tokens=self.max_tokens,
                **kwargs,
            )
        except self.BadRequestError as e:
            body = getattr(e, "body", None) or {}
            err = body.get("error", body) if isinstance(body, dict) else {}
            if err.get("code") == "json_validate_failed":
                # Let the loop log it as an invalid_output step and retry.
                return LLMOutput(err.get("failed_generation") or "", 0, 0)
            raise
        u = r.usage
        return LLMOutput(
            r.choices[0].message.content or "",
            getattr(u, "prompt_tokens", 0) or 0,
            getattr(u, "completion_tokens", 0) or 0,
        )

def make_llm(provider, model=None):
    provider = (provider or "").lower()
    if provider == "anthropic":
        return AnthropicLLM(model)
    if provider == "gemini":
        return GeminiLLM(model)
    if provider == "groq":
        return GroqLLM(model)
    raise SystemExit(f"Unknown provider {provider!r}. Use 'anthropic', 'gemini' or 'groq'.")