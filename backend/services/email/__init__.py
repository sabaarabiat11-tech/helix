"""Email subsystem: transports (`providers`) and composition (`sender`).

Import `sender` and call its `send_*` functions; nothing outside this package
should reference a provider class directly.
"""
from services.email import providers, sender

__all__ = ["providers", "sender"]
