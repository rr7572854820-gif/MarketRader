# Research Template — Competitor Tracking

This is a reusable template and process guide, not a data file. It defines how competitor tracking should be conducted so that every researcher (human or Claude) produces evidence in the same, comparable, auditable format. Do not fill this file with invented example findings — leave sections empty or marked `[Not yet collected]` until real research happens, per [CLAUDE.md](../CLAUDE.md)'s non-fabrication rules, which apply to research process documents exactly as they apply to the product itself.

Findings produced using this template feed directly into MarketRadar's evidence base (see [PRD.md](../PRD.md) §8 for MVP evidence requirements) and must meet the same bar: every claim traceable to a real, linkable source. **Never hallucinate a competitor** — see [CLAUDE.md](../CLAUDE.md) §5. Every entry in this file must correspond to a real, verifiable company or product.

Unlike the other research templates in this directory, this file is not tied to a single discovery source — it is where competitor information *discovered* via Reddit, Hacker News, Product Hunt, GitHub, or direct investigation gets consolidated, cross-referenced, and kept current over time.

---

## Purpose

Maintain an accurate, current, evidence-backed record of who already serves a given problem space, so MarketRadar can identify existing competitors (PRD §6) and surface documented weaknesses in their offerings, without ever inventing or assuming a competitor's existence, features, or flaws.

## Where Data Comes From

- Competitor mentions surfaced in other research templates ([reddit.md](./reddit.md), [hackernews.md](./hackernews.md), [producthunt.md](./producthunt.md), [github.md](./github.md)) — this file consolidates those, it does not duplicate their primary collection process.
- Direct investigation of a named competitor's own public materials: their website, public pricing page, public changelog, public documentation, and public review-platform presence (e.g., a G2 or Capterra listing, once those sources are in scope per [ROADMAP.md](../ROADMAP.md) Phase 3+).
- Only publicly available information. Do not access gated demos, private pricing, or any content requiring an account relationship with the competitor beyond what a normal prospective customer could see, and respect the terms of service of any site visited (see [PRD.md](../PRD.md) §13).

## How Information Should Be Collected

1. A competitor entry is created only once a real, named product or company has been identified through actual research — never pre-populate this file with companies believed to exist in a space "probably."
2. For each competitor, visit their current public website/product pages directly to confirm basic facts (what they claim to do, stated pricing if public, stated target customer) rather than relying solely on how they were described in a secondhand source.
3. Record the collection date for every fact captured — competitor offerings, pricing, and positioning change, and a stale fact presented as current is a form of inaccuracy.
4. Cross-reference: if the same competitor is mentioned across multiple source templates, consolidate those mentions into the single entry for that competitor here, with each underlying source link preserved.

## Signals to Look For

- A named competitor's own stated limitations (e.g., an explicit "not supported yet" in their documentation or changelog).
- Independent user complaints about the competitor found in other research templates.
- Public pricing that indicates a gap (e.g., a feature or tier that leaves a segment of the market underserved or overpaying).
- Recent changelog entries indicating active investment (or a lack of one) in a relevant area — a competitor's own changelog is direct evidence of where they are and aren't investing.
- Signs of the competitor's own trajectory: acquisitions, shutdowns, major pivots — all directly relevant to whether a space is actually as "served" as it might first appear.

## Pain Point Extraction

Competitor tracking does not originate pain points on its own — pain points are extracted from the discovery-source templates. This section instead governs how a competitor entry connects back to the pain point(s) it's relevant to:

- Every competitor entry must link to the specific pain point entr(ies) it relates to, using the pain-point labels established in the relevant discovery-source template.
- Where a competitor appears to address a pain point only partially, state specifically which part is addressed and which isn't, rather than a binary "solves it" / "doesn't solve it" judgment.

## Evidence Collection

Every competitor entry must include:

- Product/company name and current public URL.
- Direct links to every source (from any research template, or from direct investigation) that contributed a fact to this entry.
- Timestamp/collection date for every individual fact (not just one date for the whole entry — pricing might be checked on a different date than the changelog, for instance).
- Verbatim quotes for any stated weakness, limitation, or user complaint — not paraphrases.

Do not record anything as evidence that cannot be independently re-checked at the link provided. If a judgment is being made (e.g., "this competitor appears to be targeting enterprise, not SMB"), label it explicitly as inference, separate from the sourced facts it's based on.

## Recurring Complaint Tracking

- For each tracked competitor, maintain a running list of independently-sourced complaints about them, deduplicated the same way pain points are deduplicated in the discovery-source templates (same underlying complaint from different people/sources counts as recurring; the same person's complaint appearing in two places counts once).
- Note the observation window over which each complaint was gathered, since a competitor's product changes over time and an old complaint may no longer be accurate.

## Competitor Tracking

This entire file is the competitor tracking process; the specific entry format is:

```
### [Competitor Name]

**URL:** [current public URL]
**First identified:** [YYYY-MM-DD, and via which source/template]
**Last reviewed:** [YYYY-MM-DD]

**What they claim to do:** [from their own public materials, with link and date]
**Stated pricing (if public):** [with link and date, or "not public" if not disclosed]
**Relevant pain point(s) addressed:** [links to pain point entries in discovery-source templates]
**Extent of coverage:** [which part of the pain point they address, and which part, if any, they don't — evidenced, not assumed]

**Documented weaknesses:**
- [Verbatim quote] — [source link] — [date]
- [Verbatim quote] — [source link] — [date]

**Recent activity (changelog, funding, notable news):** [with links and dates — only include what's directly sourced]

**Confidence in this profile:** [Pending taxonomy — see ROADMAP.md Milestone 0.3]
```

## Market Scoring

Do not assign a market attractiveness score from this file alone, and do not use [IDEAS.md](../IDEAS.md) for this purpose — that framework evaluates candidate features for MarketRadar the product, not the market opportunities its research surfaces (see IDEAS.md's own scope note). Competitor density and documented weaknesses are instead one of several inputs toward MarketRadar's future market-attractiveness capability (see [ROADMAP.md](../ROADMAP.md) Milestone 5.3), combined with recurrence, growth trend, and willingness-to-pay signal from the discovery-source templates. Until that capability exists, do not compute or imply a score. A crowded field with well-documented weaknesses in every incumbent is a very different situation from a crowded field with no documented weaknesses at all — this file's job is to make that distinction visible with evidence, not to render a verdict on its own.

## Risk Analysis

Known risk factors specific to competitor tracking:

- **False completeness** — a short competitor list is easy to misread as "few competitors exist" when it may simply mean research hasn't found the rest yet; every competitor list in this file should be treated as "competitors found so far," never as an exhaustive market map, unless the entry explicitly states the search was exhaustive and how.
- **Staleness** — competitor offerings, pricing, and positioning change; an entry not reviewed recently should be flagged as potentially outdated rather than presented with unwarranted current-tense confidence.
- **Self-reported information bias** — a competitor's own website and marketing materials describe themselves in the best possible light; weigh self-reported claims about what they do differently from independently-sourced user complaints about what they actually deliver.
- **Survivorship bias in "documented weaknesses"** — actively-discussed competitors will naturally accumulate more visible complaints than quiet, less-discussed ones, which can make a well-known competitor look weaker on paper than a lesser-known one that's just as flawed but less talked about; do not conclude a quiet competitor has fewer weaknesses just because fewer have been documented yet.
- **Hallucination risk** — this is the single highest-risk file in the research directory for the "never hallucinate a competitor" rule; every entry must be traceable to real, checkable evidence that the company exists and does what's claimed, with no exceptions.

## Confidence Score

Apply the confidence taxonomy defined in [ROADMAP.md](../ROADMAP.md) Milestone 0.3 once it exists. Until that taxonomy is written, do not assign ad hoc confidence labels — leave this field as `[Pending taxonomy — see ROADMAP.md Milestone 0.3]` rather than inventing a scale here that would conflict with the eventual project-wide standard. At minimum, once the taxonomy exists, every competitor profile's confidence score should reflect how recently it was reviewed and how independently corroborated its documented weaknesses are.

## Source Links

Maintain a running, deduplicated list of every source link cited across all competitor entries in this file, so the full evidence trail can be reviewed independently of the entries above it.

```
[Not yet collected]
```

## Validation Checklist

Before a competitor entry is considered ready to feed into MarketRadar's evidence base, confirm:

- [ ] The competitor's existence and stated offering are confirmed via their own current public materials, not solely via a secondhand mention.
- [ ] Every documented weakness is a verbatim quote with its own link and date, not a paraphrase or an assumption.
- [ ] The entry links to the specific pain point(s) it relates to, with an explicit note of partial vs. full coverage.
- [ ] "Last reviewed" date is current, or the entry is explicitly flagged as potentially stale.
- [ ] Nothing in the entry states a competitor "probably" does or doesn't do something without a source — if it's not sourced, it's not in the entry.
- [ ] The list this entry belongs to is not implicitly presented as exhaustive unless the search process was genuinely exhaustive and that's stated.

## Weekly Summary Format

```
### Competitor Tracking Weekly Summary — Week of [YYYY-MM-DD]

**New competitors identified this week:** [list, with source]
**Existing competitor profiles updated this week:** [list, with what changed]
**New documented weaknesses found:** [list, with links]
**Pain points newly linked to a competitor this week:** [list]
**Collection issues/gaps:** [anything that limited this week's collection]
```

## Monthly Trend Format

```
### Competitor Tracking Monthly Trend — [Month YYYY]

**Total competitors actively tracked this month:** [count, by problem space if useful]
**New entrants this month:** [list]
**Apparent exits/shutdowns/major pivots this month:** [list, with source]
**Problem spaces with no tracked competitors found yet:** [list — explicitly labeled as "none found," not "none exist"]
**Problem spaces with the most densely documented weaknesses:** [list — useful signal for where a gap may be real and well-evidenced, not just assumed]
```

## Important Observations

*[Not yet collected — record genuinely notable, cross-cutting observations here as research happens (e.g., "incumbents in this space consistently under-invest in X, based on changelog review across N competitors"), not individual competitor facts, which belong in the entries above.]*

## Open Questions

*[Not yet collected — record open methodological or source-specific questions here as they arise, e.g., "how should an acquired competitor be represented once it's absorbed into an acquirer's product line — as closed, or as merged into a new entry?"]*
