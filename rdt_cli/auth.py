"""Authentication for Reddit CLI.

Strategy:
1. Try loading saved credential from ~/.config/rdt-cli/credential.json
2. Try extracting cookies from local browsers via browser-cookie3
3. No QR login — Reddit uses OAuth/cookie-based auth only
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from typing import Any

from .constants import CONFIG_DIR, CREDENTIAL_FILE, REQUIRED_COOKIES

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


# ── Browser cookie extraction ───────────────────────────────────────


def _chrome_profile_cookie_files() -> list[str]:
    """Every Chrome/Chromium cookie DB across all profiles.

    Upstream browser_cookie3 reads only the "Default" profile, so a Reddit
    session living in "Profile 1" etc. is invisible to it. We enumerate all
    profiles and hand each cookie DB to browser_cookie3 via cookie_file=.
    """
    import glob
    import os

    home = os.path.expanduser("~")
    bases = [
        os.path.join(home, "Library", "Application Support", "Google", "Chrome"),  # macOS Chrome
        os.path.join(home, "Library", "Application Support", "Chromium"),          # macOS Chromium
        os.path.join(home, ".config", "google-chrome"),                            # Linux Chrome
        os.path.join(home, ".config", "chromium"),                                 # Linux Chromium
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),  # Windows
    ]
    files: list[str] = []
    for base in bases:
        if not base or not os.path.isdir(base):
            continue
        profile_dirs = [os.path.join(base, "Default")]
        profile_dirs += sorted(glob.glob(os.path.join(base, "Profile *")))
        for pdir in profile_dirs:
            for rel in ("Network/Cookies", "Cookies"):
                f = os.path.join(pdir, rel)
                if os.path.isfile(f) and f not in files:
                    files.append(f)
    return files


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
    """Extract via uv subprocess — avoids SQLite lock. Scans all Chrome profiles."""
    script = '''
import browser_cookie3, json, glob, os
home = os.path.expanduser("~")
bases = [
    os.path.join(home, "Library", "Application Support", "Google", "Chrome"),
    os.path.join(home, "Library", "Application Support", "Chromium"),
    os.path.join(home, ".config", "google-chrome"),
    os.path.join(home, ".config", "chromium"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
]
chrome_files = []
for base in bases:
    if not base or not os.path.isdir(base):
        continue
    pdirs = [os.path.join(base, "Default")] + sorted(glob.glob(os.path.join(base, "Profile *")))
    for pdir in pdirs:
        for rel in ("Network/Cookies", "Cookies"):
            f = os.path.join(pdir, rel)
            if os.path.isfile(f) and f not in chrome_files:
                chrome_files.append(f)

def _grab(fn):
    try:
        return {c.name: c.value for c in fn()}
    except Exception:
        return {}

result = {}
for f in chrome_files:
    ck = _grab(lambda f=f: browser_cookie3.chrome(cookie_file=f, domain_name=".reddit.com"))
    if "reddit_session" in ck:
        result = ck
        break
if not result:
    for fn in [browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.brave]:
        ck = _grab(lambda fn=fn: fn(domain_name=".reddit.com"))
        if "reddit_session" in ck:
            result = ck
            break
if result:
    print(json.dumps(result))
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
    """Direct extraction — tries every Chrome profile, then other browsers."""
    import os

    try:
        import browser_cookie3
    except ImportError:
        logger.warning("browser-cookie3 not available for direct extraction")
        return None

    def _profile_label(path: str) -> str:
        d = os.path.dirname(path)
        if os.path.basename(d) == "Network":
            d = os.path.dirname(d)
        return os.path.basename(d)

    attempts = []
    for f in _chrome_profile_cookie_files():
        attempts.append(
            (f"chrome:{_profile_label(f)}",
             lambda f=f: browser_cookie3.chrome(cookie_file=f, domain_name=".reddit.com"))
        )
    for fn in (browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.brave):
        attempts.append((fn.__name__, lambda fn=fn: fn(domain_name=".reddit.com")))

    for label, getter in attempts:
        try:
            cookies = {c.name: c.value for c in getter()}
            if any(k in cookies for k in REQUIRED_COOKIES):
                cred = Credential(cookies=cookies, source=f"browser:{label}")
                save_credential(cred)
                return cred
        except Exception:
            continue
    return None


# ── Credential chain ────────────────────────────────────────────────


def get_credential() -> Credential | None:
    """Try saved → browser → return None."""
    cred = load_credential()
    if cred:
        return cred
    cred = extract_browser_credential()
    if cred:
        return cred
    return None
