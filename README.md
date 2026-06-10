# Crowdfame Event Agent

Automated pipeline that scrapes US Facebook events, runs AI-powered background checks, and posts legitimate events to the Crowdfame API daily.

## Architecture

```
Apify (Facebook Events Scraper)
  │  Scrapes 36 major US cities
  │  Returns raw event JSON
  ▼
Claude AI Validator (validator.py)
  │  Background checks every event
  │  Rejects spam, scams, past events, vague locations
  │  Normalizes approved events to Crowdfame schema
  ▼
Crowdfame API Poster (poster.py)
  │  POSTs approved events with retry logic
  │  Handles rate limits and duplicates
  ▼
GitHub Actions (runs daily at 6 AM UTC)
  │  Saves logs as artifacts
  └  Opens GitHub Issue on failure
```

---

## Setup (one-time, ~20 minutes)

### Step 1 — Get your API keys

| Service | Where to get it | Cost |
|---|---|---|
| **Apify** | [console.apify.com](https://console.apify.com/account/integrations) → Integrations | Free tier works; ~$5–15/mo for production |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/settings/api-keys) → API Keys | Pay-per-use (~$0.01–0.05/run) |
| **Crowdfame** | Your Crowdfame developer dashboard | Your internal key |

### Step 2 — Set up Apify

1. Sign up at [apify.com](https://apify.com)
2. Go to **Actors** → search for `facebook-events-scraper`
3. Click **Try for free** to add it to your account
4. Copy your **API token** from [console.apify.com/account/integrations](https://console.apify.com/account/integrations)

### Step 3 — Set up this repo

```bash
# Clone or create a new GitHub repo, then:
git clone https://github.com/YOUR_ORG/crowdfame-agent
cd crowdfame-agent

# Install dependencies (for local testing)
pip install -r requirements.txt

# Copy and fill in your env vars
cp .env.example .env
# Edit .env with your real keys
```

### Step 4 — Add GitHub Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these four secrets:

| Secret Name | Value |
|---|---|
| `APIFY_TOKEN` | Your Apify API token |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `CROWDFAME_API_URL` | Your Crowdfame API base URL |
| `CROWDFAME_API_KEY` | Your Crowdfame API key |

### Step 5 — Enable GitHub Actions

1. Push the code to GitHub (make sure `.github/workflows/agent.yml` is included)
2. Go to **Actions** tab in your repo
3. You should see **"Crowdfame Event Agent"** listed
4. Click **Run workflow** to do a manual test run first

### Step 6 — Verify it works

After the first run:
- Go to **Actions** → click the run → download the **run-logs** artifact
- Open the JSON log and verify events were scraped, validated, and posted

---

## Schedule

The agent runs **daily at 6 AM UTC** (1 AM Central Time). To change this, edit the cron in `.github/workflows/agent.yml`:

```yaml
- cron: "0 6 * * *"    # daily at 6 AM UTC
- cron: "0 6 * * 1"    # weekly on Mondays
- cron: "0 6 */2 * *"  # every 2 days
```

---

## Manual run

```bash
cd src
APIFY_TOKEN=... ANTHROPIC_API_KEY=... CROWDFAME_API_URL=... CROWDFAME_API_KEY=... python main.py
```

---

## What the AI checks for

The Claude validator rejects events that are:
- Spam, MLM, or "get rich quick" schemes
- Promoting illegal activity
- Adult/explicit content
- In the past
- Outside the US or with vague locations
- Gibberish or auto-generated text
- Duplicate events
- Missing meaningful descriptions
- From bot/fake organizer accounts

Approved events are normalized into a clean schema before posting to Crowdfame.

---

## Logs

Every run saves a JSON log to `src/logs/run_YYYYMMDD_HHMMSS.json` containing:
- Total events scraped
- How many were approved/rejected
- Rejection reason breakdown
- How many were created in Crowdfame

GitHub Actions also stores these as downloadable artifacts for 30 days.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `APIFY_TOKEN` error | Check the secret is set correctly in GitHub |
| Apify run times out | Reduce `US_LOCATIONS` list in `scraper.py` |
| All events rejected | Check `validator.py` system prompt; may need tuning |
| 401 from Crowdfame API | Verify `CROWDFAME_API_KEY` and `CROWDFAME_API_URL` |
| GitHub Action not running | Check the workflow file is in `.github/workflows/` |
