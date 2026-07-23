"""Browse commands: feed, subreddit, popular, all, user, open."""

from __future__ import annotations

import logging

import click
from rich.panel import Panel
from rich.table import Table

from ..client import RedditClient
from ..constants import SORT_OPTIONS, TIME_FILTERS
from ..exceptions import RedditApiError
from ..index_cache import save_index
from ..parser import parse_listing, parse_subreddit_info, parse_user_profile
from ._common import (
    console,
    format_score,
    format_time,
    handle_command,
    listing_options,
    maybe_print_structured,
    open_url,
    optional_auth,
    require_auth,
    save_output_to_file,
    structured_output_options,
)

logger = logging.getLogger(__name__)

# Default title truncation length
_TITLE_MAX = 50
_FULL_TITLE_MAX = 200


# ── Helpers ─────────────────────────────────────────────────────────


def _render_post_table(
    posts, title: str,
    show_subreddit: bool = True, full_text: bool = False,
) -> None:
    """Render a list of posts as a Rich table."""
    if not posts:
        console.print("[yellow]No posts found[/yellow]")
        return

    save_index([post.to_dict() for post in posts], source=title[:40])
    max_title = _FULL_TITLE_MAX if full_text else _TITLE_MAX

    table = Table(title=title, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", style="yellow", width=6, justify="right")
    if show_subreddit:
        table.add_column("Subreddit", style="magenta", max_width=15)
    table.add_column(
        "Title", style="bold cyan",
        max_width=max_title if not full_text else None,
    )
    table.add_column("Author", style="green", max_width=14)
    table.add_column("💬", style="dim", width=5, justify="right")
    table.add_column("Time", style="dim", max_width=10)

    for i, post in enumerate(posts, 1):
        title_text = post.title or "-"
        if post.stickied:
            title_text = f"📌 {title_text}"
        if post.over_18:
            title_text = f"🔞 {title_text}"
        if post.is_video:
            title_text = f"🎬 {title_text}"

        if not full_text:
            title_text = title_text[:max_title]

        row = [
            str(i),
            format_score(post.score),
        ]
        if show_subreddit:
            row.append(f"r/{post.subreddit or '?'}")
        row.extend([
            title_text,
            (post.author or "-")[:14],
            str(post.num_comments),
            format_time(post.created_utc),
        ])
        table.add_row(*row)

    console.print(table)
    console.print("\n  [dim]💡 Use [bold]rdt show <#>[/bold] to read a post[/dim]")


def _listing_render(
    data: dict, title: str,
    show_subreddit: bool = True, next_cmd: str = "",
    full_text: bool = False,
) -> None:
    """Common render for listing endpoints."""
    listing = parse_listing(data)
    _render_post_table(listing.items, title, show_subreddit=show_subreddit, full_text=full_text)
    cursor = listing.after
    if cursor and next_cmd:
        console.print(f"  [dim]▸ More: {next_cmd} --after {cursor}[/dim]")


def _handle_listing(
    cred, *, action, data_title: str, next_cmd: str = "",
    show_subreddit: bool = True,
    as_json: bool, as_yaml: bool,
    output_file: str | None = None,
    full_text: bool = False,
    compact: bool = False,
) -> None:
    """Unified listing handler with --output/--full-text/--compact support."""
    from ._common import exit_for_error, run_client_action

    try:
        data = run_client_action(cred, action)

        # --output: save to file
        if output_file:
            out_data = data
            if compact:
                out_data = [post.to_dict() for post in parse_listing(data).items]
            save_output_to_file(out_data, output_file)
            return

        # --compact: strip fields for structured output
        if compact:
            data = [post.to_dict() for post in parse_listing(data).items]
            if not as_json and not as_yaml:
                as_yaml = True

        # --json/--yaml: structured output
        if maybe_print_structured(data, as_json=as_json, as_yaml=as_yaml):
            return

        # Rich render
        _listing_render(
            data, data_title,
            show_subreddit=show_subreddit,
            next_cmd=next_cmd,
            full_text=full_text,
        )
    except RedditApiError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml)


def _resolve_current_username(client: RedditClient) -> str:
    """Resolve the current username from an authenticated session."""
    identity = client.get_me()
    username = identity.get("name") or client.session.username
    if not username:
        raise RedditApiError("Unable to resolve current username from session")
    return username


# ── feed ────────────────────────────────────────────────────────────


@click.command()
@click.option("--subs-only", is_flag=True, help="Show only posts from subscribed subreddits (sorted by time)")
@click.option("--max-subs", default=20, type=int, help="Max subscriptions to fetch (default: 20)")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts (default: 25)")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def feed(
    subs_only: bool, max_subs: int,
    limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse your home feed (requires login)"""
    cred = require_auth()
    if subs_only:
        if after:
            console.print("[yellow]⚠ --after is ignored with --subs-only[/yellow]")

        def _progress(current: int, total: int, name: str) -> None:
            if not (as_json or as_yaml):
                console.print(f"  [dim]📡 [{current}/{total}] r/{name}[/dim]")

        _handle_listing(
            cred,
            action=lambda c: c.get_subs_only_feed(
                limit_per_sub=limit, max_subs=max_subs, on_progress=_progress,
            ),
            data_title="📡 Subscriptions Feed",
            next_cmd="",
            as_json=as_json, as_yaml=as_yaml,
            output_file=output_file, full_text=full_text, compact=compact,
        )
    else:
        _handle_listing(
            cred,
            action=lambda c: c.get_home(limit=limit, after=after),
            data_title="🏠 Home Feed",
            next_cmd="rdt feed",
            as_json=as_json, as_yaml=as_yaml,
            output_file=output_file, full_text=full_text, compact=compact,
        )


# ── popular ─────────────────────────────────────────────────────────


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def popular(
    limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse /r/popular"""
    cred = optional_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_popular(limit=limit, after=after),
        data_title="🔥 Popular",
        next_cmd="rdt popular",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


# ── all ─────────────────────────────────────────────────────────────


@click.command(name="all")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def all_cmd(
    limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse /r/all"""
    cred = optional_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_all(limit=limit, after=after),
        data_title="🌍 r/all",
        next_cmd="rdt all",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


# ── sub (subreddit) ─────────────────────────────────────────────────


@click.command()
@click.argument("subreddit")
@click.option("-s", "--sort", type=click.Choice(SORT_OPTIONS), default="hot", help="Sort order")
@click.option(
    "-t", "--time", "time_filter",
    type=click.Choice(TIME_FILTERS), default=None,
    help="Time filter (for top/controversial)",
)
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def sub(
    subreddit: str, sort: str, time_filter: str | None, limit: int,
    after: str | None, as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse a subreddit (e.g., rdt sub python)"""
    cred = optional_auth()
    emoji = {"hot": "🔥", "new": "🆕", "top": "🏆", "rising": "📈"}.get(sort, "📋")
    _handle_listing(
        cred,
        action=lambda c: c.get_subreddit(
            subreddit, sort=sort, limit=limit, after=after, time_filter=time_filter,
        ),
        data_title=f"{emoji} r/{subreddit} ({sort})",
        show_subreddit=False,
        next_cmd=f"rdt sub {subreddit} -s {sort}",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


# ── sub-info ────────────────────────────────────────────────────────


@click.command("sub-info")
@click.argument("subreddit")
@structured_output_options
def sub_info(subreddit: str, as_json: bool, as_yaml: bool) -> None:
    """View subreddit info (subscribers, description)"""
    cred = optional_auth()

    def _render(data: dict) -> None:
        info = parse_subreddit_info(data)
        name = info.display_name_prefixed or f"r/{subreddit}"
        desc = info.public_description or info.description
        subs = info.subscribers
        active = info.accounts_active
        created = info.created_utc
        nsfw = "🔞 NSFW" if info.over18 else ""

        text = (
            f"[bold cyan]{name}[/bold cyan] {nsfw}\n"
            f"👥 {subs:,} subscribers · 🟢 {active:,} online\n"
            f"📅 Created: {format_time(created)}\n"
        )
        if desc:
            text += f"\n{desc[:300]}"

        panel = Panel(text, title=f"📋 {name}", border_style="cyan")
        console.print(panel)

    handle_command(
        cred,
        action=lambda c: c.get_subreddit_about(subreddit),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── rules ───────────────────────────────────────────────────────────


@click.command()
@click.argument("subreddit")
@structured_output_options
def rules(subreddit: str, as_json: bool, as_yaml: bool) -> None:
    """View a subreddit's rules"""
    cred = optional_auth()

    _KIND_LABELS = {"link": "posts", "comment": "comments", "all": "posts & comments"}

    def _render(data: dict) -> None:
        rule_list = data.get("rules", [])
        if not rule_list:
            console.print(f"[dim]r/{subreddit} has no community rules.[/dim]")
            return

        lines = []
        for i, rule in enumerate(rule_list, 1):
            name = rule.get("short_name") or rule.get("violation_reason") or f"Rule {i}"
            kind = _KIND_LABELS.get(rule.get("kind", ""), "")
            kind_tag = f" [dim]({kind})[/dim]" if kind else ""
            lines.append(f"[bold cyan]{i}. {name}[/bold cyan]{kind_tag}")
            desc = (rule.get("description") or "").strip()
            if desc:
                lines.append(f"[dim]{desc}[/dim]")
            lines.append("")

        panel = Panel("\n".join(lines).rstrip(), title=f"📜 r/{subreddit} rules", border_style="cyan")
        console.print(panel)

    handle_command(
        cred,
        action=lambda c: c.get_subreddit_rules(subreddit),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── user ────────────────────────────────────────────────────────────


@click.command()
@click.argument("username")
@structured_output_options
def user(username: str, as_json: bool, as_yaml: bool) -> None:
    """View a user's profile"""
    cred = optional_auth()

    def _render(data: dict) -> None:
        profile = parse_user_profile(data)
        name = profile.name or username
        karma_post = profile.link_karma
        karma_comment = profile.comment_karma
        created = profile.created_utc
        is_gold = "⭐ " if profile.is_gold else ""

        text = (
            f"[bold cyan]u/{name}[/bold cyan] {is_gold}\n"
            f"📊 Post karma: {karma_post:,} · Comment karma: {karma_comment:,}\n"
            f"📅 Account age: {format_time(created)}\n"
        )

        panel = Panel(text, title=f"👤 u/{name}", border_style="green")
        console.print(panel)

    handle_command(
        cred, action=lambda c: c.get_user_about(username),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── user-posts ──────────────────────────────────────────────────────


@click.command("user-posts")
@click.argument("username")
@click.option("-n", "--limit", default=25, type=int, help="Number of posts")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def user_posts(
    username: str, limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """View a user's submitted posts"""
    cred = optional_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_user_posts(username, limit=limit, after=after),
        data_title=f"📝 u/{username}'s posts",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


@click.command("user-comments")
@click.argument("username")
@click.option("-n", "--limit", default=25, type=int, help="Number of comments")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def user_comments(
    username: str, limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """View a user's comments"""
    cred = optional_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_user_comments(username, limit=limit, after=after),
        data_title=f"💬 u/{username}'s comments",
        next_cmd=f"rdt user-comments {username}",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of saved items")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def saved(
    limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse your saved posts"""
    cred = require_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_user_saved(_resolve_current_username(c), limit=limit, after=after),
        data_title="🔖 Saved",
        next_cmd="rdt saved",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


@click.command()
@click.option("-n", "--limit", default=25, type=int, help="Number of upvoted items")
@click.option("--after", default=None, help="Pagination cursor")
@listing_options
def upvoted(
    limit: int, after: str | None,
    as_json: bool, as_yaml: bool,
    output_file: str | None, full_text: bool, compact: bool,
) -> None:
    """Browse your upvoted posts"""
    cred = require_auth()
    _handle_listing(
        cred,
        action=lambda c: c.get_user_upvoted(_resolve_current_username(c), limit=limit, after=after),
        data_title="⬆ Upvoted",
        next_cmd="rdt upvoted",
        as_json=as_json, as_yaml=as_yaml,
        output_file=output_file, full_text=full_text, compact=compact,
    )


# ── open ────────────────────────────────────────────────────────────


@click.command(name="open")
@click.argument("id_or_index")
def open_post(id_or_index: str) -> None:
    """Open a post in the browser (by ID or index number)

    Examples:
      rdt open 3           # open result #3 in browser
      rdt open 1abc123     # open by post ID
    """
    from ..index_cache import get_item_by_index

    # Try as short-index
    try:
        idx = int(id_or_index)
        item = get_item_by_index(idx)
        if item:
            permalink = item.get("permalink", "")
            if permalink:
                url = f"https://reddit.com{permalink}"
                console.print(f"[dim]Opening: {url}[/dim]")
                open_url(url)
                return
        console.print(f"[yellow]Index {idx} not found in cache[/yellow]")
        return
    except ValueError:
        pass

    # Bare ID or URL
    if id_or_index.startswith("http"):
        open_url(id_or_index)
    else:
        url = f"https://reddit.com/comments/{id_or_index}"
        console.print(f"[dim]Opening: {url}[/dim]")
        open_url(url)
