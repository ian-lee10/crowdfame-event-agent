import anthropic
import json
import re
from datetime import datetime, timezone
from typing import TypedDict

client = anthropic.Anthropic()

class ValidationResult(TypedDict):
    event_id: str
    legitimate: bool
    confidence: float
    flags: list[str]
    normalized: dict | None
    reasoning: str

SYSTEM_PROMPT = """You are a strict event legitimacy agent for Crowdfame.
Evaluate Facebook events for legitimacy.

REJECT if: spam, MLM, illegal, past event, vague location, gibberish, private, <20 words description
APPROVE if: real US public event, clear title/location, legitimate organizer

For APPROVED events, extract/infer the date/time from the description if timestamps are missing.
Respond ONLY with JSON array, no markdown."""

def chunk_events(events: list[dict], chunk_size: int = 15) -> list[list[dict]]:
    return [events[i:i + chunk_size] for i in range(0, len(events), chunk_size)]

def assign_ids(events: list[dict]) -> list[dict]:
    for i, e in enumerate(events):
        if "id" not in e or not e["id"]:
            e["id"] = e.get("eventId") or e.get("url", f"event_{i}").split("/")[-1] or f"event_{i}"
    return events

def validate_chunk(chunk: list[dict]) -> list[ValidationResult]:
    slim = []
    for e in chunk:
        slim.append({
            "id": e.get("id"),
            "title": e.get("name") or e.get("title"),
            "description": (e.get("description") or "")[:500],
            "startTimestamp": e.get("startTimestamp") or e.get("start_time"),
            "location": e.get("location") or e.get("place"),
            "url": e.get("url"),
            "hasImage": bool(e.get("imageUrl")),
            "organizer": e.get("hosts") or e.get("organizer"),
        })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Validate these {len(slim)} events. For missing timestamps, extract date/time from description if possible:\n{json.dumps(slim, default=str)}"
        }]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        results = json.loads(raw)
        # Add imageUrl back to normalized events
        for i, r in enumerate(results):
            if r.get("legitimate") and r.get("normalized"):
                r["normalized"]["posterImageUrl"] = chunk[i].get("imageUrl")
        return results
    except json.JSONDecodeError:
        return [{
            "event_id": ev.get("id", "unknown"),
            "legitimate": False,
            "confidence": 0.0,
            "flags": ["parse_error"],
            "reasoning": "Parse error",
            "normalized": None,
        } for ev in chunk]

def deduplicate(results: list[ValidationResult]) -> list[ValidationResult]:
    seen_urls = set()
    deduped = []
    for r in results:
        if not r["legitimate"] or not r["normalized"]:
            deduped.append(r)
            continue
        url = r["normalized"].get("sourceUrl", "")
        if url in seen_urls:
            r["legitimate"] = False
            r["normalized"] = None
        else:
            seen_urls.add(url)
        deduped.append(r)
    return deduped

def run_validation(events: list[dict]) -> tuple[list[ValidationResult], list[dict]]:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Validating {len(events)} events...")
    events = assign_ids(events)
    chunks = chunk_events(events, chunk_size=15)
    all_results: list[ValidationResult] = []
    
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}/{len(chunks)}...")
        results = validate_chunk(chunk)
        all_results.extend(results)
    
    all_results = deduplicate(all_results)
    approved = [r["normalized"] for r in all_results if r["legitimate"] and r["normalized"]]
    rejected = len(all_results) - len(approved)
    
    print(f"  ✅ Approved: {len(approved)}")
    print(f"  ❌ Rejected: {rejected}")
    
    return all_results, approved
