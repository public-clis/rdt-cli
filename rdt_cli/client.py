"""API client for Reddit with rate limiting, retry, and anti-detection."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import DEFAULT_CONFIG, RuntimeConfig
from .constants import (
    ALL_URL,
    BASE_URL,
    COMMENT_URL,
    DEFAULT_LIMIT,
    DEL_URL,
    GRAPHQL_URL,
    HOME_URL,
    IMAGE_MIME_TO_EXT,
    IMAGE_MIME_TYPES,
    MEDIA_CDN_HOST,
    MEDIA_S3_HOST,
    MORECHILDREN_URL,
    OP_CREATE_DRAFT,
    OP_CREATE_POST,
    OP_CREATE_PROFILE_POST,
    OP_MEDIA_LEASE,
    POPULAR_URL,
    POST_COMMENTS_SHORT_URL,
    POST_COMMENTS_URL,
    SAVE_URL,
    SEARCH_URL,
    SUBREDDIT_ABOUT_URL,
    SUBREDDIT_RULES_URL,
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
from .transports import SSL_CONTEXT, ReadTransport, WriteTransport

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

    def get_subreddit_rules(self, subreddit: str) -> dict:
        """Get subreddit rules (``about/rules.json``).

        Returns the raw response: ``rules`` (community rules, each with
        ``short_name``, ``description``, ``kind``), plus Reddit-wide
        ``site_rules``.
        """
        return self._get(SUBREDDIT_RULES_URL.format(subreddit=subreddit), params={"raw_json": 1})

    def get_link_flairs(self, subreddit: str) -> list[dict[str, Any]]:
        """List a subreddit's post flair templates (``link_flair_v2.json``).

        Returns the raw template list (``id``, ``text``, ``text_editable``, …)
        for use with post flair selection. Needs auth cookies; communities
        that disallow user flair selection respond 403.
        """
        data = self._get(f"/r/{subreddit}/api/link_flair_v2.json", params={"raw_json": 1})
        return data if isinstance(data, list) else []

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

    def delete_item(self, fullname: str) -> dict:
        """Delete your own post (t3_*) or comment (t1_*). Irreversible."""
        return self._post(DEL_URL, data={"id": fullname})

    def subscribe(self, subreddit: str, action: str = "sub") -> dict:
        """Subscribe or unsubscribe. action: 'sub' or 'unsub'."""
        return self._post(SUBSCRIBE_URL, data={"sr_name": subreddit, "action": action})

    def post_comment(self, parent_fullname: str, text: str) -> dict:
        """Post a comment."""
        return self._post(COMMENT_URL, data={"parent": parent_fullname, "text": text})

    # ── Post creation (GraphQL) ─────────────────────────────────────

    def _graphql(self, operation: str, variables: dict[str, Any]) -> Any:
        """POST a shreddit GraphQL operation and return its ``data`` payload.

        Sends ``{operation, variables, csrf_token}`` as JSON. The csrf_token is
        echoed into the write transport's cookie jar so cookie == body (Reddit's
        double-submit CSRF). Raises RedditApiError on GraphQL-level errors.
        """
        if self._write_transport is None:
            raise RuntimeError("Client not initialized. Use 'with RedditClient() as client:'")
        token = self.session.ensure_csrf_token()
        self._write_transport.client.cookies.set("csrf_token", token)
        payload = {"operation": operation, "variables": variables, "csrf_token": token}
        result = self._write_request("POST", GRAPHQL_URL, json=payload)
        if isinstance(result, dict) and result.get("errors"):
            errors = result["errors"]
            msg = "; ".join(
                e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors
            ) or str(errors)
            raise RedditApiError(f"GraphQL {operation} failed: {msg}")
        if isinstance(result, dict):
            return result.get("data", result)
        return result

    @staticmethod
    def _markdown_content(body: str | None) -> dict[str, Any]:
        """Content payload for a markdown body (empty dict for no body)."""
        return {"markdown": body} if body else {}

    def resolve_subreddit_id(self, subreddit: str) -> str:
        """Resolve a subreddit name to its ``t5_`` fullname (for GraphQL input)."""
        about = self.get_subreddit_about(subreddit)
        sub_id = about.get("name") if isinstance(about, dict) else None
        if not sub_id:
            raise RedditApiError(f"Could not resolve subreddit r/{subreddit}")
        return sub_id

    def create_media_lease(self, mimetype_token: str) -> dict[str, Any]:
        """Request an S3 upload lease for an image (``mimetype_token`` e.g. 'JPEG')."""
        data = self._graphql(OP_MEDIA_LEASE, {"input": {"mimetype": mimetype_token}})
        lease = data.get("createMediaUploadLease") if isinstance(data, dict) else None
        if not isinstance(lease, dict) or not lease.get("uploadLease"):
            raise RedditApiError("Media lease request returned no upload lease")
        return lease

    def upload_image(self, path: str) -> str:
        """Upload an image to Reddit's S3 and return its media asset id.

        Flow: lease (GraphQL) → multipart POST to the S3 URL from the lease
        (lease fields verbatim + ``file`` last, no reddit cookies) → mediaId.
        """
        file_path = Path(path)
        if not file_path.is_file():
            raise RedditApiError(f"Image file not found: {path}")
        content_type, _ = mimetypes.guess_type(file_path.name)
        if content_type not in IMAGE_MIME_TYPES:
            raise RedditApiError(
                f"Unsupported image type for {path} (allowed: {', '.join(sorted(IMAGE_MIME_TYPES))})"
            )
        token = content_type.split("/")[-1].upper()  # image/jpeg → JPEG

        lease = self.create_media_lease(token)
        upload_lease = lease["uploadLease"]
        upload_url = upload_lease["uploadLeaseUrl"]
        if upload_url.startswith("//"):
            upload_url = "https:" + upload_url
        fields = {h["header"]: h["value"] for h in upload_lease.get("uploadLeaseHeaders", [])}
        media_id = lease.get("mediaId")
        if not media_id:
            raise RedditApiError("Media lease did not return a mediaId")

        # Separate client: cross-site S3 host, must NOT carry reddit cookies.
        headers = {
            "User-Agent": self._fingerprint.user_agent,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
        }
        with httpx.Client(
            follow_redirects=True, timeout=httpx.Timeout(self._timeout), verify=SSL_CONTEXT
        ) as s3:
            resp = s3.post(
                upload_url,
                data=fields,
                files={"file": (file_path.name, file_path.read_bytes(), content_type)},
                headers=headers,
            )
        if resp.status_code not in (200, 201):
            raise RedditApiError(f"Image upload failed (HTTP {resp.status_code})")
        return media_id

    def upload_image_as_embed(self, path: str) -> tuple[str, str]:
        """Upload an image for embedding in a self-post body; return (media_id, cdn_url).

        The media id goes into an RTJSON ``img`` node (renders as a real inline
        image on New Reddit); the CDN URL is the markdown fallback link target:
        ``https://i.redd.it/<mediaId>.<ext>`` serves unsigned (unlike
        ``preview.redd.it`` URLs, whose ``s=`` param is a signature).
        """
        media_id = self.upload_image(path)
        content_type, _ = mimetypes.guess_type(Path(path).name)
        ext = IMAGE_MIME_TO_EXT.get(content_type or "", "jpg")
        return media_id, f"{MEDIA_CDN_HOST}/{media_id}.{ext}"

    def create_post(
        self,
        subreddit_name: str,
        title: str,
        *,
        recaptcha_token: str,
        kind: str = "self",
        body: str | None = None,
        url: str | None = None,
        media_id: str | None = None,
        rich_text: str | None = None,
        flair_id: str | None = None,
        flair_text: str | None = None,
        nsfw: bool = False,
        spoiler: bool = False,
        is_profile: bool = False,
    ) -> Any:
        """Publish a post (subreddit ``CreatePost`` / profile ``CreateProfilePost``).

        Reddit gates post submission behind **reCAPTCHA Enterprise** (invisible,
        score-based, action ``post_submit``). ``recaptcha_token`` MUST be a fresh
        token obtained from a browser (single-use, ~2 min TTL) — it cannot be
        produced headlessly, so this call fails without one. Field shapes come
        from captured live requests (deviating from them 500s):
        the subreddit is addressed by **name** (``subredditName`` — not the
        ``t5_`` id, which drafts use), there is **no** ``postType`` field, and
        ``isCommercialCommunication``/``targetLanguage`` are always sent.
        Kind-specific fields: self→``content.markdown``|``content.richText``,
        link→``url``, image→``gallery.items[].mediaId`` (subreddit) or
        ``image.url`` (profile). A self-post may also carry ``media_id``: the
        image is attached via ``image.url`` (both targets — captured subreddit
        traffic attaches this way too, not via gallery) and renders after the
        body, uncaptioned.

        For self-posts, ``rich_text`` (stringified RTJSON, see rdt_cli.richtext)
        replaces the markdown: ``content`` carries exactly one representation,
        and the fancy-pants editor always submits ``content.richText`` alone
        (captured live requests never pair it with markdown). Reddit stores the
        RTJSON canonically and derives the markdown export from it, so ``body``
        is ignored when ``rich_text`` is given. RTJSON is the only way to get
        true inline image blocks — a markdown body renders image links as links.

        ``flair_id`` (a template id from :meth:`get_link_flairs`) attaches post
        flair, with ``flair_text`` overriding the text for editable templates.
        Community posts only. Confirmed live: the template id and text land on
        the post (``link_flair_template_id``/``link_flair_text``). A template
        with empty default text needs ``flair_text``, else the applied flair
        renders as a blank label.
        """
        if kind == "self":
            content = {"richText": rich_text} if rich_text else self._markdown_content(body)
        else:
            content = {}
        inp: dict[str, Any] = {
            "title": title,
            "isNsfw": bool(nsfw),
            "isSpoiler": bool(spoiler),
            "content": content,
            "isCommercialCommunication": False,
            "targetLanguage": "",
            "recaptchaToken": recaptcha_token,
            "correlationId": str(uuid.uuid4()),
        }
        if kind == "self" and media_id:
            inp["image"] = {"url": f"{MEDIA_S3_HOST}/{media_id}"}
        elif kind == "link":
            inp["url"] = url
        if is_profile:
            if kind == "image":
                inp["image"] = {"url": f"{MEDIA_S3_HOST}/{media_id}"}
            return self._graphql(OP_CREATE_PROFILE_POST, {"input": inp})

        inp["subredditName"] = subreddit_name.removeprefix("r/")
        if flair_id:
            flair: dict[str, Any] = {"id": flair_id}
            if flair_text:
                flair["text"] = flair_text
            inp["flair"] = flair
        if kind == "image":
            inp["gallery"] = {"items": [{"mediaId": media_id}]}
        return self._graphql(OP_CREATE_POST, {"input": inp})

    def create_draft(
        self,
        subreddit_id: str,
        title: str,
        *,
        body: str | None = None,
        url: str | None = None,
        nsfw: bool = False,
        spoiler: bool = False,
    ) -> Any:
        """Save a post draft via ``CreateDraft`` (text or link — no captcha needed).

        Reddit drafts store text (markdown) or a link URL only; they cannot hold
        images (the draft input type has no media field). Text is confirmed live;
        the link shape is best-effort.
        """
        inp: dict[str, Any] = {
            "subredditId": subreddit_id,
            "title": title,
            "isNsfw": bool(nsfw),
            "isSpoiler": bool(spoiler),
        }
        if url:
            inp["kind"] = "LINK"
            inp["url"] = url
            inp["content"] = {}
        else:
            inp["kind"] = "MARKDOWN"
            inp["content"] = self._markdown_content(body)
        return self._graphql(OP_CREATE_DRAFT, {"input": inp})

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
