---
name: rdt-cli
description: Use rdt-cli for ALL Reddit operations — browsing feeds, reading posts, searching, viewing users, upvoting, saving, and subscribing. Invoke whenever the user requests any Reddit interaction.
author: jackwener
version: "0.4.0"
tags:
  - reddit
  - rdt
  - social-media
  - cli
---

# rdt-cli — Reddit CLI Tool

**Binary:** `rdt`
**Credentials:** browser cookies (auto-extracted via browser-cookie3)

## Setup

```bash
# Install (requires Python 3.10+)
uv tool install rdt-cli
# Or: pip install rdt-cli

# Upgrade
uv tool upgrade rdt-cli
```

## Authentication

**IMPORTANT FOR AGENTS**: Before executing ANY rdt command that requires auth, check if credentials exist.

### Step 0: Check if already authenticated

```bash
rdt status --json 2>/dev/null | jq -r '.data.authenticated' | grep -q true && echo "AUTH_OK" || echo "AUTH_NEEDED"
```

If `AUTH_OK`, skip to [Command Reference](#command-reference).
If `AUTH_NEEDED`, proceed to Step 1.

### Step 1: Guide user to authenticate

Ensure user is logged into reddit.com in a supported browser (Chrome, Firefox, Edge, Brave, Arc, Chromium, Opera, Vivaldi, Safari, LibreWolf). Then:

```bash
rdt login
```

Verify with:

```bash
rdt status
rdt whoami --json | jq '.data.name // .data._session.username'
```

### Step 2: Handle common auth issues

| Symptom | Agent action |
|---------|-------------|
| `No Reddit cookies found` | Guide user to login to reddit.com in browser |
| `Session expired` | Run `rdt logout && rdt login` |
| `database is locked` | Close browser, then retry |

## Agent Defaults

All machine-readable output uses the envelope documented in [SCHEMA.md](./SCHEMA.md).
Payloads live under `.data`.

- Non-TTY stdout → auto YAML
- `--json` / `--yaml` → explicit format
- `--compact` → fewer fields (agent token-efficient)
- `--output file.json` → save structured output to file
- Rich output → **stderr** (safe for pipes: `rdt search X --json | jq .data`)
- Most read commands work without auth (public Reddit JSON API)
- Write actions (upvote, save, subscribe, comment, post) require auth + built-in 1.5-4s delay

## Command Reference

### Browsing

| Command | Description | Example |
|---------|-------------|---------|
| `rdt feed` | Browse home feed (requires login) | `rdt feed -n 10 --json` |
| `rdt feed --subs-only` | Subscriptions-only feed (no algorithm, sorted by time) | `rdt feed --subs-only -n 5 --json` |
| `rdt popular` | Browse /r/popular | `rdt popular -n 5 --json` |
| `rdt all` | Browse /r/all | `rdt all -n 10 --compact --json` |
| `rdt sub <name>` | Browse a subreddit | `rdt sub python -s top -t week` |
| `rdt sub-info <name>` | View subreddit info | `rdt sub-info rust --json` |
| `rdt user <name>` | View user profile | `rdt user spez --json` |
| `rdt user-posts <name>` | View user's posts | `rdt user-posts spez -n 5 --json` |
| `rdt user-comments <name>` | View user's comments | `rdt user-comments spez -n 5 --json` |
| `rdt saved` | View your saved items | `rdt saved -n 10 --json` |
| `rdt upvoted` | View your upvoted posts | `rdt upvoted -n 10 --json` |
| `rdt open <id_or_index>` | Open post in browser | `rdt open 3` |

### Reading

| Command | Description | Example |
|---------|-------------|---------|
| `rdt read <post_id>` | Read a post + comments | `rdt read 1abc123 --json` |
| `rdt read <post_id> --expand-more` | Expand top-level `more comments` | `rdt read 1abc123 --expand-more --json` |
| `rdt show <index>` | Read by short-index | `rdt show 3` |
| `rdt show <index> --expand-more` | Expand `more comments` from cached result | `rdt show 3 --expand-more --json` |
| `rdt whoami` | View your profile (karma, age) | `rdt whoami --json` |

### Search & Export

| Command | Description | Example |
|---------|-------------|---------|
| `rdt search <query>` | Search posts | `rdt search "python async" -s top -t year` |
| `rdt search <query> -r <sub>` | Search in subreddit | `rdt search "error" -r rust --json` |
| `rdt search <query> -o f.json` | Search + save to file | `rdt search "ML" -n 50 -o results.json` |
| `rdt export <query>` | Export to CSV/JSON | `rdt export "ML" -n 50 -o results.csv` |

### Interactions (require auth)

| Command | Description | Example |
|---------|-------------|---------|
| `rdt upvote <id_or_index>` | Upvote | `rdt upvote 3` |
| `rdt upvote <id> --down` | Downvote | `rdt upvote 3 --down` |
| `rdt upvote <id> --undo` | Remove vote | `rdt upvote 3 --undo` |
| `rdt save <id_or_index>` | Save post | `rdt save 3` |
| `rdt save <id> --undo` | Unsave | `rdt save 3 --undo` |
| `rdt subscribe <sub>` | Subscribe | `rdt subscribe python` |
| `rdt subscribe <sub> --undo` | Unsubscribe | `rdt subscribe python --undo` |
| `rdt comment <id> <text>` | Post a comment | `rdt comment 3 "Great post!"` |

### Create posts (require auth)

Exactly one of `--text` / `--url` / `--image`. Target a subreddit or a profile (`u_<name>`). Add `--json` for a structured result.

**Drafts** save headlessly. **Publishing** is gated behind reCAPTCHA Enterprise (invisible, score-based) — it needs a `--recaptcha-token` captured from a browser (single-use, ~2 min). rdt-cli never solves the captcha.

| Command | Description | Example |
|---------|-------------|---------|
| `rdt post <sub> <title> --text <body> --draft` | Save a text draft | `rdt post python "WIP" --text "..." --draft` |
| `rdt post <sub> <title> --url <url> --draft` | Save a link draft | `rdt post news "Read" --url https://ex.com --draft` |
| `rdt post <sub> <title> --text <body> --recaptcha-token <tok>` | Publish text post | `rdt post python "Hi" --text "..." --recaptcha-token <tok>` |
| `rdt post <sub> <title> --image <file> --recaptcha-token <tok>` | Publish image post | `rdt post pics "Cat" --image cat.jpg --recaptcha-token <tok>` |

Optional flags: `--nsfw`, `--spoiler`. Notes: Reddit drafts can't store images (text/link only); `--image` requires publishing with a token.

### Account

| Command | Description |
|---------|-------------|
| `rdt login` | Extract cookies from browser |
| `rdt logout` | Clear cached cookies |
| `rdt status` | Check authentication status |
| `rdt whoami` | View detailed profile info |

## Listing Options

All listing commands (feed, popular, all, sub, user-posts, user-comments, saved, upvoted, search) support:

| Flag | Description |
|------|-------------|
| `--json` | JSON output (with SCHEMA envelope) |
| `--yaml` | YAML output (with SCHEMA envelope) |
| `-o, --output FILE` | Save structured output to file |
| `--full-text` | Show full title without truncation |
| `-c, --compact` | Agent-friendly compact output (fewer fields) |

### Feed-specific Options

| Flag | Description |
|------|-------------|
| `--subs-only` | Show only posts from subscribed subreddits (sorted by time, no algorithm) |
| `--max-subs N` | Max subscriptions to fetch (default: 20) |

## Agent Workflow Examples

### Browse → Read → Upvote pipeline

```bash
rdt sub python -s top -t week -n 5
rdt show 1 --expand-more
rdt upvote 1
```

### Search → Export pipeline (structured)

```bash
rdt search "machine learning" -s top --compact --json | jq '.data'
rdt export "machine learning" -n 100 -o ml_posts.csv
```

### Search → Save to file

```bash
rdt search "rust async" -n 50 -o results.json
rdt search "python tips" -n 20 --compact -o tips.json
```

### User research

```bash
rdt user spez --json | jq '.data | {name, link_karma, comment_karma}'
rdt user-posts spez -n 10 --compact --json
rdt user-comments spez -n 10 --compact --json
```

### Saved / Upvoted review

```bash
rdt saved -n 20 --compact --json
rdt upvoted -n 20 --compact --json
```

### Subscriptions-only monitoring

```bash
rdt feed --subs-only -n 5 --compact --json
rdt feed --subs-only --max-subs 10 -o subs_feed.json
```

### Subreddit discovery

```bash
rdt sub-info python --json | jq '.data | {subscribers, accounts_active}'
rdt sub python -s top -t month -n 5 --full-text
```

## Sort Options

- **Listing sort**: `hot`, `new`, `top`, `rising`, `controversial`, `best`
- **Search sort**: `relevance`, `hot`, `top`, `new`, `comments`
- **Time filter** (for top/controversial): `hour`, `day`, `week`, `month`, `year`, `all`
- **Comment sort**: `best`, `top`, `new`, `controversial`, `old`, `qa`

## Error Codes

Structured error codes returned in the `error.code` field (see [SCHEMA.md](./SCHEMA.md)):

- `not_authenticated` — cookies expired or missing
- `rate_limited` — too many requests
- `not_found` — subreddit/user/post does not exist
- `forbidden` — private subreddit or blocked user
- `api_error` — upstream Reddit API error
- `unknown_error` — unexpected error

## Limitations

- **No DMs** — cannot access private messages
- **No live/streaming** — live features not supported
- **No media download** — cannot download images/videos
- **Single account** — one set of cookies at a time
- **Rate limited** — built-in Gaussian jitter (~1s) between requests
- **Public API only** — uses .json suffix API, not OAuth endpoints

## Anti-Detection Notes for Agents

- **Do NOT parallelize requests** — the built-in rate-limit delay is for account safety
- **Write operation delay**: 1.5-4s random delay after each write (upvote/save/subscribe/comment)
- **Batch operations**: add delays between CLI calls when doing bulk work
- **Chrome 133 fingerprint**: all requests use consistent browser identity
- **Exponential backoff**: 429/5xx errors are auto-retried with backoff

## Safety Notes

- Do not ask users to share raw cookie values in chat logs
- Prefer browser cookie extraction over manual secret copy/paste
- If auth fails, ask the user to re-login via `rdt login`
- Built-in rate-limit delay protects accounts; do not bypass it
