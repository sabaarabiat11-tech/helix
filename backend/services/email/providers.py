"""Email transport adapters.

Business logic never imports a provider directly — it calls `send_email()` in
`sender.py`, which resolves whichever adapter `EMAIL_PROVIDER` names. Adding a
new service means writing one class with a `send()` method and adding it to
`_PROVIDERS`; nothing else in the application changes.

The default is `console`, which writes messages to `data/outbox/` instead of
sending them. That keeps local development and tests completely offline while
still letting you open the real rendered HTML in a browser.
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from typing import Protocol

import httpx

from config import PROJECT_ROOT, settings
from db.timeutil import utcnow

log = logging.getLogger("helix.email")

OUTBOX_DIR = PROJECT_ROOT / "data" / "outbox"
HTTP_TIMEOUT = 20.0


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str = ""

    @property
    def to_name(self) -> str:
        return parseaddr(self.to)[0]

    @property
    def to_address(self) -> str:
        return parseaddr(self.to)[1] or self.to


class EmailSendError(Exception):
    """Transport-level failure. Callers decide whether to retry or log."""


class EmailProvider(Protocol):
    """The contract every transport satisfies."""

    name: str

    def send(self, message: EmailMessage) -> None: ...


# --- Development ------------------------------------------------------------

class ConsoleEmailProvider:
    """Writes each message to data/outbox/ and logs the path.

    Deliberately the default: a fresh clone can exercise signup, verification
    and digests end to end without any third-party account, and the emailed
    links are real and clickable straight out of the saved file.
    """

    name = "console"

    def send(self, message: EmailMessage) -> None:
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        stamp = utcnow().strftime("%Y%m%d-%H%M%S-%f")
        safe_recipient = message.to_address.replace("@", "_at_").replace("/", "_")
        path = OUTBOX_DIR / f"{stamp}_{safe_recipient}.html"
        path.write_text(message.html, encoding="utf-8")
        log.info("[console email] To: %s | %s -> %s", message.to_address, message.subject, path)


# --- SMTP (works with Gmail, Postmark, SES SMTP, Mailtrap, ...) --------------

class SMTPEmailProvider:
    name = "smtp"

    def __init__(self) -> None:
        if not settings.smtp_host:
            raise EmailSendError("SMTP_HOST is not configured")

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        if settings.email_reply_to:
            mime["Reply-To"] = settings.email_reply_to
        mime.set_content(message.text or _strip_html(message.html))
        mime.add_alternative(message.html, subtype="html")

        try:
            if settings.smtp_use_tls:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=HTTP_TIMEOUT) as server:
                    server.starttls(context=ssl.create_default_context())
                    if settings.smtp_user:
                        server.login(settings.smtp_user, settings.smtp_password)
                    server.send_message(mime)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=HTTP_TIMEOUT) as server:
                    if settings.smtp_user:
                        server.login(settings.smtp_user, settings.smtp_password)
                    server.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailSendError(f"SMTP send failed: {exc}") from exc


# --- HTTP API providers -----------------------------------------------------

def _post_json(url: str, *, headers: dict, json_body: dict | None = None, data: dict | None = None,
               auth: tuple[str, str] | None = None, provider: str) -> None:
    try:
        response = httpx.post(
            url, headers=headers, json=json_body, data=data, auth=auth, timeout=HTTP_TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"{provider} request failed: {exc}") from exc

    if response.status_code >= 400:
        raise EmailSendError(
            f"{provider} rejected the message ({response.status_code}): {response.text[:300]}"
        )


class ResendEmailProvider:
    name = "resend"

    def __init__(self) -> None:
        if not settings.resend_api_key:
            raise EmailSendError("RESEND_API_KEY is not configured")

    def send(self, message: EmailMessage) -> None:
        body = {
            "from": settings.email_from,
            "to": [message.to_address],
            "subject": message.subject,
            "html": message.html,
        }
        if message.text:
            body["text"] = message.text
        if settings.email_reply_to:
            body["reply_to"] = settings.email_reply_to
        _post_json(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json_body=body,
            provider="Resend",
        )


class SendGridEmailProvider:
    name = "sendgrid"

    def __init__(self) -> None:
        if not settings.sendgrid_api_key:
            raise EmailSendError("SENDGRID_API_KEY is not configured")

    def send(self, message: EmailMessage) -> None:
        from_name, from_email = parseaddr(settings.email_from)
        content = []
        if message.text:
            content.append({"type": "text/plain", "value": message.text})
        content.append({"type": "text/html", "value": message.html})

        body = {
            "personalizations": [{"to": [{"email": message.to_address}]}],
            "from": {"email": from_email, "name": from_name or settings.app_name},
            "subject": message.subject,
            "content": content,
        }
        if settings.email_reply_to:
            body["reply_to"] = {"email": parseaddr(settings.email_reply_to)[1]}
        _post_json(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json_body=body,
            provider="SendGrid",
        )


class MailgunEmailProvider:
    name = "mailgun"

    def __init__(self) -> None:
        if not settings.mailgun_api_key or not settings.mailgun_domain:
            raise EmailSendError("MAILGUN_API_KEY and MAILGUN_DOMAIN must both be configured")

    def send(self, message: EmailMessage) -> None:
        form = {
            "from": settings.email_from,
            "to": message.to_address,
            "subject": message.subject,
            "html": message.html,
        }
        if message.text:
            form["text"] = message.text
        if settings.email_reply_to:
            form["h:Reply-To"] = settings.email_reply_to
        _post_json(
            f"https://api.mailgun.net/v3/{settings.mailgun_domain}/messages",
            headers={},
            data=form,
            auth=("api", settings.mailgun_api_key),
            provider="Mailgun",
        )


class SESEmailProvider:
    """Amazon SES via the SendRawEmail HTTP API through boto3.

    boto3 is an optional dependency — SES also speaks SMTP, so the `smtp`
    provider with SES credentials works without installing anything extra.
    """

    name = "ses"

    def __init__(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise EmailSendError(
                "EMAIL_PROVIDER=ses needs boto3. Install it with `pip install boto3`, "
                "or use EMAIL_PROVIDER=smtp with your SES SMTP credentials."
            ) from exc
        if not settings.aws_region:
            raise EmailSendError("AWS_REGION is not configured")

    def send(self, message: EmailMessage) -> None:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        mime = MimeMessage()
        mime["From"] = settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        if settings.email_reply_to:
            mime["Reply-To"] = settings.email_reply_to
        mime.set_content(message.text or _strip_html(message.html))
        mime.add_alternative(message.html, subtype="html")

        client_kwargs = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        try:
            client = boto3.client("ses", **client_kwargs)
            client.send_raw_email(RawMessage={"Data": mime.as_bytes()})
        except (BotoCoreError, ClientError) as exc:
            raise EmailSendError(f"SES send failed: {exc}") from exc


# --- Resolution -------------------------------------------------------------

_PROVIDERS: dict[str, type] = {
    "console": ConsoleEmailProvider,
    "smtp": SMTPEmailProvider,
    "resend": ResendEmailProvider,
    "sendgrid": SendGridEmailProvider,
    "mailgun": MailgunEmailProvider,
    "ses": SESEmailProvider,
}

_cached_provider: EmailProvider | None = None


def get_provider() -> EmailProvider:
    """Resolve the configured provider once, then reuse it.

    If a real provider is configured but unusable (missing key, missing
    dependency) we log loudly and fall back to the console provider rather than
    crashing the app — a broken mail configuration should not take down signup
    or the dashboard.
    """
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider

    name = settings.email_provider or "console"
    provider_class = _PROVIDERS.get(name)

    if provider_class is None:
        log.error(
            "Unknown EMAIL_PROVIDER %r (expected one of: %s). Falling back to console.",
            name, ", ".join(sorted(_PROVIDERS)),
        )
        _cached_provider = ConsoleEmailProvider()
        return _cached_provider

    try:
        _cached_provider = provider_class()
    except EmailSendError as exc:
        log.error("Email provider %r is not usable: %s. Falling back to console.", name, exc)
        _cached_provider = ConsoleEmailProvider()

    return _cached_provider


def reset_provider_cache() -> None:
    """Test hook — forces the next get_provider() call to re-resolve."""
    global _cached_provider
    _cached_provider = None


def _strip_html(html: str) -> str:
    """Very small HTML-to-text fallback for the plain-text alternative part.
    Real templates supply their own text version; this only covers the case
    where one didn't."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


__all__ = [
    "EmailMessage",
    "EmailProvider",
    "EmailSendError",
    "get_provider",
    "reset_provider_cache",
    "ConsoleEmailProvider",
    "SMTPEmailProvider",
    "ResendEmailProvider",
    "SendGridEmailProvider",
    "MailgunEmailProvider",
    "SESEmailProvider",
]
