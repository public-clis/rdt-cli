"""Common helpers for Reddit CLI commands."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

import click
from rich.console import Console

from ..auth import Credential, get_credential
from ..client import RedditClient
from ..exceptions import RedditApiError, SessionExpiredError, error_code_for_exception

T = TypeVar("T")

console = Console(stderr=True)
error_console = Console(stderr=True)
_stdout = Console()

_SCHEMA_VERSION = "1"
_OUTPUT_ENV = "OUTPUT"


# ── Shared formatters (DRY — used by browse, search, post) ──────────


def format_score(score: int) -> str:
    """Format score as human-readable string (e.g., 1.2k)."""
    if score >= 1000:
        return f"{score / 1000:.1f}k"
    return str(score)


def format_time(ts: float) -> str:
    """Format Unix timestamp to relative time string."""
    if not ts:
        return "-"
    now = datetime.now(timezone.utc).timestamp()
    diff = now - ts
    if diff < 0:
        return "just now"
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    if diff < 86400:
        return f"{int(diff / 3600)}h ago"
    if diff < 604800:
        return f"{int(diff / 86400)}d ago"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# ── Output format resolution ────────────────────────────────────────


def resolve_output_format(*, as_json: bool, as_yaml: bool) -> str | None:
    """Resolve explicit flags first, then env override, then TTY default.

    Returns "json", "yaml", or None (for rich rendering).
    """
    if as_json and as_yaml:
        raise click.UsageError("Use only one of --json or --yaml.")
    if as_json:
        return "json"
    if as_yaml:
        return "yaml"

    output_mode = os.getenv(_OUTPUT_ENV, "auto").strip().lower()
    if output_mode == "yaml":
        return "yaml"
    if output_mode == "json":
        return "json"
    if output_mode == "rich":
        return None

    if not sys.stdout.isatty():
        return "yaml"
    return None


# ── Structured output (stable agent envelope) ──────────────────────


def success_payload(data: Any) -> dict[str, Any]:
    """Wrap structured success data in the shared agent schema."""
    return {
        "ok": True,
        "schema_version": _SCHEMA_VERSION,
        "data": data,
    }


def error_payload(code: str, message: str, *, details: Any | None = None) -> dict[str, Any]:
    """Wrap structured error data in the shared agent schema."""
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details
    return {
        "ok": False,
        "schema_version": _SCHEMA_VERSION,
        "error": error,
    }


def print_json(data: Any) -> None:
    """Print raw JSON output to stdout."""
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def print_yaml(data: Any) -> None:
    """Print raw YAML output to stdout."""
    try:
        import yaml

        click.echo(yaml.dump(
            data, allow_unicode=True, default_flow_style=False,
            sort_keys=False, default_style='"', width=1000,
        ))
    except ImportError:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def maybe_print_structured(data: Any, *, as_json: bool, as_yaml: bool) -> bool:
    """Print structured output (with envelope) when requested or when stdout is non-TTY.

    Returns True if output was printed, False if rich rendering should be used.
    """
    fmt = resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    if not fmt:
        return False
    payload = success_payload(data)
    if fmt == "json":
        print_json(payload)
    else:
        print_yaml(payload)
    return True


def emit_error(
    code: str,
    message: str,
    *,
    as_json: bool | None = None,
    as_yaml: bool | None = None,
    details: Any | None = None,
) -> bool:
    """Emit a structured error when the active output mode is machine-readable.

    Returns True if the error was emitted as structured output.
    """
    if as_json is None or as_yaml is None:
        ctx = click.get_current_context(silent=True)
        params = ctx.params if ctx is not None else {}
        as_json = bool(params.get("as_json", False)) if as_json is None else as_json
        as_yaml = bool(params.get("as_yaml", False)) if as_yaml is None else as_yaml

    fmt = resolve_output_format(as_json=bool(as_json), as_yaml=bool(as_yaml))
    if fmt is None:
        return False

    payload = error_payload(code, message, details=details)
    if fmt == "json":
        print_json(payload)
    else:
        print_yaml(payload)
    return True


# ── Auth / Client helpers ───────────────────────────────────────────


def require_auth() -> Credential:
    """Get credential or exit with error."""
    cred = get_credential()
    if not cred:
        console.print(
            "[yellow]⚠️  Not authenticated[/yellow]. Set [bold]RDT_COOKIE[/bold] "
            "(see README) or run [bold]rdt login[/bold]"
        )
        sys.exit(1)
    return cred


def optional_auth() -> Credential | None:
    """Get a credential if one is already available, else None (for public endpoints).

    Never triggers browser cookie extraction — public commands should not read
    the browser's cookie database as a side effect. Run `rdt login` once to save
    a credential if you want authenticated public browsing.
    """
    return get_credential(allow_browser=False)


def get_client(credential: Credential | None = None) -> RedditClient:
    """Create a RedditClient with optional credential."""
    return RedditClient(credential)


def run_client_action(credential: Credential | None, action: Callable[[RedditClient], T]) -> T:
    """Run a client action with auto-retry on session expiry."""
    try:
        with get_client(credential) as client:
            return action(client)
    except SessionExpiredError:
        # An anonymous run should never fall back to invasive browser extraction.
        if credential is None:
            raise
        from ..auth import extract_browser_credential

        fresh = extract_browser_credential()
        if fresh:
            with get_client(fresh) as client:
                return action(client)
        raise


def handle_command(
    credential: Credential | None,
    *,
    action: Callable[[RedditClient], T],
    render: Callable[[T], None] | None = None,
    as_json: bool = False,
    as_yaml: bool = False,
) -> T | None:
    """Run a client action with structured output support.

    - --json → JSON stdout (with envelope)
    - --yaml or non-TTY → YAML (with envelope)
    - Otherwise → rich render

    On error: emits structured error + exit(1).
    """
    try:
        data = run_client_action(credential, action)

        if maybe_print_structured(data, as_json=as_json, as_yaml=as_yaml):
            return data

        if render:
            render(data)
        return data

    except RedditApiError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml)
        return None  # unreachable, but for type checker


def handle_errors(fn: Callable[[], T], *, as_json: bool = False, as_yaml: bool = False) -> T | None:
    """Run arbitrary command logic and catch RedditApiError."""
    try:
        return fn()
    except RedditApiError as exc:
        exit_for_error(exc, as_json=as_json, as_yaml=as_yaml)
        return None


def exit_for_error(
    exc: Exception,
    *,
    as_json: bool = False,
    as_yaml: bool = False,
    prefix: str | None = None,
) -> None:
    """Emit a structured/non-structured error and terminate the command."""
    message = str(exc)
    if prefix:
        message = f"{prefix}: {message}"

    code = error_code_for_exception(exc)

    if emit_error(code, message, as_json=as_json, as_yaml=as_yaml):
        raise SystemExit(1) from None

    error_console.print(f"[red]❌ [{code}] {message}[/red]")
    raise SystemExit(1) from None


def structured_output_options(command: Callable) -> Callable:
    """Add --json/--yaml options to a Click command."""
    command = click.option("--yaml", "as_yaml", is_flag=True, help="Output as YAML")(command)
    command = click.option("--json", "as_json", is_flag=True, help="Output as JSON")(command)
    return command


def listing_options(command: Callable) -> Callable:
    """Add --json/--yaml/--output/--full-text/--compact options to listing commands."""
    command = click.option(
        "-c", "--compact", is_flag=True,
        help="Compact output (fewer fields, agent-friendly)",
    )(command)
    command = click.option(
        "--full-text", "full_text", is_flag=True,
        help="Show full title/text without truncation",
    )(command)
    command = click.option(
        "-o", "--output", "output_file", default=None,
        help="Save structured output to file (JSON/YAML)",
    )(command)
    command = click.option("--yaml", "as_yaml", is_flag=True, help="Output as YAML")(command)
    command = click.option("--json", "as_json", is_flag=True, help="Output as JSON")(command)
    return command


def output_or_render(data: Any, *, as_json: bool, as_yaml: bool, render: Callable) -> None:
    """DRY output routing: JSON / YAML (with envelope) / Rich."""
    if maybe_print_structured(data, as_json=as_json, as_yaml=as_yaml):
        return
    render(data)


def save_output_to_file(data: Any, output_file: str) -> None:
    """Save structured output to a file (auto-detect JSON/YAML by extension)."""
    payload = success_payload(data)
    ext = output_file.rsplit(".", 1)[-1].lower() if "." in output_file else "json"
    if ext in ("yml", "yaml"):
        try:
            import yaml
            text = yaml.dump(
                payload, allow_unicode=True, default_flow_style=False,
                sort_keys=False, default_style='"', width=1000,
            )
        except ImportError:
            text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)
    console.print(f"[green]✅ Saved to {output_file}[/green]")


def compact_posts(posts: list[dict]) -> list[dict]:
    """Strip non-essential fields for agent-friendly compact output."""
    keep = {"id", "name", "title", "subreddit", "author", "score", "num_comments", "permalink", "url", "created_utc"}
    return [{k: v for k, v in p.items() if k in keep} for p in posts]


def compact_post_detail(detail: Any) -> dict[str, Any]:
    """Flatten a PostDetail into a compact, agent-friendly structure."""
    from ..models import PostDetail
    from ..parser import parse_post_detail

    if not isinstance(detail, PostDetail):
        detail = parse_post_detail(detail)

    post = detail.post
    compact_post = {
        "id": post.id,
        "title": post.title,
        "subreddit": post.subreddit,
        "author": post.author,
        "score": post.score,
        "num_comments": post.num_comments,
        "selftext": post.selftext,
        "url": post.url,
        "permalink": post.permalink,
    }

    def _flatten_comments(comments: list, depth: int = 0) -> list[dict]:
        flat: list[dict] = []
        for c in comments:
            if c.author == "[more]":
                continue
            flat.append({
                "author": c.author,
                "score": c.score,
                "body": c.body,
                "depth": depth,
            })
            flat.extend(_flatten_comments(c.replies, depth + 1))
        return flat

    return {
        "post": compact_post,
        "comments": _flatten_comments(detail.comments),
    }


def write_delay() -> None:
    """Random delay for write operations (1.5-4s) to mitigate rate limits."""
    import random
    import time

    delay = random.uniform(1.5, 4.0)
    time.sleep(delay)


def open_url(url: str) -> None:
    """Open a URL in the default browser."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", url], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", url], check=True)
        elif system == "Windows":
            subprocess.run(["start", url], check=True, shell=True)
        else:
            click.echo(url)
    except (FileNotFoundError, subprocess.CalledProcessError):
        click.echo(url)

