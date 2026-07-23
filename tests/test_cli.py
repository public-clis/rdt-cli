"""Unit tests for rdt-cli — mocked, no network required."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rdt_cli import __version__
from rdt_cli.cli import cli

runner = CliRunner()


# ── CLI basic ───────────────────────────────────────────────────────


class TestCliBasic:
    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "rdt" in result.output

    def test_all_commands_registered(self):
        result = runner.invoke(cli, ["--help"])
        expected = [
            "login", "logout", "status",
            "feed", "popular", "all", "sub", "sub-info", "rules", "user",
            "user-posts", "user-comments", "saved", "upvoted", "open",
            "read", "show",
            "search", "export",
            "upvote", "save", "subscribe", "comment", "delete",
            "post",
        ]
        for cmd in expected:
            assert cmd in result.output, f"Missing command: {cmd}"

    def test_verbose_flag(self):
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0

    def test_command_count(self):
        """Ensure we have the expanded command set."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Count command lines (indented, after "Commands:" )
        lines = result.output.split("\n")
        cmd_lines = [line for line in lines if line.startswith("  ") and not line.strip().startswith("-")]
        assert len(cmd_lines) >= 23


# ── Command help ────────────────────────────────────────────────────


class TestCommandHelp:
    """Every command's --help should work without error."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "login", "logout", "status",
            "feed", "popular", "all", "sub", "sub-info", "rules", "user",
            "user-posts", "user-comments", "saved", "upvoted", "open",
            "read", "show",
            "search", "export",
            "upvote", "save", "subscribe", "comment", "delete",
            "post",
        ],
    )
    def test_help(self, cmd):
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"

    def test_read_help_has_expand_more(self):
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "--expand-more" in result.output


# ── Auth commands (mocked) ──────────────────────────────────────────


class TestAuthCommands:
    def test_status_not_authenticated(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            # CliRunner is non-TTY → YAML envelope by default
            assert "authenticated" in result.output and "false" in result.output

    def test_status_json_not_authenticated(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            result = runner.invoke(cli, ["status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["data"]["authenticated"] is False

    def test_status_json_authenticated(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test", "token": "xyz"})
        with patch("rdt_cli.auth.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.validate_session", return_value={
                "authenticated": True,
                "username": "spez",
                "capabilities": ["read", "write"],
                "modhash_present": True,
            }):
                result = runner.invoke(cli, ["status", "--json"])
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["ok"] is True
                assert data["data"]["authenticated"] is True
                assert data["data"]["cookie_count"] == 2
                assert data["data"]["username"] == "spez"
                assert data["data"]["capabilities"] == ["read", "write"]

    def test_login_already_authenticated(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test"})
        with patch("rdt_cli.auth.get_credential", return_value=cred):
            result = runner.invoke(cli, ["login"])
            assert result.exit_code == 0
            assert "Already" in result.output or "✅" in result.output

    def test_login_not_authenticated_no_browser(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.auth.extract_browser_credential", return_value=None):
                result = runner.invoke(cli, ["login"])
                assert result.exit_code == 0
                assert "No Reddit" in result.output or "❌" in result.output

    def test_login_success_from_browser(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "abc", "loid": "xyz"})
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.auth.extract_browser_credential", return_value=cred):
                result = runner.invoke(cli, ["login"])
                assert result.exit_code == 0
                assert "✅" in result.output
                assert "2 cookies" in result.output

    def test_logout(self):
        with patch("rdt_cli.auth.clear_credential") as mock_clear:
            result = runner.invoke(cli, ["logout"])
            assert result.exit_code == 0
            assert "✅" in result.output
            mock_clear.assert_called_once()


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    def test_base_url(self):
        from rdt_cli.constants import BASE_URL
        assert "reddit.com" in BASE_URL

    def test_headers_complete(self):
        from rdt_cli.constants import HEADERS
        assert "User-Agent" in HEADERS
        assert "sec-ch-ua" in HEADERS
        assert "Chrome/133" in HEADERS["User-Agent"]
        assert "sec-ch-ua-mobile" in HEADERS
        assert "sec-ch-ua-platform" in HEADERS

    def test_sort_options(self):
        from rdt_cli.constants import SORT_OPTIONS, TIME_FILTERS
        assert "hot" in SORT_OPTIONS
        assert "new" in SORT_OPTIONS
        assert "top" in SORT_OPTIONS
        assert "rising" in SORT_OPTIONS
        assert "controversial" in SORT_OPTIONS
        assert "week" in TIME_FILTERS
        assert "all" in TIME_FILTERS

    def test_required_cookies(self):
        from rdt_cli.constants import REQUIRED_COOKIES
        assert "reddit_session" in REQUIRED_COOKIES

    def test_search_sort_options(self):
        from rdt_cli.constants import SEARCH_SORT_OPTIONS
        assert "relevance" in SEARCH_SORT_OPTIONS
        assert "top" in SEARCH_SORT_OPTIONS
        assert "comments" in SEARCH_SORT_OPTIONS

    def test_default_limits(self):
        from rdt_cli.constants import DEFAULT_LIMIT, MAX_LIMIT
        assert DEFAULT_LIMIT == 25
        assert MAX_LIMIT == 100

    def test_endpoints_contain_json(self):
        from rdt_cli.constants import ALL_URL, HOME_URL, POPULAR_URL, SEARCH_URL
        assert HOME_URL.endswith(".json")
        assert POPULAR_URL.endswith(".json")
        assert ALL_URL.endswith(".json")
        assert SEARCH_URL.endswith(".json")


# ── Credential ──────────────────────────────────────────────────────


class TestCredential:
    def test_from_dict(self):
        from rdt_cli.auth import Credential
        cred = Credential.from_dict({"cookies": {"reddit_session": "abc"}})
        assert cred.is_valid
        assert cred.cookies["reddit_session"] == "abc"

    def test_to_dict(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"k": "v"})
        data = cred.to_dict()
        assert "cookies" in data
        assert "saved_at" in data

    def test_empty_credential(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={})
        assert not cred.is_valid

    def test_as_cookie_header(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"a": "1", "b": "2"})
        header = cred.as_cookie_header()
        assert "a=1" in header
        assert "b=2" in header

    def test_save_and_load(self, tmp_path, monkeypatch):
        from rdt_cli import auth
        monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(auth, "CREDENTIAL_FILE", tmp_path / "cred.json")

        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test_val"}, source="browser:chrome", username="spez")
        auth.save_credential(cred)

        loaded = auth.load_credential()
        assert loaded is not None
        assert loaded.cookies["reddit_session"] == "test_val"
        assert loaded.source == "browser:chrome"
        assert loaded.username == "spez"

    def test_load_no_file(self, tmp_path, monkeypatch):
        from rdt_cli import auth
        monkeypatch.setattr(auth, "CREDENTIAL_FILE", tmp_path / "nonexist.json")
        assert auth.load_credential() is None

    def test_clear_credential(self, tmp_path, monkeypatch):
        from rdt_cli import auth
        cred_file = tmp_path / "cred.json"
        cred_file.write_text("{}")
        monkeypatch.setattr(auth, "CREDENTIAL_FILE", cred_file)
        auth.clear_credential()
        assert not cred_file.exists()


# ── Exceptions ──────────────────────────────────────────────────────


class TestExceptions:
    def test_hierarchy(self):
        from rdt_cli.exceptions import (
            AuthRequiredError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            RedditApiError,
            SessionExpiredError,
        )
        assert issubclass(SessionExpiredError, RedditApiError)
        assert issubclass(AuthRequiredError, RedditApiError)
        assert issubclass(RateLimitError, RedditApiError)
        assert issubclass(NotFoundError, RedditApiError)
        assert issubclass(ForbiddenError, RedditApiError)

    def test_error_codes(self):
        from rdt_cli.exceptions import (
            AuthRequiredError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            SessionExpiredError,
            error_code_for_exception,
        )
        assert error_code_for_exception(AuthRequiredError()) == "not_authenticated"
        assert error_code_for_exception(SessionExpiredError()) == "not_authenticated"
        assert error_code_for_exception(RateLimitError()) == "rate_limited"
        assert error_code_for_exception(NotFoundError()) == "not_found"
        assert error_code_for_exception(ForbiddenError()) == "forbidden"
        assert error_code_for_exception(ValueError()) == "unknown_error"

    def test_rate_limit_retry_after(self):
        from rdt_cli.exceptions import RateLimitError
        exc = RateLimitError(retry_after=30.0)
        assert exc.retry_after == 30.0
        assert "30s" in str(exc)

    def test_not_found_resource(self):
        from rdt_cli.exceptions import NotFoundError
        exc = NotFoundError("r/test")
        assert "r/test" in str(exc)

    def test_reddit_api_error_fields(self):
        from rdt_cli.exceptions import RedditApiError
        exc = RedditApiError("test message", code=500, response={"error": True})
        assert exc.code == 500
        assert exc.response == {"error": True}


# ── Client ──────────────────────────────────────────────────────────


class TestClient:
    def test_context_manager(self):
        from rdt_cli.auth import Credential
        from rdt_cli.client import RedditClient
        cred = Credential(cookies={})
        with RedditClient(cred) as client:
            assert client.client is not None

    def test_client_not_initialized_error(self):
        from rdt_cli.client import RedditClient
        c = RedditClient(None)
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = c.client

    def test_request_stats(self):
        from rdt_cli.auth import Credential
        from rdt_cli.client import RedditClient
        cred = Credential(cookies={})
        with RedditClient(cred) as client:
            stats = client.request_stats
            assert stats["request_count"] == 0

    def test_extract_posts(self):
        from rdt_cli.client import RedditClient
        data = {
            "data": {
                "children": [
                    {"data": {"id": "abc", "title": "Test"}},
                    {"data": {"id": "def", "title": "Test2"}},
                ],
                "after": "t3_xyz",
            }
        }
        posts = RedditClient._extract_posts(data)
        assert len(posts) == 2
        assert posts[0]["id"] == "abc"

    def test_extract_posts_from_list(self):
        from rdt_cli.client import RedditClient
        data = [{"data": {"children": []}}, {"data": {"children": []}}]
        result = RedditClient._extract_posts(data)
        assert isinstance(result, list)

    def test_extract_after(self):
        from rdt_cli.client import RedditClient
        data = {"data": {"after": "t3_next", "children": []}}
        assert RedditClient._extract_after(data) == "t3_next"
        assert RedditClient._extract_after({"data": {"after": None}}) is None

    def test_extract_after_from_list(self):
        from rdt_cli.client import RedditClient
        assert RedditClient._extract_after([]) is None

    def test_context_manager_closes(self):
        """Verify __exit__ nulls out the http client."""
        from rdt_cli.client import RedditClient
        c = RedditClient(None)
        c.__enter__()
        assert c._http is not None
        c.__exit__(None, None, None)
        assert c._http is None

    def test_custom_timeout_and_delay(self):
        from rdt_cli.client import RedditClient
        c = RedditClient(None, timeout=5.0, request_delay=0.5, max_retries=2)
        assert c._timeout == 5.0
        assert c._request_delay == 0.5
        assert c._max_retries == 2


# ── Common helpers ──────────────────────────────────────────────────


class TestCommonHelpers:
    def test_format_score_small(self):
        from rdt_cli.commands._common import format_score
        assert format_score(42) == "42"
        assert format_score(0) == "0"
        assert format_score(999) == "999"

    def test_format_score_large(self):
        from rdt_cli.commands._common import format_score
        assert format_score(1000) == "1.0k"
        assert format_score(1500) == "1.5k"
        assert format_score(12345) == "12.3k"

    def test_format_time_zero(self):
        from rdt_cli.commands._common import format_time
        assert format_time(0) == "-"

    def test_format_time_recent(self):
        import time

        from rdt_cli.commands._common import format_time
        now = time.time()
        assert "ago" in format_time(now - 30)    # 30s ago
        assert "ago" in format_time(now - 300)   # 5m ago
        assert "ago" in format_time(now - 7200)  # 2h ago

    def test_format_time_old(self):
        from rdt_cli.commands._common import format_time
        # Very old timestamp → should return date
        result = format_time(1000000000)  # 2001-09-09
        assert "2001" in result

    def test_structured_output_options(self):
        """Verify the decorator adds --json/--yaml options."""
        import click

        from rdt_cli.commands._common import structured_output_options

        @click.command()
        @structured_output_options
        def dummy_cmd(as_json, as_yaml):
            pass

        # Check that the command has json/yaml params
        param_names = [p.name for p in dummy_cmd.params]
        assert "as_json" in param_names
        assert "as_yaml" in param_names


# ── Index Cache ─────────────────────────────────────────────────────


class TestIndexCache:
    def test_save_and_get(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [
            {"id": "abc", "name": "t3_abc", "title": "Test Post", "subreddit": "python"},
            {"id": "def", "name": "t3_def", "title": "Test Post 2", "subreddit": "rust"},
        ]
        index_cache.save_index(items, source="test")

        item = index_cache.get_item_by_index(1)
        assert item is not None
        assert item["id"] == "abc"

        item2 = index_cache.get_item_by_index(2)
        assert item2["id"] == "def"

    def test_save_empty_list(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        index_cache.save_index([], source="empty")
        assert not (tmp_path / "cache.json").exists()

    def test_save_filters_items_without_id(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [{"id": "abc", "title": "Good"}, {"title": "No ID"}]
        index_cache.save_index(items)

        info = index_cache.get_index_info()
        assert info["count"] == 1

    def test_get_out_of_range(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [{"id": "abc", "title": "Test"}]
        index_cache.save_index(items)

        assert index_cache.get_item_by_index(99) is None

    def test_get_index_zero(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        assert index_cache.get_item_by_index(0) is None

    def test_get_negative_index(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        assert index_cache.get_item_by_index(-1) is None

    def test_get_no_cache_file(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "nonexistent.json")
        assert index_cache.get_item_by_index(1) is None

    def test_get_corrupted_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("not json")
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", cache_file)
        assert index_cache.get_item_by_index(1) is None

    def test_get_index_info(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)

        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        index_cache.save_index(items, source="test_search")

        info = index_cache.get_index_info()
        assert info["exists"] is True
        assert info["count"] == 3
        assert info["source"] == "test_search"

    def test_index_info_no_file(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")

        info = index_cache.get_index_info()
        assert info["exists"] is False


# ── Show command ────────────────────────────────────────────────────


class TestShowCommand:
    def test_show_no_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")
        result = runner.invoke(cli, ["show", "1"])
        assert result.exit_code == 0
        assert "No cached" in result.output or "cache" in result.output.lower()

    def test_show_requires_int(self):
        result = runner.invoke(cli, ["show", "abc"])
        assert result.exit_code != 0  # Click will reject non-integer


# ── Open command ────────────────────────────────────────────────────


class TestOpenCommand:
    def test_open_no_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")
        result = runner.invoke(cli, ["open", "1"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_open_bare_id(self):
        """Opening by bare ID should construct a reddit URL."""
        with patch("rdt_cli.commands.browse.open_url") as mock_open:
            result = runner.invoke(cli, ["open", "1abc123"])
            assert result.exit_code == 0
            if mock_open.called:
                url = mock_open.call_args[0][0]
                assert "1abc123" in url

    def test_open_url_passthrough(self):
        """Full URL should be passed through."""
        with patch("rdt_cli.commands.browse.open_url") as mock_open:
            result = runner.invoke(cli, ["open", "https://reddit.com/r/test/123"])
            assert result.exit_code == 0
            mock_open.assert_called_once_with("https://reddit.com/r/test/123")


# ── Social command helpers ──────────────────────────────────────────


class TestResolveFullname:
    def test_fullname_passthrough(self):
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("t3_abc123") == "t3_abc123"
        assert _resolve_fullname("t1_xyz") == "t1_xyz"

    def test_bare_id(self):
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("abc123") == "t3_abc123"

    def test_index_no_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "none.json")
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("3") is None

    def test_index_with_cache(self, tmp_path, monkeypatch):
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)
        index_cache.save_index([
            {"id": "aaa", "name": "t3_aaa", "title": "First"},
            {"id": "bbb", "name": "t3_bbb", "title": "Second"},
        ])
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("2") == "t3_bbb"

    def test_index_with_cache_no_name(self, tmp_path, monkeypatch):
        """Items without fullname should fallback to t3_ + id."""
        from rdt_cli import index_cache
        monkeypatch.setattr(index_cache, "INDEX_CACHE_FILE", tmp_path / "cache.json")
        monkeypatch.setattr(index_cache, "CONFIG_DIR", tmp_path)
        index_cache.save_index([{"id": "ccc", "title": "No fullname"}])
        from rdt_cli.commands.social import _resolve_fullname
        assert _resolve_fullname("1") == "t3_ccc"


# ── Mocked browse commands ──────────────────────────────────────────


class TestMockedBrowse:
    """Test browse commands with mocked API calls."""

    def _mock_listing(self, posts=None, after=None):
        if posts is None:
            posts = [
                {"id": "abc", "title": "Test", "subreddit": "test",
                 "author": "bob", "score": 100, "num_comments": 5,
                 "created_utc": 1700000000},
            ]
        return {
            "data": {
                "children": [{"data": p} for p in posts],
                "after": after,
            }
        }

    def test_popular_mocked(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_popular", return_value=self._mock_listing()):
                result = runner.invoke(cli, ["popular", "-n", "1", "--json"])
                assert result.exit_code == 0

    def test_sub_mocked(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_subreddit", return_value=self._mock_listing()):
                result = runner.invoke(cli, ["sub", "python", "-n", "1", "--json"])
                assert result.exit_code == 0

    def test_sub_info_mocked(self):
        mock_data = {"display_name": "python", "subscribers": 1000, "accounts_active": 50}
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_subreddit_about", return_value=mock_data):
                result = runner.invoke(cli, ["sub-info", "python", "--json"])
                assert result.exit_code == 0

    def test_rules_mocked(self):
        mock_data = {
            "rules": [
                {"kind": "all", "short_name": "Be nice", "description": "No harassment.", "priority": 0},
                {"kind": "link", "short_name": "On topic", "description": "", "priority": 1},
            ],
            "site_rules": [],
        }
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_subreddit_rules", return_value=mock_data):
                result = runner.invoke(cli, ["rules", "python", "--json"])
                assert result.exit_code == 0
                assert "Be nice" in result.output

    def test_rules_rendered_mocked(self):
        mock_data = {"rules": [{"kind": "comment", "short_name": "No spam", "description": "Don't spam."}]}
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_subreddit_rules", return_value=mock_data):
                result = runner.invoke(cli, ["rules", "python"], env={"OUTPUT": "rich"})
                assert result.exit_code == 0
                assert "No spam" in result.output

    def test_rules_empty_mocked(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_subreddit_rules", return_value={"rules": []}):
                result = runner.invoke(cli, ["rules", "python"], env={"OUTPUT": "rich"})
                assert result.exit_code == 0
                assert "no community rules" in result.output

    def test_user_mocked(self):
        mock_data = {"name": "testuser", "link_karma": 100, "comment_karma": 200}
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_user_about", return_value=mock_data):
                result = runner.invoke(cli, ["user", "testuser", "--json"])
                assert result.exit_code == 0

    def test_user_comments_mocked(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_user_comments", return_value=self._mock_listing()):
                result = runner.invoke(cli, ["user-comments", "testuser", "--json"])
                assert result.exit_code == 0

    def test_saved_mocked(self):
        from rdt_cli.auth import Credential

        cred = Credential(cookies={"reddit_session": "test"}, username="spez")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.get_me", return_value={"name": "spez"}):
                with patch("rdt_cli.client.RedditClient.get_user_saved", return_value=self._mock_listing()):
                    result = runner.invoke(cli, ["saved", "--json"])
                    assert result.exit_code == 0

    def test_upvoted_mocked(self):
        from rdt_cli.auth import Credential

        cred = Credential(cookies={"reddit_session": "test"}, username="spez")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.get_me", return_value={"name": "spez"}):
                with patch("rdt_cli.client.RedditClient.get_user_upvoted", return_value=self._mock_listing()):
                    result = runner.invoke(cli, ["upvoted", "--json"])
                    assert result.exit_code == 0

    def test_delete_mocked(self):
        from unittest.mock import MagicMock

        from rdt_cli.auth import Credential

        cred = Credential(cookies={"reddit_session": "test"}, username="spez")
        delete_mock = MagicMock(return_value={})
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.validate_session", return_value={"authenticated": True}):
                with patch("rdt_cli.client.RedditClient.delete_item", delete_mock):
                    with patch("rdt_cli.commands.social.write_delay"):
                        result = runner.invoke(cli, ["delete", "1abc123", "--yes"])
                        assert result.exit_code == 0
                        assert "Deleted" in result.output
                        delete_mock.assert_called_once_with("t3_1abc123")

    def test_delete_aborts_without_confirmation(self):
        from unittest.mock import MagicMock

        from rdt_cli.auth import Credential

        cred = Credential(cookies={"reddit_session": "test"}, username="spez")
        delete_mock = MagicMock(return_value={})
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.delete_item", delete_mock):
                result = runner.invoke(cli, ["delete", "1abc123"], input="n\n")
                assert result.exit_code == 0
                delete_mock.assert_not_called()


# ── Mocked subs-only feed ──────────────────────────────────────────


class TestSubsOnlyFeed:
    """Test --subs-only flag on feed command."""

    def _mock_subs_listing(self, names):
        """Build a mock /subreddits/mine/subscriber response."""
        return {
            "data": {
                "children": [{"data": {"display_name": n}} for n in names],
                "after": None,
            }
        }

    def _mock_sub_posts(self, subreddit, created_utc=1700000000):
        return {
            "data": {
                "children": [
                    {"data": {"id": f"{subreddit}_1", "title": f"Post from {subreddit}",
                              "subreddit": subreddit, "author": "bob", "score": 10,
                              "num_comments": 1, "created_utc": created_utc}},
                ],
                "after": None,
            }
        }

    def test_feed_subs_only_json(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test"})
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.get_my_subscriptions", return_value=["python", "rust"]):
                with patch("rdt_cli.client.RedditClient.get_subreddit") as mock_sub:
                    mock_sub.side_effect = [
                        self._mock_sub_posts("python", created_utc=1700000200),
                        self._mock_sub_posts("rust", created_utc=1700000100),
                    ]
                    result = runner.invoke(cli, ["feed", "--subs-only", "--json"])
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert data["ok"] is True

    def test_feed_subs_only_empty_subscriptions(self):
        from rdt_cli.auth import Credential
        cred = Credential(cookies={"reddit_session": "test"})
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            with patch("rdt_cli.client.RedditClient.get_my_subscriptions", return_value=[]):
                result = runner.invoke(cli, ["feed", "--subs-only", "--json"])
                assert result.exit_code == 0

    def test_feed_help_shows_subs_only(self):
        result = runner.invoke(cli, ["feed", "--help"])
        assert result.exit_code == 0
        assert "--subs-only" in result.output
        assert "--max-subs" in result.output


# ── Mocked search commands ──────────────────────────────────────────


class TestMockedSearch:
    def _mock_search(self, posts=None):
        if posts is None:
            posts = [
                {"id": "xyz", "title": "Found", "subreddit": "test",
                 "author": "alice", "score": 50, "num_comments": 2},
            ]
        return {"data": {"children": [{"data": p} for p in posts], "after": None}}

    def test_search_mocked(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.search", return_value=self._mock_search()):
                result = runner.invoke(cli, ["search", "python", "--json"])
                assert result.exit_code == 0

    def test_search_empty_results(self):
        empty = {"data": {"children": [], "after": None}}
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.search", return_value=empty):
                result = runner.invoke(cli, ["search", "xxxnonexistent", "--json"])
                assert result.exit_code == 0


class TestMoreComments:
    def test_read_expand_more_json(self):
        from pathlib import Path

        post_detail = json.loads((Path(__file__).parent / "fixtures" / "post_detail.json").read_text())
        morechildren = json.loads((Path(__file__).parent / "fixtures" / "morechildren.json").read_text())

        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_post_comments", return_value=post_detail):
                with patch("rdt_cli.client.RedditClient.get_more_comments", return_value=morechildren):
                    result = runner.invoke(cli, ["read", "abc123", "--expand-more", "--json"])
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert data["ok"] is True
                    assert data["data"]["post"]["id"] == "abc123"
                    assert any(comment["id"] == "c3" for comment in data["data"]["comments"])


# ── Issue #4: YAML special chars ────────────────────────────────────


class TestYamlSpecialChars:
    """YAML output should be parseable even with colons, quotes, multi-line in values."""

    def test_yaml_with_colons(self):
        import yaml

        from rdt_cli.commands._common import print_yaml

        data = {"title": "AMC Theatres: a story", "selftext": "key: value inside text"}
        # Capture output
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_yaml(data)
        output = buf.getvalue()

        # Must be parseable
        parsed = yaml.safe_load(output)
        assert parsed["title"] == "AMC Theatres: a story"
        assert parsed["selftext"] == "key: value inside text"

    def test_yaml_with_special_chars(self):
        import yaml

        from rdt_cli.commands._common import print_yaml

        data = {
            "selftext": 'He said "hello" and # commented\nSecond line: yes',
            "score": 42,
        }
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_yaml(data)
        output = buf.getvalue()

        parsed = yaml.safe_load(output)
        assert parsed["score"] == 42
        assert "hello" in parsed["selftext"]

    def test_yaml_roundtrip_envelope(self):
        """Full envelope with special chars should roundtrip."""
        import yaml

        from rdt_cli.commands._common import print_yaml, success_payload

        payload = success_payload([{
            "title": "Test: colon",
            "selftext": "line1\nline2: continued",
            "author": "user#1",
        }])

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_yaml(payload)
        output = buf.getvalue()
        parsed = yaml.safe_load(output)
        assert parsed["ok"] is True
        assert parsed["data"][0]["title"] == "Test: colon"


# ── Issue #5: read --compact ────────────────────────────────────────


class TestReadCompact:
    """read/show --compact should produce flat, agent-friendly output."""

    def _mock_post_detail(self):
        return [
            {
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": "test123",
                                "name": "t3_test123",
                                "title": "Test Post",
                                "subreddit": "testing",
                                "author": "alice",
                                "score": 42,
                                "num_comments": 3,
                                "selftext": "Hello world",
                                "permalink": "/r/testing/comments/test123/test/",
                                "url": "https://reddit.com/r/testing/comments/test123/test/",
                                "is_self": True,
                            },
                        }
                    ],
                }
            },
            {
                "data": {
                    "children": [
                        {
                            "kind": "t1",
                            "data": {
                                "id": "c1",
                                "name": "t1_c1",
                                "author": "bob",
                                "body": "Great post!",
                                "score": 10,
                                "parent_id": "t3_test123",
                                "created_utc": 1700000000,
                                "replies": {
                                    "data": {
                                        "children": [
                                            {
                                                "kind": "t1",
                                                "data": {
                                                    "id": "c2",
                                                    "name": "t1_c2",
                                                    "author": "carol",
                                                    "body": "Thanks!",
                                                    "score": 5,
                                                    "parent_id": "t1_c1",
                                                    "created_utc": 1700000010,
                                                    "replies": "",
                                                },
                                            }
                                        ]
                                    }
                                },
                            },
                        }
                    ],
                }
            },
        ]

    def test_read_compact_json(self):
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_post_comments", return_value=self._mock_post_detail()):
                result = runner.invoke(cli, ["read", "test123", "--compact", "--json"])
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["ok"] is True
                post = data["data"]["post"]
                assert post["id"] == "test123"
                assert post["title"] == "Test Post"
                assert post["author"] == "alice"
                # Comments should be flat with depth
                comments = data["data"]["comments"]
                assert len(comments) == 2
                assert comments[0]["author"] == "bob"
                assert comments[0]["depth"] == 0
                assert comments[1]["author"] == "carol"
                assert comments[1]["depth"] == 1
                # Compact should NOT have nested fields
                assert "fullname" not in comments[0]
                assert "replies" not in comments[0]

    def test_read_compact_default_yaml(self):
        """--compact without --json should default to YAML output."""
        with patch("rdt_cli.auth.get_credential", return_value=None):
            with patch("rdt_cli.client.RedditClient.get_post_comments", return_value=self._mock_post_detail()):
                result = runner.invoke(cli, ["read", "test123", "--compact"])
                assert result.exit_code == 0
                # Should contain YAML-style output (not rich tables)
                assert "test123" in result.output
                assert "bob" in result.output

    def test_read_help_shows_compact(self):
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "--compact" in result.output

    def test_show_help_shows_compact(self):
        result = runner.invoke(cli, ["show", "--help"])
        assert result.exit_code == 0
        assert "--compact" in result.output


# ── Post creation command (mocked) ──────────────────────────────────


class TestPostCommand:
    """Test the `post` creation command with mocked client methods."""

    def _cred(self):
        from rdt_cli.auth import Credential

        return Credential(cookies={"reddit_session": "x", "csrf_token": "y"}, username="me")

    def test_text_draft(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch(
                 "rdt_cli.client.RedditClient.create_draft",
                 return_value={"createPostDraft": {"ok": True, "postDraft": {"id": "d-123"}}},
             ) as mock_draft, \
             patch("rdt_cli.client.RedditClient.create_post") as mock_post:
            result = runner.invoke(cli, ["post", "test", "WIP", "--text", "body", "--draft", "--json"])
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert data["data"]["action"] == "draft"
            assert data["data"]["draft_id"] == "d-123"
            _, kwargs = mock_draft.call_args
            assert kwargs["body"] == "body"
            mock_post.assert_not_called()

    def test_link_draft(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.create_draft", return_value={}) as mock_draft:
            result = runner.invoke(
                cli, ["post", "test", "A link", "--url", "https://example.com", "--draft", "--json"]
            )
            assert result.exit_code == 0, result.output
            _, kwargs = mock_draft.call_args
            assert kwargs["url"] == "https://example.com"

    def test_publish_requires_recaptcha_token(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.get_solvecaptcha_api_key", return_value=None):
            result = runner.invoke(cli, ["post", "test", "T", "--text", "hi"])
            assert result.exit_code == 2
            assert "reCAPTCHA" in result.output

    def test_text_publish_with_token(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "hi", "--recaptcha-token", "TOK", "--json"]
            )
            assert result.exit_code == 0, result.output
            _, kwargs = mock_post.call_args
            assert kwargs["kind"] == "self"
            assert kwargs["recaptcha_token"] == "TOK"
            assert kwargs["is_profile"] is False

    def test_publish_solves_captcha_with_api_key(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.commands.submit.get_solvecaptcha_api_key", return_value="KEY"), \
             patch("rdt_cli.commands.submit.solve_recaptcha_token", return_value="SOLVED") as mock_solve, \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(cli, ["post", "test", "T", "--text", "hi", "--json"])
            assert result.exit_code == 0, result.output
            mock_solve.assert_called_once_with("KEY")
            _, kwargs = mock_post.call_args
            assert kwargs["recaptcha_token"] == "SOLVED"

    def test_explicit_token_skips_solver(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.commands.submit.get_solvecaptcha_api_key", return_value="KEY"), \
             patch("rdt_cli.commands.submit.solve_recaptcha_token") as mock_solve, \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "hi", "--recaptcha-token", "TOK", "--json"]
            )
            assert result.exit_code == 0, result.output
            mock_solve.assert_not_called()
            _, kwargs = mock_post.call_args
            assert kwargs["recaptcha_token"] == "TOK"

    def test_solver_failure_is_an_error(self):
        from rdt_cli.captcha import CaptchaSolveError

        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.commands.submit.get_solvecaptcha_api_key", return_value="KEY"), \
             patch(
                 "rdt_cli.commands.submit.solve_recaptcha_token",
                 side_effect=CaptchaSolveError("ERROR_ZERO_BALANCE"),
             ), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.create_post") as mock_post:
            result = runner.invoke(cli, ["post", "test", "T", "--text", "hi", "--json"])
            assert result.exit_code == 1
            mock_post.assert_not_called()
            # Structured error envelope on stdout (CliRunner also mixes in the
            # stderr "Solving…" status line, so assert on the payload text).
            assert '"ok": false' in result.output
            assert "Captcha solving failed" in result.output

    def test_image_publish_with_token(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.upload_image", return_value="media123") as mock_up, \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "Pic", "--image", str(img), "--recaptcha-token", "TOK", "--json"]
            )
            assert result.exit_code == 0, result.output
            mock_up.assert_called_once_with(str(img))
            _, kwargs = mock_post.call_args
            assert kwargs["kind"] == "image"
            assert kwargs["media_id"] == "media123"

    def test_embed_requires_text_kind(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            for kind_args in (["--url", "https://e.com"], ["--image", str(img)]):
                result = runner.invoke(
                    cli, ["post", "test", "T", *kind_args, "--embed", str(img), "--draft"]
                )
                assert result.exit_code == 2
                assert "--embed only works with --text" in result.output

    def test_embed_marker_count_mismatch(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "no markers", "--embed", str(img), "--draft"]
            )
            assert result.exit_code == 2
            assert "![img]" in result.output

    def test_embed_marker_without_embed(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "look ![img] here", "--draft"]
            )
            assert result.exit_code == 2
            assert "no --embed" in result.output

    def test_embed_publish_substitutes_markers(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "cat pic.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch(
                 "rdt_cli.client.RedditClient.upload_image_as_embed",
                 return_value=("mid1", "https://i.redd.it/mid1.jpg"),
             ) as mock_up, \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli,
                ["post", "test", "T", "--text", "before ![img] after",
                 "--embed", str(img), "--recaptcha-token", "TOK", "--json"],
            )
            assert result.exit_code == 0, result.output
            mock_up.assert_called_once_with(str(img))
            _, kwargs = mock_post.call_args
            assert kwargs["kind"] == "self"
            # marker-substituted markdown still computed (drafts use it; on
            # publish create_post ignores body once rich_text is given)
            assert kwargs["body"] == "before [cat pic](https://i.redd.it/mid1.jpg) after"
            assert "![img]" not in kwargs["body"]
            # rich_text: markers become RTJSON img blocks (true inline images)
            rtjson = json.loads(kwargs["rich_text"])
            assert rtjson == {
                "document": [
                    {"e": "par", "c": [{"e": "text", "t": "before "}]},
                    {"e": "img", "id": "mid1", "c": "cat pic"},
                    {"e": "par", "c": [{"e": "text", "t": " after"}]},
                ]
            }

    def test_embed_draft_substitutes_markers(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch(
                 "rdt_cli.client.RedditClient.upload_image_as_embed",
                 return_value=("mid2", "https://i.redd.it/mid2.png"),
             ), \
             patch("rdt_cli.client.RedditClient.create_draft", return_value={}) as mock_draft:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "see ![img]", "--embed", str(img), "--draft", "--json"]
            )
            assert result.exit_code == 0, result.output
            _, kwargs = mock_draft.call_args
            # drafts are markdown-only (no RTJSON media blocks) — links fallback
            assert kwargs["body"] == "see [pic](https://i.redd.it/mid2.png)"

    def test_profile_publish_uses_profile_flag(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_prof"), \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "u_me", "T", "--text", "hi", "--recaptcha-token", "TOK", "--json"]
            )
            assert result.exit_code == 0, result.output
            _, kwargs = mock_post.call_args
            assert kwargs["is_profile"] is True

    def test_requires_a_kind(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(cli, ["post", "test", "No body", "--draft"])
            assert result.exit_code == 2
            assert "Provide --text, --url, or --image" in result.output

    def test_rejects_two_kinds(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "Two", "--text", "a", "--url", "https://e.com", "--draft"]
            )
            assert result.exit_code == 2
            assert "Provide --text, --url, or --image" in result.output

    def test_text_with_attached_image_publishes_self_with_media(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "chart.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.resolve_subreddit_id", return_value="t5_abc"), \
             patch("rdt_cli.client.RedditClient.upload_image", return_value="mid9") as mock_up, \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "body", "--image", str(img),
                      "--recaptcha-token", "TOK", "--json"],
            )
            assert result.exit_code == 0, result.output
            mock_up.assert_called_once_with(str(img))
            _, kwargs = mock_post.call_args
            # --text + --image → still a text post, image attached via media_id
            assert kwargs["kind"] == "self"
            assert kwargs["body"] == "body"
            assert kwargs["media_id"] == "mid9"

    def test_embed_combines_with_attached_image(self, tmp_path):
        cred = self._cred()
        inline = tmp_path / "inline.png"
        inline.write_bytes(b"\x89PNG\r\n\x1a\n")
        attach = tmp_path / "attach.png"
        attach.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch(
                 "rdt_cli.client.RedditClient.upload_image_as_embed",
                 return_value=("mid1", "https://i.redd.it/mid1.png"),
             ), \
             patch("rdt_cli.client.RedditClient.upload_image", return_value="mid2") as mock_up, \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "a ![img] b", "--embed", str(inline),
                      "--image", str(attach), "--recaptcha-token", "TOK", "--json"],
            )
            assert result.exit_code == 0, result.output
            # hybrid: inline RTJSON embed + attached image (feed preview) together
            mock_up.assert_called_once_with(str(attach))
            _, kwargs = mock_post.call_args
            assert kwargs["kind"] == "self"
            assert kwargs["media_id"] == "mid2"
            assert json.loads(kwargs["rich_text"])["document"][1]["id"] == "mid1"

    def test_rejects_text_with_image_draft(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "body", "--image", str(img), "--draft"]
            )
            assert result.exit_code == 2
            assert "draft" in result.output.lower()

    def test_flairs_lists_templates(self):
        cred = self._cred()
        templates = [
            {"id": "aaa-111", "text": "Discussion", "text_editable": False},
            {"id": "bbb-222", "text": "", "text_editable": True},
        ]
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.client.RedditClient.get_link_flairs", return_value=templates), \
             patch("rdt_cli.commands._common.resolve_output_format", return_value=None):
            result = runner.invoke(cli, ["flairs", "test"])
            assert result.exit_code == 0, result.output
            assert "aaa-111" in result.output
            assert "Discussion" in result.output
            # empty-default templates apply but render blank — the listing warns
            assert "no default text" in result.output

    def test_post_with_flair_passes_through(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred), \
             patch("rdt_cli.commands.submit.write_delay"), \
             patch("rdt_cli.client.RedditClient.validate_session", return_value={}), \
             patch("rdt_cli.client.RedditClient.create_post", return_value={}) as mock_post:
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "body", "--flair-id", "aaa-111",
                      "--flair-text", "Custom", "--recaptcha-token", "TOK", "--json"],
            )
            assert result.exit_code == 0, result.output
            _, kwargs = mock_post.call_args
            assert kwargs["flair_id"] == "aaa-111"
            assert kwargs["flair_text"] == "Custom"

    def test_flair_text_requires_flair_id(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "body", "--flair-text", "Custom"]
            )
            assert result.exit_code == 2
            assert "--flair-text requires --flair-id" in result.output

    def test_flair_rejected_for_draft(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "test", "T", "--text", "body", "--flair-id", "aaa", "--draft"]
            )
            assert result.exit_code == 2
            assert "publish" in result.output.lower()

    def test_flair_rejected_for_profile(self):
        cred = self._cred()
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(
                cli, ["post", "u_me", "T", "--text", "body", "--flair-id", "aaa",
                      "--recaptcha-token", "TOK"]
            )
            assert result.exit_code == 2
            assert "community" in result.output.lower()

    def test_rejects_image_draft(self, tmp_path):
        cred = self._cred()
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch("rdt_cli.commands._common.get_credential", return_value=cred):
            result = runner.invoke(cli, ["post", "test", "Pic", "--image", str(img), "--draft"])
            assert result.exit_code == 2
            assert "draft" in result.output.lower()

    def test_not_logged_in(self):
        with patch("rdt_cli.commands._common.get_credential", return_value=None):
            result = runner.invoke(cli, ["post", "test", "Title", "--text", "hi", "--draft"])
            assert result.exit_code == 1


# ── Client post-creation methods (mocked) ───────────────────────────


class TestClientPostMethods:
    def _client(self):
        from rdt_cli.auth import Credential
        from rdt_cli.client import RedditClient

        cred = Credential(cookies={"reddit_session": "x", "csrf_token": "tok"})
        return RedditClient(cred)

    def test_graphql_sends_operation_and_csrf(self):
        captured = {}

        def fake_write(method, url, **kwargs):
            captured.update(method=method, url=url, json=kwargs.get("json"))
            return {"data": {"ok": True}}

        with self._client() as client:
            with patch.object(client, "_write_request", side_effect=fake_write):
                data = client._graphql("CreatePost", {"input": {"a": 1}})
        assert data == {"ok": True}
        assert captured["url"].endswith("/svc/shreddit/graphql")
        body = captured["json"]
        assert body["operation"] == "CreatePost"
        assert body["variables"] == {"input": {"a": 1}}
        assert body["csrf_token"] == "tok"

    def test_graphql_raises_on_errors(self):
        from rdt_cli.exceptions import RedditApiError

        def fake_write(*a, **k):
            return {"data": None, "errors": [{"message": "boom"}]}

        with self._client() as client:
            with patch.object(client, "_write_request", side_effect=fake_write):
                with pytest.raises(RedditApiError, match="boom"):
                    client._graphql("CreatePost", {})

    def test_resolve_subreddit_id(self):
        with self._client() as client:
            with patch.object(
                client, "get_subreddit_about", return_value={"name": "t5_2qh1i", "display_name": "test"}
            ):
                assert client.resolve_subreddit_id("test") == "t5_2qh1i"

    def test_create_draft_payload(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={"createDraft": {"ok": True}}) as g:
                client.create_draft("t5_x", "Title", body="hello")
                op, variables = g.call_args.args
                assert op == "CreateDraft"
                inp = variables["input"]
                assert inp["subredditId"] == "t5_x"
                assert inp["title"] == "Title"
                assert inp["kind"] == "MARKDOWN"
                assert inp["content"] == {"markdown": "hello"}

    def test_create_post_self_with_rich_text(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "test", "T", recaptcha_token="TOK", kind="self",
                    body="before [s](https://i.redd.it/m1.jpg) after",
                    rich_text='{"document":[{"e":"par","c":[{"e":"text","t":"before "}]},'
                              '{"e":"img","id":"m1","c":"s"},'
                              '{"e":"par","c":[{"e":"text","t":" after"}]}]}',
                )
                op, variables = g.call_args.args
                assert op == "CreatePost"
                inp = variables["input"]
                # captured community requests address by name, without postType
                assert inp["subredditName"] == "test"
                assert "postType" not in inp
                assert "subredditId" not in inp
                content = inp["content"]
                # editor-style: content carries the RTJSON alone, never a
                # markdown+richText pair (body is ignored when rich_text given)
                assert "markdown" not in content
                rtjson = json.loads(content["richText"])
                assert rtjson["document"][1] == {"e": "img", "id": "m1", "c": "s"}

    def test_5xx_surfaces_response_body_in_error(self):
        import httpx

        from rdt_cli.exceptions import RedditApiError

        with self._client() as client:
            transport = client._write_transport
            resp = httpx.Response(
                500,
                text='{"errors":[{"message":"SUBREDDIT_NOT_ALLOWED"}]}',
                request=httpx.Request("POST", "https://www.reddit.com/svc/shreddit/graphql"),
            )
            with patch.object(transport.client, "request", return_value=resp) as mock_req, \
                 patch("rdt_cli.transports.time.sleep"):
                with pytest.raises(RedditApiError) as exc_info:
                    transport.request("POST", "/svc/shreddit/graphql")
            # the server's error body must reach the user, not a bare retry count
            assert "HTTP 500" in str(exc_info.value)
            assert "SUBREDDIT_NOT_ALLOWED" in str(exc_info.value)
            # writes fail fast: no 5xx retries (mutations aren't idempotent and
            # recaptcha tokens are single-use)
            assert mock_req.call_count == 1

    def test_read_transport_retries_5xx(self):
        import httpx

        from rdt_cli.exceptions import RedditApiError

        with self._client() as client:
            transport = client._read_transport
            resp = httpx.Response(
                503,
                text="upstream connect error",
                request=httpx.Request("GET", "https://www.reddit.com/r/test.json"),
            )
            with patch.object(transport.client, "request", return_value=resp) as mock_req, \
                 patch("rdt_cli.transports.time.sleep"):
                with pytest.raises(RedditApiError) as exc_info:
                    transport.request("GET", "/r/test.json")
            assert "HTTP 503" in str(exc_info.value)
            assert "upstream connect error" in str(exc_info.value)
            # reads keep the backoff-and-retry behavior, exhausting max_retries
            assert mock_req.call_count == client._max_retries

    def test_create_post_self_with_attached_image(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "test", "T", recaptcha_token="TOK", kind="self",
                    body="text", media_id="mid7",
                )
                op, variables = g.call_args.args
                assert op == "CreatePost"
                inp = variables["input"]
                # captured traffic: text posts attach via image.url even on
                # subreddits (gallery.items is for pure image posts only)
                assert inp["subredditName"] == "test"
                assert inp["isCommercialCommunication"] is False
                assert inp["targetLanguage"] == ""
                assert inp["content"] == {"markdown": "text"}
                assert inp["image"] == {
                    "url": "https://reddit-uploaded-media.s3-accelerate.amazonaws.com/mid7"
                }
                assert "gallery" not in inp

    def test_create_post_with_flair(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "test", "T", recaptcha_token="TOK", kind="self", body="hi",
                    flair_id="aaa-111", flair_text="Custom",
                )
                _, variables = g.call_args.args
                assert variables["input"]["flair"] == {"id": "aaa-111", "text": "Custom"}

    def test_create_post_without_flair_omits_field(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post("test", "T", recaptcha_token="TOK", kind="self", body="hi")
                _, variables = g.call_args.args
                assert "flair" not in variables["input"]

    def test_get_link_flairs(self):
        templates = [{"id": "aaa", "text": "Discussion", "text_editable": False}]
        with self._client() as client:
            with patch.object(client, "_get", return_value=templates) as g:
                assert client.get_link_flairs("test") == templates
                url, = g.call_args.args
                assert url == "/r/test/api/link_flair_v2.json"

    def test_create_post_self_rich_text_with_attached_image(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "test", "T", recaptcha_token="TOK", kind="self",
                    rich_text='{"document":[{"e":"img","id":"m1"}]}', media_id="mid9",
                )
                _, variables = g.call_args.args
                inp = variables["input"]
                assert inp["content"] == {"richText": '{"document":[{"e":"img","id":"m1"}]}'}
                assert inp["image"]["url"].endswith("/mid9")

    def test_create_profile_post_self_with_attached_image(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "t5_x", "T", recaptcha_token="TOK", kind="self",
                    body="text", media_id="mid8", is_profile=True,
                )
                op, variables = g.call_args.args
                assert op == "CreateProfilePost"
                inp = variables["input"]
                assert inp["content"] == {"markdown": "text"}
                assert inp["image"] == {
                    "url": "https://reddit-uploaded-media.s3-accelerate.amazonaws.com/mid8"
                }

    def test_create_post_self_without_rich_text_omits_field(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post("t5_x", "T", recaptcha_token="TOK", kind="self", body="hi")
                _, variables = g.call_args.args
                content = variables["input"]["content"]
                assert content == {"markdown": "hi"}
                assert "richText" not in content

    def test_create_post_link_payload(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post("test", "T", recaptcha_token="TOK", kind="link", url="https://e.com")
                op, variables = g.call_args.args
                assert op == "CreatePost"
                inp = variables["input"]
                assert inp["subredditName"] == "test"
                assert "postType" not in inp
                assert inp["url"] == "https://e.com"
                assert inp["recaptchaToken"] == "TOK"
                assert "correlationId" in inp

    def test_create_profile_post_image_payload(self):
        with self._client() as client:
            with patch.object(client, "_graphql", return_value={}) as g:
                client.create_post(
                    "t5_prof", "T", recaptcha_token="TOK", kind="image",
                    media_id="mid42", is_profile=True,
                )
                op, variables = g.call_args.args
                assert op == "CreateProfilePost"
                inp = variables["input"]
                assert inp["image"]["url"].endswith("/mid42")
                assert inp["recaptchaToken"] == "TOK"
                assert "subredditName" not in inp  # profile posts have no target

    def test_upload_image(self, tmp_path):
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        lease = {
            "mediaId": "media123",
            "uploadLease": {
                "uploadLeaseUrl": "https://s3.example/",
                "uploadLeaseHeaders": [{"header": "key", "value": "abc"}],
            },
        }
        with self._client() as client:
            with patch.object(client, "create_media_lease", return_value=lease) as mock_lease:
                with patch("httpx.Client.post") as mock_s3:
                    mock_s3.return_value.status_code = 201
                    media_id = client.upload_image(str(img))
        assert media_id == "media123"
        mock_lease.assert_called_once_with("PNG")
        # S3 upload sends lease fields + file, no reddit cookies
        _, kwargs = mock_s3.call_args
        assert kwargs["data"] == {"key": "abc"}
        assert "file" in kwargs["files"]

    def test_upload_image_as_embed(self, tmp_path):
        for name, ext in (("pic.jpg", "jpg"), ("pic.jpeg", "jpg"), ("pic.png", "png"), ("pic.webp", "webp")):
            img = tmp_path / name
            img.write_bytes(b"\x00")
            with self._client() as client:
                with patch.object(client, "upload_image", return_value="mid42") as mock_up:
                    media_id, url = client.upload_image_as_embed(str(img))
            assert media_id == "mid42"
            assert url == f"https://i.redd.it/mid42.{ext}"
            mock_up.assert_called_once_with(str(img))


# ── RTJSON building for inline embeds ───────────────────────────────


class TestRichtext:
    def test_interleaves_paragraphs_and_images(self):
        from rdt_cli.richtext import build_rtjson

        doc = json.loads(build_rtjson("before ![img] after", [("mid1", "cat pic")]))
        assert doc == {
            "document": [
                {"e": "par", "c": [{"e": "text", "t": "before "}]},
                {"e": "img", "id": "mid1", "c": "cat pic"},
                {"e": "par", "c": [{"e": "text", "t": " after"}]},
            ]
        }

    def test_multiple_images_in_order(self):
        from rdt_cli.richtext import build_rtjson

        doc = json.loads(build_rtjson("a ![img] b ![img] c", [("m1", "one"), ("m2", "two")]))
        assert doc["document"] == [
            {"e": "par", "c": [{"e": "text", "t": "a "}]},
            {"e": "img", "id": "m1", "c": "one"},
            {"e": "par", "c": [{"e": "text", "t": " b "}]},
            {"e": "img", "id": "m2", "c": "two"},
            {"e": "par", "c": [{"e": "text", "t": " c"}]},
        ]

    def test_marker_at_edges_adds_no_empty_paragraphs(self):
        from rdt_cli.richtext import build_rtjson

        doc = json.loads(build_rtjson("![img]", [("m1", "")]))
        assert doc["document"] == [{"e": "img", "id": "m1"}]  # empty caption omitted

    def test_newlines_become_paragraphs(self):
        from rdt_cli.richtext import build_rtjson

        doc = json.loads(build_rtjson("line1\n\nline2 ![img]", [("m1", "cap")]))
        # blank lines are dropped — editor documents never hold empty par nodes
        assert doc["document"] == [
            {"e": "par", "c": [{"e": "text", "t": "line1"}]},
            {"e": "par", "c": [{"e": "text", "t": "line2 "}]},
            {"e": "img", "id": "m1", "c": "cap"},
        ]

    def test_empty_body_yields_single_empty_paragraph(self):
        from rdt_cli.richtext import build_rtjson

        doc = json.loads(build_rtjson("", []))
        assert doc["document"] == [{"e": "par", "c": [{"e": "text", "t": ""}]}]

    def test_marker_media_count_mismatch_raises(self):
        from rdt_cli.richtext import build_rtjson

        with pytest.raises(ValueError):
            build_rtjson("![img] ![img]", [("m1", "one")])


# ── Captcha solving via Solvecaptcha (mocked HTTP) ──────────────────


class TestCaptchaSolver:
    """Test rdt_cli.captcha against a mocked Solvecaptcha API (MockTransport)."""

    def _run_solver(self, handler, **kwargs):
        import httpx

        from rdt_cli.captcha import solve_recaptcha_token

        real_client = httpx.Client  # capture before patching (same module object)

        def client_factory(**client_kwargs):
            return real_client(transport=httpx.MockTransport(handler), **client_kwargs)

        with patch("rdt_cli.captcha.httpx.Client", new=client_factory), \
             patch("rdt_cli.captcha.time.sleep"):
            return solve_recaptcha_token("KEY", **kwargs)

    def test_solve_success(self):
        from urllib.parse import parse_qs

        import httpx

        polls = {"n": 0}
        submitted = {}

        def handler(request):
            if request.url.path == "/in.php":
                submitted.update(parse_qs(request.content.decode()))
                return httpx.Response(200, text="OK|task123")
            polls["n"] += 1
            if polls["n"] == 1:
                return httpx.Response(200, text="CAPCHA_NOT_READY")
            return httpx.Response(200, text="OK|TOKEN123")

        token = self._run_solver(handler)
        assert token == "TOKEN123"
        assert polls["n"] == 2
        # Task submitted as a score-based Enterprise reCAPTCHA (v3 + enterprise=1)
        assert submitted["key"] == ["KEY"]
        assert submitted["method"] == ["userrecaptcha"]
        assert submitted["googlekey"] == ["6LfirrMoAAAAAHZOipvza4kpp_VtTwLNuXVwURNQ"]
        assert submitted["version"] == ["v3"]
        assert submitted["enterprise"] == ["1"]
        assert submitted["action"] == ["post_submit"]
        assert submitted["min_score"] == ["0.3"]

    def test_submit_rejected(self):
        import httpx

        from rdt_cli.captcha import CaptchaSolveError

        def handler(request):
            return httpx.Response(200, text="ERROR_ZERO_BALANCE")

        with pytest.raises(CaptchaSolveError, match="ERROR_ZERO_BALANCE"):
            self._run_solver(handler)

    def test_poll_service_error(self):
        import httpx

        from rdt_cli.captcha import CaptchaSolveError

        def handler(request):
            if request.url.path == "/in.php":
                return httpx.Response(200, text="OK|task123")
            return httpx.Response(200, text="ERROR_WRONG_CAPTCHA_ID")

        with pytest.raises(CaptchaSolveError, match="ERROR_WRONG_CAPTCHA_ID"):
            self._run_solver(handler)

    def test_timeout(self):
        import httpx

        from rdt_cli.captcha import CaptchaSolveError

        def handler(request):
            if request.url.path == "/in.php":
                return httpx.Response(200, text="OK|task123")
            return httpx.Response(200, text="CAPCHA_NOT_READY")

        with pytest.raises(CaptchaSolveError, match="no solution"):
            self._run_solver(handler, timeout=0.01, polling_interval=0.001)

    def test_api_key_env_priority(self):
        import os

        from rdt_cli.captcha import get_solvecaptcha_api_key

        # load_user_config stubbed out: env-only resolution, hermetic against
        # any real ~/.config/rdt-cli/config.json on the dev machine.
        with patch("rdt_cli.captcha.load_user_config", return_value={}):
            with patch.dict(os.environ, {}, clear=True):
                assert get_solvecaptcha_api_key() is None
            with patch.dict(os.environ, {"APIKEY_SOLVECAPTCHA": "pkg-key"}, clear=True):
                assert get_solvecaptcha_api_key() == "pkg-key"
            with patch.dict(
                os.environ,
                {"RDT_SOLVECAPTCHA_API_KEY": "rdt-key", "APIKEY_SOLVECAPTCHA": "pkg-key"},
                clear=True,
            ):
                assert get_solvecaptcha_api_key() == "rdt-key"

    def test_api_key_from_config_file(self, tmp_path):
        import os

        from rdt_cli.captcha import get_solvecaptcha_api_key

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"solvecaptcha_api_key": "file-key"}))
        with patch.dict(os.environ, {}, clear=True), \
             patch("rdt_cli.config.USER_CONFIG_FILE", cfg):
            assert get_solvecaptcha_api_key() == "file-key"

    def test_api_key_env_beats_config_file(self, tmp_path):
        import os

        from rdt_cli.captcha import get_solvecaptcha_api_key

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"solvecaptcha_api_key": "file-key"}))
        with patch.dict(os.environ, {"APIKEY_SOLVECAPTCHA": "env-key"}, clear=True), \
             patch("rdt_cli.config.USER_CONFIG_FILE", cfg):
            assert get_solvecaptcha_api_key() == "env-key"

    def test_api_key_missing_or_invalid_config_file(self, tmp_path):
        import os

        from rdt_cli.captcha import get_solvecaptcha_api_key

        with patch.dict(os.environ, {}, clear=True), \
             patch("rdt_cli.config.USER_CONFIG_FILE", tmp_path / "nope.json"):
            assert get_solvecaptcha_api_key() is None

        bad = tmp_path / "config.json"
        bad.write_text("{not json")
        with patch.dict(os.environ, {}, clear=True), \
             patch("rdt_cli.config.USER_CONFIG_FILE", bad):
            assert get_solvecaptcha_api_key() is None

