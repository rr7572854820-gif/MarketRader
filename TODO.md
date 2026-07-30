# MarketRadar — TODO

Prioritized next steps as of 2026-07-29. This is a working list, not a roadmap — see [ROADMAP.md](./ROADMAP.md) for the full phased plan and [SESSION.md](./SESSION.md) for the reasoning behind each item below. Check items off in order; each one blocks the ones below it unless noted.

## 0. Environment setup (blocking everything else)

- [x] Create a virtual environment and install dependencies — done as part of Task 2 verification (`.venv/`, gitignored). Re-run `pip install -r requirements.txt` there (or your own venv) after pulling — `anthropic` was removed, `google-genai` added.
- [ ] `.env` has an empty `GEMINI_API_KEY=` line ready — paste your real key there (never into chat).
  - Reddit is optional — leave `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` blank to stay in mock mode.
  - Gemini is required for the check to fully pass. Free tier available at https://aistudio.google.com/apikey → `GEMINI_API_KEY`.
- [ ] Run `python -m src.check_connections` and confirm Gemini shows `[OK]` (Reddit will show `[SKIP]` unless you've added credentials — that's expected, not a failure).

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
- [x] **AI provider swap — Anthropic/Claude → Google Gemini.** Removed Anthropic entirely (no money for it); added `src/ai/base.py` (`AIProvider` interface, `AIProviderError`), `src/ai/gemini_provider.py` (real, via `google-genai`), `src/ai/mock_provider.py` (offline testing), `src/ai/__init__.py` (`get_ai_provider(config)` factory). `check_connections.py` now verifies Gemini through this abstraction — it never imports `google.genai` directly. `fetch_preview.py` required zero changes, confirming the Fetcher/AI-provider separation actually works. Verified in mock mode (MockAIProvider selected correctly, `check_connection()`/`generate_text()` both work, clearly labeled fake output). **Not yet verified: a real Gemini call** — `GEMINI_API_KEY` is present in `.env` but still empty as of this check; blocked on the user pasting in a real key.
- [ ] **Task 3 — Extractor.** Feed fetched posts to Gemini (via `get_ai_provider`, never directly), get candidate pain-point quotes + one-line problem statements referencing their source item. Explicitly blocked until the real Gemini connection is verified (see item above and item 0) — do not start this until `check_connections.py` shows Gemini `[OK]`.
- [ ] **Task 4 — Verifier.** Pure, deterministic: confirm each candidate's quote literally appears in its cited source text. No AI involved — build and unit-test this independently of the Extractor.
- [ ] **Task 5 — Grouper.** Cluster verified candidates describing the same pain point, count distinct instances.
- [ ] **Task 6 — Confidence labeler.** Deterministic instance-count → Strong/Moderate/Weak.
- [ ] **Task 7 — Report writer.** Render grouped, labeled, verified pain points to a saved Markdown report + raw JSON.
- [ ] **Task 8 — CLI entrypoint.** Wire Tasks 2–7 into one command.
- [ ] **Task 9 — Dogfood pass.** Run against 2–3 real subreddits once Reddit credentials exist; manually verify every quote.

## 4. Housekeeping / smaller items

- [ ] Decide what `docs/` is for, or remove it if it has no purpose (currently an empty, undefined directory).
- [ ] Confirm with the user whether IDEAS.md's 12-dimension scoring framework is correctly scoped to MarketRadar's *own* product/feature ideas (current interpretation) rather than the market opportunities it surfaces for founders — still not explicitly confirmed (see SESSION.md Questions).
- [ ] Note: the GitHub remote is named `MarketRader` (missing the second "a") — cosmetic, not urgent, but worth fixing if/when convenient (`gh repo rename` or a new remote), since it's user-visible.
- [ ] Add unit tests once a test framework is chosen (none exists yet). Highest priority when it happens: the Verifier (Task 4) — it's the one piece standing between AI output and something presented as evidence.
- [ ] Decide whether to commit `.venv/` setup instructions somewhere more visible than this file, or leave `requirements.txt` + this checklist as the only setup docs.

## Explicitly not doing yet (avoid scope creep)

- No extraction, verification, grouping, scoring, or report-writing code yet — that's Tasks 3–7 above, one at a time.
- No populated IDEAS.md backlog entries — the framework exists; no real idea has been proposed and scored yet.
- No additional data sources beyond Reddit (real or mock) — Hacker News/Product Hunt/GitHub stay untouched until the core pipeline works end-to-end on one source.
- No architecture rework to accommodate multiple simultaneous sources — the `Fetcher` interface already supports adding one later without touching the analysis pipeline; don't build that pipeline flexibility preemptively before a second source is actually being added.
