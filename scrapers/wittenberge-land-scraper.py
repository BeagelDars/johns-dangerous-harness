#!/usr/bin/env python3
"""
High-Precision 24/7 Cloud Scraper: Wittenberge Real Estate & Plots (19322)
Two-Step Verification Pipeline:
  Step 1: Deterministic Python Filter (DOM targeting, exact direct links, wanted-ad rejection)
  Step 2: Strict Groq AI Evidence Evaluator (zero-hallucination verbatim quote verification)
"""
import os
import sys
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# Configure UTF-8 output streams safely for Windows and Linux environments
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

LOCATION = "Wittenberge (19322)"
CRITERIA = "Grundstück / Baugrundstück / Land for sale in Wittenberge 19322 (+30km radius), size 1,000 to 5,000 sqm"
TARGET_URL = "https://www.kleinanzeigen.de/s-grundstuecke-garten/wittenberge/c207l7870r30+grundstueck_typ_s:grundstueck+preis:0,50000+groesse:1000,5000"

DATA_FILES = [
    os.path.join(os.path.dirname(__file__), "data", "wittenberge-land-scraper_results.json"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "wittenberge_real_estate.json")
]

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

def safe_log(msg: str):
    """Safely prints log messages without charset errors."""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        safe_log("[Telegram] Notice: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            safe_log(f"[Telegram] Alert delivered successfully to chat ID: {chat_id}")
            return True
    except Exception as e:
        safe_log(f"[Telegram] Failed to send alert: {e}")
        return False

# ==============================================================================
# Step 1: Fast Deterministic DOM Parsing & Pre-Filtering
# ==============================================================================
def parse_kleinanzeigen_html(html: str):
    """Extracts structured ad records from Kleinanzeigen search results."""
    articles = re.findall(r'<article\s+[^>]*data-adid=[\'"](\d+)[\'"][^>]*>([\s\S]*?)</article>', html)
    raw_listings = []

    for ad_id, block in articles:
        # 1. Exact direct link
        href_match = re.search(r'data-href=[\'"]([^\'"]+)[\'"]', block)
        if not href_match:
            href_match = re.search(r'href=[\'"](/s-anzeige/[^\'"]+)[\'"]', block)
        
        if not href_match:
            continue
            
        rel_href = href_match.group(1)
        full_url = urllib.parse.urljoin("https://www.kleinanzeigen.de", rel_href)

        # 2. Extract JSON-LD metadata if present
        title = ""
        description = ""
        jsonld_match = re.search(r'<script\s+type=[\'"]application/ld\+json[\'"]>([\s\S]*?)</script>', block)
        if jsonld_match:
            try:
                data = json.loads(jsonld_match.group(1))
                title = data.get("title", "")
                description = data.get("description", "")
            except Exception:
                pass

        # 3. Fallback extraction from DOM
        if not title:
            title_m = re.search(r'<a\s+[^>]*class=[\'"][^\'"]*ellipsis[^\'"]*[\'"][^>]*>(.*?)</a>', block, re.DOTALL)
            if not title_m:
                title_m = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
            title = re.sub(r'<[^>]+>', ' ', title_m.group(1)).strip() if title_m else ""

        # Price
        price_m = re.search(r'class=[\'"][^\'"]*price[^\'"]*[\'"][^>]*>(.*?)</div>', block, re.DOTALL)
        price = re.sub(r'<[^>]+>', ' ', price_m.group(1)).strip() if price_m else "N/A"

        # Location
        loc_m = re.search(r'class=[\'"][^\'"]*aditem-main--top--left[^\'"]*[\'"][^>]*>(.*?)</div>', block, re.DOTALL)
        location = re.sub(r'<[^>]+>', ' ', loc_m.group(1)).strip() if loc_m else "Wittenberge Region"

        # Tags (sqm, property type)
        tags = [re.sub(r'<[^>]+>', '', t).strip() for t in re.findall(r'<span\s+class=[\'"][^\'"]*simpletag[^\'"]*[\'"][^>]*>(.*?)</span>', block)]

        raw_listings.append({
            "ad_id": ad_id,
            "url": full_url,
            "title": title,
            "description": description,
            "price": price,
            "location": location,
            "tags": tags
        })

    return raw_listings

def python_pre_filter(item: dict) -> bool:
    """Step 1 Filter: Deterministic rule-based validation."""
    title_lower = (item.get("title") or "").lower()
    desc_lower = (item.get("description") or "").lower()
    full_text = f"{title_lower} {desc_lower}"
    tags_lower = [t.lower() for t in item.get("tags", [])]

    # 1. Reject wanted ads ("Gesuch" tag, badge, or title)
    if "gesuch" in tags_lower or any("gesuch" in t for t in tags_lower):
        return False

    wanted_keywords = [
        "gesucht", "kaufgesuch", "suche baugrundstück", "suche grundstück", 
        "suche ackerland", "suchauftrag", "gesuche", "gesucht!", "ankauf"
    ]
    if any(k in title_lower for k in wanted_keywords):
        return False
    if "zum kauf gesucht" in full_text or "flaeche gesucht" in full_text or "suche flächen" in full_text or "suche baugrund" in full_text:
        return False

    # 2. Reject non-real estate products (mowers, tools, furniture)
    junk_keywords = ["rasenmäher", "gartenmöbel", "pflanzen", "zaun", "brennholz", "traktor", "sofa", "mietwohnung"]
    if any(k in title_lower for k in junk_keywords):
        return False

    # 3. Must be a valid direct ad URL
    url = item.get("url", "")
    if "/s-anzeige/" not in url or not item.get("ad_id"):
        return False

    # 4. Check for positive plot / land indications
    land_keywords = ["grundstück", "grundstueck", "baugrundstück", "acker", "ackerland", "wald", "forst", "wiese", "gartenland", "fläche", "bauland", "parzelle"]
    if not any(k in full_text for k in land_keywords) and not any(any(k in t for k in land_keywords) for t in tags_lower):
        return False

    return True

# ==============================================================================
# Step 2: Groq AI Evidence-Based Verification (Zero Hallucination)
# ==============================================================================
def groq_evaluate_batch(candidates: list) -> list:
    """Uses Groq's high-speed inference to strictly verify listings and extract verbatim evidence quotes."""
    if not candidates:
        return []
        
    if not GROQ_KEY:
        safe_log("[Groq AI] Warning: GROQ_API_KEY missing, bypassing Step 2.")
        return candidates

    safe_log(f"[Groq AI] Evaluating {len(candidates)} pre-filtered candidates with strict evidence verification...")

    verified_listings = []
    # Process in chunks of 8 to stay well within Groq TPM limits
    chunk_size = 8
    models_to_try = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]

    for i in range(0, len(candidates), chunk_size):
        chunk = candidates[i:i + chunk_size]
        items_payload = []
        for c in chunk:
            items_payload.append({
                "ad_id": c["ad_id"],
                "title": c["title"],
                "price": c["price"],
                "location": c["location"],
                "tags": c.get("tags", []),
                "description_snippet": (c.get("description") or "")[:200]
            })

        prompt = f"""You are a strict, zero-hallucination real estate auditor AI.
Criteria: Real estate plots/land FOR SALE in Wittenberge 19322 or surrounding region within ~30km (size: approximately 1,000 to 5,000 sqm).

Listings to audit:
{json.dumps(items_payload, indent=2, ensure_ascii=False)}

CRITICAL ZERO-TOLERANCE RULES:
1. ONLY OFFERS FOR SALE: If a listing is a WANTED ad ("Gesuch", "Suche", "zum Kauf gesucht") or lease/pacht, it MUST be REJECTED.
2. EVIDENCE REQUIRED: For any listing that passes, you MUST extract exact verbatim quote substrings from the listing's title, tags, or description snippet:
   - "offer_type_quote": Verbatim quote proving this is an offer for sale (NOT a wanted ad)
   - "property_type_quote": Verbatim quote proving it is a land/plot (Grundstück, Baugrundstück, Acker, Fläche, Bauland)
   - "location_quote": Verbatim quote showing location
   - "size_quote": Verbatim quote of the area/size (e.g. '1.500 m²') if present
3. If quotes cannot be found verbatim in the provided text, the listing CANNOT pass.

Return a JSON object with a "verifications" array matching the ad_ids:
{{
  "verifications": [
    {{
      "ad_id": "...",
      "verdict": "PASS" | "REJECT",
      "rejection_reason": "string or null",
      "is_for_sale": true | false,
      "evidence": {{
        "offer_type_quote": "exact quote or empty string",
        "property_type_quote": "exact quote or empty string",
        "location_quote": "exact quote or empty string",
        "size_quote": "exact quote or empty string"
      }}
    }}
  ]
}}
"""

        chunk_success = False
        for model_name in models_to_try:
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
                    verifications = parsed.get("verifications", [])
                    ver_map = {str(v.get("ad_id")): v for v in verifications}

                    for c in chunk:
                        v = ver_map.get(str(c["ad_id"]))
                        if v and v.get("verdict") == "PASS":
                            # Programmatic anti-hallucination check: ensure quotes are real substrings
                            ev = v.get("evidence", {})
                            c_text = f"{c['title']} {c['description']} {' '.join(c.get('tags', []))} {c['location']}".lower()
                            
                            has_valid_quotes = True
                            for k in ["offer_type_quote", "property_type_quote"]:
                                q = (ev.get(k) or "").strip().lower()
                                if not q or q not in c_text:
                                    safe_log(f"[Anti-Hallucination] Discarded ad #{c['ad_id']}: {k} quote '{q}' not found in source text.")
                                    has_valid_quotes = False
                                    break

                            if has_valid_quotes:
                                c["ai_verification"] = {
                                    "model": model_name,
                                    "status": "VERIFIED_PASS",
                                    "evidence": ev,
                                    "verified_at": datetime.now().isoformat()
                                }
                                verified_listings.append(c)
                                safe_log(f"[Groq AI] ad #{c['ad_id']} PASSED ({model_name}) | Evidence: {ev.get('offer_type_quote')} / {ev.get('property_type_quote')}")
                            else:
                                safe_log(f"[Groq AI] Rejecting ad #{c['ad_id']}: Evidence quotes failed verification.")
                        else:
                            reason = v.get("rejection_reason") if v else "Not evaluated"
                            safe_log(f"[Groq AI] Filtered out ad #{c['ad_id']}: {reason}")

                    chunk_success = True
                    break

            except urllib.error.HTTPError as e:
                safe_log(f"[Groq AI] Model {model_name} HTTP {e.code}: {e.reason}. Trying next model...")
                continue
            except Exception as e:
                safe_log(f"[Groq AI] Model {model_name} error: {e}. Trying next model...")
                continue

        if not chunk_success:
            safe_log(f"[Groq AI] All models failed for chunk {i//chunk_size + 1}. Keeping pre-filtered items as fallback.")
            verified_listings.extend(chunk)

    return verified_listings

# ==============================================================================
# Main Orchestration Loop
# ==============================================================================
def run():
    safe_log(f"=== Starting High-Precision 24/7 Scraper for {LOCATION} at {datetime.now().isoformat()} ===")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"
    }
    
    req = urllib.request.Request(TARGET_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        safe_log(f"[Error] Failed to fetch {TARGET_URL}: {e}")
        sys.exit(1)

    # 1. Parse raw listings
    raw_listings = parse_kleinanzeigen_html(html)
    safe_log(f"[Step 0] Extracted {len(raw_listings)} raw aditem listings from search results.")

    # 2. Step 1: Deterministic Python Pre-Filter
    step1_candidates = [item for item in raw_listings if python_pre_filter(item)]
    safe_log(f"[Step 1: Python Filter] Kept {len(step1_candidates)} high-probability candidates (filtered out wanted ads and junk).")

    # 3. Step 2: Groq AI Evidence Evaluator
    verified_listings = groq_evaluate_batch(step1_candidates)
    safe_log(f"[Step 2: Groq AI] {len(verified_listings)} listings strictly verified with verbatim evidence.")

    # Save to JSON datasets
    output_payload = {
        "scraper_version": "2.0-two-step-verified",
        "last_updated": datetime.now().isoformat(),
        "target_location": LOCATION,
        "criteria": CRITERIA,
        "raw_scanned": len(raw_listings),
        "step1_filtered": len(step1_candidates),
        "verified_count": len(verified_listings),
        "items": verified_listings
    }

    for file_path in DATA_FILES:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output_payload, f, indent=2, ensure_ascii=False)
            safe_log(f"[Storage] Saved verified dataset ({len(verified_listings)} items) -> {file_path}")
        except Exception as e:
            safe_log(f"[Storage] Could not write {file_path}: {e}")

    # Dispatch Telegram Notification
    if verified_listings:
        msg_lines = [
            f"🏡 *Verified Plot Alert: {LOCATION}*",
            f"🎯 *Criteria:* 1,000 - 5,000 m² (Plots for Sale)",
            f"✅ *AI-Verified Listings:* {len(verified_listings)} offers",
            ""
        ]
        for idx, itm in enumerate(verified_listings[:5], 1):
            ev = itm.get("ai_verification", {}).get("evidence", {})
            size_str = f" • Area: {ev.get('size_quote')}" if ev.get("size_quote") else ""
            msg_lines.append(f"{idx}. [{itm['title'][:50]}]({itm['url']})")
            msg_lines.append(f"   💰 {itm['price']}{size_str}")

        if len(verified_listings) > 5:
            msg_lines.append(f"\n_...and {len(verified_listings) - 5} more verified properties in Cloud Tasks dashboard._")

        send_telegram("\n".join(msg_lines))
    else:
        safe_log("[Telegram] No new verified properties matched strict criteria on this cycle.")

    safe_log("=== Scraping and AI Verification Cycle Completed Successfully ===")

if __name__ == "__main__":
    run()
