# rdt-cli

[![CI](https://github.com/jackwener/rdt-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jackwener/rdt-cli/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/rdt-cli.svg)](https://pypi.org/project/rdt-cli/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://pypi.org/project/rdt-cli/)

A CLI for Reddit — browse feeds, read posts, search, and interact via reverse-engineered API 📖

[English](#features) | [中文](#功能特性)

## More Tools

- [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) — Xiaohongshu CLI for search, reading, and posting
- [twitter-cli](https://github.com/jackwener/twitter-cli) — Twitter/X CLI for timelines, bookmarks, and posting
- [bilibili-cli](https://github.com/jackwener/bilibili-cli) — Bilibili CLI for videos, users, search, and feeds
- [discord-cli](https://github.com/jackwener/discord-cli) — Discord CLI for local-first sync, search, and export
- [tg-cli](https://github.com/jackwener/tg-cli) — Telegram CLI for local-first sync, search, and export

## Features

- 🔐 **Auth** — auto-extract browser cookies, status check, whoami
- 🏠 **Feed** — browse home feed, popular, /r/all, and subscription-only feed (`--subs-only`)
- 📋 **Subreddits** — browse any subreddit with sort/time filters, view subreddit info
- 📰 **Posts** — read posts and comment trees with syntax highlighting
- 💬 **Expanded comments** — `--expand-more` loads additional `more comments` entries
- 🔢 **Short-index navigation** — `rdt show 3` to read, `rdt open 3` to browser
- 🔍 **Search** — full-text search with subreddit, sort, and time filters
- 📤 **Export** — export search results to CSV or JSON; `-o file.json` on any listing
- 👤 **Users** — view user profiles, post history, comment history, saved and upvoted items
- ⬆️ **Interactions** — upvote/downvote, save/unsave, subscribe/unsubscribe, comment (with 1.5-4s rate-limit delay)
- ✍️ **Create posts** — save text/link **drafts** headlessly (`rdt post --draft`); publish text/link/image posts with a browser reCAPTCHA token (`--recaptcha-token`) or automatic solving via solvecaptcha.com
- 🛡️ **Anti-detection** — consistent Chrome 133 fingerprint, `sec-ch-ua` alignment, Gaussian jitter, exponential backoff
- 📊 **Structured output** — `--yaml`, `--json`, `--output FILE`, `--compact`, `--full-text`
- 📦 **Stable envelope** — see [SCHEMA.md](./SCHEMA.md) for `ok/schema_version/data/error`
- 🤖 **Agent-friendly** — Rich output on stderr, `--compact` for token-efficient output

> **AI Agent Tip:** Prefer `--yaml` for structured output unless strict JSON is required. Non-TTY stdout defaults to YAML automatically. Use `--compact` to reduce token usage.

## Installation

```bash
# Recommended: uv tool (fast, isolated)
uv tool install rdt-cli

# Or: pipx
pipx install rdt-cli
```

Upgrade to the latest version:

```bash
uv tool upgrade rdt-cli
# Or: pipx upgrade rdt-cli
```

From source:

```bash
git clone git@github.com:jackwener/rdt-cli.git
cd rdt-cli
uv sync
```

## Usage

```bash
# ─── Auth ─────────────────────────────────────────
rdt login                             # Extract cookies from browser
rdt status                            # Check login status
rdt status --json                     # Structured JSON envelope
rdt whoami                            # Detailed profile (karma, account age)
rdt logout                            # Clear saved cookies

# ─── Browse ───────────────────────────────────────
rdt feed                              # Home feed (requires login)
rdt feed --subs-only                  # Subscriptions-only feed (no algorithm)
rdt feed --subs-only -n 5 --max-subs 10  # Limit per-sub posts and max subs
rdt popular                           # Popular posts
rdt popular --full-text               # Show full titles
rdt all                               # /r/all
rdt sub python                        # Browse subreddit
rdt sub programming -s top -t week    # Sort + time filter
rdt sub-info python                   # Subreddit info (subscribers, etc.)
rdt rules python                      # Subreddit rules
rdt user spez                         # User profile
rdt user-posts spez                   # User's submitted posts
rdt user-comments spez                # User's comments
rdt saved                             # Your saved posts/items
rdt upvoted                           # Your upvoted posts

# Short index works after list commands (feed/popular/sub/search)
rdt sub python
rdt show 1                            # Read post #1 from listing
rdt open 1                            # Open post #1 in browser
rdt upvote 1                          # Upvote post #1

# ─── Reading ──────────────────────────────────────
rdt read 1abc123                      # Read post by ID
rdt read 1abc123 --expand-more        # Expand top-level "more comments"
rdt show 3                            # Read result #3 from last listing
rdt show 3 --expand-more              # Expand additional comments from cache-backed post
rdt show 1 -s top                     # Sort comments by top
rdt open 3                            # Open in browser

# ─── Search ───────────────────────────────────────
rdt search "python async"             # Global search
rdt search "rust vs go" -r programming  # Within subreddit
rdt search "ML" -s top -t year        # Sort by top, last year
rdt search "AI" -o results.json       # Save to file
rdt search "rust" --compact --json    # Compact agent output

# ─── Export ───────────────────────────────────────
rdt export "python tips" -n 100 -o tips.csv
rdt export "rust" --format json -o results.json

# ─── Interactions (require login) ─────────────────
rdt upvote 3                          # Upvote result #3
rdt upvote 3 --down                   # Downvote
rdt upvote 3 --undo                   # Remove vote
rdt save 3                            # Save result #3
rdt save 3 --undo                     # Unsave
rdt subscribe python                  # Subscribe to r/python
rdt subscribe python --undo           # Unsubscribe
rdt comment 3 "Great post!"           # Comment on result #3
rdt delete 1abc123 -y                 # Delete your own post (t1_… for comments)

# ─── Create posts (require login) ─────────────────
# Drafts save headlessly. Publishing is gated behind reCAPTCHA Enterprise:
# either pass --recaptcha-token from a browser (single-use, ~2 min), or set
# RDT_SOLVECAPTCHA_API_KEY (or APIKEY_SOLVECAPTCHA) and a token is bought from
# solvecaptcha.com automatically right before publishing (paid, ~10-60s).
rdt post python "WIP title" --text "Hello **world**" --draft   # Save a text draft
rdt post news "Cool read" --url https://example.com --draft    # Save a link draft
rdt post python "Title" --text "body" --recaptcha-token <tok>  # Publish text post
rdt post pics "My cat" --image cat.jpg                         # Publish image (captcha auto-solved)
rdt post u_yourname "On my profile" --text "hi"                # Publish to profile
rdt post python "Guide" --text "step 1 ![img] done" --embed step1.jpg  # Inline image in a text post
rdt post python "Report" --text "summary **md**" --image chart.png     # Text post + attached image
rdt flairs askscience                                          # List post flair templates (id + text)
rdt post askscience "Q" --text "…" --flair-id <template-id>    # Publish with flair (some subs require it)
```

> **Post flair (live-verified):** some communities require flair. `rdt flairs
> <subreddit>` lists the templates; pass the id via `--flair-id` when
> publishing (plus `--flair-text` to override text-editable templates).
> Publish-only, community posts only. Careful: a template with empty default
> text still applies without `--flair-text`, but renders as a blank
> (invisible) label — the listing flags such templates.

> **Attached image in a text post:** `--text` + `--image` publishes a markdown
> text post with the image attached (`image.url` in the mutation input): it
> renders after the body, uncaptioned. The body stays markdown, so formatting
> works — markdown just can't *inline* images; for that use `--embed`.
>
> **Feed visibility trade-off (live-verified):** an attached image is the
> post's preview media, so it shows on feed/list cards too. Inline (`--embed`)
> images are body content only — feed cards show just the text preview, and
> the images appear only once the post is opened. Pick `--image` for feed
> visibility, `--embed` for placement and captions. Combining `--embed` with
> `--image` gives both (live-verified): the feed card shows the attached image
> (inline embeds stay feed-hidden), and the opened post shows the inline
> embeds in place *plus* the attachment after the body — so attach a distinct
> image unless you want it appearing twice in the post.

> **Inline images in text posts:** each `--embed FILE` uploads an image and
> replaces one `![img]` marker in `--text` (markers are substituted in order).
> On publish, the body is sent editor-style as RTJSON (`content.richText`,
> *instead of* markdown — Reddit stores the RTJSON canonically and derives the
> markdown export from it): New Reddit renders each marker as a real inline
> image block (caption = file name). The RTJSON body is plain text, so keep
> `--text` unformatted when embedding — markdown syntax would show literally.
> Drafts are markdown-only, so embeds there stay links to the Reddit-hosted
> image (`https://i.redd.it/<id>.<ext>`, which serves unsigned —
> `preview.redd.it` URLs don't).

> **Note:** Reddit drafts store text/link only — not images (image drafts aren't
> supported by Reddit). Publishing any post requires a reCAPTCHA Enterprise
> token: capture one from a browser, or let rdt-cli buy one via
> [Solvecaptcha](https://solvecaptcha.com) — set `RDT_SOLVECAPTCHA_API_KEY` or
> `APIKEY_SOLVECAPTCHA` (its 2captcha-compatible API is called directly over
> httpx, so no extra dependencies). Each solve is a paid API call (~10-60s).

## Authentication

rdt-cli supports browser cookie extraction to authenticate with Reddit:

1. **Saved cookies** — loads from `~/.config/rdt-cli/credential.json`
2. **Browser cookies** — auto-detects installed browsers and extracts cookies (supports Chrome, Firefox, Edge, Brave)

`rdt login` automatically tries all installed browsers and uses the first one with valid cookies.

### Cookie TTL

Saved cookies are valid for **7 days** by default. After that, the client automatically attempts to refresh from the browser. If browser extraction fails, the existing cookies are used with a warning.

### Short-Index Navigation

After any listing command such as `feed`, `popular`, `all`, `sub`, or `search`, the CLI stores the latest ordered post list in `~/.config/rdt-cli/index_cache.json`.

- `rdt show <N>` reads the Nth post from the latest listing
- `rdt open <N>` opens the Nth post in the browser
- `rdt upvote <N>`, `rdt save <N>`, `rdt comment <N>` reuse the same short index
- Empty listings clear the index cache, so old results are not reused by accident

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT` | `auto` | Output format: `json`, `yaml`, `rich`, or `auto` (→ YAML when non-TTY) |
| `RDT_SOLVECAPTCHA_API_KEY` | — | Solvecaptcha API key — enables automatic reCAPTCHA solving when publishing posts |
| `APIKEY_SOLVECAPTCHA` | — | Fallback for the above (solvecaptcha-python's own convention) |

## Config File

`~/.config/rdt-cli/config.json` (optional) — settings applied when no env var overrides them:

```json
{
  "solvecaptcha_api_key": "your-solvecaptcha-key"
}
```

Solvecaptcha key priority: `RDT_SOLVECAPTCHA_API_KEY` → `APIKEY_SOLVECAPTCHA` → config file.
A missing or invalid file is ignored silently.

## Rate Limiting & Anti-Detection

rdt-cli includes anti-detection measures designed to minimize risk:

### Request Timing
- **Gaussian jitter**: Delays between requests use a truncated Gaussian distribution (~1s mean, σ=0.3)
- **Random long pauses**: ~5% of requests include an additional 2-5 second delay simulating reading behavior
- **Auto-retry**: Exponential backoff on HTTP 429/5xx and network errors (up to 3 retries)

### Browser Fingerprint Consistency
- **UA/Platform alignment**: User-Agent, `sec-ch-ua`, `sec-ch-ua-platform`, `sec-ch-ua-mobile` are all consistent (Chrome 133)
- **Cookie merge**: Set-Cookie headers from Reddit responses are merged back into the session

## Structured Output

All `--json` / `--yaml` output uses the shared envelope from [SCHEMA.md](./SCHEMA.md):
```yaml
ok: true
schema_version: "1"
data: { ... }
```

When stdout is not a TTY (e.g., piped or invoked by an AI agent), output defaults to YAML.
Use `OUTPUT=yaml|json|rich|auto` to override.

## Use as AI Agent Skill

rdt-cli ships with a [`SKILL.md`](./SKILL.md) that teaches AI agents how to use it.

### [Skills CLI](https://github.com/vercel-labs/skills) (Recommended)

```bash
npx skills add jackwener/rdt-cli
```

| Flag | Description |
| --- | --- |
| `-g` | Install globally (user-level, shared across projects) |
| `-a claude-code` | Target a specific agent |
| `-y` | Non-interactive mode |

### Manual Install

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/rdt-cli.git .agents/skills/rdt-cli
```

### ~~OpenClaw / ClawHub~~ (Deprecated)

> ⚠️ ClawHub 安装方式已过时，不再支持。请使用上方的 [Skills CLI](#skills-cli-recommended) 或手动安装。
## Project Structure

```text
rdt_cli/
├── __init__.py           # Version
├── __main__.py           # python -m rdt_cli entry point
├── cli.py                # Click entry point & command registration
├── client.py             # Reddit API client (rate-limit, retry, anti-detection)
├── auth.py               # Cookie authentication + TTL refresh
├── captcha.py            # reCAPTCHA Enterprise solving via the Solvecaptcha API
├── constants.py          # URLs, headers, sort options
├── exceptions.py         # Error hierarchy (6 exception types)
├── index_cache.py        # Short-index cache for show/open commands
├── richtext.py           # RTJSON document building (inline images in self-posts)
└── commands/
    ├── _common.py        # Shared helpers (envelope, output routing, formatters)
    ├── auth.py           # login, logout, status, whoami
    ├── browse.py         # feed, popular, all, sub, sub-info, rules, user, user-posts, user-comments, saved, upvoted, open
    ├── post.py           # read, show
    ├── search.py         # search, export
    ├── social.py         # upvote, save, subscribe, comment, delete
    └── submit.py         # post (text/link/image, drafts)
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Unit tests only (no network)
uv run pytest tests/ -v -m "not smoke"

# Smoke tests (need cookies)
uv run pytest tests/ -v -m smoke

# Lint
uv run ruff check .
```

## Troubleshooting

**Q: `No Reddit cookies found`**

1. Open any browser and visit https://www.reddit.com/
2. Log in with your account
3. Run `rdt login` (auto-detects browser)

**Q: `database is locked`**

Close the browser Cookie database lock — close browser, then retry `rdt login`.

**Q: `Session expired`**

Your cookies have expired. Run `rdt logout && rdt login` to refresh.

**Q: `Rate limited`**

Wait and retry; the built-in exponential backoff handles this automatically.

**Q: Requests are slow**

The built-in Gaussian jitter delay (~1s between requests) is intentional to mimic natural browsing and avoid triggering Reddit's rate limiting.

---

## 推荐项目

- [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) — 小红书搜索、阅读和发帖 CLI
- [twitter-cli](https://github.com/jackwener/twitter-cli) — Twitter/X 时间线、书签和发推 CLI
- [bilibili-cli](https://github.com/jackwener/bilibili-cli) — Bilibili 视频、用户、搜索与动态 CLI
- [discord-cli](https://github.com/jackwener/discord-cli) — Discord 本地优先同步、检索与导出 CLI
- [tg-cli](https://github.com/jackwener/tg-cli) — Telegram 本地优先同步、检索与导出 CLI

## 功能特性

- 🔐 **认证** — 自动提取浏览器 Cookie，状态检查，用户信息
- 🏠 **浏览** — 首页 Feed、Popular、/r/all、纯订阅 Feed（`--subs-only`）
- 📋 **子版块** — 浏览任意 subreddit（排序/时间过滤），查看子版块信息
- 📰 **帖子** — 阅读帖子和评论树
- 💬 **评论展开** — `--expand-more` 可展开额外评论
- 🔢 **短索引导航** — `rdt show 3` 阅读、`rdt open 3` 浏览器打开
- 🔍 **搜索** — 全文搜索，支持子版块、排序、时间过滤
- 📤 **导出** — 搜索结果导出为 CSV 或 JSON
- 👤 **用户** — 查看用户资料、发帖历史、评论历史、收藏和点赞记录
- ⬆️ **互动** — 点赞/踩、收藏、订阅、评论
- 🛡️ **反风控** — Chrome 133 指纹一致性、高斯抖动延迟、指数退避重试
- 📊 **结构化输出** — `--yaml` / `--json`，非 TTY 默认输出 YAML
- 📦 **稳定 envelope** — 参见 [SCHEMA.md](./SCHEMA.md)

## 安装

```bash
# 推荐：uv tool（快速、隔离环境）
uv tool install rdt-cli

# 或者：pipx
pipx install rdt-cli
```

升级到最新版本：

```bash
uv tool upgrade rdt-cli
# 或：pipx upgrade rdt-cli
```

从源码安装：

```bash
git clone git@github.com:jackwener/rdt-cli.git
cd rdt-cli
uv sync
```

## 使用示例

```bash
# 认证
rdt login                             # 从浏览器提取 Cookie
rdt status                            # 检查登录状态
rdt whoami                            # 查看用户资料
rdt logout                            # 清除缓存的 Cookie

# 浏览
rdt feed                              # 首页 Feed（需要登录）
rdt feed --subs-only                  # 纯订阅 Feed（无算法推荐）
rdt feed --subs-only -n 5 --max-subs 10  # 限制每个 sub 帖子数和最大 sub 数
rdt popular                           # 热门帖子
rdt all                               # /r/all
rdt sub python                        # 浏览子版块
rdt sub programming -s top -t week    # 排序 + 时间过滤
rdt sub-info python                   # 子版块信息
rdt rules python                      # 子版块规则
rdt user spez                         # 用户资料
rdt user-posts spez                   # 用户发帖
rdt user-comments spez                # 用户评论
rdt saved                             # 你的收藏
rdt upvoted                           # 你的点赞

# 阅读
rdt read 1abc123                      # 按 ID 阅读帖子
rdt read 1abc123 --expand-more        # 展开更多评论
rdt show 3                            # 阅读最近一次列表里的第 3 条
rdt show 3 --expand-more              # 展开缓存帖子里的更多评论
rdt open 3                            # 在浏览器打开

# 搜索
rdt search "python async"             # 全局搜索
rdt search "rust vs go" -r programming  # 在子版块内搜索
rdt export "python tips" -n 100 -o tips.csv  # 导出

# 互动（需要登录）
rdt upvote 3                          # 点赞
rdt save 3                            # 收藏
rdt subscribe python                  # 订阅
rdt comment 3 "Great post!"           # 评论
rdt delete 1abc123 -y                 # 删除自己的帖子/评论
```

## 认证策略

rdt-cli 支持浏览器 Cookie 提取来认证 Reddit：

1. **已保存 Cookie** — 从 `~/.config/rdt-cli/credential.json` 加载
2. **浏览器 Cookie** — 自动检测已安装浏览器并提取（支持 Chrome、Firefox、Edge、Brave）

Cookie 保存后有效期 **7 天**，超时后自动尝试从浏览器刷新。

## 常见问题

- `No Reddit cookies found` — 请先在任意浏览器打开 https://www.reddit.com/ 并登录，然后执行 `rdt login`
- `database is locked` — 关闭浏览器后重试
- `Session expired` — Cookie 过期，执行 `rdt logout && rdt login` 刷新
- `Rate limited` — 等待重试，内置指数退避会自动处理
- 请求较慢是正常的 — 内置高斯随机延迟（~1s）是为了模拟人类浏览行为，避免触发限速

## 作为 AI Agent Skill 使用

rdt-cli 自带 [`SKILL.md`](./SKILL.md)，让 AI Agent 能自动学习并使用本工具。

### [Skills CLI](https://github.com/vercel-labs/skills)（推荐）

```bash
npx skills add jackwener/rdt-cli
```

| 参数 | 说明 |
| --- | --- |
| `-g` | 全局安装（用户级别，跨项目共享） |
| `-a claude-code` | 指定目标 Agent |
| `-y` | 非交互模式 |

### 手动安装

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/rdt-cli.git .agents/skills/rdt-cli
```

### ~~OpenClaw / ClawHub~~（已过时）

> ⚠️ ClawHub 安装方式已过时，不再支持。请使用上方的 Skills CLI 或手动安装。

## License

Apache-2.0
