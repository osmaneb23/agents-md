from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4.1",
    "gemini": "gemini-2.5-pro",
    "ollama": "llama3.1",
}

PROVIDER_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}


class LlmError(RuntimeError):
    pass


def detect_provider(requested: str | None) -> str | None:
    if requested:
        if requested == "ollama" or _provider_key_present(requested):
            return requested
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return None


def _provider_key_present(provider: str) -> bool:
    return any(os.getenv(name) for name in PROVIDER_ENV.get(provider, ()))


def missing_key_message() -> str:
    return (
        "No LLM provider key found. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY; "
        "pass --provider with the matching environment key; or rerun with --no-llm for offline generation."
    )


def synthesize_with_llm(draft: str, *, provider: str, model: str | None = None) -> str:
    model = model or DEFAULT_MODELS.get(provider)
    prompt = _prompt(draft)
    if provider == "openai":
        return _openai(prompt, model)
    if provider == "anthropic":
        return _anthropic(prompt, model)
    if provider == "gemini":
        return _gemini(prompt, model)
    if provider == "ollama":
        return _ollama(prompt, model)
    raise LlmError(f"Unsupported provider: {provider}")


def _prompt(draft: str) -> str:
    return f"""Rewrite this AGENTS.md draft into a concise, high-signal file.

Rules:
- Keep it under 150 lines.
- Preserve every `<!-- agents-md:start:* -->`, `<!-- agents-md:end:* -->`, and fingerprint comment exactly.
- Do not add architecture tours, README summaries, or generic best practices.
- Keep exact commands and flags.
- Keep Always Do / Ask First / Never Do boundaries.
- Do not re-add content that the draft excluded.
- If the repo has little to say, keep the file short.

Draft:
{draft}
"""


def _openai(prompt: str, model: str | None) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LlmError("Install `agents-md[openai]` to use the OpenAI provider.") from exc
    client = OpenAI()
    response = client.responses.create(model=model or DEFAULT_MODELS["openai"], input=prompt)
    text = getattr(response, "output_text", None)
    if not text:
        raise LlmError("OpenAI response did not include text output.")
    return text


def _anthropic(prompt: str, model: str | None) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise LlmError("Install `agents-md[anthropic]` to use the Anthropic provider.") from exc
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or DEFAULT_MODELS["anthropic"],
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    chunks = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    if not chunks:
        raise LlmError("Anthropic response did not include text output.")
    return "\n".join(chunks)


def _gemini(prompt: str, model: str | None) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise LlmError("Install `agents-md[gemini]` to use the Gemini provider.") from exc
    client = genai.Client()
    response = client.models.generate_content(model=model or DEFAULT_MODELS["gemini"], contents=prompt)
    text = getattr(response, "text", None)
    if not text:
        raise LlmError("Gemini response did not include text output.")
    return text


def _ollama(prompt: str, model: str | None) -> str:
    payload = json.dumps({"model": model or DEFAULT_MODELS["ollama"], "prompt": prompt, "stream": False}).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LlmError("Could not reach local Ollama at http://127.0.0.1:11434.") from exc
    text = body.get("response")
    if not isinstance(text, str) or not text.strip():
        raise LlmError("Ollama response did not include text output.")
    return text
