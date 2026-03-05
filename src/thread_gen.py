"""
thread_gen.py — uses Gemini to generate compelling Twitter/X threads
from GitHub events and daily content topics.
"""

import os
import json
import logging
import re
import google.generativeai as genai

logger = logging.getLogger(__name__)

TWEET_MAX = 270  # safe under 280

REPO_CONTEXT = {
    "strategic-archives-agent": (
        "a fully automated YouTube content machine — uses Gemini AI to write scripts, "
        "generate AI voiceovers, create cinematic images with FLUX, animate them with Higgsfield AI, "
        "mix in royalty-free music, and upload 12 videos/day across 4 YouTube channels. Zero human input."
    ),
    "digital-products-agent": (
        "an autonomous digital products business — Gemini writes prompt packs, guides and cheatsheets, "
        "generates PDF covers, and auto-publishes them to Gumroad, Selar and Payhip via Playwright. "
        "Fully hands-free passive income."
    ),
    "bet": (
        "a value betting automation bot — polls a private odds-drop API for pre-filtered +EV bets, "
        "applies sport-specific filters (soccer + basketball), and auto-places qualifying bets on "
        "PinUp Africa via Selenium. Mathematically profitable long-term."
    ),
}

DAILY_TOPICS = [
    "A hot take about AI automation replacing manual workflows",
    "A practical tip about building profitable Python bots",
    "Something most devs get wrong about passive income with code",
    "Why Nigerian/African devs are quietly winning the AI race",
    "A specific insight from building the YouTube automation agent",
    "How to monetize open source work without selling your soul",
    "The real ROI of building in public on Twitter/X",
    "An honest take on value betting bots and EV math",
    "Why digital products are the best business model for solo devs",
    "A lesson learned from deploying AI agents on Railway",
    "The compounding effect of shipping small things consistently",
    "Why most automation tutorials are garbage and what actually works",
]


def _gemini_generate(prompt: str) -> str:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()


def _split_thread(raw: str) -> list[str]:
    """
    Parse Gemini output into individual tweet strings.
    Handles numbered lists (1. / 1/) or tweet separators (---, ===).
    """
    # Try JSON array first
    try:
        tweets = json.loads(raw)
        if isinstance(tweets, list):
            return [t.strip() for t in tweets if t.strip()]
    except Exception:
        pass

    # Try numbered lines: "1." or "1/"
    lines = re.split(r'\n(?=\d+[./])', raw.strip())
    if len(lines) > 1:
        cleaned = []
        for line in lines:
            line = re.sub(r'^\d+[./]\s*', '', line).strip()
            if line:
                cleaned.append(line)
        if cleaned:
            return cleaned

    # Fallback: split on blank lines or "---"
    parts = re.split(r'\n\s*[-=]{3,}\s*\n|\n\n+', raw.strip())
    return [p.strip() for p in parts if p.strip()]


def _truncate_tweet(text: str) -> str:
    if len(text) <= TWEET_MAX:
        return text
    return text[:TWEET_MAX - 3] + "..."


def generate_thread_from_event(event: dict, niche: str, tone: str) -> list[str]:
    """Generate a Twitter thread from a GitHub push/PR event."""
    repo = event["repo"]
    ctx = REPO_CONTEXT.get(repo, f"a new project: {repo}")
    commit_summary = event.get("body", event["title"])

    prompt = f"""You are a dev influencer tweeting about your latest work. Your tone: {tone}.
Your niche: {niche}.

You just pushed code to your GitHub repo "{repo}".
What this project does: {ctx}

What you just built/changed:
{commit_summary}

Write a Twitter thread (5–7 tweets) that:
- Opens with a killer hook that stops the scroll (no "I just..." openers — be bold)
- Explains WHAT you built and WHY it matters for making money / automating life
- Includes 1–2 specific technical details (makes it credible, not vague)
- Ends with a CTA: follow for more, or link to the repo
- Uses line breaks for readability, occasional emojis (don't overdo it)
- Each tweet must be under 270 characters
- NO hashtag spam — max 2 hashtags total, only in the last tweet

Format your response as a JSON array of strings, one string per tweet.
"""

    raw = _gemini_generate(prompt)
    tweets = _split_thread(raw)
    return [_truncate_tweet(t) for t in tweets]


def generate_daily_tweets(niche: str, tone: str, count: int = 3) -> list[str]:
    """Generate standalone daily tweets on rotating topics."""
    import random
    topics = random.sample(DAILY_TOPICS, min(count, len(DAILY_TOPICS)))
    tweets = []

    for topic in topics:
        prompt = f"""You are a dev influencer. Tone: {tone}. Niche: {niche}.

Write a single punchy tweet about: "{topic}"

Rules:
- Under 270 characters
- Strong opinion or specific insight — not generic advice
- No hashtags (or max 1)
- No em-dashes — use plain language
- Sound like a real person, not a content bot

Reply with ONLY the tweet text. Nothing else.
"""
        try:
            tweet = _gemini_generate(prompt).strip().strip('"')
            tweets.append(_truncate_tweet(tweet))
        except Exception as e:
            logger.error(f"Failed to generate daily tweet: {e}")

    return tweets


def generate_newsletter_draft(
    repo_summary: dict,
    recent_events: list[dict],
    niche: str,
) -> str:
    """Generate a weekly newsletter draft (markdown)."""
    events_text = "\n".join(
        [f"- [{e['repo']}] {e['title']}" for e in recent_events[:10]]
    ) or "No new events this week."

    repos_text = "\n".join(
        [f"- {r}: {d['description'] or 'AI automation project'}" for r, d in repo_summary.items()]
    )

    prompt = f"""Write a weekly developer newsletter in markdown format.

Author: Gabriel (Gabe), a Nigerian AI automation developer.
Niche: {niche}

What was built this week:
{events_text}

Active projects:
{repos_text}

Newsletter sections:
1. **This week in the lab** — casual summary of what was shipped (2–3 paragraphs)
2. **One thing I learned** — a genuine insight or lesson from the week
3. **Worth your time** — 2–3 curated AI/dev resources (you can use knowledge up to your cutoff)
4. **What's next** — brief teaser of what's coming

Tone: honest, direct, builds trust. Not corporate. Not hype. Like a smart friend writing to 500 fellow builders.
"""

    return _gemini_generate(prompt)
