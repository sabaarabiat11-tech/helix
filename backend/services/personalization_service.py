"""Per-user recommendation ranking.

The base `RuleBasedRecommendationEngine` answers "how notable is this person?"
— a property of the person alone, identical for every user. This module answers
the different question "how relevant is this person *to you?*", by layering a
preference-driven adjustment on top of that shared base score.

Keeping the two separate matters: the base score stays comparable across
accounts (and cacheable for the whole corpus), while personalization stays a
pure function of one user's preferences. Swapping the base engine for an ML or
LLM scorer later changes nothing here, and vice versa.

Every adjustment appends a human-readable line to `why`, so the UI can always
explain a ranking rather than presenting it as a black box.
"""
from __future__ import annotations

import re

from db import db_conn, execute, rows, today_iso, utcnow_iso
from services import user_service
from services.recommendation_service import score_all
from services.watchlist_service import followed_person_ids

# How far personalization may move a score, in points. Capped deliberately: a
# strong preference match should promote a good candidate above a comparable
# one, not push a weak profile to the top of the list.
MAX_BOOST = 25
MAX_PENALTY = 20

SENIORITY_PATTERNS = {
    "leadership": re.compile(r"director|head of|chief|vp\b|vice president|founder|principal", re.I),
    "senior": re.compile(r"senior|staff|lead\b|principal|sr\.?\b", re.I),
    "mid": re.compile(r"engineer|scientist|researcher|developer|analyst", re.I),
    "junior": re.compile(r"junior|jr\.?\b|intern|associate|graduate|phd student", re.I),
}


def _matches_any(needles: list[str], haystack: str) -> list[str]:
    """Case-insensitive substring match, returning which needles hit."""
    lowered = haystack.lower()
    return [n for n in needles if n and n.lower() in lowered]


def personalize(person: dict, prefs: dict) -> dict:
    """Return a copy of an already-scored person with a personal score applied."""
    adjustment = 0
    reasons: list[str] = []

    haystack = " ".join(
        str(person.get(field) or "") for field in ("title", "company", "reason", "location")
    )

    # --- Focus areas: the strongest personal signal ---
    focus_hits = _matches_any(prefs.get("focus_areas") or [], haystack)
    if focus_hits:
        adjustment += min(14, 7 * len(focus_hits))
        label = ", ".join(focus_hits[:2])
        reasons.append(f"Matches your focus on {label}")

    # --- Preferred companies ---
    company = str(person.get("company") or "")
    company_hits = _matches_any(prefs.get("preferred_companies") or [], company)
    if company_hits:
        adjustment += 10
        reasons.append(f"At {company}, one of your target companies")

    # --- Preferred locations ---
    location = str(person.get("location") or "")
    location_hits = _matches_any(prefs.get("preferred_locations") or [], location)
    if location_hits:
        adjustment += 6
        reasons.append(f"Based in {location}, a region you follow")

    # --- Seniority ---
    wanted = prefs.get("seniority_preference") or "any"
    if wanted != "any":
        pattern = SENIORITY_PATTERNS.get(wanted)
        title = str(person.get("title") or "")
        if pattern and pattern.search(title):
            adjustment += 8
            reasons.append(f"{wanted.capitalize()}-level role, which you prioritise")
        elif pattern:
            # A mismatch is a mild demotion, never a disqualification — job
            # titles are noisy free text and the pattern can simply miss.
            adjustment -= 6

    adjustment = max(-MAX_PENALTY, min(MAX_BOOST, adjustment))
    personal_score = max(0, min(100, int(person["score"]) + adjustment))

    return {
        **person,
        "base_score": person["score"],
        "score": personal_score,
        "personal_adjustment": adjustment,
        "stars": round(personal_score / 20),
        # Personal reasons lead: they answer "why am I seeing this?" better
        # than the generic ones do.
        "why": reasons + list(person.get("why") or []),
    }


def _load_people() -> list[dict]:
    with db_conn() as conn:
        return rows(conn, "SELECT * FROM people")


def rank_for_user(
    user_id: int,
    limit: int = 10,
    exclude_followed: bool = False,
    people: list[dict] | None = None,
    prefs: dict | None = None,
) -> list[dict]:
    """The single ranking entry point. Everything user-facing goes through it."""
    prefs = prefs if prefs is not None else user_service.get_preferences(user_id)
    corpus = people if people is not None else _load_people()

    scored = [personalize(p, prefs) for p in score_all(corpus)]

    min_score = int(prefs.get("min_score") or 0)
    if min_score:
        scored = [p for p in scored if p["score"] >= min_score]

    if exclude_followed:
        followed = followed_person_ids(user_id)
        scored = [p for p in scored if p["id"] not in followed]

    scored.sort(key=lambda p: (p["score"], p.get("discovery_date") or ""), reverse=True)
    return scored[:limit]


def recommendations_bundle(user_id: int, people: list[dict] | None = None) -> dict:
    """Everything the Recommendations page and the digest need, in one pass
    over the corpus."""
    prefs = user_service.get_preferences(user_id)
    corpus = people if people is not None else _load_people()

    ranked = rank_for_user(user_id, limit=len(corpus) or 1, people=corpus, prefs=prefs)
    followed = followed_person_ids(user_id)

    today = today_iso()
    todays = [p for p in ranked if (p.get("discovery_date") or "") == today]
    unfollowed = [p for p in ranked if p["id"] not in followed]

    return {
        # "Today" falls back to the overall best when the pipeline hasn't run
        # today, so the page is never empty for a reason the user can't see.
        "top_today": (todays or ranked)[:5],
        "top_today_is_fallback": not todays,
        "top_this_week": ranked[:10],
        "to_follow": unfollowed[:8],
        "trending_companies": trending_companies(corpus),
        "most_active_organizations": most_active_organizations(corpus),
        "preferences_applied": {
            "focus_areas": prefs.get("focus_areas") or [],
            "preferred_companies": prefs.get("preferred_companies") or [],
            "preferred_locations": prefs.get("preferred_locations") or [],
            "seniority_preference": prefs.get("seniority_preference") or "any",
            "min_score": int(prefs.get("min_score") or 0),
        },
    }


def trending_companies(people: list[dict], days: int = 7, limit: int = 6) -> list[dict]:
    """Companies with the most discoveries in the recent window."""
    from datetime import timedelta

    from db import parse_date, utcnow

    cutoff = (utcnow() - timedelta(days=days)).date()
    counts: dict[str, int] = {}
    for person in people:
        discovered = parse_date(person.get("discovery_date"))
        company = (person.get("company") or "").strip()
        if company and discovered and discovered >= cutoff:
            counts[company] = counts.get(company, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [{"name": name, "count": count} for name, count in ranked[:limit]]


def most_active_organizations(people: list[dict], limit: int = 6) -> list[dict]:
    """Largest organizations by total people discovered, all time."""
    counts: dict[str, int] = {}
    for person in people:
        company = (person.get("company") or "").strip()
        if company:
            counts[company] = counts.get(company, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [{"name": name, "count": count} for name, count in ranked[:limit]]


# --- History ----------------------------------------------------------------

def record_shown(user_id: int, people: list[dict], channel: str = "app") -> None:
    """Remember which recommendations a user has already been given.

    The unique constraint on (user, person, channel, day) makes this idempotent,
    so a page refresh doesn't inflate the history.
    """
    if not people:
        return
    now = utcnow_iso()
    day = today_iso()
    with db_conn() as conn:
        for person in people:
            execute(
                conn,
                """
                INSERT INTO recommendation_history (user_id, person_id, score, channel, shown_on, created_at)
                VALUES (:user_id, :person_id, :score, :channel, :shown_on, :created_at)
                ON CONFLICT(user_id, person_id, channel, shown_on) DO NOTHING
                """,
                {
                    "user_id": user_id,
                    "person_id": person["id"],
                    "score": int(person.get("score") or 0),
                    "channel": channel,
                    "shown_on": day,
                    "created_at": now,
                },
            )


def already_emailed_person_ids(user_id: int, since: str) -> set[int]:
    """Person ids already sent to this user by email on or after `since`
    (YYYY-MM-DD) — lets a digest lead with things the user hasn't seen."""
    with db_conn() as conn:
        found = rows(
            conn,
            "SELECT DISTINCT person_id FROM recommendation_history "
            "WHERE user_id = :user_id AND channel = 'email' AND shown_on >= :since",
            {"user_id": user_id, "since": since},
        )
    return {r["person_id"] for r in found}


def history(user_id: int, limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        return rows(
            conn,
            """
            SELECT h.person_id, h.score, h.channel, h.shown_on,
                   p.name, p.title, p.company, p.linkedin_url
            FROM recommendation_history h
            JOIN people p ON p.id = h.person_id
            WHERE h.user_id = :user_id
            ORDER BY h.shown_on DESC, h.score DESC
            LIMIT :limit
            """,
            {"user_id": user_id, "limit": limit},
        )
