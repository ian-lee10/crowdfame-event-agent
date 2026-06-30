"""
poster.py
Takes validated, normalized events and POSTs them to the Crowdfame API.
"""

import httpx
import os
import time
from datetime import datetime, timezone

CROWDFAME_API_URL = os.environ["CROWDFAME_API_URL"]  # e.g. https://app.crowdfame.com/api/external-events
CROWDFAME_API_KEY = os.environ["CROWDFAME_API_KEY"]

HEADERS = {
    "x-api-key": CROWDFAME_API_KEY,
    "Content-Type": "application/json",
}

MAX_RETRIES = 3
RETRY_DELAY = 5
BATCH_SIZE = 50  # API max per request


def run_poster(approved_events: list[dict]) -> dict:
    approved_events = [e for e in approved_events if e.get("title") and e.get("date")]
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Posting {len(approved_events)} approved events to Crowdfame API...")

    report = {"timestamp": now, "total": len(approved_events), "created": 0, "updated": 0, "failed": 0, "details": []}

    # Split into batches of 50 (API limit)
    batches = [approved_events[i:i + BATCH_SIZE] for i in range(0, len(approved_events), BATCH_SIZE)]

    for batch_num, batch in enumerate(batches, 1):
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch)} events)...")
        _post_batch(batch, report)

    print(f"\n  Summary: {report['created']} created, {report['updated']} updated, {report['failed']} failed")
    return report


def _post_batch(batch: list[dict], report: dict):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(CROWDFAME_API_URL, json=batch, headers=HEADERS, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("summary", {})
                report["created"] += summary.get("created", 0)
                report["updated"] += summary.get("updated", 0)
                report["failed"] += summary.get("failed", 0)
                report["details"].extend(data.get("results", []))
                print(f"    ✅ created={summary.get('created', 0)}, updated={summary.get('updated', 0)}, failed={summary.get('failed', 0)}")
                return
            elif resp.status_code == 401:
                raise RuntimeError("Invalid or missing API key (401)")
            elif resp.status_code == 400:
                raise RuntimeError(f"Bad request: {resp.text}")
            elif resp.status_code == 413:
                raise RuntimeError("Batch too large (>50 events)")
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
                report["failed"] += len(batch)
                print(f"  ❌ Batch failed after {MAX_RETRIES} attempts: {e}")
