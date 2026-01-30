#!/usr/bin/env python3
"""
SGM Lunch Menu Updater

Fetches the lunch menu calendar from sgmission.org, parses the image using
Google Gemini Vision API, and outputs a structured JSON file.

Environment Variables:
    GEMINI_API_KEY: Required. Your Google Gemini API key.
    MENU_IMAGE_URL: Optional. Direct URL to the menu image (bypasses page scraping).
    MENU_MONTH: Optional. Override month in YYYY-MM format (e.g., "2026-01").
"""

import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from google.genai import Client as GeminiClient
from google.genai import types as genai_types
from playwright.sync_api import sync_playwright

# Constants
MENU_URL = "https://www.sgmission.org/lunch-menu"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

# Month name to number mapping
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}

MONTH_NAMES = {v: k.capitalize() for k, v in MONTH_MAP.items()}

# Browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def extract_menu_meta_from_images(image_urls: list[str], now: datetime) -> dict:
    image_url = None
    detected_year = None
    detected_month = None

    for src in image_urls:
        if "ecatholic" not in src.lower():
            continue
        if "logo" in src.lower() or "seal" in src.lower() or "icon" in src.lower():
            continue

        date_match = re.search(r"/pictures/(\d{4})/(\d{1,2})/", src)
        if date_match:
            url_year = int(date_match.group(1))
            url_month = int(date_match.group(2))
            if url_year >= now.year - 1:
                if ".jpg" in src.lower() or image_url is None:
                    image_url = src
                    detected_year = url_year
                    detected_month = url_month

    if not image_url:
        for src in image_urls:
            if "ecatholic" in src.lower() and ".jpg" in src.lower() and "logo" not in src.lower():
                image_url = src
                break

    if not image_url:
        raise ValueError("Could not find menu image on page")

    image_url = urljoin(MENU_URL, image_url)

    if detected_year and detected_month:
        year = detected_year
        month_num = detected_month
        month_name = MONTH_NAMES[month_num]
    else:
        month_name = now.strftime("%B")
        year = now.year
        month_num = now.month
        print(f"Warning: Could not detect month/year, using current: {month_name} {year}")

    month_key = f"{year}-{month_num:02d}"

    return {
        "month_name": month_name,
        "year": year,
        "month_num": month_num,
        "image_url": image_url,
        "month_key": month_key,
    }


def fetch_menu_meta_with_playwright() -> dict:
    print(f"Fetching menu page: {MENU_URL}")
    now = datetime.now()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(MENU_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        if page.locator("text=Attention Required").count() > 0:
            browser.close()
            raise RuntimeError("Cloudflare challenge detected")

        image_urls = [img.get_attribute("src") or "" for img in page.locator("img").all()]
        browser.close()

    return extract_menu_meta_from_images(image_urls, now)


def get_menu_meta_from_env() -> dict | None:
    """Get menu metadata from environment variables (override mode)."""
    image_url = os.environ.get("MENU_IMAGE_URL")
    month_override = os.environ.get("MENU_MONTH")
    
    if not image_url:
        return None
    
    print(f"Using image URL from environment: {image_url}")
    
    if month_override:
        year, month_num = map(int, month_override.split("-"))
        month_name = MONTH_NAMES[month_num]
    else:
        now = datetime.now()
        year = now.year
        month_num = now.month
        month_name = MONTH_NAMES[month_num]
    
    month_key = f"{year}-{month_num:02d}"
    print(f"Using month: {month_name} {year} ({month_key})")
    
    return {
        "month_name": month_name,
        "year": year,
        "month_num": month_num,
        "image_url": image_url,
        "month_key": month_key,
    }


def download_image(image_url: str, month_key: str) -> Path:
    """Download the menu image and save to data/raw/."""
    print(f"Downloading image...")
    image_data = None
    content_type = ""
    
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            image_data = response.content
            content_type = response.headers.get("content-type", "")
    except Exception as e:
        print(f"requests failed for image: {e}")
    
    if not image_data:
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", image_url],
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0 and result.stdout:
                image_data = result.stdout
        except Exception as e:
            print(f"curl failed for image: {e}")
    
    if not image_data:
        raise RuntimeError(f"Could not download image from {image_url}")
    
    if "png" in content_type or image_url.lower().endswith(".png"):
        ext = ".png"
    elif "gif" in content_type or image_url.lower().endswith(".gif"):
        ext = ".gif"
    else:
        ext = ".jpg"
    
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    image_path = RAW_DIR / f"{month_key}{ext}"
    image_path.write_bytes(image_data)
    print(f"Saved image to: {image_path} ({len(image_data)} bytes)")
    
    return image_path


def parse_image_with_gemini(image_path: Path, month_name: str, year: int) -> dict:
    """
    Use Google Gemini Vision to parse the calendar image into structured data.
    
    Returns a dict mapping date strings (YYYY-MM-DD) to lunch descriptions.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    client = GeminiClient(api_key=api_key)
    image_data = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", 
        ".png": "image/png",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    
    prompt = f"""This is a school lunch calendar image for {month_name} {year}.

Please extract the lunch menu for each school day and return ONLY a valid JSON object.

Rules:
1. Keys must be ISO date format: YYYY-MM-DD (e.g., "{year}-01-15")
2. Values should be the lunch description for that day
3. For days marked as "NO SCHOOL", "HOLIDAY", "BREAK", etc., use that exact text as the value
4. For weekends or days with no lunch listed, do NOT include them in the output
5. If a day's menu is unclear or unreadable, use null as the value
6. Only include days that are within {month_name} {year}

Return ONLY the JSON object, no markdown formatting, no explanation. Example format:
{{"{year}-01-06": "Pizza with salad", "{year}-01-07": "Chicken nuggets", "{year}-01-20": "NO SCHOOL"}}"""

    print(f"Sending image to Gemini for parsing...")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            genai_types.Part.from_bytes(data=image_data, mime_type=mime_type)
        ]
    )
    
    response_text = response.text.strip()
    
    try:
        menu_map = json.loads(response_text)
    except json.JSONDecodeError:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            menu_map = json.loads(json_match.group(1))
        else:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                menu_map = json.loads(json_match.group(0))
            else:
                raise ValueError(f"Could not parse Gemini response as JSON: {response_text[:500]}")
    
    print(f"Parsed {len(menu_map)} days from calendar")
    return menu_map


def validate_menu_map(menu_map: dict, month_key: str) -> dict:
    """Validate and normalize the menu map."""
    year, month = map(int, month_key.split("-"))
    validated = {}
    
    for date_str, lunch in menu_map.items():
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Warning: Skipping invalid date format: {date_str}")
            continue
        
        if date.year != year or date.month != month:
            print(f"Warning: Skipping date outside target month: {date_str}")
            continue
        
        if lunch is None:
            validated[date_str] = None
        elif isinstance(lunch, str):
            lunch = lunch.strip()
            validated[date_str] = lunch if lunch else None
        else:
            print(f"Warning: Unexpected value type for {date_str}: {type(lunch)}")
            validated[date_str] = str(lunch) if lunch else None
    
    validated = dict(sorted(validated.items()))
    
    if not validated:
        raise ValueError("No valid menu entries after validation")
    
    print(f"Validated {len(validated)} menu entries")
    return validated


def write_menu_json(menu_map: dict, month_key: str) -> Path:
    """Write the menu map to data/YYYY-MM.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_path = DATA_DIR / f"{month_key}.json"
    
    with open(json_path, "w") as f:
        json.dump(menu_map, f, indent=2)
    
    print(f"Wrote menu to: {json_path}")
    return json_path


def check_if_update_needed(month_key: str) -> bool:
    json_path = DATA_DIR / f"{month_key}.json"
    if json_path.exists():
        print(f"Menu for {month_key} already exists: {json_path}")
        return False
    return True


def main():
    """Main entry point."""
    print("=" * 50)
    print("SGM Lunch Menu Updater")
    print("=" * 50)
    
    try:
        meta = get_menu_meta_from_env()
        if not meta:
            meta = fetch_menu_meta_with_playwright()
        
        print(f"Detected: {meta['month_name']} {meta['year']} ({meta['month_key']})")
        current_month_key = datetime.now().strftime("%Y-%m")
        if meta["month_key"] != current_month_key:
            print(f"Menu image still for {meta['month_key']}; waiting for {current_month_key}.")
            return 0

        if not check_if_update_needed(meta["month_key"]):
            print("No update needed. Exiting.")
            return 0
        
        image_path = download_image(meta["image_url"], meta["month_key"])
        menu_map = parse_image_with_gemini(image_path, meta["month_name"], meta["year"])
        menu_map = validate_menu_map(menu_map, meta["month_key"])
        write_menu_json(menu_map, meta["month_key"])
        
        print("=" * 50)
        print("Update complete!")
        print("=" * 50)
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
