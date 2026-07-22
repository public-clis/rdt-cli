"""Post creation: draft (headless) and publish (reCAPTCHA-gated) via GraphQL.

Reddit's web GraphQL (see rdt_cli.client) lets us create **drafts** headlessly,
but **publishing** a post is gated behind reCAPTCHA Enterprise (invisible,
score-based, action ``post_submit``). A valid token can only be produced by a
real browser, so publishing requires the caller to pass ``--recaptcha-token``
(obtained from DevTools, single-use, ~2 min TTL). The tool never solves the
captcha itself. Without a token, use ``--draft``.
"""

from __future__ import annotations

from typing import Any

import click

from ..client import RedditClient
from ..constants import BASE_URL
from ..exceptions import RedditApiError
from ._common import (
    console,
    exit_for_error,
    maybe_print_structured,
    require_auth,
    structured_output_options,
    write_delay,
)


def _find_first(obj: Any, keys: set[str]) -> str | None:
    """Depth-first search for the first non-empty string under any of ``keys``."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and isinstance(value, str) and value:
                return value
        for value in obj.values():
            found = _find_first(value, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, keys)
            if found:
                return found
    return None


def _permalink_from(data: Any) -> str | None:
    """Best-effort extraction of a post permalink from a GraphQL response."""
    permalink = _find_first(data, {"permalink"}) or _find_first(data, {"postUrl"})
    if permalink and permalink.startswith("/"):
        permalink = f"{BASE_URL}{permalink}"
    return permalink


_RECAPTCHA_HELP = (
    "Publishing requires a reCAPTCHA Enterprise token — Reddit gates post "
    "submission with invisible, score-based reCAPTCHA (action 'post_submit'). "
    "A token can only be produced by a browser (single-use, ~2 min). Pass it via "
    "--recaptcha-token, or use --draft to save a draft headlessly."
)


@click.command()
@click.argument("subreddit")
@click.argument("title")
@click.option("--text", "text", default=None, help="Self/text post body (markdown)")
@click.option("--url", "link_url", default=None, help="Link post URL")
@click.option(
    "--image", "image",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Image file to post (publish only; drafts can't store images)",
)
@click.option("--draft", is_flag=True, help="Save as a draft instead of publishing (text/link only)")
@click.option(
    "--recaptcha-token", "recaptcha_token", default=None,
    help="reCAPTCHA Enterprise token from a browser (required to publish)",
)
@click.option("--nsfw", is_flag=True, help="Mark as NSFW")
@click.option("--spoiler", is_flag=True, help="Mark as spoiler")
@structured_output_options
def post(
    subreddit: str,
    title: str,
    text: str | None,
    link_url: str | None,
    image: str | None,
    draft: bool,
    recaptcha_token: str | None,
    nsfw: bool,
    spoiler: bool,
    as_json: bool,
    as_yaml: bool,
) -> None:
    """Create a post in a subreddit or profile (u_<name>): text, link, or image.

    Provide exactly one of --text, --url, or --image.

    Drafts (--draft) are created headlessly. Publishing is gated behind reCAPTCHA
    Enterprise, so it needs a --recaptcha-token captured from a browser.

    Examples:
      rdt post python "My title" --text "Hello **world**" --draft
      rdt post news "Interesting" --url https://example.com --draft
      rdt post pics "My cat" --image cat.jpg --recaptcha-token <token>
      rdt post u_myname "On my profile" --text "hi" --recaptcha-token <token>
    """
    provided = [
        name for name, given in
        (("--text", text is not None), ("--url", link_url is not None), ("--image", image is not None))
        if given
    ]
    if len(provided) != 1:
        raise click.UsageError("Provide exactly one of --text, --url, or --image.")
    kind = {"--text": "self", "--url": "link", "--image": "image"}[provided[0]]

    if draft and kind == "image":
        raise click.UsageError(
            "--image cannot be combined with --draft: Reddit drafts cannot store "
            "images (the image only attaches at publish time). Publish it with "
            "--recaptcha-token, or draft text/link only."
        )
    if not draft and not recaptcha_token:
        raise click.UsageError(_RECAPTCHA_HELP)

    is_profile = subreddit.lower().startswith("u_")

    cred = require_auth()
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            subreddit_id = client.resolve_subreddit_id(subreddit)
            if draft:
                data = client.create_draft(
                    subreddit_id, title, body=text, url=link_url, nsfw=nsfw, spoiler=spoiler,
                )
                action = "Draft saved"
            else:
                media_id = client.upload_image(image) if image is not None else None
                data = client.create_post(
                    subreddit_id, title, recaptcha_token=recaptcha_token or "", kind=kind,
                    body=text, url=link_url, media_id=media_id, nsfw=nsfw, spoiler=spoiler,
                    is_profile=is_profile,
                )
                action = "Posted"
        write_delay()

        permalink = _permalink_from(data)
        draft_id = _find_first(data, {"id"}) if draft else None
        payload: dict[str, Any] = {
            "action": "draft" if draft else "post",
            "subreddit": subreddit,
            "title": title,
            "kind": kind,
            "result": data,
        }
        if permalink:
            payload["permalink"] = permalink
        if draft_id:
            payload["draft_id"] = draft_id

        if maybe_print_structured(payload, as_json=as_json, as_yaml=as_yaml):
            return
        target = permalink or draft_id or f'"{title}"'
        console.print(f"[green]✅ {action}[/green] to {subreddit}: {target}")
        if draft:
            console.print(
                f"[dim]Drafts can't be published headlessly (reCAPTCHA). "
                f"Finish in browser: {BASE_URL}/r/{subreddit}/submit[/dim]"
            )
    except RedditApiError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml, prefix="Post failed")
