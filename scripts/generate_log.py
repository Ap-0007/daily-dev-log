#!/usr/bin/env python3
"""
Daily Dev Log Generator
-----------------------
Generates a rich daily markdown log containing:
  - A coding challenge
  - A dev quote
  - GitHub stats snapshot
  - A journal prompt

Usage: python3 scripts/generate_log.py
Environment variables:
  GITHUB_TOKEN  - GitHub token for API calls (auto-set in Actions)
  GITHUB_ACTOR  - GitHub username (auto-set in Actions)
"""

import json
import os
import random
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT   = SCRIPT_DIR.parent
LOGS_DIR    = REPO_ROOT / "logs"
README_PATH = REPO_ROOT / "README.md"

CHALLENGES_FILE = SCRIPT_DIR / "challenges.json"
QUOTES_FILE     = SCRIPT_DIR / "quotes.json"
PROMPTS_FILE    = SCRIPT_DIR / "prompts.json"

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_json(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def github_api(endpoint: str, token: str) -> dict | list | None:
    url = f"https://api.github.com{endpoint}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "daily-dev-log-bot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [GitHub API] HTTP {e.code} for {endpoint}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [GitHub API] Error for {endpoint}: {e}", file=sys.stderr)
        return None


def difficulty_badge(level: str) -> str:
    colors = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    return colors.get(level, "⚪")


def count_existing_logs() -> int:
    """Count how many log files exist already (for streak display)."""
    return len(list(LOGS_DIR.rglob("*.md")))


# ─── GitHub Stats ─────────────────────────────────────────────────────────────
def fetch_github_stats(username: str, token: str) -> dict:
    print(f"  Fetching GitHub stats for @{username} ...")
    stats = {
        "username": username,
        "followers": "N/A",
        "public_repos": "N/A",
        "total_stars": "N/A",
        "top_repo": "N/A",
        "top_repo_stars": "N/A",
        "top_repo_url": "#",
    }

    user_data = github_api(f"/users/{username}", token)
    if user_data:
        stats["followers"] = user_data.get("followers", "N/A")
        stats["public_repos"] = user_data.get("public_repos", "N/A")

    # Fetch all repos to compute total stars
    page, all_repos = 1, []
    while True:
        repos = github_api(f"/users/{username}/repos?per_page=100&page={page}", token)
        if not repos:
            break
        all_repos.extend(repos)
        if len(repos) < 100:
            break
        page += 1

    if all_repos:
        total_stars = sum(r.get("stargazers_count", 0) for r in all_repos)
        stats["total_stars"] = total_stars

        top = max(all_repos, key=lambda r: r.get("stargazers_count", 0))
        stats["top_repo"] = top.get("name", "N/A")
        stats["top_repo_stars"] = top.get("stargazers_count", 0)
        stats["top_repo_url"] = top.get("html_url", "#")

    return stats


# ─── Content Builders ─────────────────────────────────────────────────────────
def build_challenge_section(challenge: dict) -> str:
    badge = difficulty_badge(challenge["difficulty"])
    return f"""## 🧩 Today's Coding Challenge

| | |
|---|---|
| **Problem** | {challenge['title']} |
| **Category** | `{challenge['category']}` |
| **Difficulty** | {badge} {challenge['difficulty']} |

### Problem Statement
{challenge['description']}

### Example
```
{challenge['example']}
```

### Starter Code
```python
{challenge['starter']}
```

> 💡 Try solving this before looking up the answer. Write your solution in a local file or a Gist!
"""


def build_quote_section(quote_obj: dict) -> str:
    return f"""## 💬 Dev Quote of the Day

> *"{quote_obj['quote']}"*
>
> — **{quote_obj['author']}**
"""


def build_stats_section(stats: dict) -> str:
    return f"""## 📊 GitHub Stats Snapshot

| Metric | Value |
|--------|-------|
| 👤 Username | [@{stats['username']}](https://github.com/{stats['username']}) |
| 👥 Followers | {stats['followers']} |
| 📁 Public Repos | {stats['public_repos']} |
| ⭐ Total Stars | {stats['total_stars']} |
| 🏆 Top Repo | [{stats['top_repo']}]({stats['top_repo_url']}) ({stats['top_repo_stars']} ⭐) |
| 📅 Snapshot Date | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |
"""


def build_journal_section(prompt: str) -> str:
    return f"""## 📝 Daily Journal Prompt

**{prompt}**

*Take 5–10 minutes to reflect and write your answer below, or in your private notes.*

---

<!-- Write your journal entry here -->
"""


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    today = datetime.now(timezone.utc)
    date_str  = today.strftime("%Y-%m-%d")
    year_str  = today.strftime("%Y")
    month_str = today.strftime("%m")

    print(f"[daily-dev-log] Generating log for {date_str} ...")

    # Load data files
    challenges = load_json(CHALLENGES_FILE)
    quotes     = load_json(QUOTES_FILE)
    prompts    = load_json(PROMPTS_FILE)

    # Use date as seed so the same day always produces the same content
    # (useful if workflow retries)
    seed = int(today.strftime("%Y%m%d"))
    rng  = random.Random(seed)

    challenge = rng.choice(challenges)
    quote_obj = rng.choice(quotes)
    prompt    = rng.choice(prompts)

    # GitHub context
    token    = os.environ.get("GITHUB_TOKEN", "")
    username = os.environ.get("GITHUB_ACTOR", "")

    if not username:
        # Fallback: try to get from git config
        import subprocess
        try:
            result = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True
            )
            username = result.stdout.strip() or "developer"
        except Exception:
            username = "developer"

    stats = fetch_github_stats(username, token) if token else {
        "username": username,
        "followers": "N/A",
        "public_repos": "N/A",
        "total_stars": "N/A",
        "top_repo": "N/A",
        "top_repo_stars": "N/A",
        "top_repo_url": "#",
    }

    # Build the log
    existing_count = count_existing_logs()
    day_number = existing_count + 1

    header = f"""# 📅 Daily Dev Log — {date_str}

**Day #{day_number} of the streak** 🔥

---

"""
    content = (
        header
        + build_challenge_section(challenge)
        + "\n"
        + build_quote_section(quote_obj)
        + "\n"
        + build_stats_section(stats)
        + "\n"
        + build_journal_section(prompt)
    )

    # Write log file
    log_path = LOGS_DIR / year_str / month_str / f"{date_str}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(content, encoding="utf-8")
    print(f"  Written: {log_path.relative_to(REPO_ROOT)}")

    # Update README
    relative_log = f"logs/{year_str}/{month_str}/{date_str}.md"
    update_readme(day_number, date_str, challenge, quote_obj, relative_log, stats)
    print("  README.md updated.")
    print("[daily-dev-log] Done! ✅")


def update_readme(day_number: int, date_str: str, challenge: dict, quote_obj: dict, log_path: str, stats: dict):
    badge_url = (
        "https://img.shields.io/badge/streak-{n}%20days-orange?style=flat-square&logo=github"
        .format(n=day_number)
    )
    readme = f"""# 📅 Daily Dev Log

[![Streak](https://img.shields.io/badge/streak-{day_number}%20days-orange?style=flat-square&logo=github)](./logs)
[![Auto-Updated](https://img.shields.io/badge/auto--updated-daily-blue?style=flat-square&logo=githubactions)](./github/workflows/daily-log.yml)

> Automatically generated every day via GitHub Actions. Each entry contains a coding challenge, a developer quote, a live GitHub stats snapshot, and a reflective journal prompt.

---

## 📌 Latest Entry — {date_str}

**→ [View Today's Log](./{log_path})**

| Section | Today |
|---------|-------|
| 🧩 Challenge | **{challenge['title']}** (`{challenge['category']}` · {challenge['difficulty']}) |
| 💬 Quote | *"{quote_obj['quote'][:80]}..."* — {quote_obj['author']} |
| 📊 Stars | ⭐ {stats['total_stars']} across {stats['public_repos']} repos |
| 👥 Followers | {stats['followers']} |

---

## 🗂 Browse All Logs

Logs are organized by year and month under the [`logs/`](./logs) directory.

```
logs/
└── YYYY/
    └── MM/
        └── YYYY-MM-DD.md
```

---

## ⚙️ How It Works

A [GitHub Actions workflow](./.github/workflows/daily-log.yml) runs every day at **midnight UTC** and:

1. Picks a random coding challenge from a curated bank of 30 problems
2. Picks a random developer quote from a list of 50+
3. Fetches live GitHub stats via the REST API
4. Picks a daily journal reflection prompt
5. Writes a new markdown file to `logs/YYYY/MM/YYYY-MM-DD.md`
6. Updates this README with the latest summary

---

*Last updated: {date_str} · Day #{day_number}*
"""
    README_PATH.write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
