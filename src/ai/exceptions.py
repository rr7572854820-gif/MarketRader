"""AI-provider-specific AIProviderError subclasses.

Mirrors src/fetchers/exceptions.py's pattern exactly: these are
subclasses of AIProviderError, not a parallel hierarchy, so base.py's
documented rule ("callers should catch this one type") still holds -
`except AIProviderError` still catches every provider's failures the
same way. The more specific types exist only so a caller that wants to
be precise about *why* a call failed (e.g. GroqProvider's own tests)
can be, without every other caller needing to change.

Only src/ai/groq_provider.py raises these currently.
"""

from __future__ import annotations

from src.ai.base import AIProviderError


class AIProviderAuthError(AIProviderError):
    """Raised when the configured API key is invalid or rejected."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when the provider's rate limit has been exceeded."""
