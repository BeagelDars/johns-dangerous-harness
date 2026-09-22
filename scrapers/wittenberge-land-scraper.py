#!/usr/bin/env python3
"""
Autonomous Cloud Scraper: wittenberge-land-scraper
Target: https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30+grundstueck_typ_s:grundstueck+preis:0,50000+groesse:1000,5000
Criteria: Land / Grundstück / Baugrundstück in Wittenberge 19322 and surrounding 30km radius (size: 1,000 to 5,000 sqm)
Scheduled via GitHub Actions (Cron: 0 */4 * * *)
"""
import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime

TARGET_URL = "https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30+grundstueck_typ_s:grundstueck+preis:0,50000+groesse:1000,5000"
CRITERIA = "Land / Grundstück / Baugrundstück in Wittenberge 19322 and surrounding 30km radius (size: 1,000 to 5,000 sqm)"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "wittenberge-land-scraper_results.json")

def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[Telegram] Skipping notification: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "JohnsHarnessScraper/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[Telegram] Notification sent successfully!")
            return True
    except Exception as e:
        print(f"[Telegram] Failed to send notification: {e}")
        return False

def run_scrape():
    print(f"[Scraper] Starting scrape for {TARGET_URL} at {datetime.now().isoformat()}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    req = urllib.request.Request(TARGET_URL, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Error] Failed to fetch {TARGET_URL}: {e}")
        sys.exit(1)

    print(f"[Scraper] Successfully downloaded {len(html)} bytes from {TARGET_URL}.")

    # Simple robust regex extraction for links and headings
    items = []
    matches = re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE)
    for href, text in matches:
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if clean_text and len(clean_text) > 8 and not href.startswith('#') and not href.startswith('javascript:'):
            full_url = urllib.parse.urljoin(TARGET_URL, href)
            if CRITERIA:
                keywords = [k.strip().lower() for k in CRITERIA.split() if len(k.strip()) > 2]
                if any(kw in clean_text.lower() for kw in keywords):
                    items.append({"title": clean_text, "url": full_url, "scraped_at": datetime.now().isoformat()})
            else:
                items.append({"title": clean_text, "url": full_url, "scraped_at": datetime.now().isoformat()})

    # Deduplicate by url
    unique_items = []
    seen = set()
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique_items.append(item)

    print(f"[Scraper] Found {len(unique_items)} matching items.")

    # Save to data directory
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_items, f, indent=2, ensure_ascii=False)
    print(f"[Scraper] Saved results to {DATA_FILE}.")

    # Telegram notification summary
    if unique_items:
        top_items = unique_items[:5]
        msg_lines = [
            f"🚀 *Scraper Alert: wittenberge-land-scraper*",
            f"📍 *Source:* {TARGET_URL}",
            f"🎯 *Matched:* {len(unique_items)} items",
            ""
        ]
        for idx, itm in enumerate(top_items, 1):
            msg_lines.append(f"{idx}. [{itm['title']}]({itm['url']})")
        
        if len(unique_items) > 5:
            msg_lines.append(f"\\n_...and {len(unique_items) - 5} more items._")

        send_telegram("\\n".join(msg_lines))
    else:
        print("[Scraper] No items matched criteria on this run.")

if __name__ == "__main__":
    run_scrape()
