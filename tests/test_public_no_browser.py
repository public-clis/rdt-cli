"""Public commands must not trigger invasive browser cookie extraction.

Reading the browser's cookie database (via browser-cookie3 in a subprocess) is
slow and invasive. It should only happen for commands that explicitly require
authentication (``require_auth``) or the explicit ``rdt login`` flow — never as
a side effect of a public read command such as popular/all/sub/search/read.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rdt_cli import auth
from rdt_cli.auth import Credential
from rdt_cli.cli import cli
from rdt_cli.commands import _common
from rdt_cli.exceptions import SessionExpiredError

runner = CliRunner()


# ── optional_auth() never touches the browser ───────────────────────


class TestOptionalAuthNeverTouchesBrowser:
    def test_no_browser_extraction_when_no_saved_credential(self, monkeypatch):
        monkeypatch.setattr(auth, "load_credential", lambda: None)
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return None

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        result = _common.optional_auth()

        assert result is None
        assert calls["n"] == 0, "optional_auth must not extract browser cookies"

    def test_returns_saved_credential_without_browser(self, monkeypatch):
        cred = Credential(cookies={"reddit_session": "abc"})
        monkeypatch.setattr(auth, "load_credential", lambda: cred)

        def boom():
            raise AssertionError("browser extraction must not run for optional auth")

        monkeypatch.setattr(auth, "extract_browser_credential", boom)

        assert _common.optional_auth() is cred


# ── get_credential(allow_browser=...) gate ──────────────────────────


class TestGetCredentialAllowBrowser:
    def test_allow_browser_false_skips_browser(self, monkeypatch):
        monkeypatch.setattr(auth, "load_credential", lambda: None)
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return None

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        assert auth.get_credential(allow_browser=False) is None
        assert calls["n"] == 0

    def test_default_still_allows_browser(self, monkeypatch):
        # The require_auth path must be unchanged: browser extraction still runs.
        cred = Credential(cookies={"reddit_session": "abc"}, source="browser:chrome")
        monkeypatch.setattr(auth, "load_credential", lambda: None)
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return cred

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        assert auth.get_credential() is cred
        assert calls["n"] == 1


# ── run_client_action retry must not browser-extract when anonymous ─


class TestRunClientActionAnonymous:
    def test_anonymous_session_expiry_does_not_extract_browser(self, monkeypatch):
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return None

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        def action(_client):
            raise SessionExpiredError()

        with pytest.raises(SessionExpiredError):
            _common.run_client_action(None, action)

        assert calls["n"] == 0, "anonymous run must not fall back to browser extraction"

    def test_authenticated_session_expiry_still_refreshes_via_browser(self, monkeypatch):
        fresh = Credential(cookies={"reddit_session": "new"})
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return fresh

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        attempts = {"n": 0}

        def action(_client):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise SessionExpiredError()
            return "ok"

        result = _common.run_client_action(Credential(cookies={"reddit_session": "old"}), action)

        assert result == "ok"
        assert calls["n"] == 1


# ── end-to-end: a public command does not extract browser cookies ───


class TestPublicCommandNoBrowser:
    def _mock_listing(self):
        return {
            "data": {
                "children": [
                    {"data": {"id": "abc", "title": "T", "subreddit": "s", "author": "a",
                              "score": 1, "num_comments": 0, "created_utc": 1700000000}}
                ],
                "after": None,
            }
        }

    def test_popular_does_not_extract_browser(self, monkeypatch):
        monkeypatch.setattr(auth, "load_credential", lambda: None)
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return None

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        with patch("rdt_cli.client.RedditClient.get_popular", return_value=self._mock_listing()):
            result = runner.invoke(cli, ["popular", "-n", "1", "--json"])

        assert result.exit_code == 0, result.output
        assert calls["n"] == 0, "`rdt popular` must not read browser cookies"
