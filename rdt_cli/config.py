"""Runtime configuration for transport, auth, and anti-detection defaults.

Also hosts loading of the optional user config file
(``~/.config/rdt-cli/config.json``) — plain JSON with settings like
``solvecaptcha_api_key`` that apply when no env var overrides them.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .constants import USER_CONFIG_FILE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeConfig:
    """Normalized runtime config used by transports and session validation."""

    timeout: float = 30.0
    read_request_delay: float = 1.0
    write_request_delay: float = 2.5
    max_retries: int = 3
    status_check_timeout: float = 10.0


DEFAULT_CONFIG = RuntimeConfig()


def load_user_config() -> dict[str, Any]:
    """Load the optional user config file (``~/.config/rdt-cli/config.json``).

    Returns an empty dict when the file is absent, unreadable, or not a JSON
    object — the file is entirely optional and must never break the CLI.
    """
    try:
        data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable config file %s: %s", USER_CONFIG_FILE, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("Ignoring config file %s: top level must be a JSON object", USER_CONFIG_FILE)
        return {}
    return data
