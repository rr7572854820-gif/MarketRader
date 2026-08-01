# MarketRadar — Engineering Guide

This is the permanent development contract for this codebase. It documents the architecture **as it actually exists today**, verified against the real source tree, not an aspirational design. Every future task should be able to start with: *"Read ENGINEERING_GUIDE.md before writing any code."*

This document does not replace [CLAUDE.md](./CLAUDE.md) (session-level operating rules for Claude Code), [README.md](./README.md) (product narrative + setup), [PRD.md](./PRD.md) (product requirements), [ROADMAP.md](./ROADMAP.md) (phased milestones), or [SESSION.md](./SESSION.md) (the append-only development journal). It sits alongside them as the "how the code is actually organized and how to extend it correctly" reference. Where this document and those disagree, treat that as a real inconsistency worth flagging (see §21), not a reason to silently pick one.

Every code fact below was verified against the real files in this repo at the time of writing (2026-07-31), not inferred from memory or convention. If a future change makes a statement here false, update this file in the same session, per CLAUDE.md §13.

---

## 1. Project Mission

MarketRadar is an AI-powered market intelligence platform that discovers real, evidence-backed business pain points from public conversations — so founders can find problems worth solving instead of generating random ideas. It is a **research platform, not an idea generator**; its entire value rests on one property: **every conclusion is traceable to real evidence.**

Non-negotiable principles (CLAUDE.md §3, README.md "Project Philosophy"):
- Evidence > Opinions. Problems > Ideas. Validation > Assumptions. Users > Features. Data > Hype. Consistency > Complexity.
- Depth before breadth — prove one source works end-to-end before adding another.
- Never fabricate evidence, never hallucinate a competitor, never present inference as fact, never silently drop uncertainty.
- The founder decides — MarketRadar informs, it never decides on the user's behalf (no build/invest verdicts anywhere in the codebase — see §9).

Current phase: a **personal, single-user MVP**, built task-by-task, deliberately bypassing ROADMAP.md's formal Phase 0 research ceremony as a recorded exception (TODO.md §1, "Sequencing gap"). ROADMAP.md's phased plan remains the reference for a future commercial version; it is not the current build plan.

---

## 2. Core Architecture

MarketRadar is a **five-stage, single-process pipeline**, run from one entrypoint, with every stage swappable behind a small interface:

```
Fetch → Analyze (Extract) → Cluster (Aggregate) → Verify → Report
```

| Stage | Module | AI calls? | Deterministic? |
|---|---|---|---|
| Fetch | `src/fetchers/` | No | Yes |
| Analyze | `src/insights/extractor.py` | Yes (1 per post) | No (AI output, but quote-verified before acceptance) |
| Cluster | `src/insights/aggregator.py` | Yes (1 batched call), with a deterministic lexical fallback | Fallback path is deterministic; AI path is not |
| Verify | `src/verification/verifier.py` | **Never** | Yes — pure string matching |
| Report | `src/reporting/` | **Never** | Yes — pure aggregation + string formatting |

`src/pipeline/pipeline.py`'s `Pipeline.run()` is the **only** place that wires all five stages together. It never contains business logic of its own beyond orchestration, retry-on-transient-fetch-failure, AI-call counting, and caching. Two consumers sit on top of it, both thin:
- `src/pipeline/runner.py` — the CLI.
- `src/api/routes.py` — the REST API.

A third, separate application, `dashboard/` (Next.js), sits on top of the REST API over HTTP only — it is not part of the Python codebase's dependency graph at all.

**The one property every stage exists to protect**: a `DiscussionInsight`'s evidence fields (`evidence_quote`, `supporting_evidence`, `buying_signals`) are guaranteed, structurally, to be verbatim substrings of the original `FetchedPost.text` — enforced once by the Extractor (`_verified_quote`), and re-checked independently and separately by the Verifier. Nothing downstream is allowed to weaken this.

---

## 3. Folder Responsibilities

```
src/
  models.py            Source-agnostic FetchedPost / FetchQuery — the one shape every fetcher returns.
  config.py             Single env-var loader (load_config()). No other module reads os.environ.
  fetchers/              Data sources: Fetcher interface, FetcherError, RedditFetcher, MockFetcher,
                         GitHubFetcher, exceptions.py, get_fetcher() factory.
  ai/                    AI backends: AIProvider interface, AIProviderError, GeminiProvider,
                         MockAIProvider, get_ai_provider() factory.
  insights/              The AI Insight Engine: models.py (DiscussionInsight/PainPoint/OpportunityCluster),
                         prompts.py, extractor.py (per-post extraction), aggregator.py (clustering).
  verification/          Independent, zero-AI re-verification of every claim: models.py, verifier.py.
  reporting/             Deterministic report building + rendering: models.py, report_generator.py,
                         formatter.py (terminal + Markdown).
  pipeline/              Orchestration: pipeline.py (Pipeline/PipelineConfig), runner.py (CLI),
                         cache.py (ResponseCache/CachingAIProvider).
  api/                   FastAPI wrapper over Pipeline: app.py, routes.py, models.py (Pydantic).
  check_connections.py   Diagnostic entrypoint: verifies Reddit/Gemini credentials only, no fetch/analyze.
  fetch_preview.py        Diagnostic entrypoint for the Fetch stage alone (predates runner.py).
  analyze_preview.py      Diagnostic entrypoint for Fetch+Analyze+Verify+Report (predates runner.py).
dashboard/               Separate Next.js/TypeScript app. Zero coupling to src/ except the REST contract.
tests/                   pytest, mirrors src/'s package structure for new subpackages
                         (tests/ai/, tests/fetchers/), flat tests/test_*.py for the rest.
research/                Empty templates for future manual research passes (Phase 0). Not wired to code.
output/                  Runtime-generated: pipeline_run_*.json + report_*.md. Gitignored contents.
.cache/                  Runtime-generated: ai_responses.json (CachingAIProvider). Gitignored.
```

Root-level documents (README.md, PRD.md, CLAUDE.md, ROADMAP.md, SESSION.md, TODO.md, IDEAS.md, this file) are the project's documentation layer — see §15.

`fetch_preview.py` and `analyze_preview.py` are explicitly **not deprecated but not the maintained entrypoint either** — `src/pipeline/runner.py` is. This is a known, named, still-open decision (TODO.md: "decide whether `analyze_preview.py` should be deprecated/removed"), not an oversight.

---

## 4. Module Boundaries

Each package exposes a small public surface; everything else is private to it.

- **`src/fetchers/`**: Nothing outside this package imports `RedditFetcher`, `MockFetcher`, or `GitHubFetcher` directly. Everything else depends only on `Fetcher`, `FetcherError`, `src.models.FetchedPost`/`FetchQuery`, and `get_fetcher()`.
- **`src/ai/`**: Same rule for `GeminiProvider`/`MockAIProvider` — only `AIProvider`, `AIProviderError`, and `get_ai_provider()` are public.
- **`src/insights/`**: Depends on `src.ai` (interface only) and `src.models`. Nothing outside `src/insights/` should need to know how extraction or clustering prompts are built.
- **`src/verification/`**: Depends **only** on `src.insights.models` (types, not logic) and `src.models`. Deliberately never imports `src.insights.extractor` — checking an AI's claim against immutable source text is a meaningful independent check; importing the same extraction logic to re-check itself would not be.
- **`src/reporting/`**: `report_generator.py` depends only on `src.insights.models`, `src.verification.models`, and `src.models` — never on `src.insights.extractor`, `src.insights.aggregator`, or `src.verification.verifier` (logic). It only ever reads already-computed output types.
- **`src/pipeline/`**: The only package allowed to import concrete stage logic across `fetchers`, `ai`, `insights`, `verification`, `reporting` all together — this is its entire reason to exist.
- **`src/api/`**: A documented, explicit **independence rule** (see `routes.py`'s own module docstring): never imports `src.ai.*`, `src.fetchers.*`, or `src.reporting.report_generator`/`formatter`. Every request goes through `Pipeline.run()` only. The sole exception is `src.reporting.models` — pure dataclasses, imported only as type shapes for JSON conversion, never for their (nonexistent, since they're plain shapes) logic.
- **`dashboard/`**: Talks to the backend exclusively through `dashboard/src/lib/api/client.ts` — the only file anywhere in `dashboard/` that calls `fetch()` against the API. It never re-implements fetching, analysis, clustering, verification, or report generation.

---

## 5. Dependency Rules (who can import whom)

```
src.models  ←  everything (the one shared vocabulary)
src.config  ←  fetchers, ai, pipeline, api, check_connections
src.fetchers.base/exceptions  ←  fetchers/__init__ (factory), pipeline
src.ai.base  ←  ai/__init__ (factory), pipeline, insights
src.insights.models  ←  insights.extractor, insights.aggregator, verification, reporting, api (via reporting.models only)
src.insights.{extractor,aggregator,prompts}  ←  pipeline ONLY
src.verification.models  ←  verification.verifier, reporting
src.verification.verifier  ←  pipeline ONLY
src.reporting.models  ←  reporting.report_generator, reporting.formatter, api.routes (types only)
src.reporting.{report_generator,formatter}  ←  pipeline ONLY (never api)
src.pipeline.pipeline  ←  pipeline.runner, api.routes (ONLY these two)
src.pipeline.cache  ←  pipeline.pipeline
dashboard/*  ←  HTTP calls to src.api only, never a Python import (separate language/runtime)
```

**Never allowed** (would violate an explicit, documented rule if introduced):
- `src.api.*` importing `src.ai.*`, `src.fetchers.*`, or `src.reporting.report_generator`/`formatter`.
- `src.verification.*` importing `src.insights.extractor`.
- `src.reporting.*` importing `src.insights.extractor`, `src.insights.aggregator`, or `src.verification.verifier`.
- Any package other than `src.fetchers`/`src.ai`'s own `__init__.py` constructing a concrete `RedditFetcher`/`GitHubFetcher`/`MockFetcher`/`GeminiProvider`/`MockAIProvider` directly.
- `dashboard/` importing or vendoring any Python code.

---

## 6. Fetcher Architecture

**Interface** (`src/fetchers/base.py`): `Fetcher.fetch(query: FetchQuery) -> List[FetchedPost]`, raising only `FetcherError` (never a source-specific exception like a `prawcore` or `requests` exception). `FetchQuery.community` is the one "which board to fetch from" field — a subreddit name for Reddit, an `"owner/repo"` string for GitHub.

**Implementations**:
- `RedditFetcher` (`reddit_fetcher.py`) — real, read-only, via PRAW. Fetches posts + their top-level comments as separate `FetchedPost` items (`item_type="post"`/`"comment"`).
- `MockFetcher` (`mock_fetcher.py`) — a fixed, 7-item, clearly-labeled (`is_mock=True`) sample dataset. Zero network calls, zero credentials required.
- `GitHubFetcher` (`github_fetcher.py`) — real, via the GitHub REST API (`requests`). Fetches open issues; folds each issue's comments into that single issue's `FetchedPost.text` (one `FetchedPost` per issue, not per comment — a deliberate simplification, see §21). Auth is optional (`GITHUB_TOKEN` only raises the rate limit, it doesn't gate availability).

**Error handling**: `src/fetchers/exceptions.py` defines `FetcherAuthError`, `FetcherRateLimitError`, `FetcherNotFoundError` as **subclasses of `FetcherError`**, not a parallel hierarchy — `except FetcherError` still catches every fetcher's failures uniformly; the subclasses exist only so a caller that wants to be specific (e.g. "tell the user to add a token") can be, without every other caller needing to change.

**Factory** (`src/fetchers/__init__.py`): `get_fetcher(config, *, source: str = "reddit", force_mock: bool = False)`. `force_mock` always wins. `source="github"` always returns a real `GitHubFetcher` (GitHub has no "configured" boolean the way Reddit does). Otherwise, Reddit is used if `config.reddit_configured`, else `MockFetcher`. **Never** construct a concrete fetcher outside this factory.

**Keyword filtering convention**: every real fetcher applies `query.keyword` **after** fetching (case-insensitive substring match against title or body/text), never by changing the underlying API query — `MockFetcher` and `GitHubFetcher` both follow this identically.

---

## 7. AI Architecture

**Interface** (`src/ai/base.py`): `AIProvider.generate_text(prompt: str) -> str` and `check_connection() -> None`, raising only `AIProviderError`. This is the **only** method any pipeline stage may call — no stage imports a provider SDK directly.

**Implementations**:
- `GeminiProvider` (`gemini_provider.py`) — real, via `google-genai`. Retries transient failures (5xx, 429) up to 3 times with exponential backoff, verified against the real `google.genai.errors` hierarchy, not guessed. `check_connection()` lists models rather than generating text, to avoid spending quota on a health check.
- `MockAIProvider` (`mock_provider.py`) — returns **deterministic, schema-valid JSON** matching the exact schemas `Extractor`/`Aggregator` expect (`src/insights/prompts.py`'s documented schemas), detected by inspecting the prompt shape itself (presence of the `"""`-delimited discussion-text block distinguishes an extraction prompt from a clustering prompt). Every evidence quote it returns is a real, verbatim substring pulled from the prompt's own embedded source text — never invented — so mock output passes the same quote-verification guardrail a real model's honest output would. Speculative fields (`user_persona`, `startup_opportunity`) are prefixed with `MOCK_RESPONSE_PREFIX`.

**Decorators** (both implement `AIProvider`, wrapping another `AIProvider` transparently — neither `Extractor` nor `Aggregator` knows either exists):
- `_CountingAIProvider` (`pipeline.py`) — counts real calls.
- `CachingAIProvider` (`pipeline/cache.py`) — caches by exact prompt hash, **only** when the response parses as valid JSON (so a malformed response is never cached, keeping `Extractor`'s own malformed-JSON retry meaningful). Wiring order matters: `CachingAIProvider` wraps `_CountingAIProvider`, never the reverse, so a cache hit never inflates `ai_calls_made`.

**Factory** (`src/ai/__init__.py`): `get_ai_provider(config, *, force_mock: bool = False)`. Real Gemini only when `config.gemini_configured`; `MockAIProvider` otherwise or when forced. **Never** construct a concrete provider outside this factory.

**Prompts** (`src/insights/prompts.py`): kept separate from parsing/validation (`extractor.py`, `aggregator.py`) so prompt wording can be iterated on independently. Every prompt's schema instructions explicitly require verbatim quotes and explicitly label speculative fields as speculative — this is enforced in the prompt text itself, not just in post-hoc parsing.

---

## 8. Verification Architecture

`src/verification/verifier.py`'s `Verifier` **independently re-checks every claim** in a `DiscussionInsight` against its original `FetchedPost`, with **zero AI calls** — pure, deterministic string matching, testable at zero cost. It never imports `extractor.py`; checking an AI's claim against immutable source text is real defense-in-depth, checking it with a second AI call is not.

Two verification ceilings, by claim type (`VerificationStatus`: `VERIFIED` / `PARTIAL` / `UNVERIFIED`):
- **Quote-bearing claims** (primary/secondary pain points, supporting evidence, buying signals) — already required by the Extractor to be verbatim substrings. Can reach `VERIFIED` (exact substring match) or fall to `UNVERIFIED`.
- **Speculative claims with no attached quote** (`user_persona`, `feature_requests`) — can reach at most `PARTIAL` (keyword-overlap heuristic, ratio ≥ 0.3, no stemming), **never `VERIFIED`** — there's no verbatim quote to confirm, so claiming `VERIFIED` here would itself be overclaiming.

`InsightVerificationResult.overall_status` is a **pessimistic, worst-case rollup**: one `UNVERIFIED` field makes the whole insight `UNVERIFIED`, regardless of how many other fields verified cleanly. `verify_all()` never silently drops an insight whose source post is missing — every field is explicitly reported `UNVERIFIED` with that reason instead.

`VerificationError` is raised (not silently handled) if an insight is ever checked against the wrong source post (`source_post_id` mismatch) — verifying against the wrong text could make a hallucinated claim look confirmed by coincidence, which is worse than not verifying at all.

---

## 9. Reporting Architecture

Two files, cleanly split by responsibility:
- `report_generator.py` — **zero AI calls, zero string rendering.** Builds an `InsightReport` from already-computed `OpportunityCluster`/`VerificationReport`/`FetchedPost` data. Every number is either a direct pass-through or a deterministic aggregation — nothing is generated, guessed, or templated from AI.
- `formatter.py` — **pure string formatting**, two outputs (`format_terminal`, `format_markdown`) plus `save_markdown_file`. No computation.

Two hard constraints, enforced structurally (not by convention):
1. **`recommended_next_action` is a fixed 5-branch decision table** (`_recommend_next_action`) that can only ever suggest a *research* action (read more, verify manually, wait for recurrence, follow up directly) — **it never says "build" or "invest."** This is a direct, load-bearing implementation of PRD.md §7/§10's "MarketRadar never makes the decision for the user."
2. **`supporting_quotes` are pulled only from `FieldVerification` entries the Verifier marked `VERIFIED`** — never straight from `DiscussionInsight`'s raw fields, and never from `PARTIAL`-status loosely-matched sentences. This is what makes the Verifier (§8) load-bearing rather than a disconnected pipeline stage that computes a number nobody downstream actually uses.

Every speculative field (`opportunity_score`, `suggested_customer_segment`) is rendered with an explicit `SPECULATIVE — AI-inferred, not a verified finding` label in both terminal and Markdown output — never printed bare.

---

## 10. Backend API Architecture

`src/api/` (FastAPI): `app.py` (app metadata, CORS, top-level exception handler), `routes.py` (every endpoint), `models.py` (Pydantic request/response schemas). See §4 for the independence rule — every request goes through `Pipeline.run()` only.

**Endpoints:**

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Config presence only; never contacts Gemini/Reddit. |
| GET | `/version` | Static metadata. |
| POST | `/analyze` | Real pipeline, "auto" semantics (real if configured, mock fallback otherwise). Returns 200 even on `summary.succeeded=false` — a completed-but-failed run is valid data, not a transport error. |
| POST | `/analyze/mock` | Forces full offline mock mode regardless of `.env`. |
| GET | `/reports` | Lists past runs (CLI + API together — one shared `output/` history). |
| GET | `/reports/{report_id}` | Execution summary + raw saved Markdown, if any. **Cannot** return a structured, per-opportunity report for a past run — see §21. |
| GET | `/download/{report_id}` | Raw Markdown file download. |

`report_id` correlation (`_find_report_id_for`) matches a just-completed run's `start_time` against saved summary file contents — **never** by reproducing `pipeline.py`'s filename timestamp format itself, so a future format change there can't silently break this.

CORS is enabled (`app.py`), scoped via `allow_origin_regex` to `localhost`/`127.0.0.1` at any port — deliberately not a wildcard, since this stays a personal, local-only tool (see §18).

`AnalyzeRequest` validation mirrors the CLI's own rules (blank subreddit rejected, blank keyword = no filter), plus one API-only addition with no CLI equivalent: `limit` capped at 100 — a network-facing endpoint needs a safety rail a human typing a command doesn't.

---

## 11. Dashboard Architecture

`dashboard/` — Next.js 16 (App Router, Turbopack), TypeScript, Tailwind v4, shadcn/ui (Base UI primitives under this generation's preset, not Radix), Recharts, next-themes. **Completely separate from `src/`** — no shared code, no shared build, connected only by the REST contract in §10.

- `src/lib/api/{types.ts, client.ts, errors.ts}` — `client.ts` is the **only** module in the entire app that calls `fetch()` against the backend. `types.ts` hand-mirrors `src/api/models.py`'s Pydantic schemas field-for-field (no shared schema generation between the two languages — see §21). `errors.ts` normalizes network failures vs. real HTTP error responses into one `ApiError` shape.
- Four pages: Home (run analysis), Reports (search/sort past runs), Report Details (`/reports/[reportId]`), Settings (API base URL override + connection test).
- `lib/report-cache.ts` caches a just-completed run's real structured `InsightReport` in `sessionStorage`. `lib/parse-report-markdown.ts` reconstructs the same shape for every other case (a past report, a fresh tab) by **parsing the saved Markdown text** — a real, documented, load-bearing coupling to `formatter.py`'s exact output format (see §21).
- Dark mode via `next-themes`; responsiveness verified at 320/375/414px viewports.

No permanent frontend automated test suite exists (a one-off Playwright script was used for live verification during Task 11 and then deleted — see SESSION.md). `npx tsc --noEmit` and `npx eslint .` are the standing static checks.

---

## 12. Configuration Rules

- **`src/config.py`'s `load_config()` is the only place any code reads `os.environ`.** No other module should call `os.environ.get`/`os.getenv` directly — this is what keeps exactly one place able to leak a secret if someone got careless with a print statement.
- `Config` is a frozen dataclass. Every field is `Optional` and defaults to "unconfigured" rather than raising — **loading** configuration and **requiring** a particular value are different concerns; each consumer checks the relevant `*_configured` property (`reddit_configured`, `gemini_configured`) itself and fails loudly, specifically, only when it actually needs that value.
- `_env_str()` treats a missing **or whitespace-only** env var as unset (a real bug found and fixed in Task 7 — a stray `GEMINI_API_KEY="   "` was previously treated as configured).
- `.env` is loaded from a fixed, explicit project-root path (`_PROJECT_ROOT / ".env"`), never via python-dotenv's implicit upward search from the current working directory — that implicit search was found to silently fail depending on invocation directory (Task 7).
- **New config fields must default to a value that keeps every existing `Config(...)` call site working unchanged** (test fixtures especially, which should not need editing just because a new source was added) — see `github_token: Optional[str] = None`, the precedent for this.
- `.env.example` documents every variable the project uses, with a comment block per source, even optional ones — copy it to `.env` and fill in real values; `.env` itself is gitignored (see §18).

---

## 13. Error Handling Standards

- **One exception type per package boundary**, that all internal/source-specific exceptions collapse into: `FetcherError` (fetchers), `AIProviderError` (ai). Calling code outside that package should catch only that one type, never a source-specific exception (a `prawcore` exception, a `requests` exception, a `google.genai` exception) — this is what keeps calling code source-agnostic. Subclassing the package's own exception (e.g. `FetcherAuthError(FetcherError)`) is allowed and used (§6) — it does not violate this rule, since `except FetcherError` still catches everything.
- **Exactly one deliberate broad `except Exception`** exists in the whole codebase: the top of `Pipeline.run()`. Documented explicitly as the sole exception to the specific-exception-types rule — `run()` must never raise; every failure is recorded in `errors` and returned as a structured, honest result instead.
- **Fail loudly at real boundaries** (a missing/invalid credential, a malformed AI response after retry, an insight verified against the wrong post) by raising a specific, typed exception with a clear message.
- **Never let a single bad item silently kill a batch.** A per-post extraction failure is logged and skipped (`Pipeline._analyze`), not fatal to the whole run; an unverifiable secondary pain point or buying signal is dropped, not fatal to the whole insight; an insight with a missing source post is marked fully `UNVERIFIED`, not dropped from the report.
- **Never expose a raw third-party exception message where it might echo request details** — provider/library exceptions are converted to this project's own exception with the *type name*, not the raw message, except where a message has been deliberately, narrowly redacted first (`gemini_provider.py`'s `_redact_secret`, explicitly marked as temporary diagnostic instrumentation).

---

## 14. Testing Standards

- **pytest**, chosen in Task 4 for plain-assert syntax and no heavy transitive dependencies.
- **Every test is zero-cost and zero-network.** No test ever calls a real Reddit, Gemini, or GitHub API — stub/fake `AIProvider`/`Fetcher` implementations (`_FixedResponseProvider`, `_SequenceResponseProvider`, `_ErrorProvider`) or `unittest.mock.patch` on `requests.get` stand in.
- Test files mirror `src/`'s package structure for anything with its own subpackage worth isolating (`tests/ai/test_mock_provider.py`, `tests/fetchers/test_github_fetcher.py`); older, simpler modules use a flat `tests/test_<module>.py`. No `__init__.py` files anywhere under `tests/` — plain rootdir-relative discovery.
- **Test isolation is a recurring, explicitly-tracked risk, not an assumption**: every test that touches the filesystem must use `tmp_path`, never the project's real `output/` or `.cache/` directories or a bare relative path like `Path("unused")` — this exact bug class has been found and fixed multiple times (Task 8's stray `unused/` file, Task 10's leaked `output/` writes, GitHubFetcher's `.cache/ai_responses.json` pollution once `MockAIProvider` started returning valid JSON). **Any config default that resolves to a real, non-tmp_path location (`.cache/ai_responses.json`, `output/`) must be overridden explicitly in a test that cares about exact counts.**
- Every `AI Provider`/`config` used in a test **explicitly forces mock mode** (`ai_provider="mock"`, `force_mock=True`) rather than `"auto"` — the real `.env` in this project has real credentials, and `"auto"` in a test would risk a real, billed API call.
- Current suite size: 163 tests (`python -m pytest tests/ -q`), zero real API cost, all passing.

---

## 15. Documentation Standards

- **README.md, PRD.md, CLAUDE.md are canonical product intent.** ROADMAP.md is the phased plan (no architecture/tech-stack/dates). SESSION.md is the append-only, newest-first, "no session left unlogged" development journal — a session that isn't logged there didn't happen, as far as future sessions are concerned. TODO.md is the living, prioritized punch list, including an explicit "Explicitly not doing yet (avoid scope creep)" section that must be updated whenever an exception to it is deliberately made (see the GitHubFetcher precedent in TODO.md §3.1).
- **A decision that changes scope, principles, or direction must update the relevant document in the same session it was made** — not as a follow-up, not silently.
- **Do not create additional planning/strategy documents** unless explicitly requested — scattered documentation is a bigger long-term cost than a slightly longer existing file (this is exactly why an "Architecture Review" is folded into the relevant SESSION.md entry per task, per §20, rather than spawned as its own file each time).
- Every module's own docstring is expected to carry real architectural reasoning (why this boundary exists, what bug prompted a design choice), not just a one-line description — this guide's own §6–§11 above lean heavily on exactly those docstrings, which is a signal they're doing their job.

---

## 16. Coding Standards

- **No dead code, no speculative abstractions, no unused feature flags.** If it isn't used, it doesn't belong.
- **Comments explain WHY, never WHAT.** A comment referencing a specific past bug, a non-obvious invariant, or a constraint is welcome; a comment restating what well-named code already shows is not.
- **Frozen dataclasses for every shared data shape** (`FetchedPost`, `FetchQuery`, `DiscussionInsight`, `PainPoint`, `OpportunityCluster`, every `verification`/`reporting` model) — immutable, structurally simple, no behavior beyond the occasional derived `@property`.
- **Factory functions, not constructors, for anything swappable.** `get_fetcher()`/`get_ai_provider()` are the only sanctioned way to obtain a concrete `Fetcher`/`AIProvider` — this is what lets a new source or provider be added as one new class + one factory branch, with zero changes to any consumer.
- **Decorators for cross-cutting concerns**, implementing the same interface as what they wrap, never modifying the wrapped class (`_CountingAIProvider`, `CachingAIProvider`).
- **Explicit over clever.** Every module here favors readable, slightly verbose code (named helper functions, explicit `if`/`return` chains over dense comprehensions in business logic) given the project's long operating horizon and the number of separate sessions/tasks that touch the same files.
- **Validate/handle errors at system boundaries only** (external API responses, user input, `.env`) — not defensively at every internal call site.

---

## 17. Performance Guidelines

- **AI responses are cached by default** (`CachingAIProvider`, keyed by exact prompt hash, JSON-validity gated) — re-running the pipeline over overlapping data reuses prior analysis instead of spending real quota again. `--no-cache` / `use_cache=False` forces fresh calls.
- **No caching exists for fetcher HTTP calls** (Reddit or GitHub) — every run re-fetches from the real source. Named gap, not yet needed at current scale (TODO.md).
- **No async/parallel fetching anywhere** — `RedditFetcher` and `GitHubFetcher` both make sequential, synchronous HTTP calls; an `N`-issue GitHub fetch costs `N+1` sequential round trips.
- **No rate-limit budget tracking** for GitHub (60 req/hour unauthenticated) or awareness of Gemini's free-tier daily quota beyond "the call fails and gets retried/reported" — both are named, accepted risks at personal-tool scale, not silently ignored.
- **The REST API has no background-job queue** — `/analyze` blocks synchronously for the full pipeline duration, acceptable for a single trusted local user, explicitly named as blocking real multi-user production use (SESSION.md Task 10 review).
- **`ResponseCache` has no file locking** — safe for one process at a time; a named, unfixed concurrency race exists if the API ever receives truly simultaneous requests (SESSION.md Task 10 review, TODO.md).

---

## 18. Security Guidelines (API keys, .env, secrets)

- **`.env` is gitignored and must never be committed.** `.env.example` documents every variable name with no real values. `src/config.py` is the only file that reads secret env vars (see §12).
- **Never print, log, or echo a credential value.** `check_connections.py` only ever prints an exception's *type name*, never its message/args. `gemini_provider.py` redacts the API key from any error string before logging it.
- **CORS is scoped to `localhost`/`127.0.0.1` only** (`allow_origin_regex`), deliberately not a wildcard — this project is a personal, local-only tool, not a public deployment. If it is ever exposed beyond that, this must be revisited alongside real authentication (see below).
- **The REST API has no authentication and no rate limiting** — explicitly named as blocking for any use beyond a single trusted local user (SESSION.md Task 10 review, TODO.md). Do not expose `uvicorn src.api.app:app` beyond localhost without addressing this first.
- **Incident precedent**: a real GitHub PAT was once accidentally pasted into `ROADMAP.md`, overwriting its content, during a live session (2026-07-31). It never reached git history (confirmed via `git log --all -p` search) because it was caught, the token was revoked and rotated, and the file was restored from git history before any commit. **If a secret-shaped string is ever found in a tracked file's working tree**: (1) treat it as compromised regardless of whether it was committed, (2) tell the user to revoke/rotate it immediately, (3) verify via full history search (not just current diff) that it never reached a commit, (4) restore the affected file from git history only after explicit confirmation, since a file you didn't modify may represent in-progress work.
- **Any new source integration that requires a credential** should follow the existing pattern exactly: optional, defaulted `Config` field; read only through `load_config()`; documented in `.env.example` with a comment explaining what it unlocks and where to generate it; never required for the project's mock-mode baseline to work.

---

## 19. Code Review Checklist

In order (CLAUDE.md §9) — do not skip ahead to standard quality concerns before these:

1. **Evidentiary integrity**: does anything touching data ingestion, source handling, or claim generation lose the link back to a real source? Is inference ever presented as fact anywhere in the change (missing a `SPECULATIVE` label, a quote not re-verified, a persona synthesized across sources)?
2. **Scope discipline**: does this change stay within the current MVP/PRD-defined scope and TODO.md's "Explicitly not doing yet" list, or does it quietly expand either without being surfaced first?
3. **Unnecessary complexity**: would a simpler version of this change satisfy the same requirement? Is a new abstraction (interface, factory branch, decorator) actually needed, or is this the third instance justifying it?
4. **Silent failure modes**: does this code fail loudly and specifically when a source/response is unavailable, malformed, or ambiguous — or does it guess, default silently, or fabricate a plausible-looking substitute?
5. **Module boundaries and dependency rules** (§4–§5): does the change import something it shouldn't (e.g. `api` reaching into `ai`/`fetchers` directly, `reporting` reaching into `extractor`/`verifier` logic)?
6. **Only then**: standard correctness, security (secrets, injection, unsafe defaults), readability, and test coverage.

---

## 20. Architecture Review Template

This is the format every non-trivial task's review has followed in SESSION.md (e.g. GitHubFetcher, Task 10's API, Task 11's dashboard) — reuse it rather than inventing a new structure per task, and fold it into that task's own SESSION.md entry rather than a new standalone file (§15).

1. **Does this violate any existing module boundary?** (§4–§5)
2. **Does it violate single responsibility anywhere non-obvious?** (e.g. a fetcher fetching comments inline — is that consistent with existing precedent, or new?)
3. **What hidden assumptions does it make about an external response shape** (a third-party API, a file format, another module's exact output)? Are they defended (`.get()` with fallbacks) or will they raise/crash on drift?
4. **What breaks if the upstream format changes** — loud failure, silent degradation, or a crash? Which of those is actually true, verified, not assumed?
5. **Does the shared data model (`FetchedPost`, `DiscussionInsight`, etc.) fit this addition well, or does it lose real information?** Name what's lost, explicitly.
6. **What happens at scale** (more sources, more concurrent users, more volume than today)? Be concrete about what specifically breaks first.
7. **Is this production-ready? State clearly: YES / PARTIAL / NO, and exactly why.**
8. **List every known limitation** as a one-line, named item — not folded into prose, so it can become a TODO.md entry directly.

---

## 21. Definition of Done for Every Future Task

A task is not done until **all** of the following are true (CLAUDE.md §14, restated with this codebase's specifics):

1. It stays within PRD.md's current MVP scope and TODO.md's documented exclusions — or an explicit, surfaced, user-approved exception has been recorded in TODO.md (see §3.1's pattern) before/while the work happened, not after.
2. Every user-facing conclusion it produces is traceable to real evidence, with inference clearly separated from fact (a `SPECULATIVE` label, a `ConfidenceLevel`, a `VerificationStatus`) wherever the existing architecture provides one.
3. It respects every module boundary and dependency rule in §4–§5, or the guide is updated in the same task if the boundary itself is being deliberately changed.
4. New code follows the existing pattern for its category: a new source → `Fetcher` + factory branch (§6); a new AI backend → `AIProvider` + factory branch (§7); a new cross-cutting concern → a decorator (§7); a new config value → an optional, defaulted `Config` field read only via `load_config()` (§12).
5. It fails loudly and specifically on bad/missing/ambiguous input at the boundary, and never silently drops an entire item when a partial, honest failure would do (§13).
6. Tests exist, are zero-cost/zero-network, follow the isolation discipline in §14, and the **full existing suite still passes** — report the exact before/after count.
7. An architecture review (§20) has been done for anything non-trivial, and its findings are recorded in SESSION.md (new entry, newest-first) — not a new standalone document.
8. TODO.md is updated: completed items checked off, new named limitations added as their own line items (not buried in a completed item's description only).
9. README.md/PRD.md/CLAUDE.md/this file are updated if the task changed product scope, principles, architecture, or how future sessions should operate — in the same task, not deferred.
10. Any discovered inconsistency between intended and actual architecture is **documented**, here or in TODO.md, not silently fixed as a drive-by unless the task was specifically about fixing it.

### Known, currently-open inconsistencies (documented per requirement, not fixed here)

- `GitHubFetcher` exists and is fully tested but is **not wired into `runner.py` or `routes.py`** — reachable only via `get_fetcher(config, source="github")` directly. No CLI flag or API field selects it yet.
- `ProjectHealthSummary.total_verified_insights` reads as 0 in nearly every real report by current, strict definition (all-fields-`VERIFIED` required) — accurate but likely to look broken to a user. Named, not redefined (SESSION.md Task 5 entry).
- `report_id` can collide when two pipeline runs complete within the same wall-clock second (`pipeline.py`'s `%Y%m%d_%H%M%S` filename scheme) — the second run's files silently overwrite the first's. Root cause is in `pipeline.py`, out of scope for the API task that found it.
- `ResponseCache.set()` has no file locking — a real, unaddressed concurrency race once more than one process/request can write to `.cache/ai_responses.json` simultaneously.
- `cache_path` (like `output_dir`) resolves relative to the current working directory, not anchored to the project root the way `.env` loading was fixed to be — a pipeline invoked from a different working directory uses a different cache file.
- The verification keyword-overlap heuristic (`_find_supporting_sentences`) has no stemming — a demonstrated miss ("processor" vs. "processors") by a small margin on its threshold. Named, not patched without further evidence it recurs.
- `dashboard/src/lib/api/types.ts` is hand-kept in sync with `src/api/models.py` with no shared schema generation — a backend field rename would only surface as a silent frontend bug, not a build failure.
- `dashboard/src/lib/parse-report-markdown.ts` reconstructs past-report data by parsing `formatter.py`'s exact Markdown output — a real, working, but load-bearing coupling to a text format owned by a different codebase, with no contract test catching drift.
- `Extractor` sometimes produces degenerate one-word "feature requests" (e.g. "automatically") — noticed during Task 4, not chased down.
- `--keyword` (CLI) accepts a blank string with no validation, inconsistent with `--subreddit`'s strictness — not fixed since nothing downstream actually breaks (blank is already treated as "no filter").
