"""Session capability detection and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .auth import Credential


def _cookie_value(cookies: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = cookies.get(name)
        if value:
            return value
    return None


@dataclass
class SessionState:
    """Normalized session information derived from saved/browser cookies."""

    cookies: dict[str, str]
    source: str = "unknown"
    username: str | None = None
    modhash: str | None = None
    last_verified_at: float | None = None
    validation_error: str | None = None
    capabilities: set[str] = field(default_factory=set)

    @classmethod
    def from_credential(cls, credential: Credential | None) -> SessionState:
        if credential is None:
            return cls(cookies={}, source="none", validation_error="No credential loaded")

        state = cls(
            cookies=dict(credential.cookies),
            source=credential.source,
            username=credential.username,
            modhash=credential.modhash,
            last_verified_at=credential.last_verified_at,
        )
        state.refresh_capabilities()
        return state

    @property
    def is_authenticated(self) -> bool:
        return "read" in self.capabilities

    @property
    def can_write(self) -> bool:
        return "write" in self.capabilities

    def refresh_capabilities(self) -> None:
        capabilities: set[str] = set()
        # reddit_session → logged-in read; token_v2 → anonymous session read.
        if self.cookies.get("reddit_session") or self.cookies.get("token_v2"):
            capabilities.add("read")

        inferred_modhash = self.modhash or _cookie_value(self.cookies, "modhash", "csrf_token")
        if inferred_modhash:
            self.modhash = inferred_modhash
            capabilities.add("write")

        self.capabilities = capabilities

    def apply_identity(self, identity: dict[str, Any]) -> None:
        """Update session from a validated identity payload."""
        data = identity.get("data", identity)
        name = data.get("name") or data.get("username")
        if name:
            self.username = name

        modhash = data.get("modhash") or self.modhash or _cookie_value(self.cookies, "modhash", "csrf_token")
        if modhash:
            self.modhash = modhash

        self.validation_error = None
        self.refresh_capabilities()

    def apply_validation_error(self, message: str) -> None:
        self.validation_error = message
        self.refresh_capabilities()


@dataclass(frozen=True)
class SessionValidationResult:
    """Result from probing the current credential."""

    authenticated: bool
    username: str | None
    capabilities: tuple[str, ...]
    source: str
    cookie_count: int
    modhash_present: bool
    last_verified_at: float | None
    error: str | None = None


def summarize_session(state: SessionState) -> SessionValidationResult:
    """Convert mutable session state to structured command output."""
    capabilities = tuple(sorted(state.capabilities))
    return SessionValidationResult(
        authenticated=state.is_authenticated,
        username=state.username,
        capabilities=capabilities,
        source=state.source,
        cookie_count=len(state.cookies),
        modhash_present=bool(state.modhash),
        last_verified_at=state.last_verified_at,
        error=state.validation_error,
    )
