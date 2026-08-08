"""The Extractor: turns one FetchedPost into one DiscussionInsight, and
extract_all_parallel(), which does that for many posts at once.

Never imports google.genai or any provider SDK directly — the only AI
access point is self._ai_provider.generate_text(), via the AIProvider
interface (src/ai/base.py). This keeps Task 3 provider-agnostic in
exactly the same way Task 2 kept the pipeline source-agnostic.

extract_all_parallel() (not "_extract_all_parallel" as originally
specified - see its own docstring) fans extract() out across a thread
pool in fixed-size batches, with a short pause between batches as a
courtesy to AI-provider rate limits. This is deliberately naive about
work distribution (fixed batch size, not adaptive to response time),
consistent with this project's "explicit over clever" standard - a
provider taking longer just means a longer batch, not a rebalance.
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from src.ai import AIProvider, AIProviderError
from src.insights.models import (
    ConfidenceLevel,
    DiscussionInsight,
    PainPoint,
    Sentiment,
)
from src.insights.prompts import build_extraction_prompt
from src.models import FetchedPost

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2  # one retry if the model returns malformed/invalid JSON

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# (post, exception) for one failed extraction - passed to an optional
# on_error callback so a caller (Pipeline) can record the specific
# failure reason, not just a count. See extract_all_parallel().
OnErrorCallback = Callable[[FetchedPost, Exception], None]
# (completed_count, total_count) after one batch finishes. See
# extract_all_parallel().
OnBatchCompleteCallback = Callable[[int, int], None]


class InsightExtractionError(Exception):
    """Raised when a FetchedPost could not be turned into a valid,
    evidence-verified DiscussionInsight — because the AI call failed,
    its output wasn't valid/complete JSON, or its primary claim
    couldn't be verified against the source text.
    """


class Extractor:
    """Extracts one DiscussionInsight per FetchedPost, via any AIProvider."""

    BATCH_SIZE = 2
    BATCH_DELAY = 1.0

    def __init__(self, ai_provider: AIProvider) -> None:
        self._ai_provider = ai_provider

    def extract(self, post: FetchedPost, ai_provider: Optional[AIProvider] = None) -> DiscussionInsight:
        """Analyze one post and return a validated DiscussionInsight.

        ai_provider overrides self._ai_provider for this one call only,
        when given - never mutates self. This is what makes
        extract_parallel_multi_key() safe to call from several worker
        threads sharing one Extractor instance at once: each thread
        passes its own provider explicitly instead of any thread
        writing to shared self state (which every other thread would
        also be reading/writing at the same time - see that method's
        own docstring for the real race this avoids).

        Raises:
            InsightExtractionError: If the AI call fails (after the
                provider's own transient-failure retries are
                exhausted), if the response can't be parsed as valid
                JSON after one retry, or if the primary pain point's
                evidence quote can't be verified against the post's
                own text.
        """
        provider = ai_provider if ai_provider is not None else self._ai_provider
        source_text = _combined_source_text(post)
        prompt = build_extraction_prompt(post.title or "", post.text, post.url)

        last_error: Optional[Exception] = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                raw_response = provider.generate_text(prompt)
            except AIProviderError as exc:
                raise InsightExtractionError(f"AI provider call failed: {exc}") from exc

            try:
                data = _parse_json_response(raw_response)
                return _build_insight(data, post, source_text)
            except InsightExtractionError as exc:
                last_error = exc
                continue

        raise InsightExtractionError(
            f"Could not extract a valid insight after {_MAX_ATTEMPTS} attempts: {last_error}"
        )

    def _extract_single_safe(
        self,
        post: FetchedPost,
        on_error: Optional[OnErrorCallback] = None,
        ai_provider: Optional[AIProvider] = None,
    ) -> Optional[DiscussionInsight]:
        """extract() for one post, but never raises - returns None on
        failure instead, after logging a warning and (if given) telling
        on_error the specific post/exception, so a caller batching many
        of these through a thread pool doesn't need its own per-item
        try/except around each future. ai_provider is forwarded to
        extract() unchanged - see that method's own docstring.
        """
        try:
            return self.extract(post, ai_provider=ai_provider)
        except InsightExtractionError as exc:
            logger.warning("Extraction failed for %s: %s", post.url, exc)
            if on_error:
                on_error(post, exc)
            return None

    def extract_all_parallel(
        self,
        posts: List[FetchedPost],
        on_error: Optional[OnErrorCallback] = None,
        on_batch_complete: Optional[OnBatchCompleteCallback] = None,
    ) -> List[DiscussionInsight]:
        """Extracts from every post, BATCH_SIZE at a time via a thread
        pool (extraction is I/O-bound - waiting on the AI provider's
        HTTP response - so threads, not processes, are the right tool,
        same reasoning as BaseFetcher.fetch_parallel). A short
        BATCH_DELAY pause between batches (never after the last one) is
        a courtesy to AI-provider rate limits under this project's
        free-tier providers.

        Works identically regardless of which Fetcher produced `posts`
        - this operates purely on the shared FetchedPost shape, after
        fetching is already done, so GitHub/Reddit/any future source
        all benefit with no source-specific code here.

        Not named "_extract_all_parallel" (originally specified) or
        called as an internal self._extract_all_parallel(...) from
        inside extract() - unlike the class's other methods, this one
        is meant to be called by an external orchestrator (Pipeline),
        which is also the one that knows discussions - Extractor
        itself only ever operates on `posts`/FetchedPost. A leading
        underscore would misstate that as a private implementation
        detail when it's this class's actual batch-extraction entry
        point.

        Per-item failures never abort the batch (same "one bad post
        never aborts the run" principle as the pre-existing sequential
        path) - on_error, if given, is how a caller recovers the exact
        failure reason for reporting (e.g. Pipeline's own `errors`
        list), since a bare None return can't carry it.
        """
        all_insights: List[DiscussionInsight] = []
        total = len(posts)
        processed = 0

        batches = [posts[i : i + self.BATCH_SIZE] for i in range(0, total, self.BATCH_SIZE)]

        for batch_num, batch in enumerate(batches):
            with ThreadPoolExecutor(max_workers=self.BATCH_SIZE) as executor:
                results = list(
                    executor.map(lambda post: self._extract_single_safe(post, on_error), batch)
                )

            valid = [r for r in results if r is not None]
            all_insights.extend(valid)
            processed += len(batch)

            logger.info("Extracted %d/%d", processed, total)
            if on_batch_complete:
                on_batch_complete(processed, total)

            is_last = batch_num == len(batches) - 1
            if not is_last:
                time.sleep(self.BATCH_DELAY)

        return all_insights

    def _extract_single_with_provider(
        self,
        post: FetchedPost,
        provider: AIProvider,
        on_error: Optional[OnErrorCallback] = None,
    ) -> Optional[DiscussionInsight]:
        """extract() against a specific provider rather than
        self._ai_provider - the thread-safe way to do that is passing
        the provider explicitly (see extract()'s own ai_provider
        parameter), never mutating shared self state from a worker
        thread.

        Broad except Exception, deliberately: this runs inside a
        ThreadPoolExecutor worker as part of
        extract_parallel_multi_key()'s per-key fan-out, and one item's
        unexpected failure must never crash that key's whole batch or
        the other keys running concurrently - same precedent as
        BaseFetcher.fetch_parallel's own safe_fetch wrapper and
        Pipeline._fetch_from_source (ENGINEERING_GUIDE.md's "exactly
        one broad except Exception" claim was already stale before
        this, per those two - see SESSION.md). _extract_single_safe's
        own narrower `except InsightExtractionError` already handles
        the expected failure case with its own logging; this is a
        last-resort net around it, not a replacement for it.
        """
        try:
            return self._extract_single_safe(post, on_error, ai_provider=provider)
        except Exception as exc:  # noqa: BLE001 — per-item isolation at a parallel fan-out boundary, see docstring
            logger.warning("Extraction failed for %s: %s", post.url, exc)
            if on_error:
                on_error(post, exc)
            return None

    def extract_parallel_multi_key(
        self,
        posts: List[FetchedPost],
        ai_providers: List[AIProvider],
        on_error: Optional[OnErrorCallback] = None,
        on_batch_complete: Optional[OnBatchCompleteCallback] = None,
    ) -> List[DiscussionInsight]:
        """Distributes posts round-robin across several independent
        AIProvider instances (typically one GroqProvider per configured
        key - see GroqProvider.get_all_key_providers()) and extracts
        each provider's share concurrently, one worker thread per
        provider - so N providers means N requests that can genuinely
        be in flight at once, each against its own key's independent
        rate-limit budget, instead of N requests all competing for one
        key's budget.

        Falls back to extract_all_parallel() (this class's existing,
        already-tested batched-single-provider path) whenever fewer
        than 2 providers are given - one provider can't be usefully
        distributed across, and spinning up the round-robin machinery
        for a single key would just reproduce extract_all_parallel()'s
        own behavior with more code, not less.

        on_error/on_batch_complete have the same contract as
        extract_all_parallel()'s own (a caller - Pipeline - relies on
        both: on_error populates the errors list surfaced in the
        dashboard's "Show details" disclosure, on_batch_complete drives
        the SSE progress percentage during the analyze stage). A
        "batch" here means one provider's entire assigned share (there
        are exactly len(ai_providers) of them, each running in its own
        thread) rather than a fixed BATCH_SIZE-sized chunk, since
        there's no equivalent fixed chunk size once every provider is
        its own independent worker. Uses as_completed() rather than
        executor.map() specifically so on_batch_complete fires as each
        provider's share actually finishes (real incremental progress),
        not only after every provider - including the slowest - is
        done, which executor.map() would otherwise force.
        """
        if len(ai_providers) < 2:
            return self.extract_all_parallel(posts, on_error=on_error, on_batch_complete=on_batch_complete)

        if not posts:
            return []

        n_keys = len(ai_providers)
        total = len(posts)
        results: List[Optional[DiscussionInsight]] = [None] * total

        key_posts: List[List[FetchedPost]] = [[] for _ in range(n_keys)]
        key_indices: List[List[int]] = [[] for _ in range(n_keys)]
        for i, post in enumerate(posts):
            key_idx = i % n_keys
            key_posts[key_idx].append(post)
            key_indices[key_idx].append(i)

        def extract_key_batch(provider: AIProvider, batch: List[FetchedPost]) -> List[Optional[DiscussionInsight]]:
            return [self._extract_single_with_provider(post, provider, on_error) for post in batch]

        processed = 0
        with ThreadPoolExecutor(max_workers=n_keys) as executor:
            future_to_key = {
                executor.submit(extract_key_batch, ai_providers[i], key_posts[i]): i
                for i in range(n_keys)
                if key_posts[i]
            }
            for future in as_completed(future_to_key):
                key_idx = future_to_key[future]
                batch_results = future.result()
                for idx, result in zip(key_indices[key_idx], batch_results):
                    results[idx] = result
                processed += len(batch_results)
                logger.info("Extracted %d/%d (multi-key)", processed, total)
                if on_batch_complete:
                    on_batch_complete(processed, total)

        return [r for r in results if r is not None]


def _combined_source_text(post: FetchedPost) -> str:
    return f"{post.title or ''}\n{post.text}"


def _parse_json_response(raw_response: str) -> Dict[str, Any]:
    cleaned = _FENCE_RE.sub("", raw_response.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InsightExtractionError(
            f"AI response was not valid JSON: {exc}. "
            f"Raw response started with: {raw_response[:200]!r}"
        ) from exc


def _verified_quote(candidate: str, source_text: str) -> str:
    """Returns candidate if it's a verbatim substring of source_text,
    otherwise "" — dropping unverifiable quotes rather than propagating
    a possibly-fabricated one.

    This is the project's core non-fabrication guardrail, applied
    inline here for Task 3's own output. It is deliberately lightweight
    (exact substring match, nothing smarter) — the standalone Verifier
    (Task 4, not started) will do more thorough, cross-post checking
    later; this is just enough to keep Task 3 from ever presenting an
    invented quote.
    """
    if not candidate:
        return ""
    return candidate if candidate in source_text else ""


def _verified_quote_list(candidates: List[str], source_text: str) -> List[str]:
    return [q for q in (_verified_quote(c, source_text) for c in candidates) if q]


def _pain_point_from_data(data: Any, source_text: str) -> Optional[PainPoint]:
    if not isinstance(data, dict):
        return None
    description = str(data.get("description", "")).strip()
    quote = _verified_quote(str(data.get("evidence_quote", "")), source_text)
    if not description or not quote:
        return None
    return PainPoint(description=description, evidence_quote=quote)


def _confidence_from_value(value: Any) -> ConfidenceLevel:
    text = str(value).strip().lower()
    for level in ConfidenceLevel:
        if level.value.lower() == text:
            return level
    return ConfidenceLevel.WEAK  # unrecognized/missing -> the conservative default


def _sentiment_from_value(value: Any) -> Sentiment:
    text = str(value).strip().lower()
    for sentiment in Sentiment:
        if sentiment.value.lower() == text:
            return sentiment
    return Sentiment.NEUTRAL  # unrecognized/missing -> the conservative default


def _clamped_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_insight(data: Dict[str, Any], post: FetchedPost, source_text: str) -> DiscussionInsight:
    primary = _pain_point_from_data(data.get("primary_pain_point"), source_text)
    if primary is None:
        raise InsightExtractionError(
            "Primary pain point missing, empty, or its evidence_quote could not be "
            "verified against the source text - refusing to present an unverified "
            "primary claim."
        )

    secondary_raw = data.get("secondary_pain_points") or []
    secondary = (
        [pp for pp in (_pain_point_from_data(item, source_text) for item in secondary_raw) if pp]
        if isinstance(secondary_raw, list)
        else []
    )

    raw_buying_signals = data.get("buying_signals") or []
    raw_supporting_evidence = data.get("supporting_evidence") or []

    return DiscussionInsight(
        source_post_id=post.id,
        source_url=post.url,
        is_mock_source=post.is_mock,
        primary_pain_point=primary,
        secondary_pain_points=secondary,
        user_persona=str(data.get("user_persona", "")).strip(),
        feature_requests=_string_list(data.get("feature_requests")),
        buying_signals=_verified_quote_list(_string_list(raw_buying_signals), source_text),
        emotional_sentiment=_sentiment_from_value(data.get("emotional_sentiment")),
        urgency_score=_clamped_int(data.get("urgency_score"), 1, 10, default=1),
        opportunity_score=_clamped_int(data.get("opportunity_score"), 1, 100, default=1),
        confidence=_confidence_from_value(data.get("confidence")),
        startup_opportunity=str(data.get("startup_opportunity", "")).strip(),
        supporting_evidence=_verified_quote_list(_string_list(raw_supporting_evidence), source_text),
    )
