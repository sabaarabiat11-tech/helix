"""Digest composition and delivery.

Builds the daily/weekly email a user receives and sends it. Runs from the API
process (instant digests) and from the standalone worker (scheduled ones), so
it holds no request state and takes no FastAPI dependencies.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from config import settings
from database import sync_from_csv
from db import db_conn, parse_date, rows, today_iso, utcnow
from services import personalization_service, user_service
from services.email import sender
from services.insights_service import generate_daily_insights
from services.watchlist_service import due_reminders

log = logging.getLogger("helix.digest")

PERIODS = {
    "daily": {"days": 1, "label": "Daily", "noun": "day"},
    "weekly": {"days": 7, "label": "Weekly", "noun": "week"},
    "instant": {"days": 1, "label": "Latest", "noun": "day"},
}

MAX_RECOMMENDATIONS = 5
MAX_INSIGHTS = 3
MAX_REMINDERS = 5


def _load_people() -> list[dict]:
    with db_conn() as conn:
        return rows(conn, "SELECT * FROM people")


def _window_stats(people: list[dict], days: int) -> tuple[list[dict], list[str]]:
    """People discovered in the window, and companies seen for the first time
    in it."""
    cutoff = (utcnow() - timedelta(days=days)).date()

    recent = []
    first_seen: dict[str, object] = {}
    for person in people:
        discovered = parse_date(person.get("discovery_date"))
        if not discovered:
            continue
        if discovered >= cutoff:
            recent.append(person)
        company = (person.get("company") or "").strip()
        if company:
            existing = first_seen.get(company)
            if existing is None or discovered < existing:
                first_seen[company] = discovered

    new_companies = sorted(
        company for company, earliest in first_seen.items() if earliest >= cutoff
    )
    return recent, new_companies


def build_digest(user: dict, period: str = "weekly", people: list[dict] | None = None) -> dict:
    """Assemble everything the digest template renders. Pure — sends nothing."""
    config = PERIODS.get(period, PERIODS["weekly"])
    corpus = people if people is not None else _load_people()
    user_id = user["id"]

    recent, new_companies = _window_stats(corpus, config["days"])

    # Lead with people this user hasn't already been emailed about in the
    # window, but never send an empty digest just because everything is a
    # repeat — fall back to the best available.
    since = (utcnow() - timedelta(days=config["days"])).date().isoformat()
    already_sent = personalization_service.already_emailed_person_ids(user_id, since)

    ranked = personalization_service.rank_for_user(
        user_id, limit=len(corpus) or 1, exclude_followed=True, people=corpus
    )
    fresh = [p for p in ranked if p["id"] not in already_sent]
    recommendations = (fresh or ranked)[:MAX_RECOMMENDATIONS]

    trending = personalization_service.trending_companies(corpus, days=config["days"])
    top_score = max((p["score"] for p in recommendations), default=0)

    insights = []
    prefs = user_service.get_preferences(user_id)
    if prefs.get("notify_ai_insights", True):
        try:
            cards = generate_daily_insights(user_id)
            insights = [
                {"category": card["category"], "description": card["description"]}
                for card in cards[:MAX_INSIGHTS]
            ]
        except Exception:
            # A digest is still worth sending without the insights section.
            log.exception("Insight generation failed for user %s", user_id)

    reminders = due_reminders(user_id, today_iso())[:MAX_REMINDERS]

    count = len(recent)
    noun = config["noun"]
    if count == 0:
        headline = f"A quiet {noun} in AI × Biology"
        summary = (
            "No new profiles cleared the pipeline this "
            f"{noun}. Here's where the network stands."
        )
    else:
        person_word = "researcher" if count == 1 else "researchers"
        headline = f"{count} new {person_word} this {noun}"
        summary = (
            f"Helix added {count} {person_word} to the network"
            + (f" across {len(new_companies)} new organizations" if new_companies else "")
            + ". These are the ones ranked highest for your interests."
        )

    date_label = utcnow().strftime("%b %d, %Y")

    return {
        "subject": f"{headline} · {settings.app_name}",
        "headline": headline,
        "summary": summary,
        "period": period,
        "period_label": config["label"],
        "period_noun": noun,
        "date_label": date_label,
        "dashboard_url": sender.app_url("/recommendations"),
        "stats": {
            "new_people": count,
            "new_companies": len(new_companies),
            "top_score": top_score,
            "total_people": len(corpus),
        },
        "recommendations": [
            {
                "name": p["name"],
                "title": p.get("title") or "",
                "company": p.get("company") or "",
                "linkedin_url": p.get("linkedin_url") or "",
                "score": p["score"],
                "why": p.get("why") or [],
            }
            for p in recommendations
        ],
        "trending_companies": [
            {**c, "url": sender.app_url(f"/companies/{c['name']}")} for c in trending
        ],
        "new_companies": new_companies[:12],
        "insights": insights,
        "reminders": reminders,
        "text_body": _text_version(headline, summary, recommendations),
    }


def _text_version(headline: str, summary: str, recommendations: list[dict]) -> str:
    lines = [headline, "", summary, ""]
    if recommendations:
        lines.append("Recommended for you:")
        for person in recommendations:
            company = f" · {person.get('company')}" if person.get("company") else ""
            lines.append(f"  • {person['name']} ({person['score']}/100){company}")
            if person.get("linkedin_url"):
                lines.append(f"    {person['linkedin_url']}")
        lines.append("")
    lines.append(f"Open Helix: {sender.app_url('/dashboard')}")
    lines.append(f"Email preferences: {sender.app_url('/settings')}")
    return "\n".join(lines)


def send_digest(user: dict, period: str = "weekly", people: list[dict] | None = None) -> bool:
    """Send one user their digest now. Used by the 'send me a test digest'
    action in Settings and by instant notifications."""
    corpus = people if people is not None else _load_people()
    digest = build_digest(user, period, corpus)
    sent = sender.send_digest_email(user, digest)
    if sent:
        # Only record delivery on success, so a failed send is retried with the
        # same content next time rather than silently skipped.
        _record_emailed(user["id"], digest["recommendations"], corpus)
    return sent


def run_digests(frequency: str, dry_run: bool = False) -> dict:
    """Send the digest to everyone subscribed to `frequency`.

    Returns a summary so the worker (and its logs) can report what happened.
    """
    if frequency not in PERIODS:
        raise ValueError(f"Unknown digest frequency: {frequency}")

    sync_from_csv()
    corpus = _load_people()
    recipients = user_service.users_wanting_digest(frequency)

    sent = 0
    failed = 0
    skipped = 0

    for user in recipients:
        if not user.get("is_active"):
            skipped += 1
            continue
        if settings.require_email_verification and not user.get("email_verified"):
            log.info("Skipping digest for unverified account %s", user["email"])
            skipped += 1
            continue

        digest = build_digest(user, frequency, corpus)

        if dry_run:
            log.info(
                "[dry-run] %s digest for %s: %s (%s recommendations)",
                frequency, user["email"], digest["headline"], len(digest["recommendations"]),
            )
            sent += 1
            continue

        if sender.send_digest_email(user, digest):
            sent += 1
            _record_emailed(user["id"], digest["recommendations"], corpus)
        else:
            failed += 1

    summary = {
        "frequency": frequency,
        "recipients": len(recipients),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "dry_run": dry_run,
    }
    log.info("Digest run complete: %s", summary)
    return summary


def _record_emailed(user_id: int, recommendations: list[dict], corpus: list[dict]) -> None:
    """Map the digest's rendered recommendations back to person ids and record
    them, so the next digest can lead with something new."""
    by_url = {p.get("linkedin_url"): p["id"] for p in corpus if p.get("linkedin_url")}
    resolved = [
        {"id": by_url[r["linkedin_url"]], "score": r["score"]}
        for r in recommendations
        if r.get("linkedin_url") and r["linkedin_url"] in by_url
    ]
    personalization_service.record_shown(user_id, resolved, channel="email")
