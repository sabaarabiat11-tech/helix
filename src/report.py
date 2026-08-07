"""Generate weekly_report.md summarizing what a run found."""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from src.pipeline import RunResult


def write_weekly_report(reports_dir: Path, result: RunResult) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    report_path = reports_dir / f"weekly_report_{today}.md"

    company_counts = Counter(p.company for p in result.new_people)
    title_counts = Counter(p.title for p in result.new_people)

    lines: list[str] = []
    lines.append(f"# Weekly Discovery Report — {today}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- People in master CSV before this run: **{result.existing_count_before}**")
    lines.append(f"- New candidates found across all sources (pre-dedupe): **{result.total_candidates_before_dedupe}**")
    lines.append(f"- New people added this run: **{len(result.new_people)}**")
    lines.append(f"- People in master CSV after this run: **{result.existing_count_before + len(result.new_people)}**")
    if result.target_shortfall:
        lines.append("- ⚠️ **Below weekly target (20–30 new people).** See notes at the bottom.")
    lines.append("")

    lines.append("## New people found, by source")
    if result.per_source_counts:
        for source_name, count in sorted(result.per_source_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- `{source_name}`: {count} raw candidates")
    else:
        lines.append("- No sources ran.")
    lines.append("")

    lines.append("## New people, by company")
    if company_counts:
        for company, count in company_counts.most_common():
            lines.append(f"- {company}: {count}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## New people, by title")
    if title_counts:
        for title, count in title_counts.most_common():
            lines.append(f"- {title}: {count}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## New additions this run")
    if result.new_people:
        lines.append("| Name | Title | Company | Location | LinkedIn |")
        lines.append("|---|---|---|---|---|")
        for p in result.new_people:
            lines.append(f"| {p.name} | {p.title} | {p.company} | {p.location} | [{p.linkedin_url}]({p.linkedin_url}) |")
    else:
        lines.append("_No new people were added this run._")
    lines.append("")

    if result.target_shortfall:
        lines.append("## Notes")
        lines.append(
            "This run found fewer than the target 20–30 new people. Common causes: "
            "the local SearXNG Docker container wasn't running (`docker compose up -d`), "
            "target companies/roles are already well-covered in the master CSV, "
            "or optional sources (company_pages, google_scholar) are "
            "disabled/misconfigured. Check the run log in `data/logs/` for "
            "per-source details."
        )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
