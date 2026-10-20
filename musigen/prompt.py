"""Written request -> spec, with a local language model behind an OpenAI-compatible chat endpoint (Ollama, llama.cpp
server, vLLM ...).  The model only fills the spec (musigen/spec.py); the music is made by the composer, so the same
spec always gives the same score.

  MUSIGEN_LLM_BASE_URL   default http://localhost:11434/v1 (Ollama)
  MUSIGEN_LLM_MODEL      required, e.g. the Qwen model the developer already runs
  MUSIGEN_LLM_API_KEY    optional

The reply must be one JSON object; an invalid spec is sent back once with the validation error.
"""
from __future__ import annotations

import json
import os
import urllib.request

from musigen.spec import Spec, SpecError, from_dict, __doc__ as SPEC_DOC

SYSTEM = (
    "You turn a composer's request (any language) into a JSON composition spec. Reply with ONE JSON object only, "
    "no prose, no code fence. Use only these fields and values:\n" + (SPEC_DOC or "") +
    "\nRules: bars are 1-based and inclusive; form bars must add up to the piece; if the request names chords per "
    "bar give 'progression' with one roman token per bar, else omit it; map wishes about single bars to 'requests'."
)


def _chat(messages: list[dict]) -> str:
    base = os.environ.get("MUSIGEN_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("MUSIGEN_LLM_MODEL")
    if not model:
        raise RuntimeError("set MUSIGEN_LLM_MODEL (and MUSIGEN_LLM_BASE_URL if not Ollama on localhost)")
    body = json.dumps({"model": model, "messages": messages, "temperature": 0,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={"Content-Type": "application/json"})
    if os.environ.get("MUSIGEN_LLM_API_KEY"):
        req.add_header("Authorization", "Bearer " + os.environ["MUSIGEN_LLM_API_KEY"])
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def spec_from_text(text: str) -> Spec:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
    for attempt in range(2):
        reply = _chat(messages)
        try:
            return from_dict(json.loads(reply))
        except (json.JSONDecodeError, SpecError, KeyError, TypeError, ValueError) as e:
            if attempt:
                raise SpecError(f"model reply is not a valid spec: {e}\n{reply}") from e
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": f"Invalid: {e}. Reply with the corrected JSON object only."}]
    raise AssertionError("unreachable")
