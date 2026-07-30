# MarketRadar — Session Journal

This is the project's running development journal. It is not a status dashboard and not a changelog — it is a record of what actually happened in each working session, including the reasoning, the mistakes, and the open threads, so that the next session (human or Claude) can pick up with full context instead of re-deriving it.

**Update this file at the end of every development session.** A session that isn't logged here didn't happen, as far as future sessions are concerned. See [CLAUDE.md](./CLAUDE.md) §13 for documentation standards this file should follow.

Do not delete old entries. This file is additive — append new sessions above or below consistently (this project logs newest-first) rather than overwriting history. If the file grows unwieldy, that's a future problem to solve deliberately (e.g., archiving old entries to a dated file), not a reason to delete the record silently.

---

## How to Fill Out a Session Entry

Copy the template below for each new session. Leave a section explicitly empty (e.g., "None this session.") rather than deleting it — a consistently structured empty section is more useful than a missing one.

```
## Session — YYYY-MM-DD

### Current Objective
What this session set out to do, in one or two sentences.

### Completed Work
What was actually finished this session — concrete, verifiable outcomes.

### In Progress
What was started but not finished, and its actual current state.

### Known Issues
Anything broken, wrong, or unresolved that the next session needs to know about.

### Next Tasks
The specific, concrete next steps — written so the next session can start immediately without re-deriving priorities.

### Important Decisions
Any real decision made this session, with the reasoning behind it — especially anything that future sessions must not silently re-litigate or contradict without reason.

### Questions
Anything left genuinely open or unresolved — for the user, or for a future session to investigate.

### Lessons Learned
What this session revealed that changes how future work should be approached — process, not just product.

### Future Improvements
Ideas worth considering later, explicitly not committed to now.
```

---

## Session Log

## Session — 2026-07-30

### Current Objective
Move from planning into implementation: define a one-week, single-user MVP scope, design its technical architecture, get the repo properly hosted on GitHub, and start building Task 1 (project setup & external connections).

### Completed Work
- Designed a one-week personal MVP scope (single source, on-demand trigger, quote-verified extraction, in-run recurrence grouping, three-tier confidence label, saved Markdown report) — deliberately narrower than ROADMAP.md's full Phase 1, cut for a one-week solo build.
- Designed the MVP's technical architecture: Python, PRAW (Reddit, read-only official API), Claude API (extraction/grouping), plain string-match quote verification (deterministic, no AI), flat-file storage (JSON + Markdown), single CLI entrypoint, no database/server/hosting.
- Fixed the git repo root problem (previously the repo root was the user's home directory, flagged repeatedly since the initial documentation session): initialized a new repo scoped to `MarketRadar/` itself, renamed default branch to `main`, committed all 8 planning documents as the root commit.
- Pushed the repo to GitHub at `github.com/rr7572854820-gif/MarketRader`.
- Built Task 1 (Project Setup & External Connections): `.gitignore`, `requirements.txt` (praw, anthropic, python-dotenv only), `.env.example`, `src/config.py` (env var loader/validator), `src/check_connections.py` (verifies Reddit + Claude auth, never logs secret values).
- Adapted Task 1 after the user said they don't have and don't want to create a Reddit API key: made Reddit fully optional. `Config.reddit_configured` is now a computed property (true only if both `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are set); `check_connections.py` skips the Reddit check (not a failure) when they're absent, and only Claude is required to pass.
- Found and read a `TODO.md` in the project root that neither of us had written in this conversation — apparently produced by a separate session or the user directly. It correctly flagged that ROADMAP.md's Phase 0 ("no software") and PRD.md §13 (source selection deliberately deferred to Milestone 0.1) hadn't formally happened before Task 1's Reddit-specific code was written. Resolved this explicitly rather than silently proceeding or silently blocking: treated the user's personal-MVP reframing (this same day) as a deliberate, recorded exception to Phase 0's ceremony for a personal tool — see Important Decisions.
- Built Task 2 (Data Fetcher): `src/models.py` (`FetchedPost`/`FetchQuery` — the one shape every source, current or future, must return), `src/fetchers/base.py` (`Fetcher` ABC + `FetcherError`), `src/fetchers/reddit_fetcher.py` (real read-only PRAW fetch of posts + top-level comments), `src/fetchers/mock_fetcher.py` (7 realistic, clearly-labeled sample posts/comments about business pain points — Stripe/QuickBooks reconciliation, no-code conditional logic, meeting-scheduler timezones, etc.), `src/fetchers/__init__.py` (`get_fetcher(config)` factory choosing real vs. mock with no caller-side branching), `src/fetch_preview.py` (CLI to print fetched posts).
- Actually ran the code rather than just writing it: created a local `.venv`, installed `requirements.txt`, and exercised `fetch_preview.py` and `check_connections.py` against the real `.env` (which has no Reddit or Anthropic credentials set). This surfaced two real bugs, both fixed before considering Task 2 done:
  1. `load_config()` hard-required `ANTHROPIC_API_KEY`, which meant the Fetcher — which has nothing to do with Claude — couldn't even be tested without a Claude key. Fixed by making Claude optional at load time too (mirroring Reddit): added `Config.anthropic_configured`, and moved the "Claude is actually required" enforcement into `check_connections.py` itself, which now fails loudly and specifically only when *it* needs Claude.
  2. Em-dash and ellipsis characters in `print()` output (not in docstrings/comments, which don't matter) rendered as `�` on the Windows console due to an encoding mismatch. Replaced with plain ASCII (`-`, `...`) in every actual print statement across `check_connections.py` and `fetch_preview.py`.
- Verified mock-mode fetch end-to-end: default fetch returns all 7 sample items, `--keyword refund` correctly narrows to 2, `--limit` truncates correctly, and `check_connections.py` now reports `[SKIP]` for Reddit and a clear `[FAIL]` for Claude (matching the real, unfilled `.env` state) instead of crashing.
- Updated `TODO.md` to mark Tasks 1–2 complete, record the sequencing-gap resolution, and lay out Tasks 3–9 (Extractor through dogfood pass) as the concrete remaining path.
- **Replaced Anthropic/Claude with Google Gemini as the AI provider**, at the user's request (no budget for Claude's paid API; Gemini has a usable free tier). Built a proper provider abstraction rather than a direct swap: `src/ai/base.py` (`AIProvider` ABC + `AIProviderError`), `src/ai/gemini_provider.py` (real, via the `google-genai` SDK), `src/ai/mock_provider.py` (offline testing — always "succeeds," returns a fixed, clearly-prefixed fake response), `src/ai/__init__.py` (`get_ai_provider(config)` factory, mirroring `get_fetcher`'s pattern exactly). `check_connections.py` now verifies the AI provider through this abstraction (`get_ai_provider(config).check_connection()`) and never imports `google.genai` directly, satisfying "the rest of the app must never directly call Gemini" literally, not just in spirit.
- Removed Anthropic entirely from `config.py` (`anthropic_api_key`/`claude_model`/`anthropic_configured`/`DEFAULT_CLAUDE_MODEL` all gone), replaced with `gemini_api_key`/`gemini_model`/`gemini_configured`/`DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"`. Updated `requirements.txt` (removed `anthropic`, added `google-genai`), `.env.example`, and the real `.env` (rewrote the Anthropic section to Gemini in place via `sed`, without ever reading the actual secret values into context — confirmed the old `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` were empty first, so nothing was lost).
- Verified the refactor's isolation actually holds, not just in theory: re-ran `fetch_preview.py` after the entire AI-provider swap with zero changes needed to it — proof that Task 2's Fetcher/pipeline separation from the AI layer works as designed.
- Verified `MockAIProvider` end-to-end (selected automatically with no `GEMINI_API_KEY` set, `check_connection()` raises nothing, `generate_text()` returns the clearly-labeled fake response) and reinstalled the venv (`pip uninstall anthropic`, `pip install -r requirements.txt` picking up `google-genai`). All files byte-compile cleanly.
- Added an empty `GEMINI_API_KEY=` line to the user's real `.env`, ready for them to paste a real key into (asked them to do it directly in the editor, not in chat).
- **Could not complete the one thing this task explicitly required before moving on:** a real, live Gemini connection test. `GEMINI_API_KEY` was still empty as of this session — blocked on the user adding it. Per their own explicit instruction ("do not begin Task 3 until the Gemini integration is fully working"), Task 3 is not started.

### In Progress
Waiting on the user to add a real `GEMINI_API_KEY` to `.env` so `check_connections.py` can be run against it for real. Everything else for the provider swap is built, wired, and verified in mock mode. Task 3 (Extractor) has not been started and must not start until that real test passes.

### Known Issues
- The user's home directory (`C:\Users\RISHABH RAJPUT`) still has its own separate, empty git repo (no commits). Left untouched — out of scope for this project.
- IDEAS.md's scope ambiguity (feature ideas about MarketRadar itself vs. market opportunities its research surfaces) — still not explicitly confirmed by the user, though still not urgent since IDEAS.md hasn't been used yet.
- `GEMINI_API_KEY` is present in `.env` but still empty as of this session — the real Gemini connection has not yet been tested, only `MockAIProvider`.
- The real Reddit path (`RedditFetcher`) has not been exercised against a live account — only its construction/import has been implicitly verified. It should get a real test the first time Reddit credentials are actually added.
- A local `.venv/` exists in the project (created for testing, already gitignored) — harmless, but worth knowing it's there.
- The default Gemini model (`gemini-2.5-flash`) hasn't been confirmed to exist under that exact name against a real API call yet — will be confirmed (or corrected) by the first real connection test.

### Next Tasks
- **Immediately:** once the user confirms a real `GEMINI_API_KEY` is in `.env`, run `python -m src.check_connections` and confirm Gemini shows `[OK]`. If the default model name is wrong, fix `DEFAULT_GEMINI_MODEL` in `src/config.py` (or have the user set `GEMINI_MODEL` directly).
- Only after that real test passes: build Task 3 (Extractor) — feed `FetchedPost` text to the AI provider via `get_ai_provider(config).generate_text(...)`, never a direct Gemini import, get back candidate pain-point quotes + one-line problem statements referencing their source `FetchedPost.id`.
- Build Task 4 (Verifier) — arguably before or alongside Task 3, since it's pure/deterministic and easiest to test in isolation with hand-written fixtures.
- Whenever the user wants to test real Reddit data, add `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` to `.env` — no code change needed.

### Important Decisions
- Chose to make Reddit optional via a config-level mock-mode flag rather than removing the Reddit dependency entirely — keeps the real path fully wired (just add credentials later) instead of requiring rework when the user is ready for real data.
- Resolved the sequencing-gap flag raised by the discovered `TODO.md` by treating it as answered, not overridden: the user's explicit personal-MVP reframing (this same day, this same conversation) already constitutes a conscious decision to bypass ROADMAP Phase 0's formal ceremony for personal use. Recorded this explicitly here and in TODO.md rather than either silently complying with the new request or silently blocking on the old flag.
- Extended the "optional config, consumer-checked" pattern from Reddit to the AI provider as well, once testing showed the alternative (hard-requiring a paid key to even test the Fetcher) was an unnecessary coupling between unrelated concerns. `load_config()` now never fails; only specific consumers that need a specific credential check for it and fail loudly themselves.
- Designed the Fetcher as an abstract `Fetcher` interface + `FetcherError`, with `RedditFetcher`/`MockFetcher` as swappable implementations behind a single `get_fetcher(config)` factory, and a single shared `FetchedPost` shape — so a future Hacker News/Product Hunt/GitHub source is one new class + one factory branch, never a change to code that consumes fetched data.
- Applied the exact same pattern to the AI provider (`AIProvider`/`AIProviderError`/`get_ai_provider`) when swapping Anthropic for Gemini, rather than doing a direct find-and-replace of Claude calls with Gemini calls — this is what makes "Anthropic, OpenAI, Grok pluggable later" actually true rather than aspirational, and it's why `fetch_preview.py` needed zero changes despite a full AI-backend swap.
- Deliberately did *not* build a concrete `AnthropicProvider`/`OpenAIProvider`/`GrokProvider` now, even though the interface supports them — per CLAUDE.md's "no dead code, no speculative abstractions," the interface being extensible is enough; building unused providers would be scope creep with nothing to test them against.
- Chose ASCII-only characters in all runtime `print()` output after hitting real Windows console mojibake — docstrings/comments can keep em-dashes freely since those are read as source text, not printed.
- Refused to treat "the code is written" as "the task is done" given the user's explicit "do not begin Task 3 until the Gemini integration is fully working" — stopped short of Task 3 and reported the real blocker (no key yet) rather than assuming success.

### Questions
- Should the home-directory git repo be removed at some point, or left alone indefinitely? Still unresolved.
- Should IDEAS.md's scope be explicitly confirmed before it's ever actually used?

### Lessons Learned
- When a user pushes back on a setup requirement (here: not wanting a Reddit API key, then not being able to afford Claude), the better fix is usually to make the dependency optional/pluggable at the architecture level rather than a one-off patch — the Reddit mock-mode pattern turned out to generalize cleanly to swapping the entire AI provider later, because it was built as a real abstraction the first time, not a special case.
- Keeping secret-handling logic in exactly one module (`config.py`) paid off a third time — removing Anthropic and adding Gemini was a contained, mechanical change, not a hunt across the codebase.
- **Actually running the code caught two real bugs that reading it carefully did not** (from Task 2) — the Claude/Fetcher coupling and the Windows console encoding issue were both invisible on inspection and obvious the moment the commands were executed. Don't skip the "run it" step even for code that looks correct.
- When a task has an explicit hard gate ("do not begin Task 3 until X works"), build everything up to that gate, verify what can be verified without the missing piece (mock mode here), and then actually stop and ask — rather than assuming the missing external dependency will show up and reporting premature success.
- Finding an unexpected file (`TODO.md`) mid-task is worth reading fully and reconciling explicitly, not working around silently — it surfaced a real, valid process concern that deserved an on-the-record answer either way.

### Future Improvements
- Once Task 3/4 exist, consider whether the mock dataset needs to grow beyond 7 items to meaningfully exercise recurrence grouping (Task 5) — 7 items across a handful of distinct topics may be too thin to test clustering logic well.

## Session — 2026-07-29

### Current Objective
Stand up MarketRadar's foundational documentation from a blank project: the source-of-truth product documents (README, PRD, CLAUDE.md), then the supporting planning documents (ROADMAP, SESSION, IDEAS) and research templates — without writing any code, architecture, or implementation detail.

### Completed Work
- Diagnosed and fixed a structural problem: several project files (`README.md`, `PRD.md`, `CLAUDE.md`, and later `IDEAS.md`, `ROADMAP.md`, `SESSION.md`) had been accidentally created as empty directories rather than actual Markdown files, likely from an earlier `mkdir` mistake. Verified each was genuinely empty before removing the directory and replacing it with a real file, so no prior work was lost.
- Wrote [README.md](./README.md): what MarketRadar is, who it's for, why it exists, long-term vision, project philosophy, and future direction.
- Wrote [PRD.md](./PRD.md): full product requirements — executive summary, problem statement, target users, personas, jobs-to-be-done, goals, non-goals, MVP definition, long-term vision, product principles, success metrics, risks, constraints, assumptions, open questions, and future expansion.
- Wrote [CLAUDE.md](./CLAUDE.md): permanent project memory for future Claude Code sessions — mission, development philosophy, product principles, always/never rules, architecture principles, coding standards, communication style, code review approach, planning approach, assumption-challenging approach, git workflow, documentation standards, and a project-wide Definition of Done.
- Fixed the structure a second time after `IDEAS.md`, `ROADMAP.md`, and `SESSION.md` were found to have the same empty-directory problem — removed and recreated as real, empty files, verified as files (not directories), and confirmed `README.md`/`PRD.md`/`CLAUDE.md` were left untouched throughout.
- Wrote [ROADMAP.md](./ROADMAP.md): seven phases (Research, MVP, Validation, Expansion, Automation, Intelligence, Scale), broken into small, independently valuable milestones, each with goal, rationale, expected outcome, dependencies, complexity, risks, and a Definition of Done — deliberately excluding architecture, technology choices, and calendar estimates.
- Wrote this file (SESSION.md) as the project's ongoing journal template and initial entry.
- Wrote [IDEAS.md](./IDEAS.md): a twelve-dimension scoring framework (Problem Severity, Market Size, Evidence Strength, Frequency, Growth Trend, Competition, Execution Difficulty, Technical Risk, Revenue Potential, Founder Fit, Long-Term Moat, Validation Status), four decision categories, an entry template, an empty active backlog and rejected-ideas log, and one clearly-labeled fictional example entry to demonstrate the format without being mistaken for real evidence.
- Resolved the `research/` naming mismatch: removed the two mistyped, empty placeholder directories (`hackersnews.md`, `productionhunt.md`) alongside the three correctly-named ones (`reddit.md`, `github.md`, `competitors.md`) — all confirmed empty immediately before removal — and created five real files with the corrected names (`reddit.md`, `hackernews.md`, `producthunt.md`, `github.md`, `competitors.md`).
- Wrote all five research templates (`research/reddit.md`, `research/hackernews.md`, `research/producthunt.md`, `research/github.md`, `research/competitors.md`), each covering purpose, data source, collection method, signals, pain-point extraction, evidence collection, recurring-complaint tracking, competitor tracking, market scoring, risk analysis, confidence score, source links, a validation checklist, weekly/monthly summary formats, and open sections for observations and open questions. Deliberately left every "findings" section empty (`[Not yet collected]`) rather than seeded with invented example data.
- Self-reviewed all eight documents for internal consistency and found two real issues, both fixed: (1) ROADMAP.md Milestone 6.1 incorrectly attributed a PRD.md §3 point to CLAUDE.md §4 — corrected the citation; (2) all five research templates' "Market Scoring" sections incorrectly pointed to IDEAS.md as the framework for scoring discovered market opportunities, contradicting IDEAS.md's own explicit scope (which covers MarketRadar's own product features, not the pain points its research surfaces) — corrected all five to point instead to ROADMAP.md's future Milestone 5.3 (Market Attractiveness Scoring), with an explicit "do not compute or imply a score" instruction until that capability exists.
- Committed the above as `6edbdc7 Finish MVP planning`, then in a later pass the same day added "Task 1" scaffolding (commit `91efc12 Complete initial MarketRadar setup`): `.gitignore`, `requirements.txt` (praw, anthropic, python-dotenv), `.env.example`, `src/__init__.py`, `src/config.py` (single-point `load_config()` env-var loader, fails loudly via `ConfigError` if Reddit/Anthropic credentials are missing, never returns partial secrets), and `src/check_connections.py` (verifies Reddit read-only auth and Claude API auth actually work; deliberately does no fetching/extraction; never prints a credential value or raw exception message, only the exception type name).
- End-of-session review pass (this entry, added retroactively): ran the actual project — confirmed git repo root is correctly scoped to the `MarketRadar` folder (the "Known Issues" entry below about a misplaced home-directory repo root is now stale/resolved), confirmed `.env` is gitignored and still unfilled (identical to `.env.example`, so no real secret has ever existed on disk or in git history), confirmed no fabricated data exists in any research template or IDEAS.md entry, and confirmed no venv/dependencies are installed yet (`python -m src.check_connections` currently fails on `ModuleNotFoundError`, not on real credential logic — expected, not a bug). Created [TODO.md](./TODO.md) as the prioritized next-steps list.

### In Progress
None — all eight documents requested this session (ROADMAP.md, SESSION.md, IDEAS.md, and the five research templates) are complete and self-reviewed.

### Known Issues
- ~~This machine's git repository root was found to be the user's entire home directory...~~ **Resolved as of the end-of-session review**: `git rev-parse --show-toplevel` now correctly resolves to the `MarketRadar` folder itself, and `git ls-files` only lists this project's own files. No action needed.
- `docs/` exists with no defined purpose yet — not addressed this session. (`src/` now has a defined purpose — see Completed Work.)
- IDEAS.md's scoring dimensions (Market Size, Growth Trend, Competition, Revenue Potential, Founder Fit, etc.) closely resemble a startup-opportunity scorecard, which created a real ambiguity about whether the framework was meant to evaluate MarketRadar's own product features or the market opportunities MarketRadar's research surfaces for founders — the latter would conflict with MarketRadar not being an idea generator. Resolved by scoping IDEAS.md explicitly to MarketRadar's own features/product ideas, but this interpretation has not been explicitly confirmed by the user — see Questions.
- **New:** `src/config.py` and `src/check_connections.py` are real, working software, and ROADMAP.md Phase 0 states explicitly "Phase 0 produces no software." Separately, PRD.md §13 lists "which initial sources offer the strongest evidence-to-effort ratio" as a sourcing decision *deliberately deferred* from the PRD, and ROADMAP.md Milestone 0.1 (Source Feasibility Assessment) — which is supposed to produce that decision — has not been done. Yet `.env.example` and `check_connections.py` already commit specifically to Reddit as the first source. This isn't fabrication or scope creep in output (the code makes no evidentiary claims), but it is a sequencing gap worth the user's explicit sign-off rather than quietly proceeding as if Milestone 0.1 were already satisfied — flagged in TODO.md.
- No venv exists and `requirements.txt` is not installed anywhere on this machine yet; `python -m src.check_connections` currently fails at `ModuleNotFoundError: No module named 'dotenv'`, before it ever reaches credential logic. Expected, not a regression — just the next setup step.

### Next Tasks
See [TODO.md](./TODO.md) for the full prioritized list. Highlights:
- Confirm with the user whether IDEAS.md's intended scope (feature/product ideas about MarketRadar itself) matches their intent, given the dimension set could also read as a market-opportunity scorecard (see Known Issues and Questions).
- Populate IDEAS.md's backlog with real, evidence-backed candidates once any actual research (Phase 0 of ROADMAP.md) begins — the framework should exist before any idea does.
- Set up a venv, install `requirements.txt`, fill in real Reddit + Anthropic credentials in `.env`, and get `python -m src.check_connections` to print "All connections verified."
- Get explicit user sign-off on the Reddit-as-first-source sequencing gap noted in Known Issues before writing any extraction code against it.

### Important Decisions
- Confirmed README.md, PRD.md, and CLAUDE.md are the project's source of truth; all subsequently written documents (ROADMAP, SESSION, IDEAS, research templates) must stay consistent with them rather than introduce new, conflicting scope or philosophy.
- Chose not to fabricate example research data inside the research templates — templates are structural/instructional only, consistent with the project's core "never fabricate evidence" rule extending even to planning documents. The one example entry in IDEAS.md is explicitly labeled fictional/illustrative for the same reason.
- Treated the empty-directory files as safe to delete only after individually verifying each was genuinely empty first, rather than assuming based on their appearance in a prior listing — applied this same discipline a second time to the `research/` directory before removing the mistyped placeholders.
- Scoped IDEAS.md to MarketRadar's own product/feature ideas, not to the market opportunities the product's research surfaces, and corrected the research templates to match — see Known Issues for the ambiguity this resolved.

### Questions
- Does IDEAS.md's scope (MarketRadar's own features, not discovered market opportunities) match what was intended, given the dimension set reads like it could apply to either?
- Should the misplaced home-directory git repository be corrected before any further work, given that it currently makes `git status` inside this project misleading?
- What should `docs/` and `src/` be used for, and when should that be defined — is `docs/` intended to hold anything beyond the top-level planning documents already in the project root?

### Lessons Learned
- Verify file-vs-directory state explicitly (not just from a prior `ls` in conversation memory) immediately before any destructive operation, even a low-risk one like removing an apparently-empty directory — state can change between when it was last observed and when it's acted on.
- When a user-specified target filename doesn't match an existing artifact's name, treat that as a signal to flag explicitly rather than silently picking one interpretation — naming mismatches are cheap to surface and expensive to leave ambiguous.
- Cross-referencing documents by section number (e.g., "PRD.md §3") is only valuable if the citations are actually checked against the source — a self-review pass caught one wrong citation and one real scope contradiction that would have shipped otherwise; this kind of check is worth doing explicitly, not just assumed correct while writing.

### Future Improvements
- Once real research begins, consider whether this journal should stay a single growing file or move to one-file-per-session once it becomes unwieldy — not a decision to make preemptively.
- Consider whether SESSION.md entries should eventually be summarized periodically (e.g., a "project history" rollup) once enough sessions accumulate that reading the full log becomes impractical.
