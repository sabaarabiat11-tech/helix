from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from fastapi import APIRouter

from database import sync_from_csv
from db import db_conn
from db import rows as fetch_rows

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Raw job titles are free text ("Senior ML Engineer" vs "Machine Learning
# Engineer II" vs "ML Research Scientist"...) and fragment into dozens of
# near-duplicates if charted as-is. Bucket into the same role categories the
# pipeline targets (config.yaml -> target_roles) plus a catch-all, purely for
# a legible chart — this doesn't touch or reflect back into the pipeline.
ROLE_BUCKETS: list[tuple[str, str]] = [
    (r"machine learning|ml\b", "Machine Learning Engineer"),
    (r"\bai scientist|artificial intelligence scientist", "AI Scientist"),
    (r"computational biolog", "Computational Biologist"),
    (r"bioinformatic", "Bioinformatics Engineer"),
    (r"research engineer|research scientist", "Research Engineer/Scientist"),
    (r"applied scientist", "Applied Scientist"),
    (r"software engineer", "Software Engineer"),
    (r"founder|co-founder|ceo|cto|chief|president|chairman", "Founder/Executive"),
]


def bucket_title(title: str) -> str:
    t = title.lower()
    for pattern, label in ROLE_BUCKETS:
        if re.search(pattern, t):
            return label
    return "Other"


@router.get("")
def get_analytics():
    sync_from_csv()

    with db_conn() as conn:
        rows = fetch_rows(conn, "SELECT company, title, source, discovery_date FROM people")

    # --- discoveries over time (daily counts + 7-day moving average) ---
    by_date: Counter[str] = Counter()
    for r in rows:
        d = r["discovery_date"]
        if d:
            by_date[d] += 1
    ordered_dates = sorted(by_date.items())
    discoveries_over_time = []
    window: list[int] = []
    for d, n in ordered_dates:
        window.append(n)
        if len(window) > 7:
            window.pop(0)
        discoveries_over_time.append({
            "date": d,
            "count": n,
            "moving_avg": round(sum(window) / len(window), 1),
        })

    # --- top companies ---
    by_company: Counter[str] = Counter()
    for r in rows:
        if r["company"]:
            by_company[r["company"]] += 1
    top_companies = [
        {"company": c, "count": n} for c, n in by_company.most_common(12)
    ]

    # --- top roles (bucketed) ---
    by_role: Counter[str] = Counter()
    for r in rows:
        by_role[bucket_title(r["title"] or "")] += 1
    top_roles = [
        {"role": role, "count": n} for role, n in by_role.most_common()
    ]

    # --- source contribution ---
    by_source: Counter[str] = Counter()
    for r in rows:
        by_source[r["source"] or "Unknown"] += 1
    source_contribution = [
        {"source": s, "count": n} for s, n in by_source.most_common()
    ]

    # --- weekly growth (last 12 ISO weeks, new-per-week + cumulative) ---
    weekly_counts: Counter[str] = Counter()
    for r in rows:
        d = r["discovery_date"]
        if not d:
            continue
        try:
            parsed = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        iso_year, iso_week, _ = parsed.isocalendar()
        weekly_counts[f"{iso_year}-W{iso_week:02d}"] += 1

    ordered_weeks = sorted(weekly_counts.keys())
    cumulative = 0
    weekly_growth = []
    for week in ordered_weeks:
        cumulative += weekly_counts[week]
        weekly_growth.append({"week": week, "new": weekly_counts[week], "cumulative": cumulative})

    # --- company growth: cumulative count over time for the top 6 companies,
    # as one row per date with a column per company (wide format — plugs
    # directly into a multi-line recharts LineChart) ---
    top_6_companies = [c["company"] for c in top_companies[:6]]
    running_totals = dict.fromkeys(top_6_companies, 0)
    company_growth = []
    for d, _ in ordered_dates:
        day_rows = [r for r in rows if r["discovery_date"] == d]
        for c in top_6_companies:
            running_totals[c] += sum(1 for r in day_rows if r["company"] == c)
        company_growth.append({"date": d, **running_totals})

    # --- heatmap: top companies x sources, count matrix ---
    top_10_companies = {c["company"] for c in top_companies[:10]}
    heatmap_counts: Counter[tuple[str, str]] = Counter()
    for r in rows:
        if r["company"] in top_10_companies:
            heatmap_counts[(r["company"], r["source"] or "Unknown")] += 1
    all_sources = sorted({s for (_, s) in heatmap_counts.keys()})
    heatmap = [
        {"company": c, "source": s, "count": heatmap_counts.get((c, s), 0)}
        for c in [tc["company"] for tc in top_companies[:10]]
        for s in all_sources
    ]

    return {
        "discoveries_over_time": discoveries_over_time,
        "top_companies": top_companies,
        "top_roles": top_roles,
        "source_contribution": source_contribution,
        "weekly_growth": weekly_growth,
        "company_growth": company_growth,
        "company_growth_keys": top_6_companies,
        "heatmap": heatmap,
        "heatmap_sources": all_sources,
    }
