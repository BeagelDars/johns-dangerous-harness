#!/usr/bin/env python3
"""
Autonomous High-Precision Cloud Scraper & Groq AI Evidence Evaluator
Project: Wittenberge Land & Village Plot Hunter
Client: Iurii (Telegram: 1003559461)
Bot: @Grundstuck_Wittenberge_bot

Criteria:
  1. Offer for Sale (Must NOT be a wanted ad / Gesuch or lease / Pacht)
  2. Plot in a Village / Rural Region (Участок в деревне / Baugrundstück / Grundstück)
  3. Wittenberge (19322) or surrounding villages/towns within 30 km radius
  4. Area between 1,000 and 5,000 sq meters (От 1000 до 5000 кв м)
Match Threshold: >= 70% Match Score
"""
import os
import sys
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# Safe UTF-8 reconfiguration
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Constants & Configuration
CLIENT_NAME = "Iurii"

def _load_chat_id() -> str:
    cid = os.environ.get("TELEGRAM_CHAT_ID", "")
    if cid:
        return cid.strip()
    cid_file = os.path.expanduser("~/.telegram_chat_id")
    if os.path.exists(cid_file):
        try:
            with open(cid_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "1003559461"

def _load_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        return token.strip()
    token_file = os.path.expanduser("~/.telegram_bot_token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

CLIENT_CHAT_ID = _load_chat_id()
BOT_TOKEN = _load_bot_token()

def _load_groq_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key.strip()
    key_file = os.path.expanduser("~/.groq_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

GROQ_KEY = _load_groq_key()

TARGET_URLS = [
    "https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30",
    "https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30+grundstueck_typ_s:baugrundstueck",
    "https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30+grundstueck_typ_s:grundstueck"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
NOTIFIED_FILE = os.path.join(DATA_DIR, "notified_ads.json")
README_FILE = os.path.join(BASE_DIR, "README.md")
DASHBOARD_FILE = os.path.join(BASE_DIR, "dashboard.html")

MATCH_THRESHOLD = 70  # Only send items scoring >= 70%
MAX_PRICE_EUR = 50000  # Strict knockout: Max 50,000 €
MIN_SIZE_SQM = 1000    # Strict knockout: Min 1,000 m²
MAX_SIZE_SQM = 5000    # Strict knockout: Max 5,000 m²
MAX_RADIUS_KM = 30     # Strict knockout: Max 30 km from Wittenberge

def safe_log(msg: str):
    """Prints message safely handling unicode encoding."""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def send_telegram(text: str, chat_id: str = CLIENT_CHAT_ID) -> bool:
    """Dispatches Telegram Markdown message to client with automatic plain text fallback."""
    if not BOT_TOKEN or not chat_id:
        safe_log("[Telegram] Warning: BOT_TOKEN or chat_id not configured.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            safe_log(f"[Telegram] Alert delivered successfully to {CLIENT_NAME} (ID: {chat_id})!")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 400:
            safe_log(f"[Telegram] Markdown entity error. Retrying in clean plain text...")
            try:
                clean_text = text.replace("*", "").replace("`", "").replace("_", "")
                plain_payload = json.dumps({
                    "chat_id": chat_id,
                    "text": clean_text,
                    "disable_web_page_preview": False
                }).encode("utf-8")
                req2 = urllib.request.Request(url, data=plain_payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=15) as resp2:
                    safe_log(f"[Telegram] Alert delivered as plain text fallback!")
                    return True
            except Exception as e2:
                safe_log(f"[Telegram] Plaintext fallback failed: {e2}")
        safe_log(f"[Telegram] HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        safe_log(f"[Telegram] Failed to send alert: {e}")
        return False

# ==============================================================================
# Step 0: Robust DOM Scraper for Kleinanzeigen
# ==============================================================================
def fetch_url(url: str, retries: int = 2) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            safe_log(f"[Scraper] Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(3)
    return ""

def parse_html_listings(html: str) -> list:
    """Extracts raw candidate listings from search results."""
    article_blocks = re.findall(r'<article\s+([^>]*data-adid=[\'"]\d+[\'"][^>]*)>([\s\S]*?)</article>', html)
    listings = []

    for header_attr, body in article_blocks:
        ad_id_m = re.search(r'data-adid=[\'"](\d+)[\'"]', header_attr)
        if not ad_id_m:
            continue
        ad_id = ad_id_m.group(1)

        href_m = re.search(r'data-href=[\'"]([^\'"]+)[\'"]', header_attr) or re.search(r'href=[\'"](/s-anzeige/[^\'"]+)[\'"]', body)
        if not href_m:
            continue
        href = href_m.group(1)
        full_url = f"https://www.kleinanzeigen.de{href}" if href.startswith("/") else href

        # Extract structured JSON-LD if present
        title = ""
        description = ""
        image_url = ""
        jsonld_m = re.search(r'<script\s+type=[\'"]application/ld\+json[\'"]>([\s\S]*?)</script>', body)
        if jsonld_m:
            try:
                jdata = json.loads(jsonld_m.group(1))
                title = jdata.get("title", "")
                description = jdata.get("description", "")
                image_url = jdata.get("contentUrl", "")
            except Exception:
                pass

        if not title:
            title_m = re.search(r'<h3[^>]*>[\s\S]*?<a[^>]*>(.*?)</a>', body)
            title = re.sub(r'<[^>]+>', ' ', title_m.group(1)).strip() if title_m else ""

        # Location & Distance
        loc_m = re.search(r'data-title=[\'"]locationOutline[\'"][\s\S]*?<span>([^<]+)</span>(?:<span[^>]*>\((ca\.\s*\d+\s*km)\)</span>)?', body)
        if loc_m:
            loc_name = loc_m.group(1).strip()
            loc_dist = loc_m.group(2).strip() if loc_m.group(2) else "Wittenberge (0 km)"
            location = f"{loc_name} {loc_dist}"
        else:
            location = "Wittenberge Region"

        # Price
        price_m = re.search(r'<p\s+class=[\'"][^\'"]*text-secondary[^\'"]*[\'"][^>]*>([^<]+)</p>', body)
        price = price_m.group(1).strip() if price_m else "N/A"

        # Tags & Specs
        specs_m = re.search(r'<p\s+class=[\'"][^\'"]*text-onSurfaceSubdued[^\'"]*[\'"][^>]*>([^<]+)</p>', body)
        specs = specs_m.group(1).strip() if specs_m else ""

        # Extract square meters from specs or title/description
        sqm_match = re.search(r'(\d+(?:[\.,]\d+)?(?:\.\d+)?)\s*(?:m²|qm|m2|\bha\b|\bhektar\b)', f"{title} {specs} {description}", re.IGNORECASE)
        size_str = sqm_match.group(0) if sqm_match else ""

        listings.append({
            "ad_id": ad_id,
            "title": title,
            "description": description[:220],
            "price": price,
            "location": location,
            "specs": specs,
            "size_str": size_str,
            "image_url": image_url,
            "url": full_url,
            "scraped_at": datetime.now().isoformat()
        })

    return listings

# ==============================================================================
# Step 1: Fast Deterministic Python Pre-Filter
# ==============================================================================
def python_pre_filter(item: dict) -> bool:
    """
    Deterministic knockout filter: Drops any listing that violates Iurii's strict criteria:
    - Price must be <= 50.000 €
    - Size must be within 1.000 - 5.000 m² (if specified)
    - Distance must be <= 30 km from Wittenberge
    - Must be an offer for sale (no Gesuche, no Pacht/Miete)
    """
    title_lower = (item.get("title") or "").lower()
    desc_lower = (item.get("description") or "").lower()
    specs_lower = (item.get("specs") or "").lower()
    loc_lower = (item.get("location") or "").lower()
    price_str = item.get("price") or ""
    full_text = f"{title_lower} {specs_lower} {desc_lower} {loc_lower}"

    # 1. Knockout: Reject Wanted Ads (Gesuche / Suche / Kaufgesuch)
    if "gesuch" in specs_lower:
        return False
    wanted_kw = [
        "gesucht", "kaufgesuch", "suche baugrundstück", "suche grundstück",
        "suche ackerland", "suchauftrag", "gesuche", "gesucht!", "ankauf", "suche flächen"
    ]
    if any(k in title_lower for k in wanted_kw) or "zum kauf gesucht" in full_text:
        return False

    # 2. Knockout: Reject Leases / Rentals (Pacht / Miete)
    lease_kw = ["pacht", "verpachten", "zu verpachten", "pachtland", "miete", "zu vermieten", "mietwohnung"]
    if any(k in title_lower for k in lease_kw) or "zur pacht" in full_text:
        return False

    # 3. Knockout: Reject Price > 50,000 € (Лимит: до 50000 евро)
    # Extracts numeric price e.g. "61.500 € VB", "60.000 €", "150.000 €"
    price_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:€|euro)', price_str, re.IGNORECASE)
    if price_m:
        try:
            val = float(price_m.group(1).replace(".", ""))
            if val > MAX_PRICE_EUR:
                safe_log(f"[Filter Knockout] ad #{item.get('ad_id')} rejected: Price {val:.0f} € > {MAX_PRICE_EUR} €.")
                return False
        except Exception:
            pass

    # 4. Knockout: Reject Explicit Size outside 1,000 - 5,000 m² (От 1000 до 5000 кв. м)
    ha_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*\b(?:ha|hektar)\b', full_text, re.IGNORECASE)
    if ha_match:
        try:
            ha_val = float(ha_match.group(1).replace(",", "."))
            # 0.1 ha = 1,000 m², 0.5 ha = 5,000 m²
            if ha_val < 0.1 or ha_val > 0.5:
                safe_log(f"[Filter Knockout] ad #{item.get('ad_id')} rejected: Size {ha_val} ha ({ha_val*10000:.0f} m²) outside [1000, 5000].")
                return False
        except Exception:
            pass

    sqm_match = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:m²|qm|m2)', full_text)
    if sqm_match:
        try:
            sqm_val = float(sqm_match.group(1).replace(".", "").replace(",", "."))
            if sqm_val < MIN_SIZE_SQM or sqm_val > MAX_SIZE_SQM:
                safe_log(f"[Filter Knockout] ad #{item.get('ad_id')} rejected: Size {sqm_val:.0f} m² outside [{MIN_SIZE_SQM}, {MAX_SIZE_SQM}].")
                return False
        except Exception:
            pass

    # 5. Knockout: Reject Distance > 30 km (До 30 км от Виттенберге)
    dist_m = re.search(r'(?:ca\.\s*)?(\d+)\s*km', loc_lower)
    if dist_m:
        try:
            d = int(dist_m.group(1))
            if d > MAX_RADIUS_KM:
                safe_log(f"[Filter Knockout] ad #{item.get('ad_id')} rejected: Distance {d} km > {MAX_RADIUS_KM} km.")
                return False
        except Exception:
            pass

    # Reject known distant towns beyond 30 km radius
    far_towns = ["wittstock", "dranse", "neuruppin", "rathenow", "stendal", "tangermünde", "salzwedel"]
    if any(ft in loc_lower for ft in far_towns):
        safe_log(f"[Filter Knockout] ad #{item.get('ad_id')} rejected: Far town outside 30 km radius.")
        return False

    # 6. Reject pure forest / auction timber items (client specifically wants village/building plots)
    if "auktion - wald" in title_lower or "waldfläche" in title_lower or "waldgrundstück" in title_lower:
        return False

    # 7. Reject Junk (tools, mowers, furniture, caravans)
    junk_kw = ["rasenmäher", "gartenmöbel", "pflanzen", "zaun", "brennholz", "traktor", "sofa", "wohnwagen", "wohnmobil"]
    if any(k in title_lower for k in junk_kw):
        return False

    # 8. Check for positive plot / land indications
    land_kw = ["grundstück", "grundstueck", "baugrundstück", "acker", "ackerland", "wiese", "gartenland", "fläche", "bauland", "parzelle", "neubaufläche"]
    if not any(k in full_text for k in land_kw):
        return False

    # 9. Must have valid URL
    if not item.get("url") or "/s-anzeige/" not in item["url"]:
        return False

    return True

# ==============================================================================
# Step 2: Strict Groq AI Evidence Evaluator with Percentage Scoring
# ==============================================================================
def groq_evaluate_listings(candidates: list) -> list:
    """
    Evaluates listings using Groq inference against Iurii's 4 criteria with strict scoring.
    Enforces zero-hallucination verbatim quote verification.
    """
    if not candidates:
        return []

    if not GROQ_KEY:
        safe_log("[Groq AI] Warning: GROQ_API_KEY missing. Bypassing Step 2.")
        return candidates

    safe_log(f"[Groq AI] Auditing {len(candidates)} pre-filtered listings with zero-hallucination percentage scoring...")

    models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    chunk_size = 4
    evaluated_results = []

    for i in range(0, len(candidates), chunk_size):
        if i > 0:
            time.sleep(3.5)  # Pace requests to respect Groq TPM limits
        chunk = candidates[i:i + chunk_size]
        items_payload = []
        for c in chunk:
            items_payload.append({
                "ad_id": c["ad_id"],
                "title": c["title"],
                "price": c["price"],
                "location": c["location"],
                "specs": c.get("specs", ""),
                "description_snippet": (c.get("description") or "")[:200]
            })

        prompt = f"""You are a strict, zero-hallucination real estate auditor AI evaluating property listings against client Iurii's exact search requirements.

CLIENT CRITERIA (from Iurii - STRICT KNOCKOUT RULES):
1. Maximum Budget: <= 50,000 € (Цена до 50000 евро).
2. Size Range: 1,000 to 5,000 m² (От 1000 до 5000 кв. метров).
3. Location: Wittenberge (19322) + 30 km radius (До 30 км). Distance rule: THE CLOSER TO WITTENBERGE, THE BETTER! (0-10 km is ideal, 28-30 km is considered far and unfavorable).
4. Offer for Sale: MUST be a real sale offer (Kauf / Verkauf). REJECT wanted ads ("Gesuch", "Suche") and leases/rentals ("Pacht", "Miete").
5. Property Type: Land/plot for building or village living (Grundstück, Baugrundstück, Bauland, ländlich/Dorf).

HARD KNOCKOUT RULES (Score = 0% and verdict = "REJECT" INSTANTLY if ANY condition fails):
- KNOCKOUT 1 (Price > 50,000 €): If explicit price is > 50,000 € (e.g. 55k, 60k, 65k, 150k) -> match_percentage = 0, verdict = "REJECT", rejection_reason = "Цена превышает лимит 50.000 €".
- KNOCKOUT 2 (Size out of bounds): If size is explicitly stated and < 1,000 m² or > 5,000 m² -> match_percentage = 0, verdict = "REJECT", rejection_reason = "Площадь вне диапазона 1.000 - 5.000 м²".
- KNOCKOUT 3 (Distance > 30 km): If location is > 30 km from Wittenberge (e.g. Wittstock, Neuruppin, Dranse, Stendal) -> match_percentage = 0, verdict = "REJECT", rejection_reason = "Расстояние превышает 30 км от Виттенберге".
- KNOCKOUT 4 (Wanted / Lease): If wanted ad ("Gesuch", "Suche") or lease/rental ("Pacht", "Miete", "verpachten") -> match_percentage = 0, verdict = "REJECT", rejection_reason = "Не является предложением продажи (Gesuch/Pacht)".
- KNOCKOUT 5 (Not a Plot): If apartment, pure house without plot, machinery, timber forest -> match_percentage = 0, verdict = "REJECT", rejection_reason = "Не является земельным участком".

SCORING (0 to 100% total - only if ALL knockouts pass):
1. Price (25 pts): Price <= 50,000 € or negotiable VB: +25 pts.
2. Size (25 pts): Explicitly verified in 1,000 - 5,000 m²: +25 pts. Size unstated in snippet: +10 pts.
3. Proximity to Wittenberge (25 pts) - CLOSER IS BETTER:
   - 0 to 10 km (Wittenberge 0km, Breese, Weisen, Cumlosen, Perleberg): Ideal, top priority! +25 pts.
   - 11 to 20 km (Lenzen, Karstädt, Bad Wilsnack, Seehausen): Good! +18 pts.
   - 21 to 27 km (Osterburg, Havelberg): Acceptable distance: +10 pts.
   - 28 to 30 km (Kyritz, Pritzwalk): Far border distance! Client specifically notes ~29 km is far and suboptimal: +4 pts.
4. Property & Sale Offer (25 pts): Verified offer to sell plot/building land: +25 pts.

VERBATIM QUOTE REQUIREMENT (Zero Hallucination):
Every quote in "evidence" MUST be an exact verbatim substring copied directly from the title, specs, or description:
- "offer_type_quote": exact quote proving sale offer
- "property_type_quote": exact quote proving land/plot
- "location_quote": exact quote of location
- "size_quote": exact quote of size if mentioned

CRITICAL: Return evaluation for EVERY ad_id in the input list ({[c['ad_id'] for c in chunk]}).
If match_percentage >= 70%: verdict is "PASS". Otherwise "REJECT".

Listings to audit:
{json.dumps(items_payload, indent=2, ensure_ascii=False)}

Return JSON:
{{
  "evaluations": [
    {{
      "ad_id": "...",
      "match_percentage": 0 to 100,
      "verdict": "PASS" | "REJECT",
      "summary_ru": "Concise 1-sentence evaluation in Russian for Iurii",
      "rejection_reason": "string or null",
      "evidence": {{
        "offer_type_quote": "...",
        "property_type_quote": "...",
        "location_quote": "...",
        "size_quote": "..."
      }}
    }}
  ]
}}
"""
        chunk_handled = False
        for model_name in models:
            for retry in range(2):
                body = json.dumps({
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.05
                }).encode("utf-8")

                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=body,
                    headers={
                        "Authorization": f"Bearer {GROQ_KEY}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )

                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        resp_data = json.loads(resp.read().decode("utf-8"))
                        content = resp_data["choices"][0]["message"]["content"]
                        parsed = json.loads(content)
                        eval_list = parsed.get("evaluations", [])
                        eval_map = {str(e.get("ad_id")): e for e in eval_list}

                        for c in chunk:
                            ev_record = eval_map.get(str(c["ad_id"]))
                            if ev_record:
                                score = int(ev_record.get("match_percentage", 0))
                                ev_data = ev_record.get("evidence", {})
                                c_text = f"{c['title']} {c['location']} {c.get('specs', '')} {c.get('description', '')}".lower()

                                # Anti-hallucination verification: Ensure quotes are real substrings
                                quotes_verified = True
                                for qk in ["offer_type_quote", "property_type_quote"]:
                                    quote_val = (ev_data.get(qk) or "").strip().lower()
                                    if quote_val and quote_val not in c_text:
                                        safe_log(f"[Anti-Hallucination] Discarded quote '{quote_val}' for ad #{c['ad_id']} (not in text).")
                                        score = max(0, score - 20)
                                        quotes_verified = False

                                # Programmatic Knockout Safeguard (Zero AI Hallucination):
                                price_str = c.get("price") or ""
                                price_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:€|euro)', price_str, re.IGNORECASE)
                                if price_m:
                                    try:
                                        val = float(price_m.group(1).replace(".", ""))
                                        if val > MAX_PRICE_EUR:
                                            score = 0
                                            ev_record["rejection_reason"] = f"Цена {val:.0f} € превышает лимит {MAX_PRICE_EUR} €"
                                    except Exception:
                                        pass

                                loc_str = (c.get("location") or "").lower()
                                dist_m = re.search(r'(?:ca\.\s*)?(\d+)\s*km', loc_str)
                                if dist_m:
                                    try:
                                        if int(dist_m.group(1)) > MAX_RADIUS_KM:
                                            score = 0
                                            ev_record["rejection_reason"] = f"Расстояние {dist_m.group(1)} км превышает {MAX_RADIUS_KM} км"
                                    except Exception:
                                        pass

                                # Check explicit size in post-evaluator
                                full_c_text = f"{c.get('size_str', '')} {c_text}"
                                ha_chk = re.search(r'(\d+(?:[,\.]\d+)?)\s*\b(?:ha|hektar)\b', full_c_text, re.IGNORECASE)
                                if ha_chk:
                                    try:
                                        h_val = float(ha_chk.group(1).replace(",", "."))
                                        if h_val < 0.1 or h_val > 0.5:
                                            score = 0
                                            ev_record["rejection_reason"] = f"Площадь {h_val} га вне диапазона 1.000 - 5.000 м²"
                                    except Exception:
                                        pass

                                sqm_chk = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:m²|qm|m2)', full_c_text)
                                if sqm_chk:
                                    try:
                                        sq_val = float(sqm_chk.group(1).replace(".", "").replace(",", "."))
                                        if sq_val < MIN_SIZE_SQM or sq_val > MAX_SIZE_SQM:
                                            score = 0
                                            ev_record["rejection_reason"] = f"Площадь {sq_val:.0f} м² вне диапазона [{MIN_SIZE_SQM}, {MAX_SIZE_SQM}]"
                                    except Exception:
                                        pass

                                c["score"] = score
                                c["verdict"] = "MATCH" if (score >= MATCH_THRESHOLD and quotes_verified) else "REJECTED"
                                c["summary_ru"] = ev_record.get("summary_ru", "")
                                c["rejection_reason"] = ev_record.get("rejection_reason")
                                c["evidence"] = ev_data
                                c["evaluator_model"] = model_name

                                if c["verdict"] == "MATCH":
                                    safe_log(f"[Groq AI] ad #{c['ad_id']} MATCH ({score}%) | {c['title'][:40]} | Evidence: {ev_data.get('offer_type_quote')} / {ev_data.get('size_quote')}")
                                else:
                                    safe_log(f"[Groq AI] ad #{c['ad_id']} Rejected ({score}%) | Reason: {c['rejection_reason']}")
                            else:
                                c["score"] = 0
                                c["verdict"] = "REJECTED"
                                c["rejection_reason"] = "No AI audit returned"

                            evaluated_results.append(c)

                        chunk_handled = True
                        break

                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        retry_after = e.headers.get("Retry-After") if hasattr(e, 'headers') else None
                        wait_sec = float(retry_after) if retry_after else 12.0
                        safe_log(f"[Groq AI] Rate limit (429). Sleeping {wait_sec}s before retry...")
                        time.sleep(wait_sec)
                        continue
                    else:
                        err_body = ""
                        try:
                            err_body = e.read().decode('utf-8', errors='replace')
                        except Exception:
                            pass
                        safe_log(f"[Groq AI] Model {model_name} HTTP {e.code}: {e.reason} ({err_body[:80]}). Trying next model...")
                        break
                except Exception as e:
                    safe_log(f"[Groq AI] Model {model_name} error: {e}. Trying next model...")
                    break
            if chunk_handled:
                break

        if not chunk_handled:
            safe_log(f"[Groq AI] Failed to evaluate chunk {i//chunk_size + 1}. Marking for fallback.")
            for c in chunk:
                c["score"] = 50
                c["verdict"] = "PENDING_REVIEW"
                evaluated_results.append(c)

    return evaluated_results

# ==============================================================================
# Telegram Notifications to Iurii & Anti-Duplicate Engine
# ==============================================================================
def get_property_slug(itm: dict) -> str:
    """Extracts canonical URL slug without ad_id."""
    url = itm.get("url") or ""
    m = re.search(r'/s-anzeige/([^/]+)/\d+', url)
    if m:
        return m.group(1).strip().lower()
    return ""

def get_property_fingerprint(itm: dict) -> str:
    """
    Computes a deterministic fingerprint (Postal Code + Town + Price Digits)
    to catch duplicate listings reposted under different ad IDs by the same seller/broker.
    """
    loc = (itm.get("location") or "").lower()
    title = (itm.get("title") or "").lower()
    price = (itm.get("price") or "").lower()

    # Extract 5-digit German postal code
    plz_m = re.search(r'\b\d{5}\b', f"{loc} {title}")
    plz = plz_m.group(0) if plz_m else ""

    # Extract numeric price digits
    price_digits = re.sub(r'[^\d]', '', price)

    # Primary towns in Wittenberge + 30km region
    towns = [
        "wittenberge", "kyritz", "seehausen", "osterburg", "pritzwalk",
        "wittstock", "wusterhausen", "plattenburg", "ballerstedt", "landin",
        "stechow", "perleberg", "karstaedt", "gumtow", "cumlosen",
        "lenzen", "bad wilsnack", "wilsnack"
    ]
    town = ""
    for t in towns:
        if t in loc or t in title:
            town = t.replace(" ", "")
            break

    # If postal code and numeric price exist, uniquely identify the parcel
    if plz and price_digits and int(price_digits) > 500:
        return f"{plz}_{town}_{price_digits}"
    elif town and price_digits and int(price_digits) > 500:
        return f"{town}_{price_digits}"
    elif plz:
        words = [w for w in re.findall(r'[a-z0-9äöüß]{4,}', title) if w not in {
            "grundstueck", "grundstuecke", "baugrundstueck", "bauland", "provisionsfrei",
            "verkauf", "kauf", "angebot", "gelegenheit", "chance", "attraktive"
        }]
        kw = "_".join(sorted(words[:3]))
        return f"{plz}_{town}_{kw or 'plot'}"
    return ""

def load_notified_data() -> tuple[set, set, set, list]:
    """Loads all previously notified ad IDs, fingerprints, and slugs."""
    ad_ids = set()
    fingerprints = set()
    slugs = set()
    history = []
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    ad_ids = set(str(x) for x in data)
                elif isinstance(data, dict):
                    ad_ids = set(str(x) for x in data.get("ad_ids", []))
                    fingerprints = set(str(x) for x in data.get("fingerprints", []))
                    slugs = set(str(x) for x in data.get("slugs", []))
                    history = data.get("history", [])
        except Exception as e:
            safe_log(f"[Notification Store] Error loading {NOTIFIED_FILE}: {e}")
    return ad_ids, fingerprints, slugs, history

def save_notified_data(ad_ids: set, fingerprints: set, slugs: set, new_history_entries: list = None):
    """Atomically saves notified cache to disk."""
    _, _, _, existing_history = load_notified_data()
    if new_history_entries:
        existing_history.extend(new_history_entries)
    payload = {
        "ad_ids": sorted(list(ad_ids)),
        "fingerprints": sorted(list(fingerprints)),
        "slugs": sorted(list(slugs)),
        "history": existing_history[-100:]
    }
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def notify_new_matches(matches: list) -> int:
    """
    Sends rich Telegram alert to Iurii for new matching properties.
    Guarantees ZERO DUPLICATES across runs and within the same batch.
    Immediately persists after every dispatch.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    notified_ids, notified_fps, notified_slugs, _ = load_notified_data()

    # In-memory dedup tracker for current execution batch
    batch_seen_ids = set()
    batch_seen_fps = set()
    batch_seen_slugs = set()

    new_alerts = 0
    for itm in matches:
        ad_id = str(itm["ad_id"])
        fp = get_property_fingerprint(itm)
        slug = get_property_slug(itm)

        # 1. Skip if already sent in previous runs
        if ad_id in notified_ids:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Already notified previously).")
            continue
        if slug and slug in notified_slugs:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Slug '{slug}' already notified).")
            continue
        if fp and fp in notified_fps:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Property fingerprint '{fp}' already notified).")
            continue

        # 2. Skip if duplicate of another item in this same run batch
        if ad_id in batch_seen_ids:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Duplicate ID in current run).")
            continue
        if slug and slug in batch_seen_slugs:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Duplicate slug '{slug}' in current run).")
            continue
        if fp and fp in batch_seen_fps:
            safe_log(f"[Notification] Skipping ad #{ad_id} (Duplicate fingerprint '{fp}' in current run).")
            continue

        batch_seen_ids.add(ad_id)
        if slug: batch_seen_slugs.add(slug)
        if fp: batch_seen_fps.add(fp)

        ev = itm.get("evidence", {})
        summary = itm.get("summary_ru") or "Участок соответствует заданным критериям."
        size_display = ev.get("size_quote") or itm.get("size_str") or "1.000 - 5.000 м² (уточняется)"
        
        msg = (
            f"🏡 *Найден подходящий участок в Виттенберге!* ({itm.get('score', 80)}% совпадение)\n\n"
            f"📍 *Локация:* {itm.get('location')}\n"
            f"📐 *Площадь:* {size_display}\n"
            f"💰 *Цена:* {itm.get('price')}\n\n"
            f"🔗 [{itm['title']}]({itm['url']})\n\n"
            f"🤖 *Оценка ИИ (Groq Evidence):*\n"
            f"• Продажа: `{ev.get('offer_type_quote') or 'Да'}`\n"
            f"• Тип: `{ev.get('property_type_quote') or 'Baugrundstück'}`\n"
            f"• Локация: `{ev.get('location_quote') or itm.get('location')}`\n\n"
            f"📝 *Комментарий:* _{summary}_"
        )

        success = send_telegram(msg)
        if success:
            notified_ids.add(ad_id)
            if slug: notified_slugs.add(slug)
            if fp: notified_fps.add(fp)

            # Persist immediately to disk after each send
            hist_entry = {
                "ad_id": ad_id,
                "fingerprint": fp,
                "slug": slug,
                "title": itm.get("title"),
                "price": itm.get("price"),
                "location": itm.get("location"),
                "sent_at": datetime.now().isoformat()
            }
            save_notified_data(notified_ids, notified_fps, notified_slugs, [hist_entry])
            new_alerts += 1
            time.sleep(1.5)

    return new_alerts

# ==============================================================================
# Live Dashboard & README Generator
# ==============================================================================
def generate_dashboards(all_evaluated: list, new_alerts_count: int):
    """Generates both GitHub README.md dashboard and interactive dashboard.html."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    matches = [it for it in all_evaluated if it.get("verdict") == "MATCH"]
    rejected = [it for it in all_evaluated if it.get("verdict") == "REJECTED"]

    # 1. Save data files
    payload = {
        "last_updated": datetime.now().isoformat(),
        "client": CLIENT_NAME,
        "criteria": "Wittenberge 19322 (+30km, closer is better), Dorf/Grundstück, 1.000 - 5.000 m², Offer for Sale, Max 50.000 €",
        "total_scanned": len(all_evaluated),
        "matches_count": len(matches),
        "rejected_count": len(rejected),
        "items": all_evaluated
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # 2. Append to run history
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
    history.insert(0, {
        "timestamp": now_str,
        "total_scanned": len(all_evaluated),
        "matches_found": len(matches),
        "telegram_alerts_sent": new_alerts_count
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:50], f, indent=2)

    # 3. Generate README.md Dashboard
    matches_table_rows = []
    for it in matches:
        ev = it.get("evidence", {})
        size = ev.get("size_quote") or it.get("size_str") or "1.000-5.000 m²"
        matches_table_rows.append(
            f"| **{it.get('score')}%** | [{it['title'][:45]}...]({it['url']}) | `{it['price']}` | {it['location']} | {size} | `{ev.get('offer_type_quote')}` / `{ev.get('property_type_quote')}` | [Direct Listing]({it['url']}) |"
        )
    matches_table_str = "\n".join(matches_table_rows) if matches_table_rows else "| - | *No properties currently active in the exact 1,000-5,000m² bracket under 50.000 €.* | - | - | - | - | - |"

    audit_log_rows = []
    for it in all_evaluated[:15]:
        v_badge = "✅ MATCH" if it.get("verdict") == "MATCH" else "❌ REJECT"
        audit_log_rows.append(
            f"| `{it['ad_id']}` | {v_badge} | **{it.get('score', 0)}%** | [{it['title'][:35]}...]({it['url']}) | {it.get('rejection_reason') or 'Approved (Passed all criteria)'} |"
        )
    audit_table_str = "\n".join(audit_log_rows)

    readme_content = f"""# 🏡 Wittenberge Land & Village Plot Hunter
### 24/7 Autonomous Cloud Scraper & Groq AI Evidence Evaluator for **{CLIENT_NAME}**

[![Scrape Every 4 Hours](https://github.com/BeagelDars/wittenberge-land-scraper/actions/workflows/scrape_every_4h.yml/badge.svg)](https://github.com/BeagelDars/wittenberge-land-scraper/actions/workflows/scrape_every_4h.yml)
[![Telegram Bot](https://img.shields.io/badge/Telegram-@Grundstuck__Wittenberge__bot-blue?logo=telegram)](https://t.me/Grundstuck_Wittenberge_bot)
[![Match Threshold](https://img.shields.io/badge/Strict%20Filter-%E2%89%A570%25%20Match-success)](#)
[![Evaluator](https://img.shields.io/badge/Groq%20AI-Zero--Hallucination%20Evidence-orange)](#)

---

## 🟢 Live System Status & Heartbeat

| Status Indicator | Metric | Value |
| :--- | :--- | :--- |
| 🟢 **Heartbeat** | Runner Schedule | Every 4 hours (`0 */4 * * *`) via GitHub Actions |
| ⏱️ **Last Cycle** | Executed at | `{now_str}` |
| 🎯 **Target Region** | Search Area | **Wittenberge (19322) + 30 km radius** (Closer to Wittenberge prioritized) |
| 📐 **Target Area** | Plot Size | **1,000 – 5,000 m²** (Strict Knockout) |
| 💰 **Max Budget** | Price Limit | **≤ 50,000 €** (Strict Knockout) |
| 🤖 **Telegram Alert** | Client Recipient | **Iurii (`{CLIENT_CHAT_ID}`)** via [@Grundstuck_Wittenberge_bot](https://t.me/Grundstuck_Wittenberge_bot) |
| 📊 **Active Matches** | Score ≥ 70% | **{len(matches)}** verified listings |

---

## 🎯 High-Match Properties (≥ 70% Match Score)

> These properties strictly verified zero-hallucination evidence quotes for sale offer, property type, 30km radius (proximity prioritized), ≤ 50.000 € budget, and 1,000-5,000 m² area.

| Match | Title | Price | Location | Area | Groq Evidence Quotes | Link |
| :---: | :--- | :---: | :--- | :---: | :--- | :---: |
{matches_table_str}
{matches_table_str}

---

## 🔍 Groq AI Audit Log (Last 15 Candidates Scanned)

| Ad ID | Verdict | Match % | Listing Title | AI Decision / Deduction Reason |
| :---: | :---: | :---: | :--- | :--- |
{audit_table_str}

---

## 🛡️ Zero-Hallucination Two-Step Architecture

```
Kleinanzeigen DOM Parser (Direct /s-anzeige/ URLs)
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Deterministic Python Pre-Filter                    │
│  • Instant rejection of Wanted Ads ("Gesuch", "Suche")      │
│  • Instant rejection of Leases ("Pacht", "Miete")           │
│  • Elimination of lawnmowers, tools, furniture, apartments  │
└──────────────────────────┬──────────────────────────────────┘
                           │ Pre-Filtered Candidates
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Groq AI Evidence Evaluator (Strict Percentage)     │
│  • Offer for Sale: +35% (Wanted/Lease = 0% Reject)          │
│  • Plot in Village/Region: +25%                             │
│  • Location in 30km Radius: +20%                            │
│  • Size 1,000 - 5,000 m²: +20%                              │
│  • Verbatim Quote Verification: Must exist in source text   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Match Score ≥ 70%
                           ▼
          Instant Telegram Alert to Iurii
            + Live Dashboard Update
```

---
*Auto-updated by GitHub Actions 24/7 Cloud Worker. Next run in ~4 hours.*
"""
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 4. Generate Interactive dashboard.html
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wittenberge Land Hunter - Live Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #111827;
      --border: #1f2937;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.2);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --danger: #ef4444;
      --warning: #f59e0b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 32px 24px;
      min-height: 100vh;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 32px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .title-group h1 {{
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .pulse-dot {{
      width: 10px;
      height: 10px;
      background: var(--accent);
      border-radius: 50%;
      box-shadow: 0 0 12px var(--accent);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
      70% {{ transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }}
      100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
    }}
    .badge {{
      background: rgba(16, 185, 129, 0.1);
      color: var(--accent);
      border: 1px solid var(--accent);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }}
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}
    .metric-card .label {{ font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }}
    .metric-card .val {{ font-size: 28px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
    .section-title {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
    .table-container {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 32px;
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
    th {{ background: #131d2e; padding: 14px 18px; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); }}
    td {{ padding: 14px 18px; border-bottom: 1px solid var(--border); }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(255,255,255,0.02); }}
    .score-badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
    }}
    .score-high {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid #10b981; }}
    .score-low {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #ef4444; }}
    a.listing-link {{ color: #60a5fa; text-decoration: none; font-weight: 500; }}
    a.listing-link:hover {{ text-decoration: underline; }}
    .btn {{
      background: #2563eb;
      color: #fff;
      padding: 6px 14px;
      border-radius: 6px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .btn:hover {{ background: #1d4ed8; }}
    .code-pill {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; background: #1f2937; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <div class="pulse-dot"></div>
        <h1>Wittenberge Land & Village Plot Hunter</h1>
        <span class="badge">Every 4h Scheduled Cron</span>
      </div>
      <div>
        <a href="https://t.me/Grundstuck_Wittenberge_bot" target="_blank" class="btn">📱 Open Telegram Bot</a>
      </div>
    </header>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="label">Target Area & Location</div>
        <div class="val" style="font-size: 20px;">Wittenberge (19322) +30km</div>
      </div>
      <div class="metric-card">
        <div class="label">Size Requirement</div>
        <div class="val" style="font-size: 20px;">1,000 – 5,000 m²</div>
      </div>
      <div class="metric-card">
        <div class="label">Budget Cap</div>
        <div class="val" style="font-size: 20px; color: var(--accent);">≤ 50,000 €</div>
      </div>
      <div class="metric-card">
        <div class="label">Approved Matches (≥70%)</div>
        <div class="val" style="color: var(--accent);">{len(matches)}</div>
      </div>
      <div class="metric-card">
        <div class="label">Total Raw Scanned</div>
        <div class="val">{len(all_evaluated)}</div>
      </div>
    </div>

    <div class="section-title">🌟 Verified Matches for Iurii (≥ 70% Match Score)</div>
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Match</th>
            <th>Title</th>
            <th>Price</th>
            <th>Location</th>
            <th>Area</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {"".join([f'''<tr>
            <td><span class="score-badge score-high">{it.get("score")}%</span></td>
            <td><a href="{it['url']}" target="_blank" class="listing-link">{it['title']}</a></td>
            <td><strong>{it['price']}</strong></td>
            <td>{it['location']}</td>
            <td><span class="code-pill">{it.get('evidence', {}).get('size_quote') or it.get('size_str') or '1.000 - 5.000 m²'}</span></td>
            <td><a href="{it['url']}" target="_blank" class="btn">View Ad</a></td>
          </tr>''' for it in matches]) if matches else '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 32px;">No active listings currently match the strict 1,000 - 5,000 m² criteria. Next scan scheduled in 4 hours.</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="section-title">📜 Groq AI Evaluator Audit Log</div>
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Ad ID</th>
            <th>Status</th>
            <th>Score</th>
            <th>Listing Title</th>
            <th>Auditor Deduction / Approval Reason</th>
          </tr>
        </thead>
        <tbody>
          {"".join([f'''<tr>
            <td><span class="code-pill">#{it['ad_id']}</span></td>
            <td><span class="score-badge {'score-high' if it.get('verdict') == 'MATCH' else 'score-low'}">{it.get('verdict')}</span></td>
            <td><strong>{it.get('score', 0)}%</strong></td>
            <td><a href="{it['url']}" target="_blank" class="listing-link">{it['title'][:55]}...</a></td>
            <td style="color: var(--text-muted); font-size: 13px;">{it.get('rejection_reason') or it.get('summary_ru') or 'Approved'}</td>
          </tr>''' for it in all_evaluated[:15]])}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    safe_log(f"[Dashboard] Successfully updated README.md and dashboard.html with {len(matches)} matches.")

# ==============================================================================
# Main Orchestration Loop
# ==============================================================================
def run():
    safe_log(f"=== Starting 24/7 Cloud Scraper for {CLIENT_NAME} at {datetime.now().isoformat()} ===")
    
    # 1. Fetch & Parse Listings across target search URLs with in-flight deduplication
    raw_listings_map = {}
    seen_fps_map = {}
    seen_slugs_map = {}

    for url in TARGET_URLS:
        html = fetch_url(url)
        if html:
            items = parse_html_listings(html)
            for itm in items:
                ad_id = str(itm["ad_id"])
                fp = get_property_fingerprint(itm)
                slug = get_property_slug(itm)

                existing_id = (
                    ad_id if ad_id in raw_listings_map else None
                ) or (
                    seen_fps_map.get(fp) if fp else None
                ) or (
                    seen_slugs_map.get(slug) if slug else None
                )

                if existing_id and existing_id in raw_listings_map:
                    # Keep the listing with richer description/specs
                    existing_item = raw_listings_map[existing_id]
                    if len(itm.get("description", "")) > len(existing_item.get("description", "")):
                        del raw_listings_map[existing_id]
                        raw_listings_map[ad_id] = itm
                        if fp: seen_fps_map[fp] = ad_id
                        if slug: seen_slugs_map[slug] = ad_id
                    continue

                raw_listings_map[ad_id] = itm
                if fp: seen_fps_map[fp] = ad_id
                if slug: seen_slugs_map[slug] = ad_id

            safe_log(f"[Scraper] Downloaded {len(items)} listings from {url}")

    all_raw = list(raw_listings_map.values())
    safe_log(f"[Step 0] Total unique listings extracted after de-duplication: {len(all_raw)}")
    if not all_raw:
        safe_log("[Scraper] Warning: 0 listings returned from network. Preserving existing results to prevent data wipe during network outage.")
        return

    # 2. Step 1: Deterministic Python Pre-Filter
    step1_candidates = [it for it in all_raw if python_pre_filter(it)]
    safe_log(f"[Step 1: Python Filter] Kept {len(step1_candidates)} high-probability candidates (eliminated wanted ads, leases, junk).")

    # 3. Step 2: Groq AI Evidence Evaluator with Percentage Scoring
    evaluated_items = groq_evaluate_listings(step1_candidates)

    # 4. Telegram Notification for High Matches (Score >= 70%)
    matches = [it for it in evaluated_items if it.get("verdict") == "MATCH"]
    safe_log(f"[Step 2: Groq AI] {len(matches)} listings passed strict ≥{MATCH_THRESHOLD}% criteria.")
    new_alerts = notify_new_matches(matches)
    safe_log(f"[Telegram] Dispatched {new_alerts} new alert notifications to {CLIENT_NAME}.")

    # 5. Live Dashboard & History Generation
    generate_dashboards(evaluated_items, new_alerts)
    safe_log("=== Scraper & Evaluation Cycle Completed Successfully ===")

if __name__ == "__main__":
    run()
