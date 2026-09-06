"""Constants for Reddit CLI — API endpoints, headers, and config paths."""

from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "rdt-cli"
CREDENTIAL_FILE = CONFIG_DIR / "credential.json"

# ── Base URL ────────────────────────────────────────────────────────
BASE_URL = "https://www.reddit.com"
OAUTH_URL = "https://oauth.reddit.com"

# ── Reddit JSON API ─────────────────────────────────────────────────
# Reddit's public JSON API: append .json to any URL
# Authenticated endpoints use oauth.reddit.com

# Listing endpoints (GET, append .json)
HOME_URL = "/.json"
POPULAR_URL = "/r/popular.json"
ALL_URL = "/r/all.json"
SUBREDDIT_URL = "/r/{subreddit}.json"              # hot by default
SUBREDDIT_NEW_URL = "/r/{subreddit}/new.json"
SUBREDDIT_TOP_URL = "/r/{subreddit}/top.json"
SUBREDDIT_RISING_URL = "/r/{subreddit}/rising.json"
SUBREDDIT_ABOUT_URL = "/r/{subreddit}/about.json"

# Post / comments
POST_COMMENTS_URL = "/r/{subreddit}/comments/{post_id}.json"
POST_COMMENTS_SHORT_URL = "/comments/{post_id}.json"
MORECHILDREN_URL = "/api/morechildren.json"

# Search
SEARCH_URL = "/search.json"
SUBREDDIT_SEARCH_URL = "/r/{subreddit}/search.json"

# User
USER_ABOUT_URL = "/user/{username}/about.json"
USER_POSTS_URL = "/user/{username}/submitted.json"
USER_COMMENTS_URL = "/user/{username}/comments.json"
USER_SAVED_URL = "/user/{username}/saved.json"
USER_UPVOTED_URL = "/user/{username}/upvoted.json"

# Auth / identity (OAuth)
ME_URL = "/api/v1/me"

# Write actions (OAuth, POST)
VOTE_URL = "/api/vote"
SAVE_URL = "/api/save"
UNSAVE_URL = "/api/unsave"
SUBSCRIBE_URL = "/api/subscribe"
COMMENT_URL = "/api/comment"
SUBSCRIPTIONS_URL = "/subreddits/mine/subscriber.json"

# ── Request Headers (Chrome 133, macOS) ─────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="133", "Not(A:Brand";v="99", "Google Chrome";v="133"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Cookie keys required for authenticated sessions ─────────────────
REQUIRED_COOKIES = {"reddit_session"}

# Chromium first: Arch/Omarchy and many Linux defaults use it, not Chrome.
# browser_cookie3.chrome() only reads ~/.config/google-chrome and cannot
# decrypt Chromium's cookie DB, so chromium must be a first-class loader.
BROWSER_COOKIE_FNS = ("chromium", "chrome", "firefox", "edge", "brave")

# ── Sort options ────────────────────────────────────────────────────
SORT_OPTIONS = ["hot", "new", "top", "rising", "controversial", "best"]

# ── Time filter for top/controversial ───────────────────────────────
TIME_FILTERS = ["hour", "day", "week", "month", "year", "all"]

# ── Search sort options ─────────────────────────────────────────────
SEARCH_SORT_OPTIONS = ["relevance", "hot", "top", "new", "comments"]

# ── Default page size ───────────────────────────────────────────────
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
