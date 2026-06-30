"""
dedup.py
Tracks Facebook event URLs already submitted to Crowdfame so we don't
re-validate or re-post them on subsequent days.

Cache file: logs/seen_events.json
  { "https://facebook.com/events/123": "2026-06-29" }
Entries older than EXPIRY_DAYS are pruned on each run (events don't recur).
"""

import json
from datetime import date, timedelta
from pathlib import Path

CACHE_PATH = Path("logs/seen_events.json")
EXPIRY_DAYS = 60


def _load() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(cache: dict[str, str]):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _event_url(event: dict) -> str | None:
    """Extract canonical Facebook event URL from a raw Apify event dict."""
    url = event.get("url") or event.get("eventUrl") or event.get("link") or ""
    return url.strip() or None


def filter_new_events(raw_events: list[dict]) -> list[dict]:
    """Return only events not already in the seen cache. Prunes stale entries."""
    cache = _load()
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=EXPIRY_DAYS)).isoformat()

    # Prune old entries
    cache = {url: seen_on for url, seen_on in cache.items() if seen_on >= cutoff}

    new_events = []
    for event in raw_events:
        url = _event_url(event)
        if not url or url not in cache:
            new_events.append(event)

    skipped = len(raw_events) - len(new_events)
    if skipped:
        print(f"  Dedup: skipped {skipped} already-seen events, {len(new_events)} new")

    return new_events


def mark_posted(events: list[dict]):
    """Record URLs of events we successfully submitted."""
    cache = _load()
    today = date.today().isoformat()
    for event in events:
        url = _event_url(event)
        if url:
            cache[url] = today
    _save(cache)
    print(f"  Dedup cache updated: {len(cache)} total seen events")
