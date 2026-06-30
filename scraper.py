"""
scraper.py
Fetches raw Facebook event data from Apify and triggers the Apify actor run.
Rotates states by day of week: Mon=TX, Tue=CA, Wed=NY, Thu=FL, Fri=IL.
"""

import httpx
import json
import os
import time
from datetime import datetime

APIFY_TOKEN = os.environ["APIFY_TOKEN"]
APIFY_ACTOR_ID = "UZBnerCFBo5FgGouO"

MARKET_TERMS = ["vendor market", "pop-up market", "flea market", "craft fair", "artisan market", "night market"]

def build_searches(cities: list[str]) -> list[str]:
    searches = []
    for city in cities:
        for term in MARKET_TERMS:
            searches.append(f"{term} {city}")
    return searches

CITIES_BY_STATE = {
    "TX": build_searches([
        "Dallas TX", "Fort Worth TX", "Houston TX",
        "San Antonio TX", "Austin TX", "El Paso TX",
    ]),
    "CA": build_searches([
        "Los Angeles CA", "San Francisco CA", "San Diego CA",
        "San Jose CA", "Sacramento CA", "Riverside CA",
    ]),
    "NY": build_searches([
        "Manhattan NY", "Brooklyn NY", "Queens NY",
        "Buffalo NY", "Albany NY",
    ]),
    "FL": build_searches([
        "Miami FL", "Orlando FL", "Tampa FL",
        "Jacksonville FL", "Fort Lauderdale FL",
    ]),
    "IL": build_searches([
        "Chicago IL", "Aurora IL", "Rockford IL",
        "Springfield IL", "Naperville IL",
    ]),
}

# Monday=0 ... Friday=4, weekends skip
WEEKDAY_STATE = {
    0: "TX",
    1: "CA",
    2: "NY",
    3: "FL",
    4: "IL",
}


def get_today_searches() -> tuple[str, list[str]]:
    state = os.environ.get("TARGET_STATE")
    if not state:
        weekday = datetime.utcnow().weekday()
        if weekday not in WEEKDAY_STATE:
            print("  Weekend — skipping run.")
            return None, []
        state = WEEKDAY_STATE[weekday]
    return state, CITIES_BY_STATE[state]


def trigger_apify_run() -> str:
    state, searches = get_today_searches()
    if not searches:
        return None
    print(f"[{datetime.now().isoformat()}] Triggering Apify actor run for {state} ({len(searches)} cities)...")

    url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs"
    payload = {
        "searchQueries": searches,
        "maxEvents": 5,
        "startUrls": []
    }

    resp = httpx.post(
        url,
        json=payload,
        params={"token": APIFY_TOKEN},
        timeout=30
    )
    resp.raise_for_status()
    run_data = resp.json()["data"]
    run_id = run_data["id"]
    print(f"  Actor run started: {run_id}")
    return run_id


def wait_for_run(run_id: str, poll_interval: int = 30, max_wait: int = 18000) -> str:
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    elapsed = 0

    while elapsed < max_wait:
        resp = httpx.get(url, params={"token": APIFY_TOKEN}, timeout=15)
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]

        print(f"  Run status: {status} ({elapsed}s elapsed)")

        if status == "SUCCEEDED":
            return data["defaultDatasetId"]
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Apify run {run_id} did not finish within {max_wait}s")


def fetch_events(dataset_id: str) -> list[dict]:
    print(f"  Fetching events from dataset: {dataset_id}")
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    resp = httpx.get(
        url,
        params={"token": APIFY_TOKEN, "format": "json", "limit": 10000},
        timeout=60
    )
    resp.raise_for_status()
    events = resp.json()
    print(f"  Retrieved {len(events)} raw events")
    return events


def run_scraper() -> list[dict]:
    run_id = trigger_apify_run()
    if run_id is None:
        return []
    dataset_id = wait_for_run(run_id)
    return fetch_events(dataset_id)


if __name__ == "__main__":
    events = run_scraper()
    with open("/tmp/raw_events.json", "w") as f:
        json.dump(events, f, indent=2)
    print(f"Saved {len(events)} raw events to /tmp/raw_events.json")
