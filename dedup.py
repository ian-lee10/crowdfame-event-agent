"""
dedup.py
Two-stage deduplication for the Crowdfame event pipeline:

  Stage 1 — URL check (before AI validation):
    Skips raw events whose Facebook URL was already submitted.

  Stage 2 — Title+date check (after AI validation, before posting):
    Skips normalized events whose (title, date) combo already exists,
    regardless of URL. This catches the same event re-scraped on a
    different day. A recurring event (same name, different date) passes
    through because the date differs.

Cache file: logs/seen_events.json
  {
    "url::https://facebook.com/events/123": "2026-06-29",
    "event::vagabond vintage market::2026-07-12": "2026-06-29"
  }
Entries older than EXPIRY_DAYS are pruned on each run.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

CACHE_PATH = Path("logs/seen_events.json")
EXPIRY_DAYS = 90


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


def _prune(cache: dict[str, str]) -> dict[str, str]:
    cutoff = (date.today() - timedelta(days=EXPIRY_DAYS)).isoformat()
    return {k: v for k, v in cache.items() if v >= cutoff}


def _url_key(event: dict) -> str | None:
    url = event.get("url") or event.get("eventUrl") or event.get("link") or ""
    url = url.strip()
    return f"url::{url}" if url else None


def _title_date_key(event: dict) -> str | None:
    """Normalized title+date key from a validated/normalized event dict."""
    title = event.get("title") or ""
    event_date = event.get("date") or ""
    if not title or not event_date:
        return None
    # Normalize title: lowercase, collapse whitespace, strip punctuation
    normalized = re.sub(r"[^\w\s]", "", title.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f"event::{normalized}::{event_date}"


# ── Stage 1: URL-based pre-filter ─────────────────────────────────────────────

def filter_new_events(raw_events: list[dict]) -> list[dict]:
    """Skip raw events whose Facebook URL is already in the cache."""
    cache = _prune(_load())

    new_events = []
    for event in raw_events:
        key = _url_key(event)
        if not key or key not in cache:
            new_events.append(event)

    skipped = len(raw_events) - len(new_events)
    if skipped:
        print(f"  Dedup (URL): skipped {skipped} already-seen events, {len(new_events)} new")

    return new_events


# ── Stage 2: Title+date post-validation filter ────────────────────────────────

def filter_approved_events(approved_events: list[dict]) -> list[dict]:
    """
    Skip normalized events whose (title, date) already exists in the cache.
    Recurring events with the same name but a different date pass through.
    """
    cache = _prune(_load())

    new_events = []
    for event in approved_events:
        key = _title_date_key(event)
        if not key or key not in cache:
            new_events.append(event)
        else:
            print(f"  Dedup (title+date): skipping '{event.get('title')}' on {event.get('date')} — already posted")

    skipped = len(approved_events) - len(new_events)
    if skipped:
        print(f"  Dedup (title+date): skipped {skipped} duplicate events")

    return new_events


# ── Mark posted ───────────────────────────────────────────────────────────────

def mark_posted(raw_events: list[dict], approved_events: list[dict]):
    """
    Record both URL keys (from raw events) and title+date keys (from
    normalized approved events) so future runs skip them.
    """
    cache = _prune(_load())
    today = date.today().isoformat()

    for event in raw_events:
        key = _url_key(event)
        if key:
            cache[key] = today

    for event in approved_events:
        key = _title_date_key(event)
        if key:
            cache[key] = today

    _save(cache)
    print(f"  Dedup cache updated: {len(cache)} total entries")
