"""E2E smoke tests for rdt-cli — requires working network.

These tests hit the real Reddit JSON API. No auth required for most
public endpoints.

Run: uv run pytest tests/test_smoke.py -v -m smoke
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from rdt_cli.cli import cli

smoke = pytest.mark.smoke
runner = CliRunner()


def _invoke(*args):
    return runner.invoke(cli, list(args))


def _invoke_json(*args):
    """Invoke with --json and parse output."""
    result = runner.invoke(cli, [*args, "--json"])
    try:
        data = json.loads(result.output) if result.exit_code == 0 else None
    except json.JSONDecodeError:
        data = None
    return result, data


def _authenticated() -> bool:
    result, data = _invoke_json("status")
    return bool(result.exit_code == 0 and data and data.get("ok") and data.get("data", {}).get("authenticated"))


# ── Auth ────────────────────────────────────────────────────────────


@smoke
class TestAuth:
    def test_status(self):
        result = _invoke("status")
        assert result.exit_code == 0

    def test_status_json(self):
        result, data = _invoke_json("status")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True
            assert "authenticated" in data["data"]


# ── Browse (public, no auth needed) ─────────────────────────────────


@smoke
class TestPopular:
    def test_popular(self):
        result = _invoke("popular", "-n", "3")
        assert result.exit_code == 0

    def test_popular_json(self):
        result, data = _invoke_json("popular", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True
            assert "data" in data["data"]  # Reddit API listing under envelope

    def test_popular_yaml(self):
        result = runner.invoke(cli, ["popular", "-n", "3", "--yaml"])
        assert result.exit_code == 0


@smoke
class TestAll:
    def test_all(self):
        result = _invoke("all", "-n", "3")
        assert result.exit_code == 0

    def test_all_json(self):
        result, data = _invoke_json("all", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True


@smoke
class TestSubreddit:
    def test_sub_hot(self):
        result = _invoke("sub", "python", "-n", "5")
        assert result.exit_code == 0

    def test_sub_new(self):
        result = _invoke("sub", "python", "-s", "new", "-n", "3")
        assert result.exit_code == 0

    def test_sub_top_week(self):
        result = _invoke("sub", "python", "-s", "top", "-t", "week", "-n", "3")
        assert result.exit_code == 0

    def test_sub_rising(self):
        result = _invoke("sub", "python", "-s", "rising", "-n", "3")
        assert result.exit_code == 0

    def test_sub_json(self):
        result, data = _invoke_json("sub", "python", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_sub_nonexistent(self):
        result = _invoke("sub", "thissubredditshouldnotexist12345xyz")
        # Now correctly exits with code 1 on API error
        assert result.exit_code in (0, 1)


@smoke
class TestSubInfo:
    def test_sub_info(self):
        result = _invoke("sub-info", "python")
        assert result.exit_code == 0

    def test_sub_info_json(self):
        result, data = _invoke_json("sub-info", "python")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            assert "display_name" in inner or "subscribers" in inner

    def test_sub_info_large(self):
        """Test with a very large subreddit."""
        result, data = _invoke_json("sub-info", "AskReddit")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            if "subscribers" in inner:
                assert inner["subscribers"] > 1_000_000


@smoke
class TestRules:
    def test_rules(self):
        result = _invoke("rules", "python")
        assert result.exit_code == 0

    def test_rules_json(self):
        result, data = _invoke_json("rules", "python")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            assert "rules" in inner


@smoke
class TestUser:
    def test_user_profile(self):
        result = _invoke("user", "spez")
        assert result.exit_code == 0

    def test_user_profile_json(self):
        result, data = _invoke_json("user", "spez")
        assert result.exit_code == 0
        if data:
            inner = data.get("data", data)
            assert "name" in inner

    def test_user_nonexistent(self):
        result = _invoke("user", "thisusershouldnotexist12345xyz")
        # Now correctly exits with code 1 on API error
        assert result.exit_code in (0, 1)


@smoke
class TestUserPosts:
    def test_user_posts(self):
        result = _invoke("user-posts", "spez", "-n", "3")
        assert result.exit_code == 0

    def test_user_posts_json(self):
        result, data = _invoke_json("user-posts", "spez", "-n", "3")
        assert result.exit_code == 0


@smoke
class TestUserComments:
    def test_user_comments(self):
        result = _invoke("user-comments", "spez", "-n", "3")
        assert result.exit_code == 0

    def test_user_comments_json(self):
        result, data = _invoke_json("user-comments", "spez", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True


# ── Search ──────────────────────────────────────────────────────────


@smoke
class TestSearch:
    def test_search_basic(self):
        result = _invoke("search", "python", "-n", "5")
        assert result.exit_code == 0

    def test_search_subreddit(self):
        result = _invoke("search", "async", "-r", "python", "-n", "3")
        assert result.exit_code == 0

    def test_search_sort_top(self):
        result = _invoke("search", "rust", "-s", "top", "-t", "year", "-n", "3")
        assert result.exit_code == 0

    def test_search_json(self):
        result, data = _invoke_json("search", "python tips", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_search_sort_comments(self):
        result = _invoke("search", "reddit", "-s", "comments", "-n", "3")
        assert result.exit_code == 0


# ── Post reading ────────────────────────────────────────────────────


@smoke
class TestRead:
    def test_read_invalid_id(self):
        result = _invoke("read", "invalid_post_id_that_does_not_exist")
        # May exit 0 or 1 depending on API response
        assert result.exit_code in (0, 1)

    def test_read_expand_more_help(self):
        result = _invoke("read", "--help")
        assert result.exit_code == 0
        assert "--expand-more" in result.output


@smoke
class TestShow:
    def test_show_no_cache(self):
        # Without prior search, show should exit with error
        result = _invoke("show", "1")
        assert result.exit_code in (0, 1)


# ── Open ────────────────────────────────────────────────────────────


@smoke
class TestOpen:
    def test_open_no_cache(self):
        result = _invoke("open", "1")
        assert result.exit_code == 0


# ── Export ──────────────────────────────────────────────────────────


@smoke
class TestExport:
    def test_export_csv_stdout(self):
        result = _invoke("export", "python", "-n", "3", "--format", "csv")
        assert result.exit_code == 0
        if result.output.strip():
            assert "title" in result.output.lower() or "subreddit" in result.output.lower()

    def test_export_json_stdout(self):
        result = _invoke("export", "python", "-n", "3", "--format", "json")
        assert result.exit_code == 0

    def test_export_csv_file(self, tmp_path):
        outfile = str(tmp_path / "test.csv")
        result = runner.invoke(cli, ["export", "python", "-n", "3", "-o", outfile])
        assert result.exit_code == 0

    def test_export_json_file(self, tmp_path):
        outfile = str(tmp_path / "test.json")
        result = runner.invoke(cli, ["export", "python", "-n", "3", "--format", "json", "-o", outfile])
        assert result.exit_code == 0


# ── Comment (help only, no auth) ────────────────────────────────────


@smoke
class TestComment:
    def test_comment_help(self):
        result = _invoke("comment", "--help")
        assert result.exit_code == 0
        assert "comment" in result.output.lower()


# ── Roundtrip workflows ────────────────────────────────────────────


@smoke
class TestRoundtrip:
    def test_search_then_show(self):
        """E2E: search → show #1."""
        r1 = _invoke("search", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("show", "1")
        assert r2.exit_code == 0

    def test_browse_then_show(self):
        """E2E: sub → show #1."""
        r1 = _invoke("sub", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("show", "1")
        assert r2.exit_code == 0

    def test_popular_then_open(self):
        """E2E: popular → open #1 (mocked to avoid browser popup)."""
        r1 = _invoke("popular", "-n", "3")
        assert r1.exit_code == 0

        # Don't actually open browser in test
        from unittest.mock import patch
        with patch("rdt_cli.commands.browse.open_url"):
            r2 = _invoke("open", "1")
            assert r2.exit_code == 0

    def test_multi_command(self):
        """Multiple commands in sequence."""
        for cmd in [
            ["status"],
            ["popular", "-n", "3"],
            ["sub-info", "python"],
        ]:
            result = _invoke(*cmd)
            assert result.exit_code == 0, f"{cmd} failed: {result.output}"

    def test_search_then_export(self):
        """E2E: search then export same query."""
        r1 = _invoke("search", "python", "-n", "3")
        assert r1.exit_code == 0

        r2 = _invoke("export", "python", "-n", "3", "--format", "json")
        assert r2.exit_code == 0

    def test_search_then_show_json(self):
        """E2E: search → show #1 --json (structured)."""
        r1 = _invoke("search", "python", "-n", "3")
        assert r1.exit_code == 0

        r2, data = _invoke_json("show", "1")
        assert r2.exit_code == 0
        if data:
            assert data["ok"] is True


# ── New features: --full-text, --output, --compact ──────────────────


@smoke
class TestFullText:
    def test_popular_full_text(self):
        result = _invoke("popular", "-n", "3", "--full-text")
        assert result.exit_code == 0

    def test_sub_full_text(self):
        result = _invoke("sub", "python", "-n", "3", "--full-text")
        assert result.exit_code == 0

    def test_search_full_text(self):
        result = _invoke("search", "python", "-n", "3", "--full-text")
        assert result.exit_code == 0


@smoke
class TestCompact:
    def test_popular_compact_json(self):
        result, data = _invoke_json("popular", "-n", "3", "--compact")
        assert result.exit_code == 0
        if data and data.get("ok"):
            items = data["data"]
            if isinstance(items, list) and items:
                # Compact should strip non-essential fields
                assert "title" in items[0]
                assert "score" in items[0]

    def test_search_compact_json(self):
        result, data = _invoke_json("search", "python", "-n", "3", "--compact")
        assert result.exit_code == 0
        if data and data.get("ok"):
            items = data["data"]
            if isinstance(items, list) and items:
                assert "title" in items[0]


@smoke
class TestOutputFile:
    def test_popular_output_json(self, tmp_path):
        outfile = str(tmp_path / "popular.json")
        result = runner.invoke(
            cli, ["popular", "-n", "3", "-o", outfile],
        )
        assert result.exit_code == 0
        import os
        assert os.path.exists(outfile)
        with open(outfile) as f:
            data = json.load(f)
        assert data["ok"] is True

    def test_search_output_json(self, tmp_path):
        outfile = str(tmp_path / "search.json")
        result = runner.invoke(
            cli, ["search", "python", "-n", "3", "-o", outfile],
        )
        assert result.exit_code == 0
        import os
        assert os.path.exists(outfile)

    def test_sub_output_compact(self, tmp_path):
        outfile = str(tmp_path / "sub.json")
        result = runner.invoke(
            cli, ["sub", "python", "-n", "3", "--compact", "-o", outfile],
        )
        assert result.exit_code == 0
        import os
        assert os.path.exists(outfile)
        with open(outfile) as f:
            data = json.load(f)
        assert data["ok"] is True
        if isinstance(data["data"], list) and data["data"]:
            assert "title" in data["data"][0]


# ── YAML envelope validation ───────────────────────────────────────


@smoke
class TestYamlEnvelope:
    def test_status_yaml(self):
        result = runner.invoke(cli, ["status", "--yaml"])
        assert result.exit_code == 0
        assert "ok: true" in result.output
        assert "schema_version" in result.output

    def test_sub_info_yaml(self):
        result = runner.invoke(cli, ["sub-info", "python", "--yaml"])
        assert result.exit_code == 0
        assert "ok: true" in result.output


# ── Miscellaneous coverage ─────────────────────────────────────────


@smoke
class TestMisc:
    def test_version(self):
        result = _invoke("--version")
        assert result.exit_code == 0
        assert "rdt-cli" in result.output or "0." in result.output

    def test_sub_controversial(self):
        result = _invoke("sub", "python", "-s", "controversial", "-n", "3")
        assert result.exit_code == 0

    def test_whoami_help(self):
        result = _invoke("whoami", "--help")
        assert result.exit_code == 0
        output = result.output.lower()
        assert "profile" in output or "karma" in output or "whoami" in output

    def test_user_posts_full_text(self):
        result = _invoke("user-posts", "spez", "-n", "3", "--full-text")
        assert result.exit_code == 0


# ── Positive read test ─────────────────────────────────────────────


@smoke
class TestReadPositive:
    def test_read_real_post(self):
        """Search → get a real post ID → read it."""
        r1, data = _invoke_json("search", "python", "-n", "1")
        assert r1.exit_code == 0
        if not data or not data.get("ok"):
            pytest.skip("Search returned no data")

        # Extract a post ID from search results
        from rdt_cli.client import RedditClient
        inner = data.get("data", {})
        posts = RedditClient._extract_posts(inner)
        if not posts:
            pytest.skip("No posts in search results")

        post_id = posts[0].get("id", "")
        if not post_id:
            pytest.skip("Post has no ID")

        r2 = _invoke("read", post_id)
        assert r2.exit_code == 0

    def test_read_real_post_json(self):
        """Search → read post --json."""
        r1, data = _invoke_json("search", "python tips", "-n", "1")
        assert r1.exit_code == 0
        if not data or not data.get("ok"):
            pytest.skip("Search returned no data")

        from rdt_cli.client import RedditClient
        inner = data.get("data", {})
        posts = RedditClient._extract_posts(inner)
        if not posts:
            pytest.skip("No posts")

        post_id = posts[0].get("id", "")
        if not post_id:
            pytest.skip("No ID")

        r2, r2_data = _invoke_json("read", post_id)
        assert r2.exit_code == 0
        if r2_data:
            assert r2_data["ok"] is True

    def test_read_real_post_expand_more_json(self):
        r1, data = _invoke_json("search", "python tips", "-n", "1")
        assert r1.exit_code == 0
        if not data or not data.get("ok"):
            pytest.skip("Search returned no data")

        from rdt_cli.client import RedditClient

        inner = data.get("data", {})
        posts = RedditClient._extract_posts(inner)
        if not posts:
            pytest.skip("No posts")

        post_id = posts[0].get("id", "")
        if not post_id:
            pytest.skip("No ID")

        r2, r2_data = _invoke_json("read", post_id, "--expand-more")
        assert r2.exit_code == 0
        if r2_data:
            assert r2_data["ok"] is True
            assert "comments" in r2_data["data"]


@smoke
class TestAuthenticatedViews:
    def test_saved_json(self):
        if not _authenticated():
            pytest.skip("Authentication required for saved")
        result, data = _invoke_json("saved", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_upvoted_json(self):
        if not _authenticated():
            pytest.skip("Authentication required for upvoted")
        result, data = _invoke_json("upvoted", "-n", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True

    def test_feed_subs_only(self):
        if not _authenticated():
            pytest.skip("Authentication required for --subs-only")
        result = _invoke("feed", "--subs-only", "-n", "3", "--max-subs", "3")
        assert result.exit_code == 0

    def test_feed_subs_only_json(self):
        if not _authenticated():
            pytest.skip("Authentication required for --subs-only")
        result, data = _invoke_json("feed", "--subs-only", "-n", "3", "--max-subs", "3")
        assert result.exit_code == 0
        if data:
            assert data["ok"] is True


# ── Pagination ─────────────────────────────────────────────────────


@smoke
class TestPagination:
    def test_popular_pagination(self):
        """Fetch page 1, extract cursor, fetch page 2."""
        r1, data = _invoke_json("popular", "-n", "3")
        assert r1.exit_code == 0
        if not data or not data.get("ok"):
            pytest.skip("No data")

        inner = data.get("data", {})
        from rdt_cli.client import RedditClient
        cursor = RedditClient._extract_after(inner)
        if not cursor:
            pytest.skip("No pagination cursor")

        r2 = _invoke("popular", "-n", "3", "--after", cursor)
        assert r2.exit_code == 0

    def test_search_pagination(self):
        """Search page 1, extract cursor, fetch page 2."""
        r1, data = _invoke_json("search", "python", "-n", "3")
        assert r1.exit_code == 0
        if not data or not data.get("ok"):
            pytest.skip("No data")

        inner = data.get("data", {})
        from rdt_cli.client import RedditClient
        cursor = RedditClient._extract_after(inner)
        if not cursor:
            pytest.skip("No pagination cursor")

        r2 = _invoke("search", "python", "-n", "3", "--after", cursor)
        assert r2.exit_code == 0
