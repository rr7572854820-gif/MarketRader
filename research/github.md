# Research Template — GitHub

This is a reusable template and process guide, not a data file. It defines how GitHub research should be conducted so that every researcher (human or Claude) produces evidence in the same, comparable, auditable format. Do not fill this file with invented example findings — leave sections empty or marked `[Not yet collected]` until real research happens, per [CLAUDE.md](../CLAUDE.md)'s non-fabrication rules, which apply to research process documents exactly as they apply to the product itself.

Findings produced using this template feed directly into MarketRadar's evidence base (see [PRD.md](../PRD.md) §8 for MVP evidence requirements) and must meet the same bar: every claim traceable to a real, linkable source.

---

## Purpose

GitHub is a candidate source for unusually precise, specific pain-point signal — issues and discussions on real projects, filed by people actually using a tool, often with reproduction detail that makes the underlying problem unambiguous. Its purpose within MarketRadar is to surface well-documented, specific gaps in existing tools (particularly developer tools, open-source infrastructure, and libraries), and to identify competitor weaknesses with unusually high precision.

## Where Data Comes From

- Issues (open and closed) on relevant public repositories.
- Discussions (where a repository has GitHub Discussions enabled) — often contain more open-ended feature requests and workaround conversations than issues do.
- Issue/PR comments, which frequently contain maintainer responses that confirm, deprioritize, or explain a limitation.
- Only publicly viewable content on public repositories, accessed consistent with GitHub's terms of service and API terms at the time of collection — verify current terms before automating collection; this template does not itself grant clearance (see [PRD.md](../PRD.md) §13 and ROADMAP.md Milestone 0.1). Never access private repositories or content requiring elevated permissions.

## How Information Should Be Collected

1. Identify relevant repositories tied to the problem space under investigation, either directly (a specific tool's own repository) or via search across GitHub for problem-indicative terms.
2. Record the exact repository, search term, or issue label filter used, and the collection date.
3. Read full issue threads, not just the original post — maintainer responses, "+1" style piling-on from other users, and eventual resolution (or lack thereof) all matter for interpreting severity and recurrence.
4. Capture the permalink, author identifier, timestamp, and full relevant text for anything that looks like a candidate pain point.
5. Note reaction counts (👍 etc.), comment count, and issue status (open/closed, and if closed, how — fixed, won't-fix, stale) as signal: an old, open, heavily-reacted issue with no resolution is a meaningfully different signal than a quickly-closed one.

## Signals to Look For

- Issues explicitly describing a missing feature or capability, especially ones with many reactions or "+1" comments from unrelated users (each independent reactor is a weak but real additional instance).
- Issues labeled by maintainers in ways that indicate acknowledged-but-unaddressed gaps (e.g., "help wanted," "enhancement," "wontfix" — the labeling itself is evidence of how the maintainer has triaged the pain).
- Discussion threads where multiple users independently describe building the same workaround, indicating a real, unaddressed gap.
- Issues that have been open a long time with sustained activity (new comments continuing well after filing) — a strong recurrence/persistence signal.
- Comments in unrelated repositories' issues that mention switching away from, or avoiding, a specific tool because of a stated limitation — this is competitor-weakness evidence appearing outside the competitor's own repository.

## Pain Point Extraction

For each candidate pain point found, record:

- **Problem statement** — a precise, neutral description of the pain point, written from the evidence, not paraphrased into something more general than what was actually said.
- **Direct quote(s)** — the actual text expressing the pain point, not a summary.
- **Context** — the repository, issue number/title, and current status (open/closed, labels applied).
- **Distinct-instance check** — confirm each supporting "+1" or reaction represents an independent person, not automated/bot activity, and that duplicate issues (common on active repositories) are merged into a single tracked pain point rather than double-counted.

## Evidence Collection

Every pain point entry must include:

- Direct permalink to the specific issue, discussion thread, or comment.
- Timestamp of the original post and, if relevant, of the most recent activity.
- Verbatim quoted text.
- Author identifier, and an explicit note of whether they are the repository's maintainer or an external user — this distinction matters for interpreting the evidence (see Risk Analysis).

Do not record anything as evidence that cannot be independently re-checked at the link provided. If a piece of context is inferred rather than stated, label it explicitly as inference, separate from the quoted evidence itself.

## Recurring Complaint Tracking

- Track pain points by a consistent problem label across repositories, so the same underlying gap appearing in multiple unrelated tools' issue trackers is recognized as a market-level recurring pain point, not just a single project's bug report.
- Record each new instance with its own link, date, and author — recurrence is the count of independent instances (including independent reactors on a single issue, counted individually), not the count of issues.
- Watch for duplicate issues within the same repository (common — many projects have a "duplicate of #X" convention) and count the cluster as one instance, not several.
- Log the observation window and repositories/search terms covered alongside recurrence counts.

## Competitor Tracking

- When an issue or discussion is filed against a specific tool, that tool is itself a competitor (or adjacent tool) whose limitation is now directly evidenced — log the tool, the specific limitation, and the link.
- Where a user explicitly states they moved to or from a specific alternative tool because of the issue at hand, capture that comparison verbatim — this is unusually strong, specific competitor-weakness evidence.
- Maintainer comments that confirm a limitation is real and by design (not a bug, but an intentional scope boundary) are especially high-value evidence — they represent the competitor's own team confirming the gap.
- Do not infer that a repository's overall popularity (stars, forks) reflects satisfaction with the tool — a very popular tool can still have well-documented, long-standing gaps; treat popularity and issue-based weakness evidence as separate signals.

## Market Scoring

Do not assign a market attractiveness score from GitHub research alone, and do not use [IDEAS.md](../IDEAS.md) for this purpose — that framework evaluates candidate features for MarketRadar the product, not the market opportunities its research surfaces (see IDEAS.md's own scope note). GitHub research instead contributes raw inputs (recurrence count, reaction-based weak-instance signal, maintainer-confirmed limitations, comparative tool-switching statements) toward MarketRadar's future market-attractiveness capability, which combines evidence across sources — see [ROADMAP.md](../ROADMAP.md) Milestone 5.3. Until that capability exists, do not compute or imply a score. Note that GitHub's population is skewed toward developers and technically sophisticated users; pain points here are strong signal for developer-tool and technical-workflow problem spaces, and weak/absent signal for problems that live entirely outside a technical audience.

## Risk Analysis

Known risk factors specific to GitHub as a source:

- **Audience skew** — heavily developer-oriented; strong for technical tooling pain points, largely blind to non-technical business pain points.
- **Maintainer relationship distorts tone** — issue discussions can turn adversarial or overly deferential depending on the maintainer's engagement style; read for actual content, not just tone, when judging severity.
- **Reaction/comment count reflects visibility, not just severity** — an old, well-known repository will naturally accumulate more reactions on any issue than a small one, independent of how painful the underlying problem actually is; avoid comparing raw reaction counts across repositories of very different sizes without accounting for this.
- **Stale or abandoned repositories** — an issue with no recent activity may reflect an abandoned project rather than a resolved or unimportant problem; check the repository's overall activity level before drawing conclusions from a quiet issue thread.
- **Bot and automated activity** — some reactions, comments, and even issues can originate from bots or automated tooling (e.g., dependency bots, stale-issue bots); exclude these from instance counts.

## Confidence Score

Apply the confidence taxonomy defined in [ROADMAP.md](../ROADMAP.md) Milestone 0.3 once it exists. Until that taxonomy is written, do not assign ad hoc confidence labels — leave this field as `[Pending taxonomy — see ROADMAP.md Milestone 0.3]` rather than inventing a scale here that would conflict with the eventual project-wide standard. Maintainer-confirmed limitations should generally register as stronger evidence than an unconfirmed user report — but the specific tiering must follow the taxonomy once it exists.

## Source Links

Maintain a running, deduplicated list of every source link cited in this research area, so the full evidence trail can be reviewed independently of the narrative findings above it.

```
[Not yet collected]
```

## Validation Checklist

Before a GitHub-derived pain point or competitor entry is considered ready to feed into MarketRadar's evidence base, confirm:

- [ ] Every quote links to the specific issue, discussion, or comment.
- [ ] Duplicate issues within a repository are merged into one tracked instance, not double-counted.
- [ ] Reaction-based instance counts exclude bot/automated activity.
- [ ] Maintainer comments are labeled as such, distinct from external user comments.
- [ ] Repository size/popularity is noted wherever reaction counts are used as supporting signal, to contextualize them.
- [ ] The observation window (dates, repositories/search terms used) is recorded alongside the findings.

## Weekly Summary Format

```
### GitHub Weekly Summary — Week of [YYYY-MM-DD]

**Repositories/search terms covered:** [list]
**New pain points identified:** [count, with links to full entries]
**Recurring pain points reinforced this week:** [count, with new instance links]
**New maintainer-confirmed limitations:** [list, with links]
**Notable single findings worth flagging:** [any unusually strong or unusually weak evidence worth a human's attention]
**Collection issues/gaps:** [anything that limited this week's collection]
```

## Monthly Trend Format

```
### GitHub Monthly Trend — [Month YYYY]

**Total distinct pain points tracked this month:** [count]
**Pain points with increasing instance frequency vs. prior month:** [list — directional only, not a formal growth claim until ROADMAP.md Phase 5 growth-detection capability exists]
**Pain points with no new instances this month:** [list]
**New repositories/search terms added to coverage:** [list]
**Source-specific risk events this month:** [e.g., a tracked repository going stale/archived, a maintainer publicly deprioritizing a tracked issue]
```

## Important Observations

*[Not yet collected — record genuinely notable, source-level observations here as research happens (e.g., "issues labeled 'wontfix' are unusually reliable evidence of a confirmed, permanent gap"), not individual pain-point findings, which belong in the evidence base itself.]*

## Open Questions

*[Not yet collected — record open methodological or source-specific questions here as they arise, e.g., "how should reaction counts be normalized across repositories of very different sizes?"]*
