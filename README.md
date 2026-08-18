# AMD Gaming Promotions RSS + Telegram

This project polls the AMD Gaming Promotions JSON endpoint, creates a custom RSS feed, and optionally sends Telegram alerts for:

- New promotions
- Key restocks (0 -> >0 keys)

The AMD Gaming site is a Discourse-based site, but its promotions page exposes structured JSON data. The implementation uses `curl-cffi` to make the request.

## 1. Create a GitHub repository

Create a new repository, for example:

`amd-gaming-promotions`

Upload all files from this project.

## 2. Add GitHub Pages

In GitHub:

Settings -> Pages -> Build and deployment -> Source: GitHub Actions

After the workflow runs, the RSS URL will be:

`https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/amd_gaming_promotions.xml`

## 3. Add Telegram secrets

Repository -> Settings -> Secrets and variables -> Actions

Create:

- `TELEGRAM_BOT_TOKEN` = your BotFather token
- `TELEGRAM_CHAT_ID` = your group/channel chat ID

Do not put the bot token directly in Python.

## 4. First run

Run the workflow manually once.

The first run creates a baseline and does NOT send all existing promotions to Telegram.

After that:

- A newly appearing promotion -> Telegram alert
- Keys changing from 0 to a positive number -> Telegram restock alert

## 5. Local testing

Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
$env:TELEGRAM_CHAT_ID="YOUR_CHAT_ID"

python -m amd_monitor.monitor
```

The generated RSS file is:

`pages/amd_gaming_promotions.xml`

## Notes

GitHub Actions scheduled jobs are not a real-time guarantee. A 5-minute schedule is the minimum practical GitHub Actions cron interval, and GitHub can delay scheduled workflows.

The Telegram alert is based on the AMD structured promotion data, not HTML link scraping. This avoids the failure mode where the page has no `/promotions/` links in the HTML.
