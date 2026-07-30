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

---

For the detailed product requirements behind this vision, see [PRD.md](./PRD.md). For how this project should be developed and how Claude Code should operate within it, see [CLAUDE.md](./CLAUDE.md).
