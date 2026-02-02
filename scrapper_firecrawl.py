import os
import json
import base64
from pathlib import Path
import requests

def scrapper_url(url,api_url,api_key):
# --- config ---
 # ← replace with your real key, or read from env (recommended)
 
    ARTIFACTS = Path("artifacts")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "url": f"{url}",
        "formats": [
            "markdown",
            {
                "type": "screenshot",
                "fullPage": True,
                "quality": 100,
                "viewport": {"width": 1366, "height": 1000},
            },
        ],
        # 'actions': [
        # { 'type': 'wait', 'milliseconds': 50000 },  # Wait for cookie banner to appear
        # # Try multiple selectors - Firecrawl will use the first one that matches
        # { 'type': 'click', 'selector': 'button:contains("Accept All"), button:contains("Accept all"), button[id*="accept"], .cookie-accept-all, #accept-cookies' },
        # { 'type': 'wait', 'milliseconds': 5000 },  # Wait for banner to disappear
        # ],
        # Try different selectors in separate actions
        # 'actions': [
        #     { 'type': 'wait', 'milliseconds': 10000 },
        #     # Try common cookie button selectors one by one
        #     { 'type': 'click', 'selector': 'button[id*="Accept all"]' },
        #     { 'type': 'wait', 'milliseconds': 10000 },
        #     { 'type': 'click', 'selector': 'button[class*="Accept all"]' },
        #     { 'type': 'wait', 'milliseconds': 10000 },
        #     { 'type': 'click', 'selector': '[data-testid*="Accept all"]' },
        #     { 'type': 'wait', 'milliseconds': 10000 },
        # ],
        "onlyMainContent": False,
        "headers": {
            "Cookie": "",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        "waitFor": 50000,
        "mobile": False,
        "skipTlsVerification": True,
        "timeout": 100000,
        "removeBase64Images": False,
        "blockAds": True,
        "proxy": "auto",
        "storeInCache": False,
    }
    
    # --- call the API ---
    resp = requests.post(api_url, headers=headers, json=payload)
    data = resp.json()
    # # (optional) save raw response for debugging
    # (ARTIFACTS / "firecrawl_response.json").write_text(
    #     json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    # )
    
    # # --- extract & save markdown ---
    # markdown = data.get("markdown") or (data.get("data") or {}).get("markdown") or ""
    # md_path = ARTIFACTS / "page.md"
    # md_path.write_text(markdown, encoding="utf-8")

    screenshot_url = data.get("screenshot") or (data.get("data") or {}).get("screenshot")
    return screenshot_url

