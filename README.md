# MarketRadar

**An evidence-driven market intelligence platform that discovers real business pain points before they become obvious.**

---

## What MarketRadar Is

MarketRadar is an AI-powered research assistant that continuously analyzes public conversations — reviews, complaints, feature requests, discussions, and trends to surface business problems that are real, recurring, growing, and poorly solved.

MarketRadar is **not** a startup idea generator. It does not invent ideas, brainstorm concepts, or produce inspirational lists of "100 startup ideas." Idea generators produce plausible-sounding fiction. MarketRadar produces evidence.

Every output MarketRadar produces is traceable to a real, public source: a specific thread, review, issue, or post, at a specific point in time, said by a real person with a real problem. If MarketRadar cannot point to the evidence, it does not make the claim.

## Who MarketRadar Is For

MarketRadar is built for people who are trying to find a problem worth solving, not people looking for validation of a problem they've already committed to.

- **Founders searching for their first (or next) idea**, who want to start from evidence instead of intuition.
- **Indie hackers and solo builders** who need to find underserved niches without a research team.
- **Product managers and innovation teams** inside existing companies, scouting adjacent markets or evaluating whether a proposed feature addresses a problem that actually exists at scale.
- **Investors and analysts** who want an evidence trail behind a market thesis, not a founder's pitch-deck narrative.

MarketRadar is explicitly **not** for people who want a shortcut past the hard part of company-building. It surfaces problems; it does not promise that any given problem is easy, defensible, or guaranteed to work as a business. That judgment always remains with the human.

## Why MarketRadar Exists

Most startups don't fail because their execution was bad. They fail because they were built on a problem that wasn't actually painful, wasn't actually growing, or was already well-served by someone else.

The information needed to avoid that mistake already exists publicly  scattered across Reddit threads, GitHub issues, one-star reviews, and Hacker News comments  but no one has time to read all of it, and human pattern-recognition is bad at spotting weak signals across thousands of sources over time.

MarketRadar exists to close that gap: to do the tedious, distributed reading that a thorough human researcher would do, at a scale no human can sustain, and to present findings the way a rigorous analyst would  with sources, caveats, and honest uncertainty, not with hype.

## Long-Term Vision

Today, most founders ask: **"What startup should I build?"** and get an answer built on guesswork, trend-chasing, or a list of ideas that all sound plausible and are all equally unfounded.

MarketRadar exists so founders can instead ask: **"What problems are growing, painful, and still poorly solved?"**  and get an answer built on evidence.

Over time, MarketRadar should become the default first step in company formation — the tool a founder opens before they open a blank document to write a pitch. Its long-term ambition is to be recognized as the world's best AI research assistant for people trying to find problems worth solving, not by generating more ideas, but by helping people trust fewer, better-evidenced ones.

This is a long-term, compounding effort. MarketRadar gets more valuable as it observes more of the internet's problem-signal over a longer period of time, because "growing" and "recurring" are claims that can only be made with history behind them.

## Project Philosophy

MarketRadar is built on a small number of non-negotiable beliefs:

- **Evidence > Opinions.** A claim without a source is not a finding.
- **Problems > Ideas.** We study what's broken, not what could be built.
- **Validation > Assumptions.** Confidence is earned by checking, not asserted by default.
- **Users > Features.** We build what makes the research trustworthy before what makes it flashy.
- **Data > Hype.** Growth in a market is measured, not narrated.
- **Consistency > Complexity.** A simple system that runs reliably beats a sophisticated one that doesn't.

Alongside these, MarketRadar holds itself to a strict standard of intellectual honesty: it never invents information, never fabricates evidence, never hallucinates a competitor that doesn't exist, and always says when the evidence behind a conclusion is thin. A confident wrong answer is worse than an honest "we don't know yet."

## Future Direction

MarketRadar starts narrow. The MVP will draw on a small number of public sources, analyzed carefully, rather than a large number analyzed shallowly. Depth and trustworthiness come before breadth.

Over time, the range of sources it draws on is expected to grow  toward the kind of coverage that includes places like Reddit, Hacker News, Product Hunt, GitHub Issues and Discussions, G2 and Capterra reviews, X, LinkedIn, YouTube comments, Discord communities, blogs, news, forums, product documentation, and changelogs. This breadth is a long-term destination, not a launch requirement, and which sources come online first will be decided by where they yield the clearest, most defensible evidence  not by which are easiest to integrate.

As it matures, MarketRadar should also grow more capable along other dimensions described in its [product requirements](./PRD.md): detecting whether a problem is growing over time, identifying existing competitors and their weaknesses, and estimating willingness to pay — always in service of the same goal, helping founders spend less time searching and more time validating.

## Getting Started

This section covers running the code, not the product vision above — see [PRD.md](./PRD.md) for requirements and [SESSION.md](./SESSION.md) for the detailed history of how it was built.

**Prerequisites:** Python 3.10+.

**1. Install dependencies** (a virtual environment is recommended but not required):

```
pip install -r requirements.txt
```

**2. Configure.** Copy `.env.example` to `.env` and fill it in:

- **Gemini (required for real analysis):** free tier available — create a key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY`.
- **Reddit (optional):** leave blank to use built-in mock sample data instead of real Reddit posts. To use real data, create a script app at https://www.reddit.com/prefs/apps and set `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT`.
- **GitHub (optional):** `GitHubFetcher` (`src/fetchers/github_fetcher.py`) discovers up to 5 relevant public repos for a topic keyword (via GitHub's Search API, filtering out archived/forked/issue-less repos), then fetches open issues + comments from each — no token required (60 req/hour, unauthenticated). Set `GITHUB_TOKEN` (a personal access token from https://github.com/settings/tokens) to raise that to 5000 req/hour. Reachable via `POST /analyze`/`/analyze/mock` (`{"source": "github", "keyword": "invoicing", ...}` — no repo name needed) and the dashboard's Source toggle. **Not yet wired into the CLI** (`src/pipeline/runner.py` has no `--source` flag) — added as a second data source ahead of TODO.md's original "prove Reddit end-to-end first" sequencing (see TODO.md and SESSION.md for that decision).

**3. Verify your setup:**

```
python -m src.check_connections
```

**4. Run it.** The full pipeline (Fetch → Analyze → Cluster → Verify → Report) runs with one command:

```
# Fully offline, zero cost — good for a first run or for testing:
python -m src.pipeline.runner --mock

# Real Reddit + real Gemini, targeting a subreddit:
python -m src.pipeline.runner --subreddit startups

# See every option:
python -m src.pipeline.runner --help
```

Reports are saved to `output/` as Markdown, alongside a JSON summary of each run (posts fetched, AI calls made, duration, errors). `src/pipeline/runner.py` is the current, actively maintained entrypoint — other scripts under `src/` (`check_connections.py`, `fetch_preview.py`, `analyze_preview.py`) are narrower diagnostic tools for individual pipeline stages, kept for that purpose, not superseded replacements for the full pipeline.

AI responses are cached by default (`.cache/ai_responses.json`, keyed by exact prompt) — re-running the pipeline over overlapping data reuses prior analysis instead of spending real Gemini quota again. Pass `--no-cache` to force fresh calls every time.

## REST API

`src/api/` exposes the same pipeline over HTTP, for anything that wants to call MarketRadar programmatically instead of via the CLI. It is a thin wrapper only — every request still goes through `Pipeline.run()`; the API never re-implements fetching, analysis, clustering, verification, or report rendering itself.

**Run the server:**

```
uvicorn src.api.app:app --reload
```

Interactive docs (Swagger UI) are then available at `http://127.0.0.1:8000/docs`, and the raw OpenAPI schema at `http://127.0.0.1:8000/openapi.json`.

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + whether Gemini/Reddit are configured. Does not contact either. |
| GET | `/version` | API name/version. |
| POST | `/analyze` | Runs the real pipeline (real Reddit/Gemini if configured, mock fallback otherwise — same "auto" behavior as the CLI). May consume real API quota. |
| POST | `/analyze/mock` | Same as `/analyze`, but forces fully offline mock mode regardless of `.env`. Zero cost, zero network calls — the same guarantee as `--mock` on the CLI. |
| GET | `/reports` | Lists past runs (CLI and API runs together — both save to `output/`), newest first. |
| GET | `/reports/{report_id}` | Full execution summary for one run, plus its saved Markdown report text if one exists. |
| GET | `/download/{report_id}` | Downloads the saved Markdown report file for one run. |

**Example: a free, offline analysis run**

```
curl -X POST http://127.0.0.1:8000/analyze/mock \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "report_format": "both"}'
```

Response (trimmed):

```json
{
  "report_id": "20260731_120000",
  "summary": {"succeeded": true, "posts_fetched": 5, "ai_calls_made": 0, "cache_hits": 0, "cache_misses": 0, "clusters_found": 0, "errors": []},
  "report": {"executive_summary": "...", "top_opportunities": [], "project_health": {...}}
}
```

(`/analyze/mock` always produces zero opportunities — `MockAIProvider`'s placeholder text is deliberately never valid JSON, so nothing extracts. Use `/analyze` with a real `GEMINI_API_KEY` configured for a real result.)

**Example: a real run against a subreddit**

```
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"subreddit": "startups", "keyword": "invoicing", "limit": 10, "use_cache": true, "report_format": "both"}'
```

**Example: a real run against GitHub, by topic keyword** (no repo name needed — `GitHubFetcher` discovers up to 5 relevant repos itself; no mock equivalent, so this always hits the real GitHub API):

```
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"source": "github", "keyword": "invoicing", "limit": 10}'
```

**Example: retrieving a past report**

```
curl http://127.0.0.1:8000/reports
curl http://127.0.0.1:8000/reports/20260731_120000
curl http://127.0.0.1:8000/download/20260731_120000 -o report.md
```

`limit` is capped at 100 requests per call through the API (the CLI has no such cap — a human typing a command can see the consequences; a network-facing endpoint can't assume that). Invalid input (an out-of-range `limit`, a blank `subreddit`, an unrecognized `report_format`) returns `422` with a structured error body; an unknown `report_id` returns `404`. See SESSION.md's Task 10 entry for the full architecture review, including known limitations.

## Dashboard

`dashboard/` is a Next.js (App Router, TypeScript, Tailwind, shadcn/ui) web UI over the REST API — a visual alternative to the CLI and raw `curl`, not a replacement for either. It talks to the backend exclusively over HTTP through one client module (`dashboard/src/lib/api/client.ts`); it never re-implements fetching, analysis, clustering, verification, or report generation.

**Run it** (with the API already running per the REST API section above):

```
cd dashboard
npm install
npm run dev
```

Then open `http://localhost:3000`. Four pages: **Home** (run an analysis — subreddit, keyword, limit, cache/mock toggles, live loading state, graceful error display), **Reports** (every past run, searchable by ID, sortable by newest/oldest), **Report Details** (executive summary, per-opportunity score/confidence/verification rate/quotes/segment/next action, plus three charts — Top Pain Points, Opportunity Scores, Verification Distribution, via Recharts), and **Settings** (API base URL override, connection test, default mock-mode preference). Dark mode and full responsiveness are built in throughout.

By default it points at `http://127.0.0.1:8000` (override via `NEXT_PUBLIC_API_BASE_URL` in `dashboard/.env.local`, copied from `.env.local.example`, or per-browser from the Settings page — handy for pointing at a non-default port without a rebuild).

One real limitation worth knowing up front: `GET /reports/{id}` (used by the Reports page) only ever returns a saved run's execution summary plus its raw Markdown text, never a JSON form of the structured report — the pipeline doesn't persist one. The Report Details page reconstructs the per-opportunity cards and charts by parsing that Markdown when you're not looking at a report you *just* ran in the same browser tab (which does have the real structured data, cached client-side). See SESSION.md's Task 11 entry for the full reasoning and its limits.

---

For the detailed product requirements behind this vision, see [PRD.md](./PRD.md). For how this project should be developed and how Claude Code should operate within it, see [CLAUDE.md](./CLAUDE.md).
