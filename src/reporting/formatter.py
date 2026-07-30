"""Pure formatting layer: renders an InsightReport as text.

No AI calls, no computation beyond string formatting — every value
rendered here was already computed by report_generator.py. Two output
formats: format_terminal (plain text for the console) and
format_markdown (a saveable .md document). save_markdown_file writes
the latter to disk; it's the only function here that touches the
filesystem.
"""

from __future__ import annotations

from pathlib import Path

from src.reporting.models import InsightReport, OpportunityReportEntry, ProjectHealthSummary

_SPECULATIVE_NOTE = "SPECULATIVE - AI-inferred, not a verified finding"


def format_terminal(report: InsightReport) -> str:
    lines = [
        "=" * 70,
        "MARKETRADAR INSIGHT REPORT",
        "=" * 70,
        "",
        "EXECUTIVE SUMMARY",
        "-" * 70,
        report.executive_summary,
        "",
        f"TOP OPPORTUNITIES ({len(report.top_opportunities)})",
        "-" * 70,
    ]

    if not report.top_opportunities:
        lines.append("No opportunity clusters were produced by this run.")
    else:
        for i, entry in enumerate(report.top_opportunities, start=1):
            lines.append("")
            lines.extend(_format_entry_terminal(i, entry))

    lines.extend(["", "PROJECT HEALTH", "-" * 70])
    lines.extend(_format_health_terminal(report.project_health))
    lines.append("=" * 70)
    return "\n".join(lines)


def _format_entry_terminal(index: int, entry: OpportunityReportEntry) -> list:
    lines = [
        f"#{index} {entry.title}",
        f"    Opportunity score [{_SPECULATIVE_NOTE}]: {entry.opportunity_score}",
        f"    Confidence: {entry.confidence.value}",
        f"    Frequency: {entry.frequency} independent discussion(s)",
        f"    Verification rate: {_format_verification_rate(entry)}",
        f"    Suggested customer segment [{_SPECULATIVE_NOTE}]: {entry.suggested_customer_segment}",
        f"    Recommended next action: {entry.recommended_next_action}",
    ]
    if entry.supporting_quotes:
        lines.append("    Supporting quotes (independently verified):")
        for quote in entry.supporting_quotes:
            lines.append(f'      - "{quote}"')
    else:
        lines.append("    Supporting quotes: none independently verified.")
    if entry.representative_discussions:
        lines.append("    Representative discussions:")
        for url in entry.representative_discussions:
            lines.append(f"      - {url}")
    return lines


def _format_verification_rate(entry: OpportunityReportEntry) -> str:
    if not entry.has_verification_data:
        return "no verification data available"
    return f"{entry.verification_rate:.0%}"


def _format_health_terminal(health: ProjectHealthSummary) -> list:
    return [
        f"Total discussions fetched:    {health.total_discussions_fetched}",
        f"Total discussions analyzed:   {health.total_discussions_analyzed}",
        f"Total opportunity clusters:   {health.total_opportunity_clusters}",
        f"Total fully-verified insights: {health.total_verified_insights}",
        f"Verification percentage:      {health.verification_percentage:.1f}%",
        f"AI provider used:             {health.ai_provider_used}",
        f"Analysis timestamp (UTC):     {health.analysis_timestamp.isoformat()}",
    ]


def format_markdown(report: InsightReport) -> str:
    lines = [
        "# MarketRadar Insight Report",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        f"## Top Opportunities ({len(report.top_opportunities)})",
        "",
    ]

    if not report.top_opportunities:
        lines.append("No opportunity clusters were produced by this run.")
    else:
        for i, entry in enumerate(report.top_opportunities, start=1):
            lines.extend(_format_entry_markdown(i, entry))

    lines.extend(["## Project Health", ""])
    lines.extend(_format_health_markdown(report.project_health))

    return "\n".join(lines) + "\n"


def _format_entry_markdown(index: int, entry: OpportunityReportEntry) -> list:
    lines = [
        f"### {index}. {entry.title}",
        "",
        f"- **Opportunity score** *({_SPECULATIVE_NOTE})*: {entry.opportunity_score}",
        f"- **Confidence**: {entry.confidence.value}",
        f"- **Frequency**: {entry.frequency} independent discussion(s)",
        f"- **Verification rate**: {_format_verification_rate(entry)}",
        f"- **Suggested customer segment** *({_SPECULATIVE_NOTE})*: {entry.suggested_customer_segment}",
        f"- **Recommended next action**: {entry.recommended_next_action}",
        "",
    ]
    if entry.supporting_quotes:
        lines.append("**Supporting quotes (independently verified):**")
        lines.append("")
        for quote in entry.supporting_quotes:
            lines.append(f"> {quote}")
            lines.append("")
    else:
        lines.append("**Supporting quotes:** none independently verified.")
        lines.append("")
    if entry.representative_discussions:
        lines.append("**Representative discussions:**")
        lines.append("")
        for url in entry.representative_discussions:
            lines.append(f"- <{url}>")
        lines.append("")
    return lines


def _format_health_markdown(health: ProjectHealthSummary) -> list:
    return [
        "| Metric | Value |",
        "|---|---|",
        f"| Total discussions fetched | {health.total_discussions_fetched} |",
        f"| Total discussions analyzed | {health.total_discussions_analyzed} |",
        f"| Total opportunity clusters | {health.total_opportunity_clusters} |",
        f"| Total fully-verified insights | {health.total_verified_insights} |",
        f"| Verification percentage | {health.verification_percentage:.1f}% |",
        f"| AI provider used | {health.ai_provider_used} |",
        f"| Analysis timestamp (UTC) | {health.analysis_timestamp.isoformat()} |",
        "",
    ]


def save_markdown_file(report: InsightReport, path: Path) -> Path:
    """Renders report as Markdown and writes it to path, creating
    parent directories if needed. Returns path for convenience.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown(report), encoding="utf-8")
    return path
