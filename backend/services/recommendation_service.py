"""Recommendation engine — scores every person 0-100 from signals already in
the data (no external API, no ML model). Deliberately built behind a small
`RecommendationEngine` interface: swapping in a future ML/LLM-based scorer
means writing one new class and changing the single line at the bottom of
this file — routers, the frontend, and every other service stay untouched.

Weights sum to 100 at maximum:
  company_importance   30  — tier of the discovering company
  title_seniority       20  — seniority signal in the job title
  ai_bio_relevance      20  — how clearly the title matches AI x Biology work
  source_confidence     15  — how reliable the discovery source is
  recency               10  — how recently they were discovered
  profile_completeness   5  — location + non-generic title + reason present
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Protocol

TIER_1_COMPANIES = {
    "Isomorphic Labs", "DeepMind", "Google DeepMind", "FutureHouse", "Arc Institute", "Insilico Medicine",
}
TIER_2_COMPANIES = {
    "Recursion", "Owkin", "Generate Biomedicines", "Deep Genomics", "Relation Therapeutics",
    "Valo Health", "Profluent", "Google Research",
}

SENIORITY_HIGH = re.compile(r"principal|staff|lead|director|head of|chief|vp|vice president", re.I)
SENIORITY_MID = re.compile(r"senior|sr\.?\b", re.I)
SENIORITY_ENTRY = re.compile(r"\bintern|associate|junior|jr\.?\b", re.I)
GENERIC_TITLE = re.compile(r"^(team member|employee)$", re.I)

AI_BIO_STRONG = re.compile(
    r"machine learning|computational biolog|bioinformatic|\bai scientist|research scientist|"
    r"research engineer|applied scientist", re.I,
)
AI_BIO_WEAK = re.compile(r"\bai\b|research|scientist|engineer", re.I)

SOURCE_CONFIDENCE = {
    "SearXNG (local)": 15,
    "SearXNG": 13,
    "GitHub": 14,
    "Company Page": 12,
    "Google Scholar": 11,
    "Manual Research": 9,
    "Brave Search (legacy)": 8,
    "Google Search (legacy)": 8,
}


@dataclass
class ScoreResult:
    score: int
    stars: int
    reasons: list[str] = field(default_factory=list)


def _company_score(company: str) -> tuple[int, str | None]:
    if company in TIER_1_COMPANIES:
        return 30, f"{company} is a top-tier AI×Biology lab"
    if company in TIER_2_COMPANIES:
        return 22, f"{company} is a leading AI-driven biotech company"
    if company:
        return 14, None
    return 0, None


def _seniority_score(title: str) -> tuple[int, str | None]:
    if SENIORITY_HIGH.search(title):
        return 20, "Senior/leadership-level role"
    if SENIORITY_MID.search(title):
        return 15, "Senior-level role"
    if SENIORITY_ENTRY.search(title):
        return 5, None
    if GENERIC_TITLE.match(title.strip()):
        return 3, None
    if title:
        return 10, None
    return 0, None


def _relevance_score(title: str, reason: str) -> tuple[int, str | None]:
    text = f"{title} {reason}"
    if AI_BIO_STRONG.search(text):
        return 20, "Strong AI×Biology relevance in title"
    if AI_BIO_WEAK.search(text):
        return 10, "Some AI/research relevance"
    return 3, None


def _source_score(source: str) -> tuple[int, str | None]:
    pts = SOURCE_CONFIDENCE.get(source, 8)
    label = f"Found via {source} (high-confidence source)" if pts >= 14 else None
    return pts, label


def _recency_score(discovery_date: str) -> tuple[int, str | None]:
    try:
        d = datetime.strptime(discovery_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0, None
    today = date.today()
    if d == today:
        return 10, "Discovered today"
    if d >= today - timedelta(days=7):
        return 6, "Discovered this week"
    if d >= today - timedelta(days=30):
        return 3, None
    return 0, None


def _completeness_score(location: str, title: str, reason: str) -> tuple[int, str | None]:
    pts = 0
    if location:
        pts += 2
    if title and not GENERIC_TITLE.match(title.strip()):
        pts += 2
    if reason:
        pts += 1
    label = "Complete profile (location + specific title)" if pts >= 4 else None
    return pts, label


class RecommendationEngine(Protocol):
    """Contract any future scorer (rule-based, ML, LLM) must satisfy."""

    def score(self, person: dict) -> ScoreResult: ...


class RuleBasedRecommendationEngine:
    """Transparent weighted heuristic — every score comes with a human-readable why."""

    def score(self, person: dict) -> ScoreResult:
        company = person.get("company") or ""
        title = person.get("title") or ""
        reason = person.get("reason") or ""
        source = person.get("source") or ""
        discovery_date = person.get("discovery_date") or ""
        location = person.get("location") or ""

        total = 0
        reasons: list[str] = []

        for scorer, args in (
            (_company_score, (company,)),
            (_seniority_score, (title,)),
            (_relevance_score, (title, reason)),
            (_source_score, (source,)),
            (_recency_score, (discovery_date,)),
            (_completeness_score, (location, title, reason)),
        ):
            pts, label = scorer(*args)
            total += pts
            if label:
                reasons.append(label)

        total = max(0, min(100, total))
        stars = round(total / 20)
        if not reasons:
            reasons.append("Matches core AI×Biology discovery criteria")

        return ScoreResult(score=total, stars=stars, reasons=reasons)


# --- Public service API -----------------------------------------------------
# Swap this one assignment to plug in a different engine (e.g. an
# LLM-backed one) without touching anything below or any caller.
engine: RecommendationEngine = RuleBasedRecommendationEngine()


def score_person(person: dict) -> ScoreResult:
    return engine.score(person)


def score_all(people: list[dict]) -> list[dict]:
    """Attach score/stars/why to every person, unsorted."""
    out = []
    for p in people:
        result = score_person(p)
        out.append({**p, "score": result.score, "stars": result.stars, "why": result.reasons})
    return out


def top_recommendations(people: list[dict], limit: int = 10) -> list[dict]:
    scored = score_all(people)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
