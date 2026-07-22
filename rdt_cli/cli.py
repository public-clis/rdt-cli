"""CLI entry point for rdt-cli.

Usage:
    rdt login / status / logout
    rdt feed / popular / all / sub <subreddit>
    rdt read <post_id> / show <index> / open <id_or_index>
    rdt search <query> / export <query>
    rdt user <username> / user-posts <username> / user-comments <username>
    rdt saved / upvoted
    rdt upvote / save / subscribe / comment
"""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands import auth, browse, post, search, social, submit


@click.group()
@click.version_option(version=__version__, prog_name="rdt")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging (show request URLs, timing)")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """rdt — Reddit in your terminal 📖"""
    ctx.ensure_object(dict)
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(name)s %(message)s",
    )


# ─── Auth commands ───────────────────────────────────────────────────

cli.add_command(auth.login)
cli.add_command(auth.logout)
cli.add_command(auth.status)
cli.add_command(auth.whoami)

# ─── Browse commands ─────────────────────────────────────────────────

cli.add_command(browse.feed)
cli.add_command(browse.popular)
cli.add_command(browse.all_cmd)
cli.add_command(browse.sub)
cli.add_command(browse.sub_info)
cli.add_command(browse.user)
cli.add_command(browse.user_posts)
cli.add_command(browse.user_comments)
cli.add_command(browse.saved)
cli.add_command(browse.upvoted)
cli.add_command(browse.open_post)

# ─── Post commands ───────────────────────────────────────────────────

cli.add_command(post.read)
cli.add_command(post.show)

# ─── Search & Export ─────────────────────────────────────────────────

cli.add_command(search.search)
cli.add_command(search.export)

# ─── Social commands ────────────────────────────────────────────────

cli.add_command(social.upvote)
cli.add_command(social.save)
cli.add_command(social.subscribe)
cli.add_command(social.comment)

# ─── Create commands ────────────────────────────────────────────────

cli.add_command(submit.post)


if __name__ == "__main__":
    cli()
