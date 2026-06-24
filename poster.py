"""
poster.py
Takes validated, normalized events and POSTs them to the Crowdfame API.
Handles retries, rate limiting, and reports results.
"""

import httpx
import json
import os
import time
from datetime import datetime, timezone

CROWDFAME_API_URL = os.environ["CROWDFAME_API_URL"]      # e.g. https://api.crowdfame.com/v1
CROWDFAME_API_KEY = os.environ["CROWDFAME_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {CROWDFAME_API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "CrowdfameEventAgent/1.0",
}

MAX_RETRIES = 3
RETRY_DELAY = 5        # seconds between retries
RATE_LIMIT_PAUSE = 1   # seconds between successful POSTs to avoid hammering the API


def run_poster(approved_events: list[dict]) -> dict:
    """POST all approved events to Crowdfame API as a single batch."""
    approved_events = [e for e in approved_events if e.get("title") and e.get("date")]
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Posting {len(approved_events)} approved events to Crowdfame API...")

    report = {
        "timestamp": now,
        "total": len(approved_events),
        "created": 0,
        "duplicates": 0,
        "errors": 0,
        "invalid": 0,
        "details": []
    }

    url = f"{CROWDFAME_API_URL}/events"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client() as client:
                resp = client.post(url, json=approved_events, headers=HEADERS, timeout=30)

            if resp.status_code == 201:
                data = resp.json()
                report["created"] = data.get("created", 0)
                report["duplicates"] = data.get("skipped", 0)
                print(f"  ✅ Created: {report['created']}, ⏭️  Skipped (duplicates): {report['duplicates']}")
                break
            elif resp.status_code == 422:
                print(f"  ❌ Validation error from API: {resp.text}")
                break
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                print(f"    Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
            else:
                resp.raise_for_status()

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt < MAX_RETRIES:
                print(f"    Attempt {attempt} failed ({e}). Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                report["errors"] = len(approved_events)
                print(f"  ❌ All events failed: {e}")

    print(f"\n  Summary: {report['created']} created, {report['duplicates']} duplicates, "
          f"{report['invalid']} invalid, {report['errors']} errors")

    return report


if __name__ == "__main__":
    with open("/tmp/approved_events.json") as f:
        approved = json.load(f)

    report = run_poster(approved)

    with open("/tmp/post_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to /tmp/post_report.json")
