"""Authentication for Reddit CLI.

Strategy:
1. Try loading saved credential from ~/.config/rdt-cli/credential.json
2. Try extracting cookies from local browsers via browser-cookie3
3. No QR login — Reddit uses OAuth/cookie-based auth only
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any

from .constants import (
    CONFIG_DIR,
    CREDENTIAL_FILE,
    ENV_COOKIE,
    ENV_MODHASH,
    ENV_SESSION,
    REQUIRED_COOKIES,
)

logger = logging.getLogger(__name__)

# Credential TTL: attempt refresh after 7 days
CREDENTIAL_TTL_DAYS = 7
_CREDENTIAL_TTL_SECONDS = CREDENTIAL_TTL_DAYS * 86400


# ── Credential data class ───────────────────────────────────────────


class Credential:
    """Holds Reddit session cookies."""

    def __init__(
        self,
        cookies: dict[str, str],
        *,
        source: str = "unknown",
        username: str | None = None,
        modhash: str | None = None,
        saved_at: float | None = None,
        last_verified_at: float | None = None,
    ):
        self.cookies = cookies
        self.source = source
        self.username = username
        self.modhash = modhash
        self.saved_at = saved_at
        self.last_verified_at = last_verified_at

    @property
    def is_valid(self) -> bool:
        return bool(self.cookies)

    def to_dict(self) -> dict[str, Any]:
        saved_at = self.saved_at or time.time()
        return {
            "cookies": self.cookies,
            "source": self.source,
            "username": self.username,
            "modhash": self.modhash,
            "saved_at": saved_at,
            "last_verified_at": self.last_verified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Credential:
        return cls(
            cookies=data.get("cookies", {}),
            source=data.get("source", "saved"),
            username=data.get("username"),
            modhash=data.get("modhash"),
            saved_at=data.get("saved_at"),
            last_verified_at=data.get("last_verified_at"),
        )

    def as_cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


# ── Persistence ─────────────────────────────────────────────────────


def save_credential(credential: Credential) -> None:
    """Save credential to disk with restricted permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if credential.saved_at is None:
        credential.saved_at = time.time()
    CREDENTIAL_FILE.write_text(json.dumps(credential.to_dict(), indent=2, ensure_ascii=False))
    CREDENTIAL_FILE.chmod(0o600)


def load_credential() -> Credential | None:
    """Load saved credential with TTL-based auto-refresh."""
    if not CREDENTIAL_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        cred = Credential.from_dict(data)
        if not cred.is_valid:
            return None

        # TTL check — auto-refresh if stale
        saved_at = data.get("saved_at", 0)
        if saved_at and (time.time() - saved_at) > _CREDENTIAL_TTL_SECONDS:
            logger.info("Credential older than %d days, attempting browser refresh", CREDENTIAL_TTL_DAYS)
            fresh = extract_browser_credential()
            if fresh:
                logger.info("Auto-refreshed credential from browser")
                return fresh
            logger.warning("Cookie refresh failed; using existing cookies")

        return cred
    except (json.JSONDecodeError, KeyError):
        return None


def clear_credential() -> None:
    """Remove saved credential file."""
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()


# ── Environment variable credential ─────────────────────────────────


def parse_cookie_header(header: str) -> dict[str, str]:
    """Parse a raw Cookie header ("a=1; b=2") into a name→value dict.

    Splits each pair on the first '=' only (cookie values such as JWTs may
    contain '='). Blank segments and nameless pairs are skipped.
    """
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        name, sep, value = part.strip().partition("=")
        name = name.strip()
        if not sep or not name:
            continue
        cookies[name] = value.strip()
    return cookies


def extract_env_credential() -> Credential | None:
    """Build a credential from environment variables (no browser access).

    - RDT_COOKIE  : full raw Cookie header (most robust — carries the whole set)
    - RDT_SESSION : reddit_session cookie value (convenience; overlays RDT_COOKIE)
    - RDT_MODHASH : modhash (enables write actions)

    Returned in-memory only; env credentials are never written to disk.
    """
    raw = os.getenv(ENV_COOKIE)
    session = os.getenv(ENV_SESSION)
    modhash = os.getenv(ENV_MODHASH)

    cookies: dict[str, str] = {}
    if raw:
        cookies.update(parse_cookie_header(raw))
    if session:
        cookies["reddit_session"] = session.strip()
    if modhash:
        cookies["modhash"] = modhash.strip()

    if not cookies:
        return None

    return Credential(
        cookies=cookies,
        source="env",
        modhash=modhash.strip() if modhash else None,
    )


# ── Browser cookie extraction ───────────────────────────────────────


def extract_browser_credential() -> Credential | None:
    """Extract Reddit cookies from installed browsers.

    Uses subprocess to avoid SQLite lock when browser is running.
    """
    if shutil.which("uv"):
        cred = _extract_subprocess()
        if cred:
            return cred
    return _extract_direct()


def _extract_subprocess() -> Credential | None:
    """Extract via uv subprocess — avoids SQLite lock."""
    script = '''
import browser_cookie3, json
cookies = {}
for browser_fn in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.brave]:
    try:
        jar = browser_fn(domain_name=".reddit.com")
        for c in jar:
            cookies[c.name] = c.value
        if cookies:
            break
    except Exception:
        continue
if cookies:
    print(json.dumps(cookies))
'''
    try:
        result = subprocess.run(
            ["uv", "run", "--with", "browser-cookie3", "python3", "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            cookies = json.loads(result.stdout.strip())
            if any(k in cookies for k in REQUIRED_COOKIES):
                cred = Credential(cookies=cookies, source="browser:subprocess")
                save_credential(cred)
                return cred
    except Exception as e:
        logger.debug("Subprocess extraction failed: %s", e)
    return None


def _extract_direct() -> Credential | None:
    """Fallback direct extraction (may fail if browser is open)."""
    try:
        import browser_cookie3
    except ImportError:
        logger.warning("browser-cookie3 not available for direct extraction")
        return None

    for fn in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.brave]:
        try:
            jar = fn(domain_name=".reddit.com")
            cookies = {c.name: c.value for c in jar}
            if any(k in cookies for k in REQUIRED_COOKIES):
                cred = Credential(cookies=cookies, source=f"browser:{fn.__name__}")
                save_credential(cred)
                return cred
        except Exception:
            continue
    return None


# ── Credential chain ────────────────────────────────────────────────


def get_credential(*, allow_browser: bool = True) -> Credential | None:
    """Resolve a credential: env → saved → browser → None.

    Priority order:
    1. Environment variables (RDT_COOKIE / RDT_SESSION) — non-invasive, highest
       priority, read fresh each run.
    2. Saved credential file.
    3. Browser cookie extraction — invasive (reads the browser's cookie database)
       and slow, so it is the last resort and is gated behind ``allow_browser``.
       Public/optional endpoints pass ``allow_browser=False`` to avoid the browser.
    """
    cred = extract_env_credential()
    if cred:
        return cred
    cred = load_credential()
    if cred:
        return cred
    if allow_browser:
        cred = extract_browser_credential()
        if cred:
            return cred
    return None
