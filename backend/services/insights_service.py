"""AI Insights — currently a rule-based/statistical engine (no LLM configured
in this project). Built behind an `InsightsEngine` interface on purpose: a
future LLM-backed engine (e.g. one that reads the same `_gather_context()`
data and asks a model to narrate it) is a single new class swapped in at the
bottom of this file — routers and the frontend never change.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Protocol

from db import db_conn, rows
from services.recommendation_service import top_recommendations
from services.watchlist_service import list_watchlist


def _gather_context(user_id: int | None = None) -> dict:
    """The discovery corpus is shared; only the watchlist overlay — which
    drives the "people you haven't followed yet" card — is per user."""
    with db_conn() as conn:
        people = rows(conn, "SELECT * FROM people")
    watched_ids = {w["person_id"] for w in list_watchlist(user_id)} if user_id else set()
    return {"people": people, "watched_ids": watched_ids}


class InsightsEngine(Protocol):
    def generate(self, context: dict) -> list[dict]: ...


class RuleBasedInsightsEngine:
    def generate(self, context: dict) -> list[dict]:
        people = context["people"]
        watched_ids = context["watched_ids"]
        cards: list[dict] = []

        today = date.today()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)

        def _parsed_date(p):
            try:
                return date.fromisoformat(p.get("discovery_date") or "")
            except ValueError:
                return None

        # --- Best discoveries today ---
        today_people = [p for p in people if _parsed_date(p) == today]
        if today_people:
            best_today = top_recommendations(today_people, limit=3)
            cards.append({
                "id": "best-today",
                "category": "Best Discoveries Today",
                "description": f"{len(today_people)} people discovered today — top matches by relevance score.",
                "items": [
                    {"name": p["name"], "company": p["company"], "title": p["title"], "score": p["score"]}
                    for p in best_today
                ],
            })
        else:
            cards.append({
                "id": "best-today",
                "category": "Best Discoveries Today",
                "description": "No new people discovered yet today — run the pipeline to find some.",
                "items": [],
            })

        # --- Fastest growing companies (last 7 days) ---
        recent = [p for p in people if (d := _parsed_date(p)) and d >= week_ago]
        growth = Counter(p["company"] for p in recent if p["company"])
        cards.append({
            "id": "fastest-growing",
            "category": "Fastest Growing Companies",
            "description": "Companies with the most people discovered in the last 7 days.",
            "items": [{"company": c, "count": n} for c, n in growth.most_common(5)],
        })

        # --- Companies with increasing hiring activity (this week vs prior week) ---
        prior_week = [p for p in people if (d := _parsed_date(p)) and two_weeks_ago <= d < week_ago]
        this_week_counts = Counter(p["company"] for p in recent if p["company"])
        prior_week_counts = Counter(p["company"] for p in prior_week if p["company"])
        increasing = []
        for company, count in this_week_counts.items():
            delta = count - prior_week_counts.get(company, 0)
            if delta > 0:
                increasing.append({"company": company, "this_week": count, "delta": delta})
        increasing.sort(key=lambda x: x["delta"], reverse=True)
        cards.append({
            "id": "increasing-hiring",
            "category": "Companies With Increasing Hiring Activity",
            "description": "Week-over-week growth in discoveries per company.",
            "items": increasing[:5],
        })

        # --- Most interesting researchers (highest score, specific titles) ---
        specific = [p for p in people if p.get("title") and p["title"].lower() not in ("team member", "employee")]
        interesting = top_recommendations(specific, limit=5)
        cards.append({
            "id": "interesting-researchers",
            "category": "Most Interesting Researchers",
            "description": "Highest-scoring people with a specific, identifiable role.",
            "items": [
                {"name": p["name"], "company": p["company"], "title": p["title"], "score": p["score"], "why": p["why"]}
                for p in interesting
            ],
        })

        # --- Suggested people to contact first ---
        not_watched = [p for p in people if p["id"] not in watched_ids]
        suggestions = top_recommendations(not_watched, limit=5)
        cards.append({
            "id": "contact-first",
            "category": "Suggested People to Contact First",
            "description": "Top-ranked people you haven't added to your watchlist yet.",
            "items": [
                {"id": p["id"], "name": p["name"], "company": p["company"], "title": p["title"], "score": p["score"]}
                for p in suggestions
            ],
        })

        # --- Trends compared with last week ---
        this_week_total = len(recent)
        prior_week_total = len(prior_week)
        if prior_week_total > 0:
            pct = round((this_week_total - prior_week_total) / prior_week_total * 100)
        else:
            pct = 100 if this_week_total > 0 else 0
        cards.append({
            "id": "week-trend",
            "category": "Trends vs. Last Week",
            "description": f"{this_week_total} new people this week vs. {prior_week_total} the week before.",
            "items": [{"metric": "week_over_week_change_pct", "value": pct}],
        })

        return cards


# Swap this one assignment for an LLM-backed engine later.
engine: InsightsEngine = RuleBasedInsightsEngine()


def generate_daily_insights(user_id: int | None = None) -> list[dict]:
    return engine.generate(_gather_context(user_id))
