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

STATE_DIR = Path(os.getenv("STATE_DIR", "state"))
STATE_FILE = STATE_DIR / "github_state.json"
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
    """Returns list of new events since last check.

    Each event dict: {repo, type, title, body, sha, url, timestamp}

    Notes:
    - By default, first run *seeds state* and posts nothing (prevents spam).
    - If `POST_RECENT_MINUTES` is set (e.g. 60), first run will post events that
      occurred within that recent window (useful on Railway restarts).
    """
    state = _load_state()
    new_events = []

    post_recent_minutes = int(os.getenv("POST_RECENT_MINUTES", "0") or "0")
    recent_cutoff = None
    if post_recent_minutes > 0:
        recent_cutoff = datetime.now(timezone.utc).timestamp() - (post_recent_minutes * 60)

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
                # Seed state on first run. Default behavior: don't post (prevents spam).
                # If POST_RECENT_MINUTES is set, post only events inside that window.
                if commits:
                    state.setdefault(repo, {})["last_sha"] = commits[0]["sha"]

                    if recent_cutoff is None:
                        logger.info(
                            f"[{repo}] First run — seeded state at {commits[0]['sha'][:7]}, no post"
                        )
                    else:
                        def _ts(iso: str) -> float:
                            # GitHub gives e.g. 2026-03-31T09:59:00Z
                            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()

                        recent_commits = [
                            c for c in commits
                            if _ts(c["commit"]["committer"]["date"]) >= recent_cutoff
                        ]
                        if recent_commits:
                            # Create a single rolled-up commit event
                            title = (
                                recent_commits[0]["commit"]["message"].split("\n")[0]
                                if len(recent_commits) == 1
                                else f"{len(recent_commits)} new commits"
                            )
                            body = "\n".join(
                                [f"• {x['commit']['message'].split(chr(10))[0]}" for x in recent_commits[:5]]
                            )
                            new_events.append({
                                "repo": repo,
                                "type": "push",
                                "title": title,
                                "body": body,
                                "sha": commits[0]["sha"][:7],
                                "url": f"https://github.com/{username}/{repo}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "commit_count": len(recent_commits),
                            })
                            logger.info(
                                f"[{repo}] First run — posting {len(recent_commits)} recent commit(s) from last {post_recent_minutes}m"
                            )
                        else:
                            logger.info(
                                f"[{repo}] First run — seeded state at {commits[0]['sha'][:7]}, no recent commits in last {post_recent_minutes}m"
                            )
                # don't return/continue here; allow PR merge detection below

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

            prs_url = f"{GITHUB_API}/repos/{username}/{repo}/pulls?state=closed&per_page=5"
            pr_r = requests.get(prs_url, headers=_headers(), timeout=10)
            if pr_r.ok:
                prs = pr_r.json()
                last_pr_id = state.get(repo, {}).get("last_pr_id")

                # Helper for time filtering (first run restarts on Railway)
                def _pr_is_recent(pr_obj: dict) -> bool:
                    if recent_cutoff is None:
                        return True
                    merged_at = pr_obj.get("merged_at")
                    if not merged_at:
                        return False
                    ts = datetime.fromisoformat(merged_at.replace("Z", "+00:00")).timestamp()
                    return ts >= recent_cutoff

                for pr in prs:
                    if not pr.get("merged_at"):
                        continue

                    # If we have history, stop when we reach last seen
                    if last_pr_id is not None and str(pr["number"]) == str(last_pr_id):
                        break

                    # On first run, only post PR merges inside the recent window (if configured)
                    if is_first_run and recent_cutoff is not None and not _pr_is_recent(pr):
                        continue

                    # Record latest merged PR so future cycles don't repost
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

                # If first run and we didn't post anything, still seed last_pr_id to avoid future spam.
                if is_first_run and last_pr_id is None:
                    for pr in prs:
                        if pr.get("merged_at"):
                            state.setdefault(repo, {})["last_pr_id"] = pr["number"]
                            break

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
