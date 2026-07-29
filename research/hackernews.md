# Research Template — Hacker News

This is a reusable template and process guide, not a data file. It defines how Hacker News research should be conducted so that every researcher (human or Claude) produces evidence in the same, comparable, auditable format. Do not fill this file with invented example findings — leave sections empty or marked `[Not yet collected]` until real research happens, per [CLAUDE.md](../CLAUDE.md)'s non-fabrication rules, which apply to research process documents exactly as they apply to the product itself.

Findings produced using this template feed directly into MarketRadar's evidence base (see [PRD.md](../PRD.md) §8 for MVP evidence requirements) and must meet the same bar: every claim traceable to a real, linkable source.

---

## Purpose

Hacker News is a candidate source for pain points expressed by a technically sophisticated, builder-heavy audience — often more precise and less emotionally charged than general social media, but also narrower in who it represents. Its purpose within MarketRadar is to surface specific, well-articulated problems (especially in developer tools, infrastructure, and technical/business workflows) and to catch early signal on emerging frustrations before they're widely discussed elsewhere.

## Where Data Comes From

- Story threads and their nested comments, both on submitted links ("Show HN," articles, blog posts) and text/"Ask HN" posts.
- "Ask HN" threads specifically, which frequently contain direct requests for tools or solutions and are unusually rich in explicit pain-point language.
- Only publicly viewable content, accessed in a manner consistent with Hacker News' and Y Combinator's terms of use at the time of collection (including any API terms, if a public API is used) — verify current terms before automating collection; this template does not itself grant clearance (see [PRD.md](../PRD.md) §13 and ROADMAP.md Milestone 0.1).

## How Information Should Be Collected

1. Identify relevant threads via front-page/new monitoring, search for problem-indicative terms, or by following specific topic tags/domains relevant to the problem space under investigation.
2. Record the exact search term, listing (front page / new / "Ask HN"), and collection date — HN rankings shift quickly, so reproducibility depends on logging what was actually viewed and when.
3. Read full comment trees, not just the top-level story or top comment — HN threads often contain the most specific pain-point detail several replies deep, where a practitioner corrects or elaborates on the original point.
4. Capture the permalink, commenter identifier (HN username), timestamp, and full relevant text for anything that looks like a candidate pain point.
5. Note points and comment count at time of collection as weak, secondary engagement signal only — HN's front-page dynamics reward general interest and discussion-worthiness, which does not necessarily track how common or painful the underlying problem is.

## Signals to Look For

- "Ask HN" posts explicitly asking for tool recommendations or reporting a gap ("Is there a tool that does X? Everything I've tried is missing Y").
- Comments describing a workaround or homegrown solution built specifically because nothing else solved the problem.
- Threads where a "Show HN" submission draws comments pointing out a limitation or a gap the new tool still doesn't address — these are effectively unsolicited market feedback on an adjacent space.
- Recurring mentions of the same frustration across unrelated stories over time (e.g., the same complaint about a category of tool showing up under different submissions).
- Direct statements of willingness to pay or of an existing budget being spent on a worse alternative.

## Pain Point Extraction

For each candidate pain point found, record:

- **Problem statement** — a precise, neutral description of the pain point, written from the evidence, not paraphrased into something more general than what was actually said.
- **Direct quote(s)** — the actual text expressing the pain point, not a summary.
- **Context** — the story it appeared under, the type of thread ("Ask HN," "Show HN," article discussion), and comment depth/reply chain if relevant to interpreting it correctly.
- **Distinct-instance check** — confirm this is an independent expression of the pain point, not the same commenter restating themselves across threads, or a quoted/copied comment.

## Evidence Collection

Every pain point entry must include:

- Direct permalink to the specific comment (HN permalinks are comment-specific, not just story-level — always link the exact comment).
- Timestamp of the original comment.
- Verbatim quoted text.
- Commenter identifier (HN username) — for deduplication purposes (see Recurring Complaint Tracking), not for any personal profiling.

Do not record anything as evidence that cannot be independently re-checked at the link provided. If a piece of context is inferred rather than stated (e.g., "this commenter appears to run an infrastructure team"), label it explicitly as inference, separate from the quoted evidence itself.

## Recurring Complaint Tracking

- Track pain points by a consistent problem label (not by thread), so the same underlying complaint appearing under different stories over time is recognized as recurring rather than logged as unrelated one-offs.
- Record each new instance with its own link, date, and commenter — recurrence is the count of independent instances, not the count of threads it appeared in.
- Watch for the same commenter repeating themselves across multiple threads and count it as one instance, not several.
- Log the observation window alongside recurrence counts, since HN's discussion volume on any given topic can be bursty around specific news events.

## Competitor Tracking

- When a pain point thread names a specific existing tool, product, or service (positively or negatively), record the name and the exact quoted context.
- Only log a competitor if it is explicitly named in the source material — never infer that a well-known tool in the space is "probably" being discussed if it isn't actually named.
- Where a named competitor is criticized, capture the specific stated weakness verbatim, with its own link, logged separately from the general pain point evidence so it stays independently traceable.
- HN "Show HN" threads are a particularly useful competitor-tracking source: makers of existing tools often participate directly in the comments, sometimes responding to criticism — capture maker responses too, as they can confirm or contest a stated weakness.

## Market Scoring

Do not assign a market attractiveness score from Hacker News research alone, and do not use [IDEAS.md](../IDEAS.md) for this purpose — that framework evaluates candidate features for MarketRadar the product, not the market opportunities its research surfaces (see IDEAS.md's own scope note). HN research instead contributes raw inputs (recurrence count, severity signal, willingness-to-pay statements, named competitor weaknesses, maker responses) toward MarketRadar's future market-attractiveness capability, which combines evidence across sources — see [ROADMAP.md](../ROADMAP.md) Milestone 5.3. Until that capability exists, do not compute or imply a score. Note explicitly that HN's audience skews toward technical, English-speaking, startup-adjacent users — any market-size inference drawn from HN alone should be treated as narrower than the general population, not representative of it.

## Risk Analysis

Known risk factors specific to Hacker News as a source:

- **Audience skew** — HN's commentariat is disproportionately technical, startup-adjacent, and English-language; pain points that resonate strongly on HN may not generalize to a broader founder or business audience, and pain points that matter to non-technical audiences may be underrepresented or entirely absent.
- **Contrarian/critical tone** — HN comment culture rewards sharp criticism, which can make genuine pain points sound more severe than they are, or can surface criticism of a tool that isn't really about a recurring pain point at all (e.g., a one-off bad experience).
- **Front-page selection bias** — what reaches the front page (and therefore gets seen and commented on) is shaped by voting dynamics that favor novelty and discussion-worthiness, not necessarily how common or painful a problem is; searching directly for problem-indicative terms, not just browsing the front page, helps offset this.
- **Self-promotional noise** — "Show HN" threads in particular can contain promotional comments from the poster or affiliated accounts; treat maker-authored comments about their own product with appropriate skepticism when using them as competitor-weakness evidence.

## Confidence Score

Apply the confidence taxonomy defined in [ROADMAP.md](../ROADMAP.md) Milestone 0.3 once it exists. Until that taxonomy is written, do not assign ad hoc confidence labels — leave this field as `[Pending taxonomy — see ROADMAP.md Milestone 0.3]` rather than inventing a scale here that would conflict with the eventual project-wide standard.

## Source Links

Maintain a running, deduplicated list of every source link cited in this research area, so the full evidence trail can be reviewed independently of the narrative findings above it.

```
[Not yet collected]
```

## Validation Checklist

Before a Hacker News–derived pain point is considered ready to feed into MarketRadar's evidence base, confirm:

- [ ] Every quote links to the specific comment, not just the parent story.
- [ ] Recurrence count reflects independent commenters/instances, not the same person restating themselves.
- [ ] Any competitor mention is verbatim and directly sourced, not inferred.
- [ ] Maker/self-promotional comments (if used) are clearly labeled as such, not presented as neutral third-party evidence.
- [ ] The observation window (dates, listings/search terms used) is recorded alongside the findings.
- [ ] Audience-skew caveat is noted wherever this source is the sole or primary evidence behind a broader market claim.

## Weekly Summary Format

```
### Hacker News Weekly Summary — Week of [YYYY-MM-DD]

**Listings/search terms covered:** [list]
**New pain points identified:** [count, with links to full entries]
**Recurring pain points reinforced this week:** [count, with new instance links]
**New competitor mentions (including maker responses):** [list, with links]
**Notable single findings worth flagging:** [any unusually strong or unusually weak evidence worth a human's attention]
**Collection issues/gaps:** [anything that limited this week's collection]
```

## Monthly Trend Format

```
### Hacker News Monthly Trend — [Month YYYY]

**Total distinct pain points tracked this month:** [count]
**Pain points with increasing instance frequency vs. prior month:** [list — directional only, not a formal growth claim until ROADMAP.md Phase 5 growth-detection capability exists]
**Pain points with no new instances this month:** [list]
**New topic areas/search terms added to coverage:** [list]
**Source-specific risk events this month:** [e.g., unusually promotional threads, notable maker pushback on captured competitor weaknesses]
```

## Important Observations

*[Not yet collected — record genuinely notable, source-level observations here as research happens (e.g., "Ask HN threads yield meaningfully higher pain-point density than Show HN threads"), not individual pain-point findings, which belong in the evidence base itself.]*

## Open Questions

*[Not yet collected — record open methodological or source-specific questions here as they arise, e.g., "how should maker responses be weighted when they contest a stated competitor weakness?"]*
