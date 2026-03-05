"""
github_watcher.py — polls GitHub for new events on Gabe's repos.
Tracks last-seen commit SHA per repo so we only fire on genuinely new activity.
"""

import os
import json
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE_FILE = Path("state/github_state.json")
GITHUB_API = "https://api.github.com"


def _load_state() -> dict:
    STATE_FILE.parent.mkdir(exist_ok=True)
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_new_events(username: str, repos: list[str]) -> list[dict]:
    """
    Returns list of new events since last check.
    Each event dict: {repo, type, title, body, sha, url, timestamp}
    """
    state = _load_state()
    new_events = []

    for repo in repos:
        try:
            # --- New commits on default branch ---
            commits_url = f"{GITHUB_API}/repos/{username}/{repo}/commits"
            r = requests.get(commits_url, headers=_headers(), timeout=10)
            if r.status_code == 404:
                logger.warning(f"Repo not found: {repo}")
                continue
            r.raise_for_status()
            commits = r.json()

            last_sha = state.get(repo, {}).get("last_sha")
            is_first_run = last_sha is None

            new_commits = []
            for c in commits:
                if c["sha"] == last_sha:
                    break
                new_commits.append(c)

            if is_first_run:
                # Seed state silently on first run — don't post about old commits
                if commits:
                    state.setdefault(repo, {})["last_sha"] = commits[0]["sha"]
                    logger.info(f"[{repo}] First run — seeded state at {commits[0]['sha'][:7]}, no post")
                continue

            if new_commits:
                # Update state with latest SHA
                state.setdefault(repo, {})["last_sha"] = commits[0]["sha"]

                # Roll up multiple commits into one event
                if len(new_commits) == 1:
                    c = new_commits[0]
                    title = c["commit"]["message"].split("\n")[0]
                    body = "\n".join(
                        [x["commit"]["message"].split("\n")[0] for x in new_commits]
                    )
                else:
                    title = f"{len(new_commits)} new commits"
                    body = "\n".join(
                        [f"• {x['commit']['message'].split(chr(10))[0]}" for x in new_commits[:5]]
                    )

                new_events.append({
                    "repo": repo,
                    "type": "push",
                    "title": title,
                    "body": body,
                    "sha": commits[0]["sha"][:7],
                    "url": f"https://github.com/{username}/{repo}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "commit_count": len(new_commits),
                })

            # --- Merged PRs ---
            if is_first_run:
                continue  # already seeded above, skip PR check on first run

            prs_url = f"{GITHUB_API}/repos/{username}/{repo}/pulls?state=closed&per_page=5"
            pr_r = requests.get(prs_url, headers=_headers(), timeout=10)
            if pr_r.ok:
                prs = pr_r.json()
                last_pr_id = state.get(repo, {}).get("last_pr_id")
                for pr in prs:
                    if not pr.get("merged_at"):
                        continue
                    if str(pr["number"]) == str(last_pr_id):
                        break
                    state.setdefault(repo, {})["last_pr_id"] = pr["number"]
                    new_events.append({
                        "repo": repo,
                        "type": "pull_request",
                        "title": f"PR #{pr['number']} merged: {pr['title']}",
                        "body": pr.get("body") or "",
                        "sha": None,
                        "url": pr["html_url"],
                        "timestamp": pr["merged_at"],
                        "commit_count": 0,
                    })
                    break  # one PR event per cycle is enough

        except Exception as e:
            logger.error(f"Error checking {repo}: {e}")

    _save_state(state)
    return new_events


def get_repo_summary(username: str, repos: list[str]) -> dict:
    """Returns a summary of all repos for weekly newsletter context."""
    summary = {}
    for repo in repos:
        try:
            r = requests.get(
                f"{GITHUB_API}/repos/{username}/{repo}",
                headers=_headers(), timeout=10
            )
            if r.ok:
                data = r.json()
                summary[repo] = {
                    "description": data.get("description", ""),
                    "stars": data.get("stargazers_count", 0),
                    "language": data.get("language", "Python"),
                    "updated_at": data.get("updated_at", ""),
                }
        except Exception as e:
            logger.error(f"Error fetching {repo} summary: {e}")
    return summary
