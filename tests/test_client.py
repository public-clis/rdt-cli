from __future__ import annotations

from unittest.mock import patch

import pytest

from rdt_cli.auth import Credential
from rdt_cli.client import RedditClient
from rdt_cli.exceptions import ForbiddenError, RedditApiError


def test_validate_session_success_updates_username_and_capabilities() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", return_value={"name": "spez", "modhash": "mh"}):
            result = client.validate_session()

    assert result["authenticated"] is True
    assert result["username"] == "spez"
    assert "write" in result["capabilities"]


def test_validate_session_failure_preserves_read_capability() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", side_effect=RedditApiError("boom")):
            result = client.validate_session()

    assert result["authenticated"] is False
    assert result["capabilities"] == ["read"]
    assert result["error"] == "boom"


def test_get_user_saved_uses_saved_endpoint() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", return_value={"ok": True}) as mock_get:
            data = client.get_user_saved("spez", limit=5, after="t3_next")

    assert data == {"ok": True}
    mock_get.assert_called_once_with("/user/spez/saved.json", params={"limit": 5, "raw_json": 1, "after": "t3_next"})


def test_get_user_upvoted_uses_upvoted_endpoint() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", return_value={"ok": True}) as mock_get:
            data = client.get_user_upvoted("spez", limit=7)

    assert data == {"ok": True}
    mock_get.assert_called_once_with("/user/spez/upvoted.json", params={"limit": 7, "raw_json": 1})


def test_get_more_comments_uses_api_morechildren() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", return_value={"json": {"data": {"things": []}}}) as mock_get:
            data = client.get_more_comments("abc123", ["c3", "c4"], sort="top")

    assert data["json"]["data"]["things"] == []
    mock_get.assert_called_once_with(
        "/api/morechildren.json",
        params={
            "api_type": "json",
            "link_id": "t3_abc123",
            "children": "c3,c4",
            "sort": "top",
            "limit_children": False,
            "raw_json": 1,
        },
    )


def test_search_falls_back_to_api_host_when_search_json_is_forbidden() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", side_effect=[ForbiddenError(), {"ok": True}]) as mock_get:
            data = client.search("test", limit=5)

    assert data == {"ok": True}
    assert mock_get.call_count == 2
    first, second = mock_get.call_args_list
    assert first.args[0] == "/search.json"
    assert second.args[0] == "https://api.reddit.com/search"
    assert first.kwargs["params"] == second.kwargs["params"]


def test_subreddit_search_falls_back_to_api_host_when_search_json_is_forbidden() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", side_effect=[ForbiddenError(), {"ok": True}]) as mock_get:
            data = client.search("asyncio", subreddit="python", limit=3)

    assert data == {"ok": True}
    first, second = mock_get.call_args_list
    assert first.args[0] == "/r/python/search.json"
    assert second.args[0] == "https://api.reddit.com/r/python/search"
    assert second.kwargs["params"]["restrict_sr"] == "on"


def test_search_does_not_fall_back_on_other_errors() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_get", side_effect=RedditApiError("boom")) as mock_get:
            with pytest.raises(RedditApiError):
                client.search("test")

    assert mock_get.call_count == 1
