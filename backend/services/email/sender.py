"""High-level email sending.

Business logic calls the `send_*` functions here and never touches templates or
transports. Every attempt — success or failure — is recorded in `email_log`,
so a user reporting "I never got the reset email" is answerable from the
database rather than from guesswork.

Sending never raises. A mail outage must not turn signup into a 500; the caller
gets False and the reason is in the log.
"""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from config import settings
from db import db_conn, insert_returning_id, utcnow_iso
from services.email.providers import EmailMessage, EmailSendError, get_provider

log = logging.getLogger("helix.email")

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# StrictUndefined turns a typo'd variable into a loud error at render time
# instead of a silently blank section in an email a customer receives.
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def app_url(path: str = "") -> str:
    """Build a public, absolute URL. Always derived from PUBLIC_URL so emails
    sent from a real deployment never contain localhost links."""
    return f"{settings.public_url.rstrip('/')}{path}"


def _base_context() -> dict:
    return {
        "app_name": settings.app_name,
        "app_url": app_url(),
        # "/" is the public landing page; signed-in users belong on /dashboard.
        "dashboard_url": app_url("/dashboard"),
        "preferences_url": app_url("/settings"),
    }


def render(template_name: str, subject: str, **context) -> str:
    template = _env.get_template(template_name)
    return template.render(subject=subject, **_base_context(), **context)


def _log_attempt(user_id: int | None, to: str, subject: str, template: str,
                 provider: str, status: str, error: str = "") -> None:
    with db_conn() as conn:
        insert_returning_id(
            conn,
            """
            INSERT INTO email_log (user_id, to_email, subject, template, provider, status, error, created_at)
            VALUES (:user_id, :to_email, :subject, :template, :provider, :status, :error, :created_at)
            """,
            {
                "user_id": user_id,
                "to_email": to,
                "subject": subject,
                "template": template,
                "provider": provider,
                "status": status,
                "error": error[:1000],
                "created_at": utcnow_iso(),
            },
        )


def send_email(to: str, subject: str, template_name: str, user_id: int | None = None,
               text: str = "", **context) -> bool:
    """Render and send. Returns True on success, False on any failure."""
    provider = get_provider()
    try:
        html = render(template_name, subject, **context)
    except Exception as exc:  # template bugs must not escape into a request
        log.exception("Failed to render email template %s", template_name)
        _log_attempt(user_id, to, subject, template_name, provider.name, "failed", f"render error: {exc}")
        return False

    try:
        provider.send(EmailMessage(to=to, subject=subject, html=html, text=text))
    except EmailSendError as exc:
        log.error("Email to %s failed via %s: %s", to, provider.name, exc)
        _log_attempt(user_id, to, subject, template_name, provider.name, "failed", str(exc))
        return False
    except Exception as exc:  # a provider raising something unexpected
        log.exception("Unexpected email failure to %s via %s", to, provider.name)
        _log_attempt(user_id, to, subject, template_name, provider.name, "failed", str(exc))
        return False

    _log_attempt(user_id, to, subject, template_name, provider.name, "sent")
    return True


# --- Transactional ----------------------------------------------------------

def send_verification_email(user: dict, token: str) -> bool:
    url = app_url(f"/verify-email?token={quote(token)}")
    return send_email(
        to=user["email"],
        subject=f"Confirm your email · {settings.app_name}",
        template_name="verify_email.html",
        user_id=user["id"],
        user=user,
        verify_url=url,
        expires_hours=settings.email_token_ttl_hours,
        text=(
            f"Welcome to {settings.app_name}.\n\n"
            f"Confirm your email address:\n{url}\n\n"
            f"This link expires in {settings.email_token_ttl_hours} hours."
        ),
    )


def send_password_reset_email(user: dict, token: str) -> bool:
    url = app_url(f"/reset-password?token={quote(token)}")
    return send_email(
        to=user["email"],
        subject=f"Reset your password · {settings.app_name}",
        template_name="reset_password.html",
        user_id=user["id"],
        user=user,
        reset_url=url,
        expires_hours=settings.email_token_ttl_hours,
        text=(
            f"Reset your {settings.app_name} password:\n{url}\n\n"
            f"This link expires in {settings.email_token_ttl_hours} hours and can be used once.\n"
            "If you didn't request this, ignore this email — your password stays unchanged."
        ),
    )


WELCOME_STEPS = [
    {
        "title": "Tell Helix what you care about",
        "body": "Set your focus areas, target companies and seniority in Settings — recommendations re-rank around them immediately.",
    },
    {
        "title": "Build your watchlist",
        "body": "Follow anyone worth tracking. Add notes, set a priority and a reminder date, and they'll appear in your digest when it's time to reach out.",
    },
    {
        "title": "Check AI Insights",
        "body": "A standing read on what's moving — fastest-growing labs, who's hiring, and who to contact first.",
    },
]


def send_welcome_email(user: dict, digest_frequency: str = "weekly") -> bool:
    return send_email(
        to=user["email"],
        subject=f"Welcome to {settings.app_name}",
        template_name="welcome.html",
        user_id=user["id"],
        user=user,
        steps=WELCOME_STEPS,
        digest_frequency=digest_frequency,
        text=(
            f"Welcome to {settings.app_name}, {user['name']}.\n\n"
            f"Open your dashboard: {app_url('/dashboard')}\n\n"
            "Get started by setting your focus areas in Settings, following people "
            "worth tracking, and checking AI Insights."
        ),
    )


def send_digest_email(user: dict, digest: dict) -> bool:
    return send_email(
        to=user["email"],
        subject=digest["subject"],
        template_name="digest.html",
        user_id=user["id"],
        user=user,
        digest=digest,
        text=digest.get("text_body", digest["headline"]),
    )
