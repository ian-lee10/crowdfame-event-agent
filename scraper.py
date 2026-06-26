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

CITIES_BY_STATE = {
    "TX": [
        # DFW Metro
        "events Dallas TX",
        "events Fort Worth TX",
        "events Arlington TX",
        "events Plano TX",
        "events Frisco TX",
        "events McKinney TX",
        "events Irving TX",
        "events Garland TX",
        "events Denton TX",
        "events Grand Prairie TX",
        # Houston Metro
        "events Houston TX",
        "events Sugar Land TX",
        "events The Woodlands TX",
        "events Pasadena TX",
        # San Antonio Metro
        "events San Antonio TX",
        "events New Braunfels TX",
        # Austin Metro
        "events Austin TX",
        "events Round Rock TX",
        "events Cedar Park TX",
        # Other major TX cities
        "events El Paso TX",
        "events Lubbock TX",
        "events Amarillo TX",
        "events Corpus Christi TX",
        "events Waco TX",
        "events Midland TX",
    ],
    "CA": [
        # LA Metro
        "events Los Angeles CA",
        "events Long Beach CA",
        "events Anaheim CA",
        "events Santa Ana CA",
        "events Riverside CA",
        "events San Bernardino CA",
        "events Glendale CA",
        "events Pasadena CA",
        # Bay Area
        "events San Francisco CA",
        "events San Jose CA",
        "events Oakland CA",
        "events Berkeley CA",
        "events Fremont CA",
        "events Santa Clara CA",
        # San Diego
        "events San Diego CA",
        "events Chula Vista CA",
        # Other
        "events Sacramento CA",
        "events Fresno CA",
        "events Bakersfield CA",
        "events Stockton CA",
    ],
    "NY": [
        # NYC Boroughs
        "events Manhattan NY",
        "events Brooklyn NY",
        "events Queens NY",
        "events Bronx NY",
        "events Staten Island NY",
        # NYC Suburbs
        "events Yonkers NY",
        "events White Plains NY",
        "events Hempstead NY",
        # Upstate
        "events Buffalo NY",
        "events Rochester NY",
        "events Albany NY",
        "events Syracuse NY",
        "events Niagara Falls NY",
        "events Saratoga Springs NY",
    ],
    "FL": [
        # Miami Metro
        "events Miami FL",
        "events Fort Lauderdale FL",
        "events Boca Raton FL",
        "events West Palm Beach FL",
        "events Hialeah FL",
        # Orlando Metro
        "events Orlando FL",
        "events Kissimmee FL",
        "events Sanford FL",
        # Tampa Bay
        "events Tampa FL",
        "events St Petersburg FL",
        "events Clearwater FL",
        "events Sarasota FL",
        # Other
        "events Jacksonville FL",
        "events Tallahassee FL",
        "events Gainesville FL",
        "events Pensacola FL",
        "events Fort Myers FL",
    ],
    "IL": [
        # Chicago Metro
        "events Chicago IL",
        "events Naperville IL",
        "events Aurora IL",
        "events Joliet IL",
        "events Evanston IL",
        "events Waukegan IL",
        "events Elgin IL",
        "events Schaumburg IL",
        "events Oak Park IL",
        # Downstate
        "events Rockford IL",
        "events Peoria IL",
        "events Springfield IL",
        "events Champaign IL",
    ],
}

# Monday=0 ... Friday=4, weekend days fall back to TX
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
        "maxEvents": 30,
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


def wait_for_run(run_id: str, poll_interval: int = 15, max_wait: int = 600) -> str:
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
