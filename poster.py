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


def post_event(event: dict, client: httpx.Client) -> dict:
    """POST a single event to the Crowdfame API with retries."""
    url = f"{CROWDFAME_API_URL}/events"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.post(url, json=event, headers=HEADERS, timeout=15)

            if resp.status_code == 201:
                return {"status": "created", "id": resp.json().get("id"), "event": event["title"]}
            elif resp.status_code == 409:
                return {"status": "duplicate", "event": event["title"]}
            elif resp.status_code == 422:
                return {"status": "invalid", "event": event["title"], "detail": resp.text}
            elif resp.status_code == 429:
                # Rate limited — back off
                retry_after = int(resp.headers.get("Retry-After", 60))
                print(f"    Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            else:
                resp.raise_for_status()

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt < MAX_RETRIES:
                print(f"    Attempt {attempt} failed ({e}). Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                return {"status": "error", "event": event.get("title", "unknown"), "detail": str(e)}

    return {"status": "error", "event": event.get("title", "unknown"), "detail": "Max retries exceeded"}


def run_poster(approved_events: list[dict]) -> dict:
    """
    POST all approved events to Crowdfame API.
    Returns a summary report.
    """
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

    with httpx.Client() as client:
        for i, event in enumerate(approved_events):
            result = post_event(event, client)
            report["details"].append(result)

            status = result["status"]
            if status == "created":
                report["created"] += 1
                print(f"  [{i+1}/{len(approved_events)}] ✅ Created: {event.get('title')}")
            elif status == "duplicate":
                report["duplicates"] += 1
                print(f"  [{i+1}/{len(approved_events)}] ⏭️  Duplicate: {event.get('title')}")
            elif status == "invalid":
                report["invalid"] += 1
                print(f"  [{i+1}/{len(approved_events)}] ⚠️  Invalid: {event.get('title')} — {result.get('detail')}")
            else:
                report["errors"] += 1
                print(f"  [{i+1}/{len(approved_events)}] ❌ Error: {event.get('title')} — {result.get('detail')}")

            time.sleep(RATE_LIMIT_PAUSE)

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
