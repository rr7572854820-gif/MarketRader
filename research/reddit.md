# Research Template — Reddit

This is a reusable template and process guide, not a data file. It defines how Reddit research should be conducted so that every researcher (human or Claude) produces evidence in the same, comparable, auditable format. Do not fill this file with invented example findings — leave sections empty or marked `[Not yet collected]` until real research happens, per [CLAUDE.md](../CLAUDE.md)'s non-fabrication rules, which apply to research process documents exactly as they apply to the product itself.

Findings produced using this template feed directly into MarketRadar's evidence base (see [PRD.md](../PRD.md) §8 for MVP evidence requirements) and must meet the same bar: every claim traceable to a real, linkable source.

---

## Purpose

Reddit is a candidate source for discovering pain points expressed in relatively unguarded, community-context conversation — people asking for help, venting about a tool, or comparing alternatives within a community that already shares context. Its purpose within MarketRadar is to surface recurring, specific complaints and unmet needs, not general opinion or sentiment.

## Where Data Comes From

- Subreddit posts and their comment threads, within subreddits relevant to a given problem space (e.g., a professional community, a tool's own subreddit, an industry-specific subreddit).
- Search results within Reddit for problem-indicative phrases (see Signals below), scoped to relevant subreddits or site-wide where appropriate.
- Only publicly viewable content. Do not access private subreddits, deleted/removed content, or anything requiring authenticated access beyond what a normal logged-out viewer could see. Access must comply with Reddit's terms of service and API terms at the time of collection — verify current terms before automating any collection; this template does not itself grant clearance (see [PRD.md](../PRD.md) §13 and ROADMAP.md Milestone 0.1).

## How Information Should Be Collected

1. Identify a small set of relevant subreddits or search terms tied to a specific problem space under investigation — do not attempt to boil the ocean across all of Reddit at once.
2. Record the exact search term or subreddit/sort combination used, and the date of collection — reproducibility matters, since Reddit's ranking and visible content change over time.
3. Read full threads, not just post titles — the pain point is often more precise in the comments than in the original post.
4. Capture the permalink, author (username, not real identity), timestamp, and full relevant text for anything that looks like a candidate pain point.
5. Note engagement signal (upvotes, comment count) at time of collection, since it can indicate how widely a complaint resonates — but treat it as a weak, secondary signal, not proof of recurrence on its own (see Confidence Score below).

## Signals to Look For

- Direct complaints ("X is so frustrating," "I hate that Y doesn't do Z").
- Explicit requests for a tool/solution that doesn't seem to exist yet ("Is there anything that does X? I can't find one").
- Workaround descriptions ("I ended up just doing X manually because nothing handles this").
- Comparison threads where multiple existing tools are criticized for the same gap.
- Repeated questions across different threads/times that indicate an unresolved, recurring need.
- Explicit statements of willingness to pay ("I would pay for a tool that just did X") — rare, but high-value when found; see [research/reddit.md — Evidence Collection](#evidence-collection).

## Pain Point Extraction

For each candidate pain point found, record:

- **Problem statement** — a precise, neutral description of the pain point, written from the evidence, not paraphrased into something more general than what was actually said.
- **Direct quote(s)** — the actual text expressing the pain point, not a summary.
- **Context** — what subreddit, what kind of thread (question, rant, comparison, help request), and any relevant surrounding context needed to interpret the quote correctly.
- **Distinct-instance check** — confirm this is an independent expression of the pain point, not a repost, a quote of another thread, or the same user restating themselves.

## Evidence Collection

Every pain point entry must include:

- Direct permalink to the specific comment or post (not just the thread root, if the evidence is in a comment).
- Timestamp of the original post/comment.
- Verbatim quoted text.
- Author identifier (username) — for deduplication purposes (see Recurring Complaint Tracking), not for any personal profiling.

Do not record anything as evidence that cannot be independently re-checked at the link provided. If a piece of context is inferred rather than stated (e.g., "this user seems to run a small business"), label it explicitly as inference, separate from the quoted evidence itself.

## Recurring Complaint Tracking

- Track pain points by a consistent problem label (not by thread), so that the same underlying complaint found in multiple threads or subreddits can be recognized as recurring rather than logged as unrelated one-offs.
- Record each new instance of a previously-seen pain point with its own link, date, and author — recurrence is the count of independent instances, not the count of threads.
- Watch for same-author repetition (one person posting the same complaint repeatedly) and count it as one instance, not several, to avoid inflating recurrence counts artificially.
- Log the observation window (date range searched) alongside recurrence counts, since "recurring" is only meaningful relative to a defined time period.

## Competitor Tracking

- When a pain point thread names a specific existing tool, product, or service (positively or negatively), record the name and the exact quoted context.
- Only log a competitor if it is explicitly named in the source material — never infer that a well-known tool in the space is "probably" being discussed if it isn't actually named.
- Where a named competitor is criticized, capture the specific stated weakness verbatim, with its own link — this is distinct from the general pain point evidence and should be logged separately so it can be traced back to its own source.

## Market Scoring

Do not assign a market attractiveness score from Reddit research alone, and do not use [IDEAS.md](../IDEAS.md) for this purpose — that framework evaluates candidate features for MarketRadar the product, not the market opportunities its research surfaces (see IDEAS.md's own scope note). Reddit research instead contributes raw inputs (recurrence count, severity signal from complaint language, any willingness-to-pay statements, named competitor weaknesses) toward MarketRadar's future market-attractiveness capability, which combines evidence across sources — see [ROADMAP.md](../ROADMAP.md) Milestone 5.3. Until that capability exists, do not compute or imply a score; single-source Reddit findings alone are an input, not a verdict.

## Risk Analysis

Known risk factors specific to Reddit as a source:

- **Community bias** — a subreddit's culture can amplify certain complaints (e.g., contrarian or highly technical subreddits) in ways that don't represent the broader population with the problem.
- **Karma/engagement gaming** — upvote counts can be manipulated or can reflect meme/humor value rather than genuine shared pain; do not treat upvotes as a substitute for counting genuine independent instances.
- **Sarcasm and hyperbole** — Reddit's conversational tone frequently uses exaggeration; read full context before recording a quote as literal pain-point evidence.
- **Brigading / coordinated posting** — some threads or subreddits are subject to coordinated campaigns; if a research window coincides with an unusual spike, note it and treat the spike with extra scrutiny before counting it as organic recurrence.
- **Deleted/edited content** — quoted evidence can later be deleted or edited by the author; note the collection date so later discrepancies are understood as a source-drift issue, not a data-integrity failure on MarketRadar's part.

## Confidence Score

Apply the confidence taxonomy defined in [ROADMAP.md](../ROADMAP.md) Milestone 0.3 once it exists. Until that taxonomy is written, do not assign ad hoc confidence labels — leave this field as `[Pending taxonomy — see ROADMAP.md Milestone 0.3]` rather than inventing a scale here that would conflict with the eventual project-wide standard.

## Source Links

Maintain a running, deduplicated list of every source link cited in this research area, so the full evidence trail can be reviewed independently of the narrative findings above it.

```
[Not yet collected]
```

## Validation Checklist

Before a Reddit-derived pain point is considered ready to feed into MarketRadar's evidence base, confirm:

- [ ] Every quote has a working, specific permalink (not just a subreddit or thread root when the evidence is in a comment).
- [ ] Recurrence count reflects independent authors/instances, not reposts or same-author repetition.
- [ ] Any competitor mention is verbatim and directly sourced, not inferred.
- [ ] Sarcasm, humor, or hyperbole has been ruled out through full-context reading, not title/snippet only.
- [ ] The observation window (dates, subreddits/search terms used) is recorded alongside the findings.
- [ ] Nothing in the write-up states something as fact that the source only implies or suggests.

## Weekly Summary Format

```
### Reddit Weekly Summary — Week of [YYYY-MM-DD]

**Subreddits/search terms covered:** [list]
**New pain points identified:** [count, with links to full entries]
**Recurring pain points reinforced this week:** [count, with new instance links]
**New competitor mentions:** [list, with links]
**Notable single findings worth flagging:** [any unusually strong or unusually weak evidence worth a human's attention]
**Collection issues/gaps:** [anything that limited this week's collection — access issues, low activity, etc.]
```

## Monthly Trend Format

```
### Reddit Monthly Trend — [Month YYYY]

**Total distinct pain points tracked this month:** [count]
**Pain points with increasing instance frequency vs. prior month:** [list — directional only, not a formal growth claim until ROADMAP.md Phase 5 growth-detection capability exists]
**Pain points with no new instances this month:** [list]
**New subreddits/communities added to coverage:** [list]
**Source-specific risk events this month:** [e.g., suspected brigading, major subreddit rule changes, API/access changes]
```

## Important Observations

*[Not yet collected — record genuinely notable, source-level observations here as research happens (e.g., "this subreddit's culture skews heavily toward X type of complaint"), not individual pain-point findings, which belong in the evidence base itself.]*

## Open Questions

*[Not yet collected — record open methodological or source-specific questions here as they arise, e.g., "how should we treat subreddits with overlapping membership when counting recurrence across them?"]*
