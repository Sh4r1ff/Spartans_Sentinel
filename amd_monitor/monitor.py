import html
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from curl_cffi import requests

AMD_URL = "https://www.amdgaming.com/promotions"
PAGES_DIR = Path("docs")
DATA_DIR = PAGES_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
RSS_FILE = PAGES_DIR / "amd_gaming_promotions.xml"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/151.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.7",
    "Referer": AMD_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_promotions():
    r = requests.get(
        AMD_URL,
        headers=HEADERS,
        impersonate="chrome",
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise RuntimeError(
            f"Unexpected AMD response shape. Top-level keys: {list(data) if isinstance(data, dict) else type(data)}"
        )
    return data["items"]


def load_state():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "updated_at": datetime.now(UTC).isoformat(),
        "promotions": {
            str(x.get("id")): {
                "title": x.get("title", ""),
                "keys_available": int(x.get("keysAvailable") or 0),
                "status": x.get("status", ""),
                "slug": x.get("slug", ""),
            }
            for x in items
            if x.get("id") is not None
        },
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def promotion_url(item):
    slug = item.get("slug", "")
    return f"https://www.amdgaming.com/promotions/{slug}" if slug else AMD_URL


def telegram_send_photo(item, restock=False):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets not configured; skipping Telegram notification.")
        return

    title = item.get("title", "AMD Gaming Promotion")
    platform = item.get("platform") or "Unknown platform"
    keys = int(item.get("keysAvailable") or 0)
    url = promotion_url(item)
    image = item.get("thumbnailImageUrl")

    label = "🔄 KEY RESTOCK" if restock else "🎁 NEW AMD PROMOTION"
    caption = (
        f"{label} | {'✅ Available' if keys > 0 else '❌ Empty'}"
        f" ({keys} Keys)\n\n"
        f"🎮 {platform} | {title}\n\n"
        f"🔑 Keys available: {keys}\n"
        f"🔗 Claim: {url}\n\n"
        f"Source: AMD Gaming Promotions"
    )

    api = f"https://api.telegram.org/bot{BOT_TOKEN}/"
    if image:
        resp = requests.post(
            api + "sendPhoto",
            data={"chat_id": CHAT_ID, "photo": image, "caption": caption},
            timeout=30,
        )
    else:
        resp = requests.post(
            api + "sendMessage",
            data={"chat_id": CHAT_ID, "text": caption},
            timeout=30,
        )

    resp.raise_for_status()
    print(f"Telegram notification sent: {title}")


def detect_changes(items, old_state):
    # First run only establishes a baseline. This prevents a flood of old giveaways.
    if old_state is None:
        return [], []

    old = old_state.get("promotions", {})
    new_items = []
    restocked = []

    for item in items:
        pid = str(item.get("id"))
        if pid not in old:
            new_items.append(item)
            continue

        previous_keys = int(old[pid].get("keys_available") or 0)
        current_keys = int(item.get("keysAvailable") or 0)

        # 0 -> positive is the useful "keys dropped again" event.
        if previous_keys <= 0 and current_keys > 0:
            restocked.append(item)

    return new_items, restocked


def build_rss(items):
    now = datetime.now(UTC)
    entries = []

    for item in items:
        status = item.get("status", "")
        if item.get("deleted") or status.lower() in {"deleted"}:
            continue

        title = item.get("title") or "AMD Gaming Promotion"
        platform = item.get("platform") or "Unknown"
        developer = item.get("developer") or "Unknown"
        keys = int(item.get("keysAvailable") or 0)
        slug = item.get("slug") or str(item.get("id"))
        link = promotion_url(item)
        image = item.get("thumbnailImageUrl") or ""
        created = int(item.get("createdAt") or 0)
        pub = datetime.fromtimestamp(created, tz=UTC) if created else now

        content = item.get("content") or ""
        # Keep the feed valid XML while allowing the original HTML inside CDATA.
        content = content.replace("]]>", "]]]]><![CDATA[>")
        image_html = (
            f'<p><img src="{escape(image)}" alt="{escape(title)}" '
            f'style="max-width:100%;height:auto;"></p>' if image else ""
        )
        meta = (
            f"<p><strong>Platform:</strong> {escape(platform)}<br>"
            f"<strong>Developer:</strong> {escape(developer)}<br>"
            f"<strong>Keys available:</strong> {keys}</p>"
        )
        links = (
            f'<p><a href="{escape(link)}">Claim / Open Giveaway</a> · '
            f'<a href="{AMD_URL}">All AMD Promotions</a></p>'
        )
        description = f"<![CDATA[{image_html}{content}{meta}{links}]]>"

        entries.append(
            f"""    <item>
      <title>{escape(f"🎁 AMD Promotions | {title}")}</title>
      <link>{escape(link)}</link>
      <guid isPermaLink="false">amd-promotion-{escape(str(item.get("id")))}</guid>
      <pubDate>{pub.strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
      <description>{description}</description>
      <category>{escape(platform)}</category>
    </item>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AMD Gaming Promotions</title>
    <link>{AMD_URL}</link>
    <description>Free game giveaways and promotions from AMD Gaming</description>
    <lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
{chr(10).join(entries)}
  </channel>
</rss>
"""


def main():
    print("Fetching AMD Gaming promotions...")
    items = fetch_promotions()
    print(f"Found {len(items)} promotions.")

    old_state = load_state()
    new_items, restocked = detect_changes(items, old_state)

    if old_state is None:
        print("First run: baseline created; no Telegram notifications sent.")
    else:
        for item in new_items:
            telegram_send_photo(item, restock=False)
        for item in restocked:
            telegram_send_photo(item, restock=True)

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    RSS_FILE.write_text(build_rss(items), encoding="utf-8")
    save_state(items)

    print(f"RSS written to {RSS_FILE}")
    print(f"New promotions: {len(new_items)}")
    print(f"Restocks: {len(restocked)}")


if __name__ == "__main__":
    main()
