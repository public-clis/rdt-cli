"""API client for Reddit with rate limiting, retry, and anti-detection."""

from __future__ import annotations

import logging
from typing import Any

from .config import DEFAULT_CONFIG, RuntimeConfig
from .constants import (
    ALL_URL,
    COMMENT_URL,
    DEFAULT_LIMIT,
    HOME_URL,
    MORECHILDREN_URL,
    POPULAR_URL,
    POST_COMMENTS_SHORT_URL,
    POST_COMMENTS_URL,
    SAVE_URL,
    SEARCH_URL,
    SUBREDDIT_ABOUT_URL,
    SUBREDDIT_SEARCH_URL,
    SUBSCRIBE_URL,
    SUBSCRIPTIONS_URL,
    UNSAVE_URL,
    USER_ABOUT_URL,
    USER_COMMENTS_URL,
    USER_POSTS_URL,
    USER_SAVED_URL,
    USER_UPVOTED_URL,
    VOTE_URL,
)
from .exceptions import (
    RedditApiError,
)
from .fingerprint import BrowserFingerprint
from .session import SessionState
from .transports import ReadTransport, WriteTransport

logger = logging.getLogger(__name__)


class RedditClient:
    """Reddit API client with Gaussian jitter, exponential backoff, and session-stable identity.

    Anti-detection strategy:
    - Gaussian jitter delay between requests
    - 5% chance of random long pause (2-5s) to mimic reading
    - Exponential backoff on HTTP 429/5xx (up to 3 retries)
    - Response cookies merged back into session jar
    - Per-request logging with counter
    """

    def __init__(
        self,
        credential: object | None = None,
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self.credential = credential
        self._timeout = timeout
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._config = RuntimeConfig(
            timeout=timeout,
            read_request_delay=request_delay,
            write_request_delay=max(request_delay, DEFAULT_CONFIG.write_request_delay),
            max_retries=max_retries,
            status_check_timeout=min(timeout, DEFAULT_CONFIG.status_check_timeout),
        )
        self._fingerprint = BrowserFingerprint.chrome133_mac()
        self.session = SessionState.from_credential(credential)
        self._read_transport: ReadTransport | None = None
        self._write_transport: WriteTransport | None = None
        self._http = None

    @property
    def client(self):
        if not self._read_transport:
            raise RuntimeError("Client not initialized. Use 'with RedditClient() as client:'")
        return self._read_transport.client

    def __enter__(self) -> RedditClient:
        self._read_transport = ReadTransport(
            self.session,
            config=self._config,
            fingerprint=self._fingerprint,
            request_delay=self._config.read_request_delay,
        )
        self._write_transport = WriteTransport(
            self.session,
            config=self._config,
            fingerprint=self._fingerprint,
            request_delay=self._config.write_request_delay,
        )
        self._http = self._read_transport.client
        return self

    def __exit__(self, *args: Any) -> None:
        if self._read_transport:
            self._read_transport.close()
            self._read_transport = None
        if self._write_transport:
            self._write_transport.close()
            self._write_transport = None
        self._http = None

    @property
    def request_stats(self) -> dict[str, int]:
        read_count = self._read_transport.request_count if self._read_transport else 0
        write_count = self._write_transport.request_count if self._write_transport else 0
        return {"request_count": read_count + write_count}

    # ── Core request ────────────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Read request through the low-risk transport."""
        if not self._read_transport:
            raise RuntimeError("Client not initialized. Use 'with RedditClient() as client:'")
        return self._read_transport.request(method, url, **kwargs)

    def _write_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Write request through the authenticated transport."""
        if not self._write_transport:
            raise RuntimeError("Client not initialized. Use 'with RedditClient() as client:'")
        return self._write_transport.request(method, url, **kwargs)

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET request."""
        return self._request("GET", url, params=params)

    def _post(self, url: str, data: dict[str, Any] | None = None) -> Any:
        """POST request."""
        return self._write_request("POST", url, data=data)

    @staticmethod
    def _format_api_errors(errors: Any) -> str:
        """Flatten Reddit's json.errors list into a readable message."""
        if not isinstance(errors, list):
            return str(errors)

        messages: list[str] = []
        for error in errors:
            if isinstance(error, (list, tuple)):
                message = ": ".join(str(part) for part in error if part)
            else:
                message = str(error)
            if message:
                messages.append(message)
        return "; ".join(messages) or "Reddit API returned an error"

    def _raise_for_api_errors(self, response: Any) -> None:
        """Raise when an old Reddit API response contains json.errors."""
        if not isinstance(response, dict):
            return

        json_response = response.get("json")
        if not isinstance(json_response, dict):
            return

        errors = json_response.get("errors")
        if errors:
            raise RedditApiError(self._format_api_errors(errors), response=response)

    # ── Listing helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_posts(data: dict) -> list[dict]:
        """Extract post list from Reddit Listing response."""
        if isinstance(data, list):
            # Comments endpoint returns [post_listing, comments_listing]
            return data
        children = data.get("data", {}).get("children", [])
        return [child.get("data", child) for child in children]

    @staticmethod
    def _extract_after(data: dict) -> str | None:
        """Extract pagination cursor."""
        if isinstance(data, list):
            return None
        return data.get("data", {}).get("after")

    # ── Feed / Listing endpoints ────────────────────────────────────

    def get_home(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get home feed (requires login)."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(HOME_URL, params=params)

    def get_popular(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get /r/popular."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(POPULAR_URL, params=params)

    def get_all(self, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get /r/all."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(ALL_URL, params=params)

    def get_subreddit(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = DEFAULT_LIMIT,
        after: str | None = None,
        time_filter: str | None = None,
    ) -> dict:
        """Get subreddit listing."""
        url = f"/r/{subreddit}.json" if sort == "hot" else f"/r/{subreddit}/{sort}.json"
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        if time_filter and sort in ("top", "controversial"):
            params["t"] = time_filter
        return self._get(url, params=params)

    def get_subreddit_about(self, subreddit: str) -> dict:
        """Get subreddit info."""
        data = self._get(SUBREDDIT_ABOUT_URL.format(subreddit=subreddit), params={"raw_json": 1})
        return data.get("data", data)

    # ── Post / Comments ─────────────────────────────────────────────

    def get_post_comments(
        self,
        post_id: str,
        subreddit: str | None = None,
        sort: str = "best",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        """Get post and its comments.

        Returns [post_listing, comments_listing].
        """
        if subreddit:
            url = POST_COMMENTS_URL.format(subreddit=subreddit, post_id=post_id)
        else:
            url = POST_COMMENTS_SHORT_URL.format(post_id=post_id)
        params: dict[str, Any] = {"sort": sort, "limit": limit, "raw_json": 1}
        return self._get(url, params=params)

    def get_more_comments(
        self,
        post_id: str,
        children: list[str],
        *,
        sort: str = "best",
    ) -> dict:
        """Expand additional comments for a post."""
        if not children:
            return {"json": {"data": {"things": []}}}
        params: dict[str, Any] = {
            "api_type": "json",
            "link_id": f"t3_{post_id}",
            "children": ",".join(children),
            "sort": sort,
            "limit_children": False,
            "raw_json": 1,
        }
        return self._get(MORECHILDREN_URL, params=params)

    # ── Search ──────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        subreddit: str | None = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = DEFAULT_LIMIT,
        after: str | None = None,
    ) -> dict:
        """Search posts."""
        if subreddit:
            url = SUBREDDIT_SEARCH_URL.format(subreddit=subreddit)
        else:
            url = SEARCH_URL
        params: dict[str, Any] = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": limit,
            "restrict_sr": "on" if subreddit else "off",
            "raw_json": 1,
        }
        if after:
            params["after"] = after
        return self._get(url, params=params)

    # ── User ────────────────────────────────────────────────────────

    def get_user_about(self, username: str) -> dict:
        """Get user profile info."""
        data = self._get(USER_ABOUT_URL.format(username=username), params={"raw_json": 1})
        return data.get("data", data)

    def get_user_posts(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's submitted posts."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_POSTS_URL.format(username=username), params=params)

    def get_user_comments(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's comments."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_COMMENTS_URL.format(username=username), params=params)

    def get_user_saved(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's saved items."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_SAVED_URL.format(username=username), params=params)

    def get_user_upvoted(self, username: str, limit: int = DEFAULT_LIMIT, after: str | None = None) -> dict:
        """Get user's upvoted items."""
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if after:
            params["after"] = after
        return self._get(USER_UPVOTED_URL.format(username=username), params=params)

    # ── Identity (requires auth) ────────────────────────────────────

    def get_me(self) -> dict:
        """Get current user info and enrich session capabilities."""
        data = self._get("/api/me.json", params={"raw_json": 1})
        if isinstance(data, dict):
            self.session.apply_identity(data)
        return data

    def validate_session(self) -> dict[str, Any]:
        """Probe a lightweight auth endpoint to classify current credential."""
        try:
            identity = self.get_me()
            return {
                "authenticated": True,
                "username": self.session.username,
                "capabilities": sorted(self.session.capabilities),
                "modhash_present": bool(self.session.modhash),
                "identity": identity,
            }
        except RedditApiError as exc:
            self.session.apply_validation_error(str(exc))
            return {
                "authenticated": False,
                "username": self.session.username,
                "capabilities": sorted(self.session.capabilities),
                "modhash_present": bool(self.session.modhash),
                "error": str(exc),
            }

    # ── Write actions (require authentication) ──────────────────────

    def vote(self, fullname: str, direction: int) -> dict:
        """Vote on a post or comment. direction: 1=upvote, 0=unvote, -1=downvote."""
        return self._post(VOTE_URL, data={"id": fullname, "dir": str(direction)})

    def save_item(self, fullname: str) -> dict:
        """Save a post or comment."""
        return self._post(SAVE_URL, data={"id": fullname})

    def unsave_item(self, fullname: str) -> dict:
        """Unsave a post or comment."""
        return self._post(UNSAVE_URL, data={"id": fullname})

    def subscribe(self, subreddit: str, action: str = "sub") -> dict:
        """Subscribe or unsubscribe. action: 'sub' or 'unsub'."""
        return self._post(SUBSCRIBE_URL, data={"sr_name": subreddit, "action": action})

    def post_comment(self, parent_fullname: str, text: str) -> dict:
        """Post a comment."""
        response = self._post(
            COMMENT_URL,
            data={
                "api_type": "json",
                "thing_id": parent_fullname,
                "text": text,
            },
        )
        self._raise_for_api_errors(response)
        return response

    # ── Subscription feed ───────────────────────────────────────────

    def get_my_subscriptions(
        self, limit: int = 100, max_subs: int = 20,
    ) -> list[str]:
        """Get names of subscribed subreddits (up to max_subs)."""
        names: list[str] = []
        after: str | None = None
        while len(names) < max_subs:
            params: dict[str, Any] = {"limit": min(limit, 100), "raw_json": 1}
            if after:
                params["after"] = after
            data = self._get(SUBSCRIPTIONS_URL, params=params)
            children = data.get("data", {}).get("children", [])
            if not children:
                break
            for child in children:
                name = child.get("data", {}).get("display_name", "")
                if name:
                    names.append(name)
                if len(names) >= max_subs:
                    break
            after = data.get("data", {}).get("after")
            if not after:
                break
        return names

    def get_subs_only_feed(
        self,
        limit_per_sub: int = DEFAULT_LIMIT,
        max_subs: int = 20,
        on_progress: Any = None,
    ) -> dict:
        """Aggregate newest posts from subscribed subreddits.

        Returns a synthetic listing dict compatible with parse_listing().
        """
        subs = self.get_my_subscriptions(max_subs=max_subs)
        if not subs:
            return {"data": {"children": [], "after": None}}

        all_posts: list[dict] = []
        seen_ids: set[str] = set()

        for i, sub_name in enumerate(subs):
            if on_progress:
                on_progress(i + 1, len(subs), sub_name)
            try:
                data = self.get_subreddit(sub_name, sort="new", limit=limit_per_sub)
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", child)
                    pid = post.get("id", "")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        all_posts.append(child if "data" in child else {"data": child})
            except RedditApiError as exc:
                logger.warning("Skipping r/%s: %s", sub_name, exc)

        # Sort by created_utc descending
        all_posts.sort(
            key=lambda c: c.get("data", {}).get("created_utc", 0),
            reverse=True,
        )

        return {"data": {"children": all_posts, "after": None}}
