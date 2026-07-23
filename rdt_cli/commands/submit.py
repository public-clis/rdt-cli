"""Post creation: draft (headless) and publish (reCAPTCHA-gated) via GraphQL.

Reddit's web GraphQL (see rdt_cli.client) lets us create **drafts** headlessly,
but **publishing** a post is gated behind reCAPTCHA Enterprise (invisible,
score-based, action ``post_submit``). A valid token can come from two sources:

1. ``--recaptcha-token`` — captured from a real browser (DevTools, single-use,
   ~2 min TTL), or
2. automatic solving — when a Solvecaptcha API key is configured (env
   ``RDT_SOLVECAPTCHA_API_KEY`` / ``APIKEY_SOLVECAPTCHA``, or
   ``solvecaptcha_api_key`` in ``~/.config/rdt-cli/config.json``), a token is
   bought from solvecaptcha.com just before publishing (see rdt_cli.captcha).

Without either, use ``--draft``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from ..captcha import get_solvecaptcha_api_key, solve_recaptcha_token
from ..client import RedditClient
from ..constants import BASE_URL
from ..exceptions import RedditApiError
from ..richtext import build_rtjson
from ._common import (
    console,
    exit_for_error,
    handle_command,
    maybe_print_structured,
    require_auth,
    structured_output_options,
    write_delay,
)


@click.command()
@click.argument("subreddit")
@structured_output_options
def flairs(subreddit: str, as_json: bool, as_yaml: bool) -> None:
    """List a subreddit's post flair templates (for `rdt post --flair-id`).

    Some communities require post flair; pick a template id here and pass it
    via --flair-id when publishing.
    """
    cred = require_auth()

    def _render(data: list[dict]) -> None:
        if not data:
            console.print("[dim]No selectable post flairs.[/dim]")
            return
        for f in data:
            editable = " [dim](text editable)[/dim]" if f.get("text_editable") else ""
            text = f.get("text") or "[yellow](no default text — pass --flair-text or the flair shows blank)[/yellow]"
            console.print(f"[bold cyan]{f.get('id', '')}[/bold cyan]  {text}{editable}")

    handle_command(
        cred,
        action=lambda c: c.get_link_flairs(subreddit),
        render=_render, as_json=as_json, as_yaml=as_yaml,
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


def _embed_images(text: str, embeds: tuple[str, ...], urls: list[str]) -> str:
    """Replace each ``![img]`` marker with a markdown link to an uploaded image.

    Markers are substituted in order: the Nth ``![img]`` becomes
    ``[<file stem>](<cdn url>)`` for the Nth --embed file.
    """
    parts = text.split("![img]")
    out = [parts[0]]
    for embed, url, tail in zip(embeds, urls, parts[1:], strict=True):
        out.append(f"[{Path(embed).stem}]({url})")
        out.append(tail)
    return "".join(out)


_RECAPTCHA_HELP = (
    "Publishing requires a reCAPTCHA Enterprise token — Reddit gates post "
    "submission with invisible, score-based reCAPTCHA (action 'post_submit'). "
    "Either pass a browser-captured token via --recaptcha-token (single-use, "
    "~2 min), or configure a Solvecaptcha API key to buy one automatically "
    "(env RDT_SOLVECAPTCHA_API_KEY / APIKEY_SOLVECAPTCHA, or "
    "'solvecaptcha_api_key' in ~/.config/rdt-cli/config.json). Without "
    "either, use --draft to save a draft headlessly."
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
    help="Image file to post — alone: an image post; with --text: attached "
         "after the body (publish only; drafts can't store images)",
)
@click.option("--draft", is_flag=True, help="Save as a draft instead of publishing (text/link only)")
@click.option(
    "--embed", "embeds",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Image to embed inline in the --text body; one per ![img] marker, in order",
)
@click.option(
    "--recaptcha-token", "recaptcha_token", default=None,
    help="reCAPTCHA Enterprise token from a browser (otherwise a token is "
         "bought via Solvecaptcha when an API key is configured)",
)
@click.option(
    "--flair-id", "flair_id", default=None,
    help="Post flair template id (see `rdt flairs <subreddit>`; publish only)",
)
@click.option(
    "--flair-text", "flair_text", default=None,
    help="Custom flair text (only for text-editable flair templates)",
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
    embeds: tuple[str, ...],
    recaptcha_token: str | None,
    flair_id: str | None,
    flair_text: str | None,
    nsfw: bool,
    spoiler: bool,
    as_json: bool,
    as_yaml: bool,
) -> None:
    """Create a post in a subreddit or profile (u_<name>): text, link, or image.

    Provide --text, --url, or --image; --text plus --image is also allowed
    (the image is attached to the text post, shown after the body, no
    caption). With --text, --embed uploads an image and substitutes it for an
    ![img] marker in the body (one marker per --embed, in order), giving true
    inline images in a text post. --embed may be combined with --image: the
    attachment then also provides the feed-card preview (inline embeds alone
    never show in feeds; the attachment additionally renders after the body).

    Drafts (--draft) are created headlessly. Publishing is gated behind reCAPTCHA
    Enterprise: pass a browser-captured --recaptcha-token, or set a Solvecaptcha
    API key (env RDT_SOLVECAPTCHA_API_KEY or APIKEY_SOLVECAPTCHA) and a token is
    bought automatically right before publishing.

    Communities that require post flair: list templates with `rdt flairs
    <subreddit>` and pass --flair-id (plus --flair-text for text-editable
    templates). Flair applies at publish only, community posts only.

    Examples:
      rdt post python "My title" --text "Hello **world**" --draft
      rdt post news "Interesting" --url https://example.com --draft
      rdt post pics "My cat" --image cat.jpg --recaptcha-token <token>
      rdt post python "Guide" --text "step 1 ![img] done" --embed step1.jpg
      rdt post u_myname "On my profile" --text "hi"   # solves via Solvecaptcha
      rdt post askscience "Q" --text "…" --flair-id 1234-abcd
    """
    provided = [
        name for name, given in
        (("--text", text is not None), ("--url", link_url is not None), ("--image", image is not None))
        if given
    ]
    if not provided or (len(provided) > 1 and provided != ["--text", "--image"]):
        raise click.UsageError(
            "Provide --text, --url, or --image. Only --text --image may be "
            "combined: a text post with the image attached after the body."
        )
    kind = "self" if text is not None else {"--url": "link", "--image": "image"}[provided[0]]

    if embeds and kind != "self":
        raise click.UsageError(
            "--embed only works with --text (inline images live in the self-post body)."
        )
    markers = text.count("![img]") if text else 0
    if embeds and markers != len(embeds):
        raise click.UsageError(
            f"--embed was given {len(embeds)} image(s) but the --text body has "
            f"{markers} ![img] marker(s). Place one ![img] marker per embedded "
            "image, in order."
        )
    if markers and not embeds:
        raise click.UsageError(
            f"The --text body has {markers} ![img] marker(s) but no --embed was "
            "given. Pass one --embed <file> per marker, or remove the markers."
        )

    if draft and image is not None:
        raise click.UsageError(
            "--image cannot be combined with --draft: Reddit drafts cannot store "
            "images (the image only attaches at publish time). Publish it with "
            "--recaptcha-token (or a configured Solvecaptcha API key), or draft "
            "text/link only."
        )

    if flair_text and not flair_id:
        raise click.UsageError("--flair-text requires --flair-id (a template id from `rdt flairs`).")
    if flair_id and draft:
        raise click.UsageError("Flair applies at publish time — drafts don't store it.")

    # Token source for publishing: explicit flag wins; otherwise a Solvecaptcha
    # API key must be configured (a token is bought just before publishing).
    solver_api_key: str | None = None
    if not draft and not recaptcha_token:
        solver_api_key = get_solvecaptcha_api_key()
        if not solver_api_key:
            raise click.UsageError(_RECAPTCHA_HELP)

    is_profile = subreddit.lower().startswith("u_")
    if flair_id and is_profile:
        raise click.UsageError("Flair is a community feature — profile posts can't take one.")

    cred = require_auth()
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            rich_text: str | None = None
            if embeds:
                console.print(f"[dim]⏳ Uploading {len(embeds)} embedded image(s)…[/dim]")
                uploaded = [client.upload_image_as_embed(embed) for embed in embeds]
                # Two body representations: publishing sends the RTJSON (true
                # inline image blocks); drafts are markdown-only, so they get
                # the marker-substituted CDN-link body instead.
                rich_text = build_rtjson(
                    text or "",
                    [(media_id, Path(embed).stem) for (media_id, _), embed in zip(uploaded, embeds, strict=True)],
                )
                text = _embed_images(text or "", embeds, [url for _, url in uploaded])
            if draft:
                # Drafts address the subreddit by t5_ id (confirmed live);
                # publishing addresses it by name, as the editor does.
                subreddit_id = client.resolve_subreddit_id(subreddit)
                data = client.create_draft(
                    subreddit_id, title, body=text, url=link_url, nsfw=nsfw, spoiler=spoiler,
                )
                action = "Draft saved"
            else:
                media_id = client.upload_image(image) if image is not None else None
                if recaptcha_token is None:
                    # Solve last — the token is single-use with a ~2 min TTL.
                    console.print(
                        "[dim]⏳ Solving reCAPTCHA Enterprise via solvecaptcha.com "
                        "(paid, usually ~10-60s)…[/dim]"
                    )
                    recaptcha_token = solve_recaptcha_token(solver_api_key or "")
                data = client.create_post(
                    subreddit, title, recaptcha_token=recaptcha_token, kind=kind,
                    body=text, url=link_url, media_id=media_id, rich_text=rich_text,
                    flair_id=flair_id, flair_text=flair_text,
                    nsfw=nsfw, spoiler=spoiler, is_profile=is_profile,
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
