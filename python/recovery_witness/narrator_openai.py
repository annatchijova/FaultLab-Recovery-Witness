"""OpenAI-backed Narrator adapter.

This module plugs into the same `Narrator` boundary used everywhere else in
`narrator.py` and `cli.py`: it receives an already-rendered prompt string and
returns prose. It never sees a sealed payload, a hidden oracle field, or any
value that could feed back into a seal. See docs/investigator-agent-design.md.

The API key is read from an environment variable at call time and is never
stored on the returned callable, logged, or included in any exception
message. stdlib-only (``urllib``); no new dependency is introduced.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_SYSTEM_PROMPT = (
    "You narrate an already-sealed laboratory case file for a mechanic. "
    "The figures you are given are fixed and must not be altered, "
    "contradicted, or extended into a vehicle diagnosis."
)


def _redacted_error(prefix: str, detail: str) -> RuntimeError:
    # Never interpolate raw request/response bodies that could echo a header;
    # only the caller-supplied prefix and a short, pre-checked detail string.
    return RuntimeError(f"{prefix}: {detail}")


def make_openai_narrator(
    *,
    model: str = DEFAULT_MODEL,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    timeout: float = 20.0,
):
    """Build a Narrator callable backed by the OpenAI chat completions API.

    The API key is looked up from ``os.environ[api_key_env]`` on every call,
    not captured at construction time, so it never becomes an attribute of
    the returned callable that could be printed or serialized by accident.
    """

    def openai_narrator(prompt: str) -> str:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise _redacted_error(
                "openai_narrator", f"environment variable {api_key_env} is not set"
            )

        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            _ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            # error.read() may contain provider-side error text but never the
            # key we sent; the key only ever appears in the outgoing header.
            raise _redacted_error(
                "openai_narrator", f"HTTP {error.code} from the narration backend"
            ) from None
        except urllib.error.URLError as error:
            raise _redacted_error(
                "openai_narrator", f"network error reaching the narration backend ({error.reason})"
            ) from None

        try:
            decoded: dict[str, Any] = json.loads(raw)
            text = decoded["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise _redacted_error(
                "openai_narrator", "malformed response from the narration backend"
            ) from None

        if not isinstance(text, str) or not text.strip():
            raise _redacted_error("openai_narrator", "empty narration text")
        return text

    openai_narrator.__name__ = f"openai_narrator[{model}]"
    return openai_narrator
