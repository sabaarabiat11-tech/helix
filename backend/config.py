"""Central application settings, resolved once from the environment.

Every deployment-specific value in the application flows through this module —
nothing else reads os.environ directly. That is what makes the app deployable
to a real domain without code changes: the same image runs locally against
SQLite and a console mailer, or in production against Postgres, Resend and a
public origin, purely by changing environment variables.

The pipeline (src/, run.py, start.py) has its own config.yaml/.env handling and
is deliberately untouched by this module.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root if present. Real deployments set real
# environment variables instead; load_dotenv never overrides those.
load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key) or default)
    except ValueError:
        return default


def _env_list(key: str, default: list[str] | None = None) -> list[str]:
    raw = _env(key)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def _registrable_domain(url: str) -> str:
    """Host of a URL, ignoring port and scheme.

    Deliberately a plain host comparison rather than a public-suffix lookup:
    `helix.vercel.app` and `helix-api.up.railway.app` are different hosts and
    must be treated as cross-site, and treating any host difference as
    cross-site errs toward the stricter cookie policy, which is the safe
    direction to be wrong in.
    """
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _default_database_url() -> str:
    """SQLite in data/app.db — the historical location, so existing installs
    keep their data with no migration step."""
    db_path = PROJECT_ROOT / "data" / "app.db"
    return f"sqlite:///{db_path.as_posix()}"


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True)
class Settings:
    # --- Identity -----------------------------------------------------------
    app_name: str = "Helix"
    environment: str = "development"
    debug: bool = False

    # --- URLs ---------------------------------------------------------------
    # public_url is where the browser reaches the app. Everything user-facing
    # (email links, OAuth redirect URIs) is built from it, never from a
    # hardcoded localhost.
    public_url: str = "http://localhost:5173"
    api_url: str = "http://localhost:8000"
    cors_origins: list[str] = field(default_factory=list)

    # --- Database -----------------------------------------------------------
    database_url: str = ""

    # Regex matched against the Origin header, in addition to the exact list
    # above. Exists for Vercel preview deployments, whose hostnames contain a
    # per-build hash and so cannot be enumerated ahead of time.
    cors_origin_regex: str = ""

    # --- Security -----------------------------------------------------------
    secret_key: str = ""
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    email_token_ttl_hours: int = 24
    cookie_secure: bool = False
    cookie_domain: str = ""
    cookie_samesite: str = "lax"

    # --- Email --------------------------------------------------------------
    email_provider: str = "console"
    email_from: str = "Helix <no-reply@helix.local>"
    email_reply_to: str = ""
    resend_api_key: str = ""
    sendgrid_api_key: str = ""
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # --- Features -----------------------------------------------------------
    # Whether any signed-in user may trigger the discovery pipeline. In a real
    # multi-tenant deployment the pipeline is infrastructure, not a per-user
    # action, so this defaults off outside development.
    allow_user_triggered_runs: bool = True
    require_email_verification: bool = False
    signup_enabled: bool = True

    # --- Scheduler ----------------------------------------------------------
    # Runs the digest sends from inside the API process. On by default so
    # recommendation emails work without anyone configuring a cron job; turn
    # off once a real scheduled job runs workers/digest_worker.py.
    enable_scheduler: bool = True
    scheduler_hour: int = 8          # UTC hour for the daily send
    scheduler_weekday: int = 0       # 0 = Monday, for the weekly send

    # --- OAuth --------------------------------------------------------------
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def is_staging(self) -> bool:
        return self.environment.lower() == "staging"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_cross_site(self) -> bool:
        """True when the browser origin and the API are different sites.

        This is the normal shape of the target deployment — frontend on
        Vercel, API on Railway — and it changes what a session cookie must
        look like: a `SameSite=Lax` cookie is simply not sent on cross-site
        requests, so sign-in would appear to succeed and then every subsequent
        request would 401. Deriving it here rather than asking the operator to
        set it makes that class of misconfiguration impossible.
        """
        return _registrable_domain(self.public_url) != _registrable_domain(self.api_url)

    @property
    def oauth_providers(self) -> dict[str, OAuthProviderConfig]:
        return {
            "google": OAuthProviderConfig(
                name="google",
                client_id=self.google_client_id,
                client_secret=self.google_client_secret,
                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
                scope="openid email profile",
            ),
            "github": OAuthProviderConfig(
                name="github",
                client_id=self.github_client_id,
                client_secret=self.github_client_secret,
                authorize_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                userinfo_url="https://api.github.com/user",
                scope="read:user user:email",
            ),
            "linkedin": OAuthProviderConfig(
                name="linkedin",
                client_id=self.linkedin_client_id,
                client_secret=self.linkedin_client_secret,
                # LinkedIn's current "Sign In with LinkedIn using OpenID
                # Connect" product — the older r_liteprofile flow is retired.
                authorize_url="https://www.linkedin.com/oauth/v2/authorization",
                token_url="https://www.linkedin.com/oauth/v2/accessToken",
                userinfo_url="https://api.linkedin.com/v2/userinfo",
                scope="openid email profile",
            ),
        }

    @property
    def enabled_oauth_providers(self) -> list[str]:
        return [name for name, cfg in self.oauth_providers.items() if cfg.configured]

    def oauth_redirect_uri(self, provider: str) -> str:
        return f"{self.api_url.rstrip('/')}/api/auth/oauth/{provider}/callback"


# HS256 derives a 256-bit MAC, so a key shorter than 32 bytes provides less
# entropy than the algorithm's output — RFC 7518 §3.2 requires at least this.
MIN_SECRET_KEY_BYTES = 32

_GENERATE_HINT = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


def _resolve_secret_key(environment: str) -> str:
    """Resolve the signing key, refusing to start a hosted deployment with a
    weak or absent one.

    Development generates a key so a fresh clone runs with zero configuration.
    That is exactly wrong for production, where an ephemeral key would sign
    every user out on each restart and redeploy — so there it is a hard
    failure instead.
    """
    key = _env("SECRET_KEY")
    is_hosted = environment.lower() in {"production", "prod", "staging"}

    if not key:
        if is_hosted:
            raise RuntimeError(
                f"SECRET_KEY must be set when ENVIRONMENT={environment}.\n"
                f"Generate one with:\n    {_GENERATE_HINT}"
            )
        return secrets.token_urlsafe(48)

    if is_hosted and len(key.encode("utf-8")) < MIN_SECRET_KEY_BYTES:
        raise RuntimeError(
            f"SECRET_KEY is too short ({len(key)} characters). "
            f"HS256 needs at least {MIN_SECRET_KEY_BYTES} bytes of key material.\n"
            f"Generate a proper one with:\n    {_GENERATE_HINT}"
        )

    return key


def _railway_domain() -> str:
    """Railway's own public hostname for this service, if we're on Railway.

    Railway injects RAILWAY_PUBLIC_DOMAIN into every deploy. Using it means
    API_URL is correct automatically — and API_URL is not cosmetic here: the
    cookie SameSite policy is derived by comparing its host against
    PUBLIC_URL's, so a wrong value silently breaks sign-in.
    """
    return _env("RAILWAY_PUBLIC_DOMAIN") or _env("RAILWAY_STATIC_URL")


def _is_platform_hosted() -> bool:
    """True when a hosting platform's own markers are present.

    Lets the app notice it is deployed even when ENVIRONMENT was never set —
    the exact state that had this backend running in development mode on a
    public URL, with an ephemeral SECRET_KEY and a database that vanishes on
    every redeploy.
    """
    return bool(_railway_domain() or _env("RAILWAY_ENVIRONMENT") or _env("RENDER") or _env("FLY_APP_NAME"))


def _resolve_cors_origins(public_url: str, is_hosted: bool) -> list[str]:
    """Allowed browser origins.

    Never returns "*" — the API is called with credentials, and the
    combination of a wildcard origin and credentialed requests is both
    rejected by browsers and a genuine security hole. Localhost is allowed in
    development only; a hosted deployment trusts nothing but its own frontend
    plus anything explicitly listed.
    """
    explicit = _env_list("CORS_ORIGINS")
    origins = set(explicit)

    if public_url:
        origins.add(public_url.rstrip("/"))
    if not is_hosted:
        origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})

    return sorted(o for o in origins if o)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    platform_hosted = _is_platform_hosted()

    # A deploy on Railway/Render/Fly is production unless explicitly told
    # otherwise. Defaulting to "development" there is actively dangerous: it
    # generates a throwaway SECRET_KEY on every boot (signing all users out on
    # each redeploy) and leaves the API docs public.
    environment = _env("ENVIRONMENT") or ("production" if platform_hosted else "development")

    railway_domain = _railway_domain()
    default_api_url = f"https://{railway_domain}" if railway_domain else "http://localhost:8000"

    public_url = _env("PUBLIC_URL", "http://localhost:5173").rstrip("/")
    api_url = _env("API_URL", default_api_url).rstrip("/")
    is_prod = environment.lower() in {"production", "prod"}
    is_hosted = is_prod or environment.lower() == "staging"

    # In a split deployment the session cookie travels cross-site, which the
    # browser only permits with SameSite=None — and only accepts alongside
    # Secure. Both are derived rather than configured, since getting either
    # wrong produces a login that succeeds and then immediately stops working.
    # An explicit COOKIE_SAMESITE still wins, for the rare proxy setup that
    # needs something else.
    cross_site = is_hosted and _registrable_domain(public_url) != _registrable_domain(api_url)
    default_samesite = "none" if cross_site else "lax"
    cookie_samesite = _env("COOKIE_SAMESITE", default_samesite).lower()
    cookie_secure = _env_bool("COOKIE_SECURE", is_hosted or cookie_samesite == "none")

    return Settings(
        app_name=_env("APP_NAME", "Helix"),
        environment=environment,
        debug=_env_bool("DEBUG", not is_prod),
        public_url=public_url,
        api_url=api_url,
        cors_origins=_resolve_cors_origins(public_url, is_hosted),
        cors_origin_regex=_env("CORS_ORIGIN_REGEX"),
        database_url=_env("DATABASE_URL") or _default_database_url(),
        secret_key=_resolve_secret_key(environment),
        access_token_ttl_minutes=_env_int("ACCESS_TOKEN_TTL_MINUTES", 30),
        refresh_token_ttl_days=_env_int("REFRESH_TOKEN_TTL_DAYS", 30),
        email_token_ttl_hours=_env_int("EMAIL_TOKEN_TTL_HOURS", 24),
        cookie_secure=cookie_secure,
        cookie_domain=_env("COOKIE_DOMAIN"),
        cookie_samesite=cookie_samesite,
        email_provider=_env("EMAIL_PROVIDER", "console").lower(),
        email_from=_env("EMAIL_FROM", "Helix <no-reply@helix.local>"),
        email_reply_to=_env("EMAIL_REPLY_TO"),
        resend_api_key=_env("RESEND_API_KEY"),
        sendgrid_api_key=_env("SENDGRID_API_KEY"),
        mailgun_api_key=_env("MAILGUN_API_KEY"),
        mailgun_domain=_env("MAILGUN_DOMAIN"),
        aws_region=_env("AWS_REGION"),
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY"),
        smtp_host=_env("SMTP_HOST"),
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD"),
        smtp_use_tls=_env_bool("SMTP_USE_TLS", True),
        allow_user_triggered_runs=_env_bool("ALLOW_USER_TRIGGERED_RUNS", not is_prod),
        require_email_verification=_env_bool("REQUIRE_EMAIL_VERIFICATION", False),
        signup_enabled=_env_bool("SIGNUP_ENABLED", True),
        enable_scheduler=_env_bool("ENABLE_SCHEDULER", True),
        scheduler_hour=max(0, min(23, _env_int("SCHEDULER_HOUR", 8))),
        scheduler_weekday=max(0, min(6, _env_int("SCHEDULER_WEEKDAY", 0))),
        google_client_id=_env("GOOGLE_CLIENT_ID"),
        google_client_secret=_env("GOOGLE_CLIENT_SECRET"),
        github_client_id=_env("GITHUB_CLIENT_ID"),
        github_client_secret=_env("GITHUB_CLIENT_SECRET"),
        linkedin_client_id=_env("LINKEDIN_CLIENT_ID"),
        linkedin_client_secret=_env("LINKEDIN_CLIENT_SECRET"),
    )


settings = get_settings()


def audit_configuration() -> list[str]:
    """Problems that would let the app boot but behave wrongly in production.

    These are warnings rather than startup failures on purpose: refusing to
    start would take a running service down over, say, a missing mail key.
    They are logged loudly at boot so the cause is visible in the deploy log
    instead of being discovered later through a support ticket.
    """
    problems: list[str] = []

    if not settings.is_production and _is_platform_hosted():
        problems.append(
            f"ENVIRONMENT={settings.environment} on a hosted platform. Set ENVIRONMENT=production "
            "so secure cookies are enabled and the API docs are not public."
        )

    if settings.is_production:
        if settings.is_sqlite:
            problems.append(
                "DATABASE_URL is unset, so this is running on SQLite inside the container. "
                "Every redeploy will erase all accounts and watchlists. "
                "Point it at PostgreSQL: postgresql+psycopg://USER:PASS@HOST:PORT/DB"
            )
        if settings.email_provider == "console":
            problems.append(
                "EMAIL_PROVIDER=console in production — verification and password-reset emails "
                "are written to data/outbox/ inside the container and nobody receives them."
            )
        if "localhost" in settings.public_url or "127.0.0.1" in settings.public_url:
            problems.append(
                f"PUBLIC_URL is {settings.public_url}. It must be the real frontend URL, or the "
                "browser origin will be blocked by CORS and every email link will point at localhost."
            )
        if settings.is_cross_site and settings.cookie_samesite != "none":
            problems.append(
                f"Frontend and API are on different hosts but cookie SameSite is "
                f"'{settings.cookie_samesite}'. Sign-in will appear to work and then 401."
            )

    return problems
