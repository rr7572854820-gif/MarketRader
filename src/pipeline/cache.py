"""A simple, disk-persisted cache for AI provider responses.

Deliberately minimal: one JSON file, read-modify-write on each set(),
no eviction/TTL, no atomic writes. Appropriate for a single-process
personal tool at the current scale (see SESSION.md's Task 8 entry for
the tradeoffs this accepts) — this is not a general-purpose caching
framework.

CachingAIProvider is the actual integration point: an AIProvider-
implementing decorator, same pattern as pipeline.py's
_CountingAIProvider, so it's transparent to Extractor and Aggregator —
neither needs to know or care that responses are being cached.

Critical design constraint: only responses that parse as valid JSON
are cached. Extractor.extract() (src/insights/extractor.py) retries
once on malformed JSON using the *identical* prompt. If a malformed
response were cached, that retry would receive the exact same bad
response instead of a fresh attempt, silently defeating it. Gating on
JSON validity means a retry always misses the cache and gets a real
call — this is a generic heuristic, not a hard dependency on
Extractor's or Aggregator's specific schemas, but it does assume (true
for every current consumer) that a cacheable response is JSON-shaped.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.ai.base import AIProvider

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def hash_prompt(prompt: str) -> str:
    """Cache key: a hash of the exact prompt text. Correct by
    construction — since prompts fully embed source text (see
    src/insights/prompts.py), identical prompts mean identical intent,
    and any change to the source text or the prompt template itself
    naturally produces a different key.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _looks_like_json(text: str) -> bool:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    try:
        json.loads(cleaned)
        return True
    except json.JSONDecodeError:
        return False


class ResponseCache:
    """A flat JSON file mapping prompt-hash -> cached response text.

    Fails open: any problem reading an existing cache file (missing,
    corrupted, unreadable) is treated as an empty cache rather than
    raised — a broken cache file must never break the pipeline. Write
    failures are logged and swallowed for the same reason: caching is
    an optimization, not a correctness requirement.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Cache file %s unreadable (%s) - starting with an empty cache.", self._path, type(exc).__name__
            )
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, key: str) -> Optional[str]:
        value = self._data.get(key)
        return value if isinstance(value, str) else None

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not write cache file %s (%s) - continuing without persisting.", self._path, type(exc).__name__)

    def __len__(self) -> int:
        return len(self._data)


class CachingAIProvider(AIProvider):
    """Wraps any AIProvider and caches generate_text responses by a
    hash of the exact prompt. See module docstring for why only
    JSON-shaped responses are cached.
    """

    def __init__(self, wrapped: AIProvider, cache: ResponseCache) -> None:
        self._wrapped = wrapped
        self._cache = cache
        self.hits = 0
        self.misses = 0

    def check_connection(self) -> None:
        self._wrapped.check_connection()

    def generate_text(self, prompt: str) -> str:
        key = hash_prompt(prompt)
        cached = self._cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached

        self.misses += 1
        response = self._wrapped.generate_text(prompt)
        if _looks_like_json(response):
            self._cache.set(key, response)
        return response
