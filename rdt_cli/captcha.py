"""reCAPTCHA Enterprise solving via the Solvecaptcha API (solvecaptcha.com).

Publishing a Reddit post is gated behind reCAPTCHA Enterprise (invisible,
score-based, action ``post_submit`` — see rdt_cli.client.create_post). A token
can be captured from a browser, or bought from a captcha-solving service. This
module talks to the Solvecaptcha API directly — the 2captcha-compatible
protocol that the ``solvecaptcha-python`` package wraps (POST /in.php, poll
/res.php) — over httpx, so no extra runtime dependency is needed.

API key resolution (first match wins, see SOLVECAPTCHA_KEY_ENV_VARS):
  1. ``RDT_SOLVECAPTCHA_API_KEY``
  2. ``APIKEY_SOLVECAPTCHA`` (solvecaptcha-python's own convention)
  3. ``solvecaptcha_api_key`` in the user config file
     (``~/.config/rdt-cli/config.json``)

The returned token is single-use with a ~2 minute TTL — submit the post
immediately after solving.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .config import load_user_config
from .constants import (
    BASE_URL,
    RECAPTCHA_ACTION,
    RECAPTCHA_SITEKEY,
    SOLVECAPTCHA_API_URL,
    SOLVECAPTCHA_KEY_ENV_VARS,
)
from .exceptions import RedditApiError

logger = logging.getLogger(__name__)

__all__ = [
    "CaptchaSolveError",
    "get_solvecaptcha_api_key",
    "solve_recaptcha_token",
]


class CaptchaSolveError(RedditApiError):
    """Raised when the captcha-solving service rejects the task or times out."""

    def __init__(self, message: str, code: int | str | None = None):
        super().__init__(f"Captcha solving failed: {message}", code=code)


def get_solvecaptcha_api_key() -> str | None:
    """Return the Solvecaptcha API key: env vars first, then the config file."""
    for var in SOLVECAPTCHA_KEY_ENV_VARS:
        key = os.environ.get(var, "").strip()
        if key:
            return key
    key = str(load_user_config().get("solvecaptcha_api_key", "")).strip()
    return key or None


def solve_recaptcha_token(
    api_key: str,
    *,
    sitekey: str = RECAPTCHA_SITEKEY,
    page_url: str = f"{BASE_URL}/",
    action: str = RECAPTCHA_ACTION,
    min_score: float = 0.3,
    timeout: float = 180.0,
    polling_interval: float = 5.0,
) -> str:
    """Buy a reCAPTCHA Enterprise token for Reddit from Solvecaptcha.

    Submits a score-based Enterprise task (``method=userrecaptcha``,
    ``version=v3``, ``enterprise=1`` — how 2captcha-style APIs model
    reCAPTCHA Enterprise) and polls for the solution. ``min_score`` is the
    worker's target score; scores above ~0.3 are rarely achievable. Returns
    the ``g-recaptcha-response`` token (single-use, ~2 min TTL — use it
    immediately). Raises CaptchaSolveError on service errors or timeout.
    """
    task = {
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": sitekey,
        "pageurl": page_url,
        "version": "v3",
        "enterprise": 1,
        "action": action,
        "min_score": min_score,
    }
    with httpx.Client(base_url=SOLVECAPTCHA_API_URL, timeout=httpx.Timeout(30.0)) as http:
        captcha_id = _submit(http, task)
        logger.debug(
            "Solvecaptcha task %s submitted (sitekey=%s, action=%s)",
            captcha_id, sitekey, action,
        )
        return _poll(http, api_key, captcha_id, timeout=timeout, polling_interval=polling_interval)


def _submit(http: httpx.Client, task: dict) -> str:
    """POST the task to in.php and return the captcha id."""
    try:
        resp = http.post("/in.php", data=task)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise CaptchaSolveError(f"could not reach Solvecaptcha: {exc}") from exc
    body = resp.text.strip()
    if body.startswith("OK|"):
        return body[3:]
    # ERROR_WRONG_USER_KEY, ERROR_ZERO_BALANCE, ERROR_WRONG_GOOGLEKEY, ...
    raise CaptchaSolveError(f"task rejected: {body}")


def _poll(
    http: httpx.Client,
    api_key: str,
    captcha_id: str,
    *,
    timeout: float,
    polling_interval: float,
) -> str:
    """Poll res.php until the token is ready; returns the token."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            resp = http.get(
                "/res.php",
                params={"key": api_key, "action": "get", "id": captcha_id},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise CaptchaSolveError(f"result polling failed: {exc}") from exc
        body = resp.text.strip()
        if body.startswith("OK|"):
            return body[3:]
        if body == "CAPCHA_NOT_READY":
            if time.monotonic() >= deadline:
                raise CaptchaSolveError(f"no solution after {timeout:.0f}s")
            time.sleep(polling_interval)
            continue
        raise CaptchaSolveError(f"service error: {body}")
