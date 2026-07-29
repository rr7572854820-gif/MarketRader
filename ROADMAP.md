# MarketRadar — Roadmap

This roadmap sequences MarketRadar's work into small, independently buildable milestones, each of which delivers real value on its own rather than being a fragment that only matters once a later milestone ships.

This document does not specify architecture, technology choices, or implementation details — see [CLAUDE.md](./CLAUDE.md) §6 for why those are deliberately deferred. It also does not commit to calendar dates; complexity and dependency order are given instead, because at this stage duration estimates would be false precision. Scope boundaries here must stay consistent with [PRD.md](./PRD.md) — if a milestone description ever seems to expand scope beyond the MVP definition (PRD §8) or long-term vision (PRD §9, §16), the PRD wins and this document should be corrected.

**How to read each milestone:**
- **Goal** — what this milestone accomplishes, in outcome terms.
- **Why it matters** — the reason this is worth doing now, not just eventually.
- **Expected outcome** — the concrete, checkable thing that exists once this milestone is done.
- **Dependencies** — what must already be true or already exist.
- **Estimated complexity** — Low / Medium / High, a relative judgment of effort and uncertainty, not a time estimate.
- **Potential risks** — what could make this milestone harder, slower, or less valuable than expected.
- **Definition of Done** — the checklist that must be true before the milestone is considered complete (in addition to, not instead of, [CLAUDE.md §14](./CLAUDE.md)'s project-wide Definition of Done).

---

## Phase 0 — Research

**Phase intent:** Before building anything, establish that the core premise is sound: that real, checkable pain-point evidence is findable in public sources, that a rigorous manual process can find it, and that founders actually want this. Phase 0 produces no software — it produces confidence (or disconfirmation) in the approach.

### Milestone 0.1 — Source Feasibility Assessment

- **Goal:** Produce a documented assessment of which public sources are realistically accessible (technically and legally) and likely to contain useful pain-point signal.
- **Why it matters:** PRD §13 requires that MarketRadar only use sources within their terms of service and applicable law. Committing to a source before checking this is a legal and trust risk, and discovering an access blocker late is expensive.
- **Expected outcome:** A short written assessment, per candidate source, covering access method availability, terms-of-service posture, and a rough judgment of signal density.
- **Dependencies:** None — this is the project's starting point.
- **Estimated complexity:** Low.
- **Potential risks:** Terms of service can be ambiguous or can change; a source that looks accessible today may not remain so.
- **Definition of Done:** Written assessment exists, covers at least the sources most likely to be chosen for MVP, and each source has an explicit access/legal verdict (not just a technical one).

### Milestone 0.2 — Manual Research Pilot (Single Source, No Tooling)

- **Goal:** By hand, without any software, pick one source and manually extract 10–20 real, cited pain points from it over a defined time window.
- **Why it matters:** This is the cheapest possible way to test whether the core hypothesis — that recurring, evidenced pain points are findable in public conversation — holds, before any engineering investment. It also produces a reference example of what "good evidence" looks like.
- **Expected outcome:** A small, real, fully-sourced set of pain-point write-ups, each linking back to original posts/threads/reviews.
- **Dependencies:** Milestone 0.1 (need a source cleared for use).
- **Estimated complexity:** Low.
- **Potential risks:** The chosen source may turn out to have thin or low-quality signal, which would be a valuable early finding, not a failure — but it means the source choice should be revisited before Phase 1.
- **Definition of Done:** At least 10 pain points documented, each with a direct source link, a description of the recurring problem, and a rough count of how many separate instances were observed.

### Milestone 0.3 — Evidence & Confidence Taxonomy

- **Goal:** Define, in writing, the vocabulary MarketRadar will use to classify evidence strength and confidence level, consistently, across every future output.
- **Why it matters:** PRD §10 requires that confidence be "earned and shown" on every conclusion. Without a shared, precise taxonomy defined up front, confidence labeling will be inconsistent and, eventually, meaningless.
- **Expected outcome:** A short reference document defining evidence types (e.g., direct quote, aggregated count, inferred pattern) and confidence tiers, with clear criteria for when each applies.
- **Dependencies:** Milestone 0.2 (the pilot will surface real edge cases that should inform the taxonomy, rather than defining it in the abstract).
- **Estimated complexity:** Medium — this is a small document, but getting the distinctions right requires real thought, not just labeling.
- **Potential risks:** An overly complex taxonomy will be ignored in practice; an overly simple one won't capture real differences in evidence quality. Both failure modes are easy to fall into.
- **Definition of Done:** Taxonomy is written down, was tested against the Milestone 0.2 pilot findings (each finding can be classified without ambiguity), and is referenced, not restated, by later work.

### Milestone 0.4 — Founder Problem-Interviews

- **Goal:** Talk to a small number of real founders (pre-idea or early-idea stage) about how they currently search for problems to solve, and whether the pain MarketRadar addresses is one they actually feel.
- **Why it matters:** PRD §14 lists an explicit assumption — that founders currently make problem-selection decisions with insufficient evidence and would change behavior given better evidence — that has not yet been tested against real people. Building on an untested assumption this central would be a direct violation of "Validation > Assumptions."
- **Expected outcome:** Notes from a handful of structured conversations, and an honest written judgment of whether the assumption holds, partially holds, or doesn't.
- **Dependencies:** None strictly, though it's most useful once Milestone 0.2's pilot output exists as something concrete to show and react to.
- **Estimated complexity:** Low complexity, but time- and relationship-dependent (finding willing founders to interview is the hard part, not the interview itself).
- **Potential risks:** Small sample size risk — a handful of conversations can mislead in either direction. Treat this as directional evidence, not proof, and say so explicitly in the findings.
- **Definition of Done:** At least 5 founder conversations completed and documented, with an explicit written conclusion about whether the core assumption is supported, and what would need to be true for MVP to be worth building.

---

## Phase 1 — MVP

**Phase intent:** Prove the core evidence loop end-to-end, on a single source, with a real founder able to use the output. This is the smallest version of MarketRadar that is actually MarketRadar, per PRD §8.

### Milestone 1.1 — Single-Source Pain Point Extraction

- **Goal:** Reliably extract candidate pain points, with source links, from the single source chosen and cleared in Phase 0.
- **Why it matters:** This is the foundational capability everything else in the product depends on. Without it working trustworthily, nothing downstream matters.
- **Expected outcome:** A repeatable process that turns raw content from the chosen source into a list of candidate pain points, each tied to specific source material.
- **Dependencies:** Phase 0 complete (source cleared, taxonomy defined, pilot process proven manually).
- **Estimated complexity:** Medium.
- **Potential risks:** The line between "genuine recurring pain point" and "one loud complaint" is easy to get wrong; extraction quality directly determines whether the rest of the product is trustworthy.
- **Definition of Done:** Extraction process runs against real source data and produces output a human reviewer agrees is accurate, for a defined evaluation sample.

### Milestone 1.2 — Evidence Linking & Confidence Labeling

- **Goal:** Every extracted pain point carries a direct link back to its source material and a confidence label per the Milestone 0.3 taxonomy.
- **Why it matters:** This is the single non-negotiable property of the entire product (README.md, CLAUDE.md §1). A version of MarketRadar without this is not MarketRadar — it's an idea generator with extra steps.
- **Expected outcome:** No pain point can exist in the system's output without an attached source reference and confidence label.
- **Dependencies:** Milestone 1.1, Milestone 0.3.
- **Estimated complexity:** Medium.
- **Potential risks:** Pressure to ship something that "looks complete" can create a temptation to soften this requirement for edge cases (e.g., weak or missing links) — this must be resisted per CLAUDE.md §5.
- **Definition of Done:** A sampled audit of outputs finds zero pain points without a working source link and an assigned confidence label.

### Milestone 1.3 — Recurrence Detection (Single Source)

- **Goal:** Distinguish pain points that recur across multiple distinct instances within the source from one-off complaints.
- **Why it matters:** PRD §8 defines "basic recurrence" as in-scope for MVP; a single complaint is an anecdote, not a signal, and the product's credibility depends on making that distinction visibly.
- **Expected outcome:** Each surfaced pain point shows how many separate instances support it within the observed window.
- **Dependencies:** Milestone 1.1.
- **Estimated complexity:** Medium.
- **Potential risks:** Near-duplicate complaints (same person posting twice, or reposts) can be miscounted as independent recurrence if not handled carefully.
- **Definition of Done:** Recurrence counts on a sample of outputs are manually verified as accurate against the underlying source material.

### Milestone 1.4 — Minimal Founder-Facing Shortlist

- **Goal:** Produce a simple, readable output that a founder can actually use — a shortlist of evidenced pain points, each with its supporting evidence, recurrence, and confidence visible together.
- **Why it matters:** This is the first point in the roadmap where a real user (Persona 1/2 from PRD §4) receives value. Everything before this was necessary but internal.
- **Expected outcome:** A founder can review a shortlist and understand, for each entry, what the evidence is, how strong it is, and where it came from — without needing anything explained to them.
- **Dependencies:** Milestones 1.1–1.3.
- **Estimated complexity:** Low (the hard work is upstream; this is presentation of already-trustworthy data).
- **Potential risks:** A poorly presented shortlist can undersell good evidence, or a well-designed one can oversell weak evidence — presentation must not distort the underlying confidence signal.
- **Definition of Done:** At least one real founder (ideally from the Milestone 0.4 interview pool) reviews the shortlist and confirms they understand what's evidenced versus inferred, without additional explanation.

### Milestone 1.5 — In-Source Competitor Mention Capture

- **Goal:** Where the source material itself mentions existing tools, products, or competitors in connection with a pain point, capture and surface those mentions.
- **Why it matters:** PRD §8 defines basic competitor identification as in-scope for MVP, and PRD §6 lists it as a core goal — but only from what's actually in the evidence, never invented (CLAUDE.md §5 — never hallucinate a competitor).
- **Expected outcome:** Where competitor mentions exist in source material, they appear alongside the relevant pain point with their own source link; where none exist, the shortlist says so rather than leaving an unexplained gap.
- **Dependencies:** Milestone 1.1.
- **Estimated complexity:** Low–Medium.
- **Potential risks:** Temptation to fill in "obvious" competitors from general knowledge rather than from the evidence itself — this must be explicitly refused, per CLAUDE.md §5.
- **Definition of Done:** Every competitor mention shown in output traces to a specific piece of source material; no competitor appears without one.

---

## Phase 2 — Validation

**Phase intent:** Test the MVP against real founders and real use, and rigorously check whether the product's central promise — trustworthy evidence — actually holds up under use, not just under internal review.

### Milestone 2.1 — Closed Pilot With Real Founders

- **Goal:** Put the MVP shortlist in front of a small, closed group of founders (ideally drawn from or similar to the Milestone 0.4 interview pool) and observe real usage.
- **Why it matters:** Internal review can confirm the product works as designed; only real usage can confirm it's actually useful.
- **Expected outcome:** Direct observation and feedback from a small set of real target users using real output.
- **Dependencies:** Phase 1 complete.
- **Estimated complexity:** Medium (logistics-heavy, not technically heavy).
- **Potential risks:** A pilot group that is too small, too friendly, or too similar to the founder's own network can produce falsely positive signal.
- **Definition of Done:** At least 5 founders have used the real output on a real problem-search question, and structured feedback has been collected from each.

### Milestone 2.2 — Trust & Action Feedback Loop

- **Goal:** Directly measure whether pilot users trust the findings enough to act on them (e.g., proceed to their own direct validation, like user interviews) versus disregarding the output.
- **Why it matters:** PRD §11 identifies "founder trust and follow-through" as a core success metric; this milestone is the first place that can actually be measured with real data.
- **Expected outcome:** A clear, honest account of how many pilot users took a real next step based on MarketRadar's output, and why or why not.
- **Dependencies:** Milestone 2.1.
- **Estimated complexity:** Low–Medium.
- **Potential risks:** Self-reported trust can diverge from actual behavior; where possible, prefer observing real follow-through over asking users to self-assess.
- **Definition of Done:** Follow-through outcomes documented for each pilot participant, with an honest written assessment — not just a summary statistic — of what's working and what isn't.

### Milestone 2.3 — Evidence Integrity Audit

- **Goal:** Systematically check a sample of the MVP's outputs against their cited sources to verify there is zero fabrication and that confidence labels are honest.
- **Why it matters:** PRD §12 names fabrication as the single largest risk to the entire product; this cannot be assumed to be true just because it was designed in — it must be actively checked.
- **Expected outcome:** An audit report with a clear pass/fail per sampled output, and root-cause analysis of any failure found.
- **Dependencies:** Phase 1 complete, ideally run in parallel with Milestone 2.1.
- **Estimated complexity:** Medium.
- **Potential risks:** Auditing your own system for a problem you don't want to find is a genuine bias risk; the audit should be adversarial in spirit — actively trying to find a fabrication, not confirming there isn't one.
- **Definition of Done:** A defined sample size (large enough to be meaningful, e.g., not fewer than 30 outputs) fully audited, zero tolerance for confirmed fabrication, and any confirmed issue has a documented fix before this milestone closes.

### Milestone 2.4 — Second Source Generalization Test

- **Goal:** Apply the same extraction, evidence-linking, and confidence process (built for one source in Phase 1) to a second, different source, without redesigning the approach from scratch.
- **Why it matters:** This is the first real test of whether the MVP's approach generalizes, or whether it was accidentally over-fit to the quirks of the first source — a critical thing to learn before committing to Phase 3's broader expansion.
- **Expected outcome:** A working answer to "does this approach hold on a second, structurally different source," with specifics on what needed to change and what didn't.
- **Dependencies:** Phase 1 complete, Milestone 0.1 (second source must already be cleared).
- **Estimated complexity:** Medium–High — genuinely uncertain until attempted.
- **Potential risks:** A second source with very different structure (e.g., long-form reviews vs. short threaded discussions) may reveal that core assumptions from Phase 1 don't transfer cleanly.
- **Definition of Done:** Second source produces evidenced, confidence-labeled pain points meeting the same bar as Milestone 1.2–1.3, and a written account exists of what generalized and what required source-specific handling.

---

## Phase 3 — Expansion

**Phase intent:** Grow source coverage and cross-source analytical depth deliberately, per the sequencing principle in PRD §9 — guided by evidentiary value, not ease of integration.

### Milestone 3.1 — Third and Fourth Source Onboarding

- **Goal:** Bring two more sources online, selected using the Milestone 0.1 feasibility framework and prioritized by expected evidentiary value.
- **Why it matters:** Broader coverage increases the range of problems MarketRadar can speak to with evidence — but only once Phase 2 has proven the approach is trustworthy enough to extend.
- **Expected outcome:** Two additional sources producing pain points to the same evidentiary standard as the first two.
- **Dependencies:** Phase 2 complete (validation and integrity audit passed).
- **Estimated complexity:** Medium per source, informed by what Milestone 2.4 learned about generalization.
- **Potential risks:** Each new source type can introduce its own signal-quality risks (see PRD §12 — noise, sarcasm, inauthentic activity); do not assume Milestone 2.4's learnings fully cover new source types.
- **Definition of Done:** Both sources pass the same integrity-audit bar established in Milestone 2.3.

### Milestone 3.2 — Cross-Source Pain Point Deduplication

- **Goal:** Recognize when the same underlying pain point appears across multiple sources and merge them into a single, stronger-evidenced entry rather than presenting duplicates.
- **Why it matters:** A pain point evidenced independently across sources is meaningfully stronger signal than the same count within one source — and presenting it as fragmented duplicates would understate that, while naively merging different problems would overstate it.
- **Expected outcome:** Pain points that genuinely recur across sources are shown as a single entry with combined evidence; genuinely distinct pain points remain distinct.
- **Dependencies:** Milestone 3.1 (need at least 3 active sources to make this meaningful).
- **Estimated complexity:** High — this is a genuinely hard judgment problem, not a mechanical merge.
- **Potential risks:** Over-eager merging can conflate superficially similar but substantively different problems, actively damaging evidence quality.
- **Definition of Done:** A sampled audit confirms merged pain points are genuinely the same underlying problem, and confidently distinct pain points are never incorrectly merged.

### Milestone 3.3 — Recurring Complaint Tracking Over Time

- **Goal:** Track a given pain point's presence across multiple observation windows, not just within a single snapshot.
- **Why it matters:** This is a prerequisite for any future growth-trend claim (Phase 5) and for the "recurring" half of PRD's core goals (§6) to mean something beyond a single point in time.
- **Expected outcome:** A pain point's evidence history is retained and viewable across time, not overwritten by each new observation.
- **Dependencies:** Milestone 3.1, Milestone 3.2 (dedup must exist first, or tracking over time will double-count).
- **Estimated complexity:** Medium.
- **Potential risks:** Without enough historical width yet, early trend data will be thin — this milestone should explicitly avoid presenting "trend" claims prematurely; that's Phase 5's job, once there's enough history to support it responsibly.
- **Definition of Done:** A pain point observed in two or more time windows shows its full evidence history, correctly attributed to each window.

### Milestone 3.4 — Competitor Gap Analysis (In-Evidence Only)

- **Goal:** For pain points with competitor mentions captured (building on Milestone 1.5), surface documented weaknesses or complaints about those competitors — again, only where the evidence itself states them.
- **Why it matters:** PRD §6 lists identifying weaknesses in existing solutions as a core goal; this is where that becomes real, still bound by the same non-fabrication rule.
- **Expected outcome:** Where source material documents a specific weakness of a named competitor, that weakness is surfaced with its own citation, next to the relevant pain point.
- **Dependencies:** Milestone 1.5, Milestone 3.1 (more sources increase odds of finding real competitor-weakness evidence).
- **Estimated complexity:** Medium.
- **Potential risks:** Highest fabrication-adjacent risk milestone so far — strong temptation to infer competitor weaknesses from general knowledge rather than require them to be evidenced; this must be resisted absolutely.
- **Definition of Done:** Every surfaced competitor weakness traces to a specific, checkable piece of source material; audit confirms zero inferred-but-unsourced weaknesses appear.

---

## Phase 4 — Automation

**Phase intent:** Reduce the manual effort required to keep MarketRadar's evidence base current, without weakening the trust properties Phases 0–3 established. Automation here means removing manual toil, not removing rigor.

### Milestone 4.1 — Scheduled Re-Ingestion

- **Goal:** Automatically re-check existing sources on a defined cadence, rather than requiring a person to manually trigger each refresh.
- **Why it matters:** "Recurring" and, later, "growing" claims depend on consistent, ongoing observation — manual, ad hoc refresh cycles introduce gaps that undermine both.
- **Expected outcome:** Sources are re-checked on a predictable schedule without manual intervention, and outages or failures in that process are visible, not silent.
- **Dependencies:** Phase 3 complete (multiple sources, deduplication and time-tracking already working).
- **Estimated complexity:** Medium.
- **Potential risks:** Automated ingestion that fails silently is worse than manual ingestion that a person notices has stopped — failure visibility must be designed in from the start of this milestone, not added later.
- **Definition of Done:** Re-ingestion runs on schedule for a sustained period without silent failures; any failure produces a visible, actionable signal.

### Milestone 4.2 — Automated Confidence Scoring

- **Goal:** Apply the Milestone 0.3 confidence taxonomy automatically and consistently, rather than requiring manual judgment on every new pain point.
- **Why it matters:** Manual confidence-labeling does not scale with Phase 4's increased ingestion frequency and Phase 3's multi-source volume; but automating this is high-stakes, since it directly governs whether output is honest.
- **Expected outcome:** New pain points receive a confidence label automatically, matching what a careful human applying the same taxonomy would assign.
- **Dependencies:** Milestone 0.3, Milestone 4.1, a validated track record of manual labeling to check automated labeling against.
- **Estimated complexity:** High.
- **Potential risks:** This is one of the highest-risk milestones in the whole roadmap for silently drifting from the taxonomy's intent over time; ongoing spot-checking against manual judgment should continue well past this milestone's initial completion.
- **Definition of Done:** Automated labels match careful manual labels on a held-out evaluation sample at a rate the team is genuinely comfortable relying on, with disagreements analyzed and understood, not just tolerated.

### Milestone 4.3 — Emerging Pain Point Alerting

- **Goal:** Surface newly-recurring pain points to relevant users as they cross a meaningful evidence threshold, rather than requiring users to manually re-check for new findings.
- **Why it matters:** This turns MarketRadar from a tool a founder has to remember to check into one that proactively brings evidence to them — a meaningful step toward the long-term vision (README.md).
- **Expected outcome:** Users receive a notification (through whatever channel is later decided — out of scope here) when a pain point newly crosses a defined recurrence/confidence threshold.
- **Dependencies:** Milestones 4.1, 4.2.
- **Estimated complexity:** Medium.
- **Potential risks:** Poorly tuned thresholds create alert fatigue (too noisy) or missed signal (too conservative); both need real tuning against real usage, not a one-time guess.
- **Definition of Done:** Threshold-crossing events reliably generate an alert, and a pilot group confirms the alerts are meaningful, not noisy, over a sustained period.

### Milestone 4.4 — Self-Serve Single-User Workspace

- **Goal:** Let a single founder independently run their own searches and review their own shortlist without requiring hands-on operator involvement.
- **Why it matters:** Every prior phase has likely required significant manual operator involvement to produce output for pilot users; this milestone is what makes MarketRadar usable as a standalone product rather than a service delivered by hand.
- **Expected outcome:** A founder can, unassisted, get evidence-backed output for a topic or question they care about.
- **Dependencies:** Milestones 4.1–4.3.
- **Estimated complexity:** Medium–High.
- **Potential risks:** Removing the human operator also removes a natural checkpoint that's been implicitly catching quality issues throughout earlier phases — extra care is needed to ensure the automated integrity checks (Milestone 2.3-style audits) are still happening without a person triggering them.
- **Definition of Done:** A new founder, with no prior involvement in the project, successfully uses the workspace unassisted and produces output they consider trustworthy and understandable.

---

## Phase 5 — Intelligence

**Phase intent:** Deepen analytical capability — growth detection, willingness-to-pay signal, market attractiveness — building on the time-series and multi-source foundation established in Phases 3–4. This phase is explicitly deferred past MVP (PRD §8) and should not be pulled forward.

### Milestone 5.1 — Growth Trend Detection

- **Goal:** Distinguish pain points that are growing in frequency/intensity over time from ones that are stable or declining, using the time-series data built up since Milestone 3.3.
- **Why it matters:** PRD's Open Questions (§15) explicitly flag that this must be done responsibly given weak historical baselines in most public sources; rushing this ahead of sufficient time-series depth would produce confident-sounding but unreliable trend claims — a direct violation of "Silence is better than fabrication."
- **Expected outcome:** A defensible, appropriately caveated growth/stable/declining classification for pain points with sufficient observation history.
- **Dependencies:** Milestone 3.3 sustained over a meaningful time period (this milestone cannot start on day one of Phase 5 — it requires the historical depth Phase 3–4 have been accumulating).
- **Estimated complexity:** High.
- **Potential risks:** The single greatest risk here is presenting a trend claim with false confidence because the underlying time window is still too short — this milestone's Definition of Done must include a check against exactly that.
- **Definition of Done:** Trend classifications are shown only where the underlying observation window meets a pre-defined minimum, classifications below that bar are explicitly labeled as insufficient data rather than guessed at, and a sample of classifications has been checked against independent judgment.

### Milestone 5.2 — Willingness-to-Pay Signal Extraction

- **Goal:** Systematically extract explicit, directly-stated willingness-to-pay signal from source material (e.g., a person stating they'd pay for a fix, or naming a price they already pay for a worse alternative).
- **Why it matters:** PRD §6 and Persona 2 (Chris) both need this to avoid "mistaking complaining for demand" — but PRD §8 is explicit that this must stay grounded in directly quoted signal, never modeled or estimated, even at this later stage.
- **Expected outcome:** Where willingness-to-pay signal exists in the evidence, it's surfaced with its citation; where it doesn't, the output says so rather than estimating a number.
- **Dependencies:** Phase 3–4 maturity (more sources and volume increase the odds of finding this relatively rare signal type).
- **Estimated complexity:** Medium–High.
- **Potential risks:** Strong product pressure to fill this gap with an estimated number when direct signal is sparse — must be resisted per the same non-fabrication principle that governs everything else.
- **Definition of Done:** Every willingness-to-pay signal shown traces to an explicit, quoted statement in source material; pain points without such signal are labeled as having none, not silently omitted or guessed at.

### Milestone 5.3 — Market Attractiveness Scoring

- **Goal:** Combine the existing evidence dimensions (recurrence, growth, competition, willingness-to-pay signal) into a single, transparent, explainable view of how attractive a given problem space looks.
- **Why it matters:** PRD's Open Questions (§15) explicitly ask when, if ever, MarketRadar should move toward scoring — this milestone is that moment, and it must be approached cautiously, since a single blended score risks obscuring the very evidence trail the product exists to provide.
- **Expected outcome:** A market-attractiveness view that a user can fully decompose back into its underlying, individually-sourced components — never a black-box number.
- **Dependencies:** Milestones 5.1, 5.2.
- **Estimated complexity:** High.
- **Potential risks:** Any scoring mechanism risks becoming the de facto "answer" that users stop questioning, undermining PRD §10's "the founder decides" principle — the design of this milestone must actively work against being over-trusted.
- **Definition of Done:** Every component of the score is independently visible and sourced, pilot users confirm they understand the score is decomposable evidence rather than a verdict, and low-confidence inputs visibly reduce confidence in the overall view rather than being silently absorbed into a falsely-precise number.

### Milestone 5.4 — Cross-Problem Comparison

- **Goal:** Let a user compare multiple evidenced problems against each other on the same dimensions, to support prioritization among several real candidates.
- **Why it matters:** Persona 1 (Sam)'s job-to-be-done is fundamentally about narrowing a wide search space — comparison is what makes a shortlist actually useful for decision-making, not just informative.
- **Expected outcome:** A user can view several problems side by side on evidence, recurrence, growth, competition, and willingness-to-pay signal.
- **Dependencies:** Milestone 5.3.
- **Estimated complexity:** Medium.
- **Potential risks:** Side-by-side comparison format can create implicit pressure toward false precision (e.g., ranking problems that shouldn't be strictly ordered given their different confidence levels) — comparison must preserve and display confidence differences, not flatten them.
- **Definition of Done:** Users can compare problems with differing confidence levels without the interface implying false equivalence between well-evidenced and weakly-evidenced entries.

---

## Phase 6 — Scale

**Phase intent:** Extend MarketRadar to the adjacent users and broader source coverage described in the long-term vision (README.md, PRD §3, §16), once the core product has proven durable value for its primary user.

### Milestone 6.1 — Multi-User / Team Workspaces

- **Goal:** Support more than one person collaborating around the same research (e.g., a small founding team, or a product team per Persona 3).
- **Why it matters:** PRD §3 explicitly defers multi-user support past the primary founder use case; this milestone is where that deferred need gets addressed, once single-user value is proven durable.
- **Expected outcome:** Multiple users can view and discuss the same evidenced findings within a shared context.
- **Dependencies:** Phase 4 (self-serve single-user product) proven durable in real use.
- **Estimated complexity:** Medium–High.
- **Potential risks:** Team features can quietly shift the product's center of gravity toward internal PM/enterprise workflows (Persona 3) at the expense of the primary founder experience (Personas 1–2) — PRD §3 explicitly requires serving the founder well first; this must be actively protected here.
- **Definition of Done:** A small team can collaborate on shared findings without any degradation to the single-user experience that came before it.

### Milestone 6.2 — Broad Source Coverage

- **Goal:** Extend source coverage toward the fuller long-term list in README.md (G2, Capterra, X, LinkedIn, YouTube comments, Discord, blogs, news, forums, documentation, changelogs), sequenced by evidentiary value as each becomes accessible.
- **Why it matters:** This is the literal fulfillment of the long-term vision's breadth ambition — but only once depth and trust have been established at every phase prior, per "Depth before breadth" (CLAUDE.md §2).
- **Expected outcome:** A meaningfully wider set of active sources, each held to the exact same evidentiary and integrity bar as the first ones.
- **Dependencies:** Phases 3–5 patterns (dedup, time-tracking, integrity auditing) proven robust enough to extend to many more sources without a proportional increase in manual oversight.
- **Estimated complexity:** High, and ongoing rather than a single discrete effort — likely to be an umbrella for many individual source-onboarding milestones over time.
- **Potential risks:** The single greatest risk of this entire roadmap: adding sources faster than the integrity and quality processes can absorb, silently degrading the trust the product's whole value rests on. Each new source should individually clear the same bar as Milestone 2.3, not a diluted one.
- **Definition of Done:** Each newly added source individually passes the same evidence-integrity audit bar established in Phase 2, with no exceptions made for the sake of coverage speed.

### Milestone 6.3 — Investor / Analyst Reporting View

- **Goal:** Provide an output format suited to the adjacent investor/analyst user (Persona-adjacent, PRD §3) — an evidence trail behind a market thesis, not a pitch narrative.
- **Why it matters:** This is an explicitly named adjacent-user need in PRD §3, deferred until the primary founder experience is well-served.
- **Expected outcome:** A report format that presents the same underlying evidence, restructured for a thesis-evaluation use case rather than a problem-discovery one.
- **Dependencies:** Milestone 5.3 (market attractiveness view) and 6.1 (multi-user context, since this often serves a small analyst team).
- **Estimated complexity:** Medium.
- **Potential risks:** Risk of this format implicitly encouraging more confident-sounding claims than the underlying evidence supports, since investor contexts often reward decisiveness — the same confidence/uncertainty discipline must hold here without exception.
- **Definition of Done:** Reports generated for this use case pass the same integrity and confidence-labeling bar as founder-facing output, verified by the same audit process.

### Milestone 6.4 — External Integration Layer

- **Goal:** Allow MarketRadar's evidence and findings to be consumed by external tools a founder or team already uses, rather than only through MarketRadar's own interface.
- **Why it matters:** By this point in the roadmap, MarketRadar's core value is well-established; meeting users in their existing workflows is a natural way to extend that value without compromising it.
- **Expected outcome:** Findings can be accessed or consumed outside of MarketRadar's own primary interface, through a defined, documented mechanism.
- **Dependencies:** A mature, stable version of the product across Phases 1–5, since an integration layer built on unstable internals would need to be redone repeatedly.
- **Estimated complexity:** Medium–High (specific complexity is implementation-dependent and out of scope for this document).
- **Potential risks:** External consumers of MarketRadar's findings may strip out confidence labeling and source links when re-presenting the data elsewhere, defeating the entire evidentiary premise — this risk should shape how this milestone is eventually scoped, even though the specific mechanism is not decided here.
- **Definition of Done:** External access to findings preserves confidence labeling and source traceability by design, not as an optional or droppable field.

---

## Cross-Phase Notes

- **No phase should be started before the prior phase's core risks are understood and addressed**, even if calendar pressure suggests otherwise — this is a direct consequence of "Depth before breadth" (CLAUDE.md §2) and is more important than roadmap velocity.
- **Every milestone that touches evidence, confidence, or competitor claims carries fabrication risk by default.** Where a milestone's Definition of Done does not explicitly mention an integrity check, that is an oversight to correct before the milestone is considered actually done, not a signal that the risk doesn't apply.
- **This roadmap will be wrong in places.** It is a planning tool, not a commitment ledger. When real work in a phase reveals that a milestone's assumptions don't hold, update this document rather than silently deviating from it — per CLAUDE.md §13, keep it current, not aspirational.
