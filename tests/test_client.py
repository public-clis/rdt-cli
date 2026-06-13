from __future__ import annotations

from unittest.mock import patch

from rdt_cli.auth import Credential
from rdt_cli.client import RedditClient
from rdt_cli.exceptions import RedditApiError


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


def test_post_comment_uses_reddit_comment_payload() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    with RedditClient(cred) as client:
        with patch.object(client, "_post", return_value={"json": {"errors": []}}) as mock_post:
            data = client.post_comment("t3_abc123", "Useful context.")

    assert data == {"json": {"errors": []}}
    mock_post.assert_called_once_with(
        "/api/comment",
        data={
            "api_type": "json",
            "thing_id": "t3_abc123",
            "text": "Useful context.",
        },
    )


def test_post_comment_raises_on_reddit_api_errors() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    response = {"json": {"errors": [["BAD_THING", "bad target", "thing_id"]]}}

    with RedditClient(cred) as client:
        with patch.object(client, "_post", return_value=response):
            try:
                client.post_comment("t3_abc123", "Useful context.")
            except RedditApiError as exc:
                assert "BAD_THING" in str(exc)
                assert exc.response == response
            else:
                raise AssertionError("expected RedditApiError")
