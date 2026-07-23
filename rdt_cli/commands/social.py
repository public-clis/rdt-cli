"""Social / interaction commands: upvote, save, subscribe, comment."""

from __future__ import annotations

import click

from ..client import RedditClient
from ..exceptions import RedditApiError
from ..index_cache import get_item_by_index
from ._common import console, exit_for_error, require_auth, write_delay

# ── Helpers ─────────────────────────────────────────────────────────


def _resolve_fullname(id_or_index: str) -> str | None:
    """Resolve an ID or short-index to a Reddit fullname (t3_xxx).

    Accepts:
    - Short index (e.g., "3") → from cache
    - Bare post ID (e.g., "1abc123") → prepend t3_
    - Full name (e.g., "t3_1abc123") → as-is
    """
    # Try as short-index first
    try:
        idx = int(id_or_index)
        item = get_item_by_index(idx)
        if item:
            name = item.get("name", "")
            if name:
                return name
            pid = item.get("id", "")
            if pid:
                return f"t3_{pid}"
        console.print(f"[yellow]Index {idx} not found in cache[/yellow]")
        return None
    except ValueError:
        pass

    # Full name
    if id_or_index.startswith("t3_") or id_or_index.startswith("t1_"):
        return id_or_index

    # Bare ID → assume post
    return f"t3_{id_or_index}"


# ── upvote ──────────────────────────────────────────────────────────


@click.command()
@click.argument("id_or_index")
@click.option("--undo", is_flag=True, help="Remove vote")
@click.option("--down", is_flag=True, help="Downvote instead")
def upvote(id_or_index: str, undo: bool, down: bool) -> None:
    """Upvote a post (by ID or index number)

    Examples:
      rdt upvote 3           # upvote result #3
      rdt upvote 1abc123     # upvote by post ID
      rdt upvote 3 --down    # downvote
      rdt upvote 3 --undo    # remove vote
    """
    cred = require_auth()
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            fullname = _resolve_fullname(id_or_index)
            if not fullname:
                return
            direction = 0 if undo else (-1 if down else 1)
            action_label = "Unvoted" if undo else ("⬇ Downvoted" if down else "⬆ Upvoted")
            client.vote(fullname, direction=direction)
        write_delay()
        console.print(f"[green]✅ {action_label}[/green] {fullname}")
    except RedditApiError as exc:
        exit_for_error(exc, prefix="Vote failed")


# ── save / unsave ──────────────────────────────────────────────────


@click.command()
@click.argument("id_or_index")
@click.option("--undo", is_flag=True, help="Unsave")
def save(id_or_index: str, undo: bool) -> None:
    """Save a post (by ID or index number)

    Examples:
      rdt save 3           # save result #3
      rdt save 3 --undo    # unsave
    """
    cred = require_auth()
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            fullname = _resolve_fullname(id_or_index)
            if not fullname:
                return
            if undo:
                client.unsave_item(fullname)
                write_delay()
                console.print(f"[green]✅ Unsaved[/green] {fullname}")
            else:
                client.save_item(fullname)
                write_delay()
                console.print(f"[green]✅ Saved[/green] {fullname}")
    except RedditApiError as exc:
        exit_for_error(exc, prefix="Save failed")


# ── delete ──────────────────────────────────────────────────────────


@click.command()
@click.argument("id_or_index")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def delete(id_or_index: str, yes: bool) -> None:
    """Delete your own post or comment (by ID or index number)

    Irreversible; only works on things submitted by the logged-in
    account. A bare ID is assumed to be a post — pass a t1_ fullname
    to delete a comment.

    Examples:
      rdt delete 3              # delete result #3 (asks to confirm)
      rdt delete 1abc123 -y     # delete a post by ID, no prompt
      rdt delete t1_abc123 -y   # delete a comment by fullname
    """
    cred = require_auth()
    fullname = _resolve_fullname(id_or_index)
    if not fullname:
        return
    if not yes and not click.confirm(f"Delete {fullname}? This cannot be undone"):
        console.print("[dim]Aborted.[/dim]")
        return
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            client.delete_item(fullname)
        write_delay()
        console.print(f"[green]✅ Deleted[/green] {fullname}")
    except RedditApiError as exc:
        exit_for_error(exc, prefix="Delete failed")


# ── subscribe / unsubscribe ────────────────────────────────────────


@click.command()
@click.argument("subreddit")
@click.option("--undo", is_flag=True, help="Unsubscribe")
def subscribe(subreddit: str, undo: bool) -> None:
    """Subscribe to a subreddit

    Examples:
      rdt subscribe python
      rdt subscribe python --undo
    """
    cred = require_auth()
    action = "unsub" if undo else "sub"
    label = "Unsubscribed from" if undo else "Subscribed to"

    try:
        with RedditClient(cred) as client:
            client.validate_session()
            client.subscribe(subreddit, action=action)
        write_delay()
        console.print(f"[green]✅ {label}[/green] r/{subreddit}")
    except RedditApiError as exc:
        exit_for_error(exc, prefix="Subscribe failed")


# ── comment ─────────────────────────────────────────────────────────


@click.command()
@click.argument("id_or_index")
@click.argument("text")
def comment(id_or_index: str, text: str) -> None:
    """Post a comment on a post (by ID or index number)

    Examples:
      rdt comment 3 "Great post!"
      rdt comment 1abc123 "Thanks for sharing"
    """
    cred = require_auth()
    try:
        with RedditClient(cred) as client:
            client.validate_session()
            fullname = _resolve_fullname(id_or_index)
            if not fullname:
                return
            client.post_comment(fullname, text)
        write_delay()
        console.print(f"[green]✅ Comment posted[/green] on {fullname}")
    except RedditApiError as exc:
        exit_for_error(exc, prefix="Comment failed")
