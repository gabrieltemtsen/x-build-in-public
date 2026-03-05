# x-build-in-public

> Automated "build in public" engine for developers. Watches your GitHub repos, generates compelling Twitter/X threads with Gemini AI, and posts daily value tweets — fully hands-free.

---

## What It Does

1. **GitHub Watcher** — polls your repos every 30 minutes for new commits and merged PRs
2. **Thread Generator** — Gemini writes a 5–7 tweet thread explaining what you built and why it matters
3. **Daily Content Machine** — posts 3 standalone value tweets/day on rotating AI/dev topics
4. **Weekly Newsletter** — drafts a markdown newsletter from your week's activity (Beehiiv publishing optional)
5. **Telegram Alerts** — notifies you every time something is posted

---

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# fill in your credentials
```

### 3. Run (dry run first!)
```bash
python -m src.main
```

`DRY_RUN=true` (default) — logs everything without posting. Set to `false` when ready to go live.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `X_BEARER_TOKEN` | ✅ | X/Twitter Bearer Token |
| `X_CONSUMER_KEY` | ✅ | X/Twitter API Key |
| `X_CONSUMER_SECRET` | ✅ | X/Twitter API Key Secret |
| `X_ACCESS_TOKEN` | ✅ | X/Twitter Access Token |
| `X_ACCESS_TOKEN_SECRET` | ✅ | X/Twitter Access Token Secret |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `GITHUB_TOKEN` | Optional | Increases GitHub rate limit to 5000 req/hr |
| `TELEGRAM_BOT_TOKEN` | Optional | For post notifications |
| `TELEGRAM_CHAT_ID` | Optional | Your Telegram chat ID |
| `DRY_RUN` | Optional | `true` = log only, no real posts (default: `true`) |
| `BEEHIIV_API_KEY` | Optional | Enables auto-publishing newsletter to Beehiiv |

---

## Project Structure

```
x-build-in-public/
├── src/
│   ├── github_watcher.py   # polls GitHub API; tracks last-seen SHA per repo
│   ├── thread_gen.py       # Gemini prompts → Twitter thread / daily tweets / newsletter
│   ├── tweet_poster.py     # Tweepy wrapper; posts threads with reply chain
│   ├── scheduler.py        # APScheduler: watch interval + daily posting times
│   ├── notifier.py         # Telegram notifications
│   └── main.py             # entrypoint + orchestrator
├── config/
│   └── config.yaml         # repos to watch, posting schedule, tone/niche
├── state/                  # auto-created; tracks last-seen GitHub events
├── newsletter_drafts/      # auto-created; weekly markdown drafts saved here
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Posting Schedule

Configured in `config/config.yaml`:

```yaml
github:
  check_interval_minutes: 30   # poll GitHub every 30 min

content:
  daily_tweets: 3
  posting_times_wat:
    - "09:00"
    - "13:00"
    - "18:30"
```

Posting times have ±5 min jitter built in to look natural.

---

## Monetisation Path

| Milestone | Income |
|---|---|
| 500 followers | Affiliate link clicks ($200–500/mo) |
| 1K followers | Newsletter sponsorships ($200–500/edition) |
| 2K followers | Inbound consulting DMs ($1K–3K/mo) |
| 5K followers | GitHub sponsors + product sales ($2K–5K/mo) |

---

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway service → connect repo
3. Set all env vars in Railway dashboard
4. Set `DRY_RUN=false` when happy with output quality
