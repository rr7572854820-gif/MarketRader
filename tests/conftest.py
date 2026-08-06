"""Shared pytest fixtures, autouse only where the alternative is every
test having to remember the same patch itself.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _no_real_batch_delay():
    """Extractor.extract_all_parallel() sleeps BATCH_DELAY (1.5s)
    between real extraction batches as a courtesy to AI-provider rate
    limits (src/insights/extractor.py) - real, wall-clock sleeps in
    every test with more than BATCH_SIZE (5) mocked posts would have
    made the suite ~19x slower (confirmed: 231 tests went from ~9s to
    ~190s before this fixture existed). Patched via the class constant,
    not time.sleep itself - extractor.py does `import time` (not `from
    time import sleep`), so patching "...extractor.time.sleep" patches
    the one shared time module process-wide, not just this module's use
    of it (confirmed the hard way: it silently broke an unrelated
    test's own direct time.sleep(1.1) call elsewhere in the suite).
    Setting BATCH_DELAY to 0 leaves the real time.sleep(0) call in
    place (negligible cost) and can't leak into any other test.
    """
    with patch("src.insights.extractor.Extractor.BATCH_DELAY", 0):
        yield


@pytest.fixture(autouse=True)
def _no_real_post_extraction_delay():
    """Pipeline.run() sleeps _POST_EXTRACTION_DELAY_SECONDS (3s) between
    extraction and clustering as a courtesy to AI-provider rate limits
    (src/pipeline/pipeline.py) - same real-sleep-in-every-test risk as
    Extractor.BATCH_DELAY above, and the same reason it's patched by
    name rather than via time.sleep itself (pipeline.py also does
    `import time`, not `from time import sleep`).
    """
    with patch("src.pipeline.pipeline._POST_EXTRACTION_DELAY_SECONDS", 0):
        yield
