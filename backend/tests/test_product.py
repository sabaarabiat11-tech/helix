"""Per-user isolation, personalization, watchlist and email composition."""
from __future__ import annotations

# --- Isolation between accounts ---------------------------------------------

def test_watchlists_are_isolated_between_users(client, registered):
    alice_auth, _, _ = registered("alice")
    bob_auth, _, _ = registered("bob")

    person_id = client.get("/api/discoveries?page_size=1", headers=alice_auth).json()["results"][0]["id"]

    assert client.post(f"/api/watchlist/{person_id}", headers=alice_auth).status_code == 200
    client.patch(f"/api/watchlist/{person_id}", headers=alice_auth, json={"notes": "alice private"})

    # The same researcher can be followed by both, with independent notes.
    assert client.get("/api/watchlist", headers=bob_auth).json() == []
    assert client.post(f"/api/watchlist/{person_id}", headers=bob_auth).status_code == 200
    client.patch(f"/api/watchlist/{person_id}", headers=bob_auth, json={"notes": "bob private"})

    alice_entry = client.get("/api/watchlist", headers=alice_auth).json()[0]
    bob_entry = client.get("/api/watchlist", headers=bob_auth).json()[0]
    assert alice_entry["notes"] == "alice private"
    assert bob_entry["notes"] == "bob private"


def test_search_never_leaks_another_users_notes(client, registered):
    alice_auth, _, _ = registered("alice")
    bob_auth, _, _ = registered("bob")

    person_id = client.get("/api/discoveries?page_size=1", headers=alice_auth).json()["results"][0]["id"]
    client.post(f"/api/watchlist/{person_id}", headers=alice_auth)
    client.patch(f"/api/watchlist/{person_id}", headers=alice_auth, json={"notes": "zebracorn"})

    assert client.get("/api/search?q=zebracorn", headers=bob_auth).json()["watchlist"] == []
    assert len(client.get("/api/search?q=zebracorn", headers=alice_auth).json()["watchlist"]) == 1


def test_watchlist_rejects_invalid_values(client, registered):
    auth, _, _ = registered()
    person_id = client.get("/api/discoveries?page_size=1", headers=auth).json()["results"][0]["id"]
    client.post(f"/api/watchlist/{person_id}", headers=auth)

    assert client.patch(
        f"/api/watchlist/{person_id}", headers=auth, json={"priority": "urgent"}
    ).status_code == 400
    assert client.post("/api/watchlist/999999", headers=auth).status_code == 404


def test_following_twice_is_idempotent(client, registered):
    auth, _, _ = registered()
    person_id = client.get("/api/discoveries?page_size=1", headers=auth).json()["results"][0]["id"]
    client.post(f"/api/watchlist/{person_id}", headers=auth)
    client.post(f"/api/watchlist/{person_id}", headers=auth)
    assert len(client.get("/api/watchlist", headers=auth).json()) == 1


# --- Notifications ----------------------------------------------------------

def test_broadcast_respects_per_user_opt_out(client, registered):
    from services import notification_service

    opted_in_auth, _, _ = registered("optedin")
    opted_out_auth, _, _ = registered("optedout")
    client.patch(
        "/api/users/me/preferences", headers=opted_out_auth, json={"notify_new_companies": False}
    )

    before_in = client.get("/api/notifications", headers=opted_in_auth).json()["unread_count"]
    before_out = client.get("/api/notifications", headers=opted_out_auth).json()["unread_count"]

    notification_service.broadcast("company", "New company", "Acme Bio appeared.")

    assert client.get("/api/notifications", headers=opted_in_auth).json()["unread_count"] == before_in + 1
    assert client.get("/api/notifications", headers=opted_out_auth).json()["unread_count"] == before_out


def test_marking_read_is_scoped_to_the_caller(client, registered):
    from services import notification_service

    alice_auth, _, _ = registered("alice")
    bob_auth, _, _ = registered("bob")
    notification_service.broadcast("discovery", "Shared event", "Something happened.")

    bob_notifications = client.get("/api/notifications", headers=bob_auth).json()["notifications"]
    client.post(f"/api/notifications/{bob_notifications[0]['id']}/read", headers=bob_auth)

    assert client.get("/api/notifications", headers=bob_auth).json()["unread_count"] == 0
    assert client.get("/api/notifications", headers=alice_auth).json()["unread_count"] >= 1


# --- Personalization --------------------------------------------------------

def test_recommendations_are_explained(client, registered):
    auth, _, _ = registered()
    people = client.get("/api/recommendations?limit=5", headers=auth).json()["recommended_today"]
    assert len(people) == 5
    assert all(person["why"] for person in people), "every recommendation must justify itself"
    scores = [p["score"] for p in people]
    assert scores == sorted(scores, reverse=True)


def test_recommendation_limit_is_bounded(client, registered):
    """The endpoint caps `limit` so one request can't ask the server to score
    and serialize the entire corpus."""
    auth, _, _ = registered()
    assert client.get("/api/recommendations?limit=50", headers=auth).status_code == 200
    assert client.get("/api/recommendations?limit=200", headers=auth).status_code == 422


def test_preferences_boost_matching_people_and_say_why(client, registered):
    # Goes through the service rather than the API because the assertion is
    # about ranking across the whole corpus, and the endpoint deliberately
    # caps how much of it one request can return.
    from services import personalization_service

    auth, user, _ = registered()
    bundle = client.get("/api/recommendations/bundle", headers=auth).json()
    target = bundle["most_active_organizations"][0]["name"]

    client.patch("/api/users/me/preferences", headers=auth, json={"preferred_companies": [target]})
    ranked = personalization_service.rank_for_user(user["id"], limit=1000)

    boosted = [p for p in ranked if p["company"] == target and p["personal_adjustment"] > 0]
    assert boosted, "a target company should raise its people's scores"
    person = boosted[0]
    assert person["score"] > person["base_score"]
    assert any("target compan" in reason for reason in person["why"])


def test_min_score_filters_results(client, registered):
    from services import personalization_service

    auth, user, _ = registered()

    unfiltered = personalization_service.rank_for_user(user["id"], limit=1000)
    assert unfiltered, "fixture data should produce some recommendations"

    # Derived from the data rather than hardcoded: the corpus's top score is
    # whatever the scoring weights happen to produce, so a fixed threshold
    # like 95 would silently start matching nothing if the weights change.
    scores = sorted(p["score"] for p in unfiltered)
    threshold = scores[len(scores) // 2]

    client.patch("/api/users/me/preferences", headers=auth, json={"min_score": threshold})
    filtered = personalization_service.rank_for_user(user["id"], limit=1000)

    assert filtered, "a median threshold should still leave results"
    assert len(filtered) < len(unfiltered), "the threshold should actually exclude someone"
    assert all(p["score"] >= threshold for p in filtered)


def test_bundle_contains_every_section(client, registered):
    auth, _, _ = registered()
    bundle = client.get("/api/recommendations/bundle", headers=auth).json()
    for key in (
        "top_today", "top_this_week", "to_follow",
        "trending_companies", "most_active_organizations", "preferences_applied",
    ):
        assert key in bundle
    assert len(bundle["top_this_week"]) <= 10


def test_invalid_preferences_are_rejected(client, registered):
    auth, _, _ = registered()
    assert client.patch(
        "/api/users/me/preferences", headers=auth, json={"digest_frequency": "hourly"}
    ).status_code == 400
    assert client.patch(
        "/api/users/me/preferences", headers=auth, json={"seniority_preference": "wizard"}
    ).status_code == 400


# --- Email ------------------------------------------------------------------

def test_digest_renders_completely(client, registered):
    from services import digest_service, user_service

    auth, user, _ = registered()
    digest = digest_service.build_digest(user_service.get_by_id(user["id"]), "weekly")

    for key in ("subject", "headline", "summary", "stats", "recommendations", "text_body"):
        assert key in digest
    assert set(digest["stats"]) == {"new_people", "new_companies", "top_score", "total_people"}


def test_digest_html_has_no_unrendered_template_tags(client, registered):
    from services import digest_service, user_service
    from services.email import sender

    _, user, _ = registered()
    full_user = user_service.get_by_id(user["id"])
    digest = digest_service.build_digest(full_user, "weekly")
    html = sender.render(
        "digest.html", digest["subject"], user=full_user, digest=digest
    )

    assert html.lstrip().startswith("<!DOCTYPE")
    assert "{{" not in html and "{%" not in html
    # Links must be absolute and public, never localhost-relative.
    assert "http" in html


def test_emails_are_logged(client, registered):
    from db import db_conn, scalar

    _, user, _ = registered()
    with db_conn() as conn:
        sent = scalar(
            conn, "SELECT COUNT(*) FROM email_log WHERE user_id = :uid", {"uid": user["id"]}
        )
    # Signup sends a verification email and a welcome email.
    assert sent >= 2


# --- Data integrity ---------------------------------------------------------

def test_account_deletion_cascades_but_spares_shared_corpus(client, registered):
    from db import db_conn, scalar

    auth, user, _ = registered()
    person_id = client.get("/api/discoveries?page_size=1", headers=auth).json()["results"][0]["id"]
    client.post(f"/api/watchlist/{person_id}", headers=auth)

    with db_conn() as conn:
        corpus_before = scalar(conn, "SELECT COUNT(*) FROM people")

    assert client.delete("/api/users/me", headers=auth).status_code == 200

    with db_conn() as conn:
        assert scalar(
            conn, "SELECT COUNT(*) FROM watchlist WHERE user_id = :uid", {"uid": user["id"]}
        ) == 0
        assert scalar(conn, "SELECT COUNT(*) FROM people") == corpus_before


def test_csv_export_matches_the_database(client, registered):
    auth, _, _ = registered()
    total = client.get("/api/stats", headers=auth).json()["total_people"]
    response = client.get("/api/export/csv", headers=auth)
    assert response.status_code == 200
    assert response.text.startswith("Name,Title,Company")
    assert len(response.text.strip().splitlines()) == total + 1
