# MarketRadar — Idea Backlog & Evaluation Framework

This file is not a list of things to build. It is an evaluation system for deciding, with discipline, whether something *should* be built — and a permanent record of every idea that has gone through that evaluation, including the ones that were rejected.

**Nothing gets implemented without going through this framework first.** Per [CLAUDE.md](./CLAUDE.md) §5, MarketRadar must never expand scope beyond what's documented in [PRD.md](./PRD.md) without the tradeoff being explicitly surfaced — this file is where that surfacing happens, on the record, before any feature work begins.

This applies to feature ideas about MarketRadar itself (the product), not to the pain points MarketRadar's research surfaces for founders — those belong in the product's own evidence store once it exists, not in this planning document.

---

## Why an Evaluation Framework, Not a List

A raw idea list rewards volume and enthusiasm. It answers "what could we build?" This project needs a tool that answers a harder question: "does this survive scrutiny?" — consistent with the project's core stance that Validation beats Assumptions and Evidence beats Opinions ([README.md](./README.md)).

Every idea entered here is scored on the same twelve dimensions, using the same scale, so that ideas can be compared honestly instead of on whichever was pitched most persuasively. An idea that scores well on excitement but poorly on evidence strength should lose to an idea that scores modestly across the board but is actually backed by something real.

---

## Scoring Dimensions

Each dimension is scored **1 (very weak) to 5 (very strong)**. A score is only valid if it's accompanied by a one-line justification — an unjustified number is not a score, it's a guess wearing a score's clothing.

1. **Problem Severity** — How painful is the underlying problem for the people who have it? (1 = mild annoyance, 5 = actively costs them money, time, or customers today.)
2. **Market Size** — How many people or businesses plausibly have this problem? (1 = a handful of anecdotes, 5 = a large, identifiable population.)
3. **Evidence Strength** — How solid is the evidence behind this idea specifically, not the general problem space? (1 = a hunch or a single conversation, 5 = multiple independent, citable sources.)
4. **Frequency** — How often does this pain point or need actually recur, based on evidence? (1 = a one-off mention, 5 = a constantly recurring complaint across sources and time.)
5. **Growth Trend** — Is the underlying problem or need growing, stable, or shrinking? (1 = shrinking or already fading, 5 = clearly and demonstrably growing.)
6. **Competition** — How crowded or well-served is this space already? (1 = many strong, well-funded incumbents, 5 = genuinely underserved.)
7. **Execution Difficulty** — How hard would this actually be to build and ship well, independent of technical risk? (1 = very hard / many moving parts, 5 = simple and self-contained.)
8. **Technical Risk** — How much genuine technical uncertainty is involved? (1 = relies on unproven or fragile techniques, 5 = well-understood, low-risk implementation path.)
9. **Revenue Potential** — Is there credible signal that this would generate revenue or otherwise justify the investment? (1 = no signal or actively unclear, 5 = strong, evidenced signal.)
10. **Founder Fit** — Does this align with the skills, resources, and focus actually available right now? (1 = far outside current capability or focus, 5 = squarely within it.)
11. **Long-Term Moat** — If this works, how defensible does it stay over time? (1 = trivially copyable, 5 = compounds in a way that's hard to replicate — e.g., accumulated evidence history.)
12. **Validation Status** — How much of this has actually been checked against reality versus reasoned about in the abstract? (1 = pure theory, 5 = directly validated with real users or real data.)

**A missing or "N/A" score is not the same as a low score — it means the evaluation is incomplete, and the idea cannot receive a Decision until every dimension has an actual score with justification.**

## Decision Categories

After scoring, every idea receives exactly one Decision:

- **Rejected** — Evaluated and explicitly not pursued. Stays documented, with reasoning, per the requirement that rejected ideas remain on record.
- **Watchlist** — Not rejected, but not actionable yet; usually waiting on more evidence, a dependency elsewhere in [ROADMAP.md](./ROADMAP.md), or a change in circumstances. Revisit when the blocking condition changes.
- **Needs More Evidence** — The idea is promising enough that the right next step is targeted validation (more research, a small test, a user conversation) before a real Decision can be made — not a "maybe," but a defined next action.
- **Approved for Deeper Validation** — Cleared this framework's evaluation and is ready to move toward planning/implementation, subject to the normal process in CLAUDE.md (plan before coding, stay within PRD scope, etc.). Being "Approved" here is not itself authorization to skip planning — it means the idea has earned the right to be planned.

There is no "Approved for direct implementation" category. Every idea, regardless of score, goes through planning before code, per [CLAUDE.md](./CLAUDE.md) §10.

## Entry Template

```
### [Idea Title]

**Submitted:** YYYY-MM-DD
**Submitted by:** [name/role]
**One-line description:** What this idea actually is, in plain language.

| Dimension | Score (1–5) | Justification |
|---|---|---|
| Problem Severity | | |
| Market Size | | |
| Evidence Strength | | |
| Frequency | | |
| Growth Trend | | |
| Competition | | |
| Execution Difficulty | | |
| Technical Risk | | |
| Revenue Potential | | |
| Founder Fit | | |
| Long-Term Moat | | |
| Validation Status | | |

**Decision:** [Rejected / Watchlist / Needs More Evidence / Approved for Deeper Validation]
**Reasoning:** Why this decision follows from the scores above — especially if the decision isn't the obvious average (e.g., one very low score that's disqualifying on its own, such as Evidence Strength).
**Revisit condition:** (for Watchlist / Needs More Evidence only) — what specifically would change this evaluation.
```

---

## Active Backlog

*No ideas have been submitted and evaluated yet — this is a brand-new project. This section will hold ideas with a Decision of Watchlist, Needs More Evidence, or Approved for Deeper Validation, using the template above. Do not pre-populate this section with invented ideas; an idea only belongs here once someone has actually proposed it and it has gone through real (not illustrative) scoring.*

---

## Rejected Ideas Log

*No ideas have been rejected yet. When an idea is rejected, move its full entry here rather than deleting it — the reasoning behind a rejection is often as valuable as the idea itself, especially if a similar idea resurfaces later and someone needs to know it was already considered.*

---

## Illustrative Example (Not a Real Evaluated Idea)

The example below exists only to show what a completed entry looks like end to end. It is clearly fictional and must not be treated as a real backlog item, cited as evidence of anything, or counted toward the project's actual idea pipeline.

```
### [EXAMPLE] Auto-generated weekly digest email of top new pain points

**Submitted:** 2026-07-29
**Submitted by:** Example only — illustrative
**One-line description:** Email pilot users a weekly summary of newly-surfaced, high-confidence pain points instead of requiring them to check the product.

| Dimension | Score (1–5) | Justification |
|---|---|---|
| Problem Severity | 2 | Convenience feature, not solving a new pain point on its own. |
| Market Size | N/A | Not independently evaluable — depends entirely on the size of the existing user base. |
| Evidence Strength | 1 | No evidence yet that users want this specific delivery mechanism versus checking in-product. |
| Frequency | N/A | Not applicable to a feature idea in this form. |
| Growth Trend | N/A | Not applicable. |
| Competition | N/A | Not a market-facing idea in itself. |
| Execution Difficulty | 4 | Straightforward if the underlying alerting capability (ROADMAP.md Milestone 4.3) already exists. |
| Technical Risk | 4 | Low — well-understood mechanism. |
| Revenue Potential | 2 | Plausible retention benefit, no direct evidence. |
| Founder Fit | 4 | Within current focus and capability. |
| Long-Term Moat | 1 | Trivially copyable; no defensibility on its own. |
| Validation Status | 1 | Purely theoretical at this point — no user has asked for this. |

**Decision:** Needs More Evidence
**Reasoning:** Several dimensions are marked N/A because this is a delivery-mechanism idea layered on top of a capability (Milestone 4.3 alerting) that doesn't exist yet — evaluating it in isolation, before that dependency exists and before any user has expressed a preference for this delivery format, would produce a hollow score. Illustrates why some ideas should wait on a dependency rather than be forced through a premature Decision.
**Revisit condition:** Once Milestone 4.3 (Emerging Pain Point Alerting) exists and pilot users have given feedback on preferred delivery format.
```
