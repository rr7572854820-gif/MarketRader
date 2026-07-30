# MarketRadar — TODO

Prioritized next steps as of 2026-07-29. This is a working list, not a roadmap — see [ROADMAP.md](./ROADMAP.md) for the full phased plan and [SESSION.md](./SESSION.md) for the reasoning behind each item below. Check items off in order; each one blocks the ones below it unless noted.

## 0. Environment setup (blocking everything else)

- [x] Create a virtual environment and install dependencies — done as part of Task 2 verification (`.venv/`, gitignored). Re-run `pip install -r requirements.txt` there (or your own venv) after pulling — `anthropic` was removed, `google-genai` added.
- [x] `GEMINI_API_KEY` added to `.env` and verified working (see item below).
  - Reddit is still optional — leave `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` blank to stay in mock mode.
- [x] Ran `python -m src.check_connections` — Gemini shows `[OK]`, Reddit shows `[SKIP]` (expected, not a failure).

## 1. Sequencing gap — resolved as a deliberate exception

This item previously blocked further code on the grounds that ROADMAP.md Phase 0 says "no software" and PRD.md §13 defers source selection to Milestone 0.1, which hadn't been done.

**Resolution:** the user has since explicitly reframed MarketRadar as a personal, single-user daily-use tool (not commercial), and directed a one-week MVP built task-by-task, bypassing Phase 0's formal ceremony by design — see SESSION.md's 2026-07-30 entries for the full reasoning. This is treated as the second option originally listed here (a deliberate, recorded exception), not as the gap being silently ignored. ROADMAP.md's Phase 0 remains accurate for a *future* commercial version, per the same reframing.

## 2. ROADMAP Phase 0 — Research (deferred, not abandoned)

Not being done in sequence for the personal MVP — see item 1. Worth revisiting formally only if commercialization is ever considered:
- [ ] Milestone 0.1 — Source Feasibility Assessment.
- [ ] Milestone 0.2 — Manual Research Pilot.
- [ ] Milestone 0.3 — Evidence & Confidence Taxonomy (the personal MVP is using a lightweight 3-tier label instead, per the MVP design — see SESSION.md).
- [ ] Milestone 0.4 — Founder Problem-Interviews (not applicable — single user).

## 3. Personal MVP build (current path)

- [x] **Task 1 — Project Setup & External Connections.** `.gitignore`, `requirements.txt`, `.env.example`, `src/config.py`, `src/check_connections.py`. Adapted so Reddit and the AI provider are both optional at config-load time — each consumer checks `config.reddit_configured` / `config.gemini_configured` itself and fails loudly and specifically if it needs one that's missing.
- [x] **Task 2 — Data Fetcher.** `src/models.py` (`FetchedPost`, `FetchQuery` — the one shape every source must return), `src/fetchers/base.py` (`Fetcher` interface, `FetcherError`), `src/fetchers/reddit_fetcher.py` (real, read-only PRAW), `src/fetchers/mock_fetcher.py` (7-item realistic sample dataset, clearly labeled `is_mock=True`), `src/fetchers/__init__.py` (`get_fetcher(config)` factory — chooses real vs. mock automatically), `src/fetch_preview.py` (verification CLI). Tested end-to-end in mock mode: fetch, keyword filter, and limit all work; real Reddit path not yet tested against a live account (none configured).
- [x] **AI provider swap — Anthropic/Claude → Google Gemini. Fully verified with a real key and a real API call.** Removed Anthropic entirely (no money for it); added `src/ai/base.py` (`AIProvider` interface, `AIProviderError`), `src/ai/gemini_provider.py` (real, via `google-genai`), `src/ai/mock_provider.py` (offline testing), `src/ai/__init__.py` (`get_ai_provider(config)` factory). `check_connections.py` verifies Gemini through this abstraction — it never imports `google.genai` directly. `fetch_preview.py` required zero changes, confirming the Fetcher/AI-provider separation actually works. Live-tested: `check_connections.py` → `[OK]`; `get_ai_provider()` returns a real `GeminiProvider` (confirmed via `isinstance`, not just mock fallback); `generate_text("Reply with exactly: MarketRadar Gemini connection successful.")` → exact match response. One real bug found and fixed along the way: the default model `gemini-2.5-flash` is listed by `client.models.list()` but blocked from generation for new API keys (404) — switched the default to the `gemini-flash-latest` alias, which was tested and confirmed working before being committed as the default.
- [x] **Task 3 — AI Insight Engine.** Redefined and expanded beyond the original "Extractor" scope (per-discussion pain points, persona, feature requests, buying signals, sentiment, urgency, opportunity score, confidence, startup opportunity, evidence — plus aggregation: merge/cluster/count/rank). Built as `src/insights/` (`models.py`, `prompts.py`, `extractor.py`, `aggregator.py`) + `src/analyze_preview.py` demo. Live-tested against the real Gemini connection and mock Reddit data. **This absorbs most of what Tasks 5 and 6 below were originally scoped to do** — see the renumbering note under those items.
- [x] **Task 3.1 — Fix Opportunity Clustering.** The Task 3 review found clustering didn't work (7 discussions → 7 clusters, 0 merges, similarity scores an order of magnitude below threshold). Investigated (root cause: semantic gap, keyword overlap has no access to meaning), evaluated four approaches (embeddings, local semantic matching, better normalization, AI-assisted grouping), chose AI-assisted batch clustering (reuses existing `AIProvider`, no new dependency) with the old keyword heuristic kept as a fallback. **Result, measured on the same mock dataset: 7 discussions → 5 clusters. 80% item-level recall on known duplicates (4/5), 0% false merges.** One real duplicate pair (no-code, 2/2) merged perfectly; the reconciliation trio partially merged (2/3) — one item's own extracted framing emphasized a different angle, a real remaining gap, not chased further this session. Also fixed a genuine observability bug found while measuring: `Aggregator` was silently falling back to the old lexical clustering (e.g. on hitting the Gemini free-tier daily quota mid-testing) with zero indication — now exposes `last_method`/`last_fallback_reason`, surfaced as a `[WARN]` by the CLI.
- [ ] **Task 4 — Verifier.** Originally scoped as "confirm each candidate's quote literally appears in its cited source text" — `Extractor` already does a lightweight version of this inline (drops/fails on unverified quotes). What's left for a real Task 4: **cross-post** verification, and a decision on whether secondary pain points / buying signals / supporting evidence should fail loudly when unverifiable (currently: silently dropped) the same way the primary pain point already does.
- [x] **Task 5 — Grouper.** Superseded by Task 3's `Aggregator`, now fixed by Task 3.1 — clustering works well enough to be genuinely useful (see Task 3.1 above), though not perfect (one known partial-miss case). Revisit only if the remaining gap turns out to matter in real use.
- [ ] **Task 6 — Confidence labeler.** Done as part of Task 3 — every `DiscussionInsight` and `OpportunityCluster` carries a `ConfidenceLevel` (Strong/Moderate/Weak, matching the project's existing lightweight taxonomy). Nothing further needed here specifically.
- [ ] **Task 7 — Report writer.** Still not built. Should render `DiscussionInsight`/`OpportunityCluster` (from `src/insights/models.py`) to a saved Markdown report + raw JSON — the shapes already exist; this task is presentation/persistence, not new analysis.
- [ ] **Task 8 — CLI entrypoint.** `src/analyze_preview.py` is a working demo (Fetch → Analyze → Print) but not the final polished single entrypoint — no saved-report output yet (that's Task 7), no combined Fetch→Analyze→Report flow.
- [ ] **Task 9 — Dogfood pass.** Run against 2–3 real subreddits once Reddit credentials exist; manually verify every quote. Still blocked on Reddit credentials (optional, user's choice).

## 4. Housekeeping / smaller items

- [ ] Decide what `docs/` is for, or remove it if it has no purpose (currently an empty, undefined directory).
- [ ] Confirm with the user whether IDEAS.md's 12-dimension scoring framework is correctly scoped to MarketRadar's *own* product/feature ideas (current interpretation) rather than the market opportunities it surfaces for founders — still not explicitly confirmed (see SESSION.md Questions).
- [ ] Note: the GitHub remote is named `MarketRader` (missing the second "a") — cosmetic, not urgent, but worth fixing if/when convenient (`gh repo rename` or a new remote), since it's user-visible.
- [ ] Add unit tests once a test framework is chosen (none exists yet). Highest priority when it happens: the Extractor's quote-verification logic and the Aggregator's clustering response parser — the latter already has 6 hand-verified synthetic edge cases (see SESSION.md Task 3.1 entry) that should become real test cases, not just a one-off manual check.
- [ ] Decide whether to commit `.venv/` setup instructions somewhere more visible than this file, or leave `requirements.txt` + this checklist as the only setup docs.
- [x] ~~Decide whether keyword-overlap clustering is acceptable to keep shipping as-is~~ — resolved by Task 3.1: AI-assisted clustering is now primary, keyword-overlap is a fallback only.
- [ ] Build a schema-aware fake `AIProvider` for testing `src/insights/` offline, once a test framework exists — deliberately not bolted onto the shared `MockAIProvider` (see SESSION.md for why). Still open; now also needs to cover the clustering prompt/response shape, not just extraction.
- [ ] **New:** the Gemini free-tier daily quota for the default model is exhausted as of this session (cumulative Task 3 + 3.1 testing). Will reset; `check_connections.py` is the fastest way to confirm when it has.
- [ ] **New:** decide whether to switch the project default from `gemini-flash-latest` to `gemini-flash-lite-latest` (confirmed working with separate quota during this session) — a real cost/quality tradeoff for the user to decide, not something to switch as a side effect of testing convenience.
- [ ] **New:** the reconciliation trio's partial merge miss (comment-002) is a known, specific, unfixed gap — richer clustering-prompt context (secondary pain points, not just primary) is the flagged next experiment if it turns out to matter.
- [ ] **New:** consider a small local cache of AI responses keyed by input hash, purely to stop iterative testing from burning through daily quota re-running the same measurement (see SESSION.md Future Improvements).

## Explicitly not doing yet (avoid scope creep)

- Task 4 (Verifier proper), Task 7 (Report writer), and Task 8 (final CLI entrypoint) — not started.
- No populated IDEAS.md backlog entries — the framework exists; no real idea has been proposed and scored yet.
- No additional data sources beyond Reddit (real or mock) — Hacker News/Product Hunt/GitHub stay untouched until the core pipeline works end-to-end on one source.
- No architecture rework to accommodate multiple simultaneous sources — the `Fetcher` interface already supports adding one later without touching the analysis pipeline; don't build that pipeline flexibility preemptively before a second source is actually being added.
- No further clustering fixes beyond AI-assisted clustering (Task 3.1) — the remaining reconciliation-trio partial miss is a named, deferred gap, not silently abandoned (see above).
