# Research Template — Product Hunt

This is a reusable template and process guide, not a data file. It defines how Product Hunt research should be conducted so that every researcher (human or Claude) produces evidence in the same, comparable, auditable format. Do not fill this file with invented example findings — leave sections empty or marked `[Not yet collected]` until real research happens, per [CLAUDE.md](../CLAUDE.md)'s non-fabrication rules, which apply to research process documents exactly as they apply to the product itself.

Findings produced using this template feed directly into MarketRadar's evidence base (see [PRD.md](../PRD.md) §8 for MVP evidence requirements) and must meet the same bar: every claim traceable to a real, linkable source.

---

## Purpose

Product Hunt is a candidate source for two distinct kinds of signal: (1) launch-comment feedback that reveals gaps or limitations in new products, directly from early users and the maker themselves, and (2) a live view of which existing products already serve a given problem space, useful for competitor discovery. Its purpose within MarketRadar is less about raw pain-point volume than about grounding competitor identification and surfacing specific, dated criticism of existing solutions.

## Where Data Comes From

- Product launch pages and their comment sections, including maker replies.
- Product descriptions, categorization/tags, and stated feature sets, useful for competitor cataloguing.
- Only publicly viewable content, accessed consistent with Product Hunt's terms of service at the time of collection (including any API terms, if used) — verify current terms before automating collection; this template does not itself grant clearance (see [PRD.md](../PRD.md) §13 and ROADMAP.md Milestone 0.1).

## How Information Should Be Collected

1. Identify relevant product categories/tags or search terms tied to the problem space under investigation.
2. Record the exact category, tag, or search term used, and the collection date — Product Hunt's catalog and comment activity change continuously.
3. Read full comment sections on relevant launches, not just the top comment — maker responses to critical comments are often where the most specific evidence of a gap appears.
4. Capture the permalink, commenter identifier, timestamp, and full relevant text for anything that looks like a candidate pain point or competitor-weakness statement.
5. Note upvote count for the product itself and for individual comments as weak, secondary signal only — launch-day popularity reflects the Product Hunt community's response, not necessarily broader market pain.

## Signals to Look For

- Comments pointing out a missing feature or a specific limitation in the launched product.
- Comments comparing the launch unfavorably (or favorably) to a named existing alternative.
- Maker responses that concede a gap ("great point, we don't support that yet") — this is unusually direct, dated evidence of a real limitation, stated by the product's own team.
- Comments explicitly stating a pricing complaint or a willingness-to-pay signal ("would pay for this if it had X").
- Patterns across multiple unrelated launches in the same category pointing at the same unmet need (e.g., several products in a category all getting the same complaint).

## Pain Point Extraction

For each candidate pain point found, record:

- **Problem statement** — a precise, neutral description of the pain point, written from the evidence, not paraphrased into something more general than what was actually said.
- **Direct quote(s)** — the actual text expressing the pain point, not a summary.
- **Context** — which product launch it appeared under, and whether it's a user comment or a maker reply (these carry different evidentiary weight — see Risk Analysis).
- **Distinct-instance check** — confirm this is an independent expression of the pain point, not a repeated comment from the same person across multiple launches.

## Evidence Collection

Every pain point or competitor-weakness entry must include:

- Direct permalink to the specific launch page (and comment, if the platform supports comment-level linking).
- Timestamp of the original comment or maker reply.
- Verbatim quoted text.
- Commenter identifier, and an explicit note of whether they are the product's maker, a user, or unidentified.

Do not record anything as evidence that cannot be independently re-checked at the link provided. If a piece of context is inferred rather than stated, label it explicitly as inference, separate from the quoted evidence itself.

## Recurring Complaint Tracking

- Track pain points by a consistent problem label across different product launches, so the same underlying complaint appearing under multiple unrelated launches in a category is recognized as recurring, not logged as isolated feedback on a single product.
- Record each new instance with its own link, date, and commenter — recurrence is the count of independent instances across different launches/commenters, not the count of comments on one launch.
- Log the observation window and the category/tags covered alongside recurrence counts, since Product Hunt's relevant launch volume in any given category can be sparse or bursty.

## Competitor Tracking

Product Hunt is the primary competitor-discovery source among MarketRadar's initial candidate sources — treat this section with particular care:

- Catalog every distinct product found in a relevant category, with its stated feature set, launch date, and current (at time of collection) upvote/comment count, regardless of whether it drew any criticism — a competitor's existence itself is relevant evidence, not just its flaws.
- Where a specific weakness is stated (by a user or conceded by a maker), capture it verbatim with its own link, logged separately from the general pain point evidence so it stays independently traceable to that exact product and comment.
- Maker-conceded weaknesses are unusually strong evidence (a maker has no incentive to overstate their own product's flaws) — flag these distinctly from user-alleged weaknesses, which are more prone to individual bias or a single bad experience.
- Do not assume a product's category or tags fully describe what it does — read the actual description before concluding it is or isn't a real competitor to a given pain point.

## Market Scoring

Do not assign a market attractiveness score from Product Hunt research alone, and do not use [IDEAS.md](../IDEAS.md) for this purpose — that framework evaluates candidate features for MarketRadar the product, not the market opportunities its research surfaces (see IDEAS.md's own scope note). Product Hunt research instead contributes raw inputs (competitor catalog, stated weaknesses, willingness-to-pay signal) toward MarketRadar's future market-attractiveness capability, which combines evidence across sources — see [ROADMAP.md](../ROADMAP.md) Milestone 5.3. Until that capability exists, do not compute or imply a score. Note that Product Hunt's audience and launch volume skew toward consumer/prosumer software and English-language, tech-forward products — categories with little Product Hunt presence should not be read as "no competition exists," only as "no competition found on this source."

## Risk Analysis

Known risk factors specific to Product Hunt as a source:

- **Launch-day bias** — comment activity and sentiment on launch day are shaped by the maker's own outreach to friends, existing users, and communities, and may not represent broader or later opinion; where possible, revisit a product's comment section well after launch day to see if later, less-curated feedback differs.
- **Comment relationship to maker** — some early comments come from people connected to the maker (friends, colleagues, existing customers invited to support the launch); read comments for signs of this rather than treating all comments as neutral outside feedback.
- **Sparse or absent competition ≠ validated absence** — a category with few or no Product Hunt launches may simply mean the category isn't well represented on this specific platform, not that no competitors exist; cross-check against other sources before concluding a space is "underserved."
- **Rapid catalog churn** — products can be relaunched, rebranded, or discontinued; note the collection date on every competitor entry so later discrepancies are understood as source drift, not a data-integrity issue.

## Confidence Score

Apply the confidence taxonomy defined in [ROADMAP.md](../ROADMAP.md) Milestone 0.3 once it exists. Until that taxonomy is written, do not assign ad hoc confidence labels — leave this field as `[Pending taxonomy — see ROADMAP.md Milestone 0.3]` rather than inventing a scale here that would conflict with the eventual project-wide standard. Maker-conceded weaknesses and clearly-neutral user comments should generally register as stronger evidence than comments with an apparent maker/promoter relationship — but the specific tiering must follow the taxonomy once it exists, not an ad hoc judgment made here.

## Source Links

Maintain a running, deduplicated list of every source link cited in this research area, so the full evidence trail can be reviewed independently of the narrative findings above it.

```
[Not yet collected]
```

## Validation Checklist

Before a Product Hunt–derived pain point or competitor entry is considered ready to feed into MarketRadar's evidence base, confirm:

- [ ] Every quote links to the specific launch page (and comment, where linkable).
- [ ] Each competitor entry notes its feature set, launch date, and collection date.
- [ ] Every stated weakness is labeled as either maker-conceded or user-alleged, not left ambiguous.
- [ ] Recurrence count reflects independent commenters/launches, not repeated comments from the same person.
- [ ] Where a category shows no competitors found, the write-up says "not found on Product Hunt," not "no competitors exist."
- [ ] The observation window (dates, categories/tags/search terms used) is recorded alongside the findings.

## Weekly Summary Format

```
### Product Hunt Weekly Summary — Week of [YYYY-MM-DD]

**Categories/tags/search terms covered:** [list]
**New pain points identified:** [count, with links to full entries]
**New or updated competitor catalog entries:** [count, with links]
**New maker-conceded weaknesses found:** [list, with links]
**Notable single findings worth flagging:** [any unusually strong or unusually weak evidence worth a human's attention]
**Collection issues/gaps:** [anything that limited this week's collection]
```

## Monthly Trend Format

```
### Product Hunt Monthly Trend — [Month YYYY]

**Total distinct pain points tracked this month:** [count]
**Competitor catalog size for tracked categories:** [count, with net change vs. prior month — new entrants, relaunches, apparent discontinuations]
**Pain points with increasing instance frequency vs. prior month:** [list — directional only, not a formal growth claim until ROADMAP.md Phase 5 growth-detection capability exists]
**New categories/tags added to coverage:** [list]
**Source-specific risk events this month:** [e.g., a category becoming saturated with new launches, a major relaunch/rebrand affecting a tracked competitor]
```

## Important Observations

*[Not yet collected — record genuinely notable, source-level observations here as research happens (e.g., "maker replies to critical comments are consistently more informative than the comments themselves"), not individual pain-point findings, which belong in the evidence base itself.]*

## Open Questions

*[Not yet collected — record open methodological or source-specific questions here as they arise, e.g., "how should a relaunch of an existing product be treated in the competitor catalog — as a new entry or an update to the existing one?"]*
