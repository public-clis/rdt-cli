"""Auth commands: login, logout, status, whoami."""

from __future__ import annotations

import click

from ._common import (
    console,
    handle_command,
    maybe_print_structured,
    require_auth,
    structured_output_options,
)


@click.command()
def login() -> None:
    """Extract browser cookies for Reddit authentication"""
    from ..auth import extract_browser_credential, get_credential

    # Check if already logged in
    cred = get_credential()
    if cred:
        console.print("[green]✅ Already authenticated[/green]")
        return

    console.print("[dim]🔍 Searching for Reddit cookies in browsers...[/dim]")
    cred = extract_browser_credential()
    if cred:
        console.print(f"[green]✅ Login successful![/green] ({len(cred.cookies)} cookies extracted)")
    else:
        console.print("[red]❌ No Reddit cookies found.[/red]")
        console.print("  [dim]Set [bold]RDT_COOKIE[/bold] from your browser's cookie header (see README),[/dim]")
        console.print("  [dim]or log into reddit.com in your browser, then retry.[/dim]")


@click.command()
def logout() -> None:
    """Clear saved Reddit cookies"""
    from ..auth import clear_credential

    clear_credential()
    console.print("[green]✅ Credentials cleared[/green]")


@click.command()
@structured_output_options
def status(as_json: bool, as_yaml: bool) -> None:
    """Check authentication status"""
    from ..auth import CREDENTIAL_FILE, get_credential
    from ..client import RedditClient
    from ..session import summarize_session

    cred = get_credential()
    state = summarize_session(RedditClient(cred).session)
    info = {
        "authenticated": state.authenticated,
        "cookie_count": state.cookie_count,
        "credential_file": str(CREDENTIAL_FILE),
        "source": state.source,
        "username": state.username,
        "capabilities": list(state.capabilities),
        "modhash_present": state.modhash_present,
        "last_verified_at": state.last_verified_at,
        "error": state.error,
    }

    if cred:
        with RedditClient(cred) as client:
            result = client.validate_session()
        state = summarize_session(client.session)
        info.update(
            {
                "authenticated": result["authenticated"],
                "username": result.get("username") or state.username,
                "capabilities": result.get("capabilities", list(state.capabilities)),
                "modhash_present": result.get("modhash_present", state.modhash_present),
                "last_verified_at": state.last_verified_at,
                "error": result.get("error"),
            }
        )

    if maybe_print_structured(info, as_json=as_json, as_yaml=as_yaml):
        return

    if info["authenticated"]:
        console.print(f"[green]✅ Authenticated[/green] ({info['cookie_count']} cookies)")
        if info["username"]:
            console.print(f"  [dim]user: {info['username']}[/dim]")
        console.print(f"  [dim]capabilities: {', '.join(info['capabilities']) or '-'}[/dim]")
        console.print(f"  [dim]source: {info['source']}[/dim]")
    else:
        console.print("[yellow]⚠️  Not authenticated[/yellow]")
        if info["error"]:
            console.print(f"  [dim]{info['error']}[/dim]")
        console.print("  [dim]Set RDT_COOKIE (see README) or run 'rdt login' to use browser cookies[/dim]")


@click.command()
@structured_output_options
def whoami(as_json: bool, as_yaml: bool) -> None:
    """Show current user profile (karma, account age)"""
    from rich.panel import Panel

    from ._common import format_time

    cred = require_auth()

    def _render(data: dict) -> None:
        name = data.get("name", "?")
        karma_post = data.get("link_karma", 0)
        karma_comment = data.get("comment_karma", 0)
        total_karma = data.get("total_karma", karma_post + karma_comment)
        created = data.get("created_utc", 0)
        is_gold = "⭐ " if data.get("is_gold") else ""
        is_mod = "🛡️ " if data.get("is_mod") else ""

        text = (
            f"[bold cyan]u/{name}[/bold cyan] {is_gold}{is_mod}\n"
            f"📊 Total karma: {total_karma:,}\n"
            f"   Post: {karma_post:,} · Comment: {karma_comment:,}\n"
            f"📅 Joined: {format_time(created)}\n"
        )

        panel = Panel(text, title="👤 Me", border_style="green")
        console.print(panel)

    def _action(client):
        me = client.get_me()
        name = me.get("name") or client.session.username
        if not name:
            return me
        profile = client.get_user_about(name)
        profile.setdefault("name", name)
        profile["_session"] = {
            "capabilities": sorted(client.session.capabilities),
            "modhash_present": bool(client.session.modhash),
        }
        return profile

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)
