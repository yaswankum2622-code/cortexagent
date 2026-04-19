"""Mock calendar booking tool — writes to local JSON file."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


logger = logging.getLogger(__name__)
CALENDAR_FILE = Path("data/calendar_bookings.json")


def calendar_book(title: str, date: str, duration_min: int = 30) -> Dict[str, Any]:
    """
    Mock-book a calendar event. Persists to data/calendar_bookings.json.

    Real implementation would call Google Calendar API. This is a portfolio mock.
    """
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    event = {
        "event_id": event_id,
        "title": title,
        "date": date,
        "duration_min": int(duration_min),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "booked_mock",
    }

    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CALENDAR_FILE.exists():
        try:
            with open(CALENDAR_FILE, "r", encoding="utf-8") as file_obj:
                existing = json.load(file_obj)
        except Exception:
            existing = []
    else:
        existing = []

    existing.append(event)
    with open(CALENDAR_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(existing, file_obj, indent=2)

    return {
        "event_id": event_id,
        "confirmation": f"Booked: {title} on {date} ({duration_min} min)",
        "status": "success",
        "note": "Mock implementation. Real version would call Google Calendar API.",
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Calendar Tool — Smoke Test")
    print("=" * 60)
    result = calendar_book(
        title="Monitor AAPL Q1 2025 earnings call",
        date="2025-02-01",
        duration_min=45,
    )
    print(f"Status: {result['status']}")
    print(f"Event ID: {result['event_id']}")
    print(f"Confirmation: {result['confirmation']}")
    print(f"Note: {result['note']}")
    print(f"\nFile written to: {CALENDAR_FILE}")
    if CALENDAR_FILE.exists():
        with open(CALENDAR_FILE, "r", encoding="utf-8") as file_obj:
            content = json.load(file_obj)
        print(f"Total events in file: {len(content)}")
