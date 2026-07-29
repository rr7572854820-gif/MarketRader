# MarketRadar — Product Requirements Document

**Status:** Draft — Pre-MVP
**Owner:** Founder
**Last updated:** 2026-07-29

---

## 1. Executive Summary

MarketRadar is an AI-powered market intelligence platform that discovers real, evidence-backed business pain points by analyzing public conversations — reviews, complaints, feature requests, discussions, and trend signals — across the internet.

It exists to answer a question founders currently answer badly: *what problem is worth solving?* Today that question is usually answered with intuition, anecdote, or an idea-generation tool that produces plausible-sounding fiction. MarketRadar answers it with sourced evidence: a specific pain point, tied to specific public conversations, assessed for how often it recurs, whether it is growing, who already serves it, where those solutions fall short, and what signal exists about willingness to pay.

MarketRadar is a research tool, not an idea generator, and not a decision-maker. It surfaces and organizes evidence; the founder still decides what to build. Its value is measured by how much validated research it can hand a founder before they write a single line of code — and by how honestly it communicates the limits of what the evidence actually shows.

This document defines the product's problem space, users, scope, principles, and success criteria. It intentionally does not define architecture, technology choices, or a delivery roadmap — those are separate, later decisions.

---

## 2. Problem Statement

Founders — first-time and repeat alike — routinely commit months or years to building products before they have real evidence that the underlying problem is painful, common, growing, or underserved.

This happens for structural reasons, not carelessness:

- **The evidence is real but scattered.** People describe their problems constantly — in reviews, support forums, GitHub issues, Reddit threads — but no single one of these sources gives a complete picture, and no person has time to read across all of them.
- **Pattern recognition at this scale exceeds human capacity.** A single painful, recurring, growing problem might be visible only as a faint, repeated signal spread across hundreds of unrelated conversations over months. Humans are good at noticing a single vivid complaint; they are bad at noticing weak, distributed, longitudinal signal.
- **Existing tools optimize for the wrong output.** Idea-generation tools produce a large volume of plausible ideas with no evidence trail. They optimize for inspiration, not for truth, and they cannot be trusted to tell a founder when they don't actually know something.
- **Competitive and pricing reality is discovered too late.** Founders frequently learn "there are already five well-funded companies solving this" or "nobody has ever paid for this" only after significant time has been invested, because that research is tedious and easy to skip or do superficially.

The result is a systemic misallocation of founder time and capital toward problems that were never validated to begin with — not because founders are unwilling to validate, but because rigorous validation, done manually, does not scale to the number of problem candidates a founder should reasonably consider.

---

## 3. Target Users

MarketRadar has one primary user type at MVP, with two adjacent user types expected to matter later.

**Primary (MVP): Early-stage founders and indie hackers searching for a problem to solve.** These are people who have not yet committed to an idea, or who have a rough hypothesis and want to stress-test it against evidence before going further.

**Adjacent (post-MVP): Product managers and innovation teams at existing companies.** These users already have a product and a customer base; they use MarketRadar to scout adjacent problem spaces or to check whether a proposed feature addresses a problem with real, external evidence behind it, not just internal opinion.

**Adjacent (post-MVP): Investors and analysts.** These users want a sourced evidence trail behind a market thesis — either their own or a founder's — rather than relying solely on a pitch deck's framing.

MarketRadar's design should not compromise the rigor of the primary user's experience in order to accommodate the adjacent users prematurely. Serve the founder well first.

---

## 4. User Personas

### Persona 1 — "Searching Sam," the pre-idea founder
Sam left a stable job or is moonlighting nights and weekends, and has not yet settled on what to build. Sam has domain instincts but no structured way to test them. Sam's biggest risk is committing to the first idea that feels exciting rather than the one with the strongest evidence behind it. Sam needs MarketRadar to narrow a wide-open search space down to a shortlist of problems worth a closer look, each with a clear reason to believe it's real.

### Persona 2 — "Committed Chris," the founder validating one specific bet
Chris already has a working hypothesis — often from personal frustration with an existing tool — and wants to know: is this problem bigger than just me? Is it growing? Who else is already solving it, and why are they failing? Would people actually pay for a better answer? Chris needs MarketRadar to either strengthen conviction with evidence or surface disqualifying facts (a dominant incumbent, no willingness to pay, a shrinking rather than growing need) before more time is sunk in.

### Persona 3 — "Scouting Priya," the PM at an existing company (post-MVP)
Priya is evaluating whether a proposed roadmap item solves a problem that shows up in the wild, independent of what internal stakeholders believe. Priya needs MarketRadar to corroborate or challenge an internal assumption with external, public evidence.

---

## 5. User Jobs-To-Be-Done

Framed as jobs, independent of any particular feature:

1. "When I don't know what to build, help me find problems that are real, recurring, and currently underserved — so I can stop guessing."
2. "When I have a hunch about a problem, help me find out if other people share it, and how many — so I know if it's bigger than just me."
3. "When I'm looking at a problem, tell me who already solves it and where they fall short — so I know if there's room for a better answer."
4. "When I'm considering a problem, tell me whether it's getting worse or better over time — so I don't build for a market that's disappearing."
5. "When I'm evaluating a problem, tell me what evidence exists about people's willingness to pay for a solution — so I don't mistake complaining for demand."
6. "When I'm given a conclusion, show me the evidence behind it and how confident I should be — so I can trust the research enough to act on it, or know when I shouldn't yet."

---

## 6. Goals

- Surface real, recurring business pain points from public sources, each backed by identifiable evidence.
- Distinguish problems that are growing from problems that are static or shrinking.
- Identify existing competitors or solutions addressing a given problem.
- Surface documented weaknesses or gaps in those existing solutions.
- Surface available signal on willingness to pay for a given problem.
- Present every conclusion alongside the evidence it rests on, and an honest confidence level.
- Reduce the time founders spend on manual, exploratory research, so more of their time goes to direct validation (talking to users, testing willingness to pay directly).

## 7. Non-Goals

- MarketRadar does not generate startup ideas, taglines, business plans, or pitch decks.
- MarketRadar does not build, design, or recommend specific product features or technical solutions to a discovered problem.
- MarketRadar does not make investment, funding, or go/no-go decisions on behalf of the user. It informs judgment; it does not replace it.
- MarketRadar does not guarantee that a surfaced problem is a viable business — market attractiveness signal is an input to the founder's judgment, not a verdict.
- MarketRadar is not a general-purpose social listening, brand monitoring, or customer support analytics tool, even though it may share underlying techniques with such tools.
- At MVP, MarketRadar does not attempt full coverage of every source listed in its long-term vision. Breadth of source coverage is explicitly deferred.

## 8. MVP Definition

The MVP's purpose is to prove the core evidence loop end to end, on a narrow slice of sources, with high trustworthiness, rather than to prove broad coverage.

**In scope for MVP** (in outcome terms, not implementation terms):

- Discovery of recurring pain-point signals from a small, deliberately limited set of public sources — chosen for signal quality and access feasibility, not for maximum breadth.
- For each discovered pain point: a clear statement of the problem, the number and nature of supporting instances, and direct links back to the original public source material.
- A basic view of whether a pain point is recurring over the observed time window, based only on the sources actually analyzed.
- A basic identification of existing solutions or competitors mentioned in connection with the pain point, where such mentions exist in the source material.
- Explicit, visible confidence labeling on every conclusion, distinguishing well-supported findings from weakly-supported ones.
- Clear separation, in every output, between what is directly evidenced and what is the system's own inference or assumption.

**Explicitly out of scope for MVP:**

- Broad multi-source aggregation across the full long-term source list.
- Automated willingness-to-pay estimation beyond directly quoted, explicit signal in source material (e.g., no modeled/estimated pricing without a stated source).
- Team collaboration features, workspaces, or multi-user accounts.
- Any form of automated outreach, publishing, or action taken on a founder's behalf.
- Long-term historical trend modeling beyond what the initially chosen sources support.

The MVP is successful if a founder can go from "I don't know what to build" or "is my hunch real" to a shortlist of evidence-backed problems, each traceable to real public conversations, in a fraction of the time manual research would take — without MarketRadar ever presenting an invented or unsupported claim as fact.

## 9. Long-Term Vision

MarketRadar's long-term destination, elaborated in [README.md](./README.md), is to become the default research assistant founders consult before committing to an idea — expanding source coverage over time (toward sources such as Reddit, Hacker News, Product Hunt, GitHub, G2, Capterra, X, LinkedIn, YouTube, Discord, blogs, news, forums, documentation, and changelogs), deepening its analysis (stronger growth detection, more rigorous competitive-gap analysis, better willingness-to-pay estimation), and eventually serving adjacent users like internal product teams and investors — always without compromising the evidentiary rigor established at MVP.

Growth in MarketRadar's capability should be sequenced by where it most improves the trustworthiness and completeness of evidence, not by which integration is easiest to build next. That sequencing is a future planning exercise and is intentionally not specified in this document.

## 10. Product Principles

- **Evidence is the product.** Every feature exists in service of stronger, clearer, more traceable evidence — not in service of more output volume.
- **Silence is better than fabrication.** When evidence is insufficient to support a conclusion, MarketRadar says so rather than filling the gap with a plausible-sounding guess.
- **Confidence is earned and shown.** Every conclusion carries a visible indication of how strong the underlying evidence is.
- **Assumptions are labeled as assumptions.** The system must never let inference silently masquerade as fact.
- **Depth before breadth.** A small number of sources analyzed rigorously outperforms a large number analyzed shallowly.
- **The founder decides.** MarketRadar's job ends at presenting well-reasoned, well-sourced findings. It does not tell founders what to build.

## 11. Success Metrics

Success should ultimately be judged by whether MarketRadar changes founder behavior for the better, not by system throughput. Candidate categories of measurement (specific targets and instrumentation are a later decision, not part of this document):

- **Evidence integrity:** rate of conclusions traceable to real, checkable public sources; near-zero incidence of fabricated or hallucinated evidence, competitors, or statistics.
- **Research time saved:** time from "no idea" or "one hunch" to a defensible, evidence-backed shortlist, compared to manual baseline research.
- **Founder trust and follow-through:** whether founders act on MarketRadar's findings by conducting further direct validation (e.g., user interviews) rather than discarding or distrusting the output.
- **Honest uncertainty:** rate at which MarketRadar correctly flags low-confidence findings as low-confidence, rather than overstating certainty.
- **Signal quality over time:** whether problems MarketRadar identifies as "growing" are borne out by continued observation, and whether ones it flags as weak or shrinking are not later regretted.

## 12. Risks

- **Fabrication risk.** The single largest risk to MarketRadar's value proposition is any instance of invented evidence, hallucinated competitors, or fabricated statistics — this would undermine the entire premise of the product, not just one output.
- **Source access and terms-of-service risk.** Many valuable sources (review platforms, social networks) restrict automated access; source selection must respect platform terms and applicable law, which will materially constrain coverage, especially early on.
- **Signal quality risk.** Public conversation data is noisy; enthusiasm, sarcasm, one-off venting, and coordinated or inauthentic activity (e.g., brigading, astroturfed reviews) can all be mistaken for genuine, recurring pain if not handled carefully.
- **Survivorship and visibility bias.** Problems that are painful but discussed in private (e.g., enterprise contexts, non-English-language communities, offline conversations) will be systematically underrepresented relative to problems that happen to be discussed loudly in public, English-language, indexed forums.
- **Over-trust risk.** Founders may treat MarketRadar's output as a guarantee of business viability rather than as research input, especially if confidence signaling is not made sufficiently prominent and legible.
- **Staleness risk.** Public conversation trends shift; a "growing problem" finding has a shelf life, and presenting it without a timestamp or freshness indicator risks misleading users later.
- **Competitive replication risk.** The core technique (aggregating and analyzing public sentiment) is not proprietary; durable advantage must come from evidentiary rigor, trustworthiness, and depth of historical signal, not from access to any single source alone.

## 13. Constraints

- MarketRadar may only use publicly accessible information and must operate within the terms of service of any source it draws from, and within applicable law (including data protection and platform-access regulations).
- MarketRadar must never present AI-generated inference as though it were directly observed evidence.
- The MVP is constrained to a small set of sources by design, not by a temporary technical limitation — this is a deliberate scope choice described in Section 8, not a gap to be immediately filled.
- This document does not authorize any specific technology, architecture, or vendor choice; those decisions are out of scope here by design.

## 14. Assumptions

- Founders who are earlier in their search are more receptive to evidence-led discovery than founders who are already emotionally committed to an idea; the product should serve both, but expect different behavior from each.
- Sufficient publicly available signal exists, within the constraints above, to detect real recurring pain points without needing private or proprietary data sources at MVP.
- A meaningfully large population of founders currently make problem-selection decisions with materially insufficient evidence, and would change behavior if better evidence were easy to obtain.
- Confidence/uncertainty signaling, if made clear and prominent, will be respected by users rather than ignored in favor of the headline conclusion.

These are assumptions, not established facts, and should be revisited as the product is used in the real world.

## 15. Open Questions

- Which initial sources offer the strongest evidence-to-effort ratio for the MVP, given access constraints described in Section 13? (A sourcing decision, deliberately deferred from this document.)
- How should "growing" versus "recurring but stable" be distinguished responsibly, given that most public sources do not provide clean historical baselines?
- What is the right way to communicate confidence/uncertainty so that it is actually read and internalized by users, rather than skipped past to the headline finding?
- How should MarketRadar handle problem spaces where evidence is abundant but solution-worthiness is genuinely ambiguous (e.g., real pain, but a fundamentally unprofitable market)?
- At what point, if any, should MarketRadar move from purely descriptive market-attractiveness signal toward any form of scoring or ranking — and what are the risks of doing so prematurely?
- How should the product handle non-English-language sources and communities, both for coverage and for avoiding systematic blind spots?

These questions are intentionally left open; answering them is future scoping and planning work, not part of this document.

## 16. Future Expansion

Consistent with the long-term vision in [README.md](./README.md), future expansion is expected along several dimensions, sequenced by future planning work rather than by this document:

- **Source breadth:** incorporating additional public sources over time as access, quality, and evidentiary value justify each addition.
- **Analytical depth:** stronger trend/growth detection, more rigorous competitive gap analysis, and more defensible willingness-to-pay signal extraction.
- **User breadth:** extending support toward adjacent users such as internal product teams and investors, without diluting the rigor the primary founder user depends on.
- **Longitudinal value:** as MarketRadar observes the same problem spaces over longer periods, its ability to distinguish genuine trends from noise should compound — this is a structural long-term advantage, not an MVP capability.

---

*This document intentionally excludes architecture, technology stack, implementation planning, and roadmap sequencing. Those are separate deliverables to be produced later, once the requirements captured here are reviewed and agreed upon.*
