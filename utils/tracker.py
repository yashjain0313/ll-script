"""
Tracker — View and update your outreach status
Run: python utils/tracker.py
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import TRACKER_FILE


def load_tracker() -> list[dict]:
    if not os.path.exists(TRACKER_FILE):
        return []
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def print_summary():
    rows = load_tracker()
    if not rows:
        print("📭 No outreach data yet. Run main.py first!")
        return

    # Stats
    by_company  = defaultdict(list)
    by_status   = defaultdict(int)
    for r in rows:
        by_company[r["company"]].append(r)
        by_status[r["status"]] += 1

    print("\n" + "="*55)
    print("📊  OUTREACH TRACKER SUMMARY")
    print("="*55)
    print(f"  Total connections sent : {len(rows)}")
    for status, count in by_status.items():
        emoji = {"Sent": "📤", "Accepted": "✅", "Replied": "💬"}.get(status, "•")
        print(f"  {emoji} {status:<18}: {count}")

    print("\n" + "-"*55)
    print("  By Company:")
    for company, people in by_company.items():
        statuses = [p["status"] for p in people]
        accepted = statuses.count("Accepted")
        replied  = statuses.count("Replied")
        print(f"  🏢 {company:<25} {len(people)} sent  |  {accepted} accepted  |  {replied} replied")

    print("="*55)
    print(f"\n  📁 Full data: {TRACKER_FILE}")


def mark_accepted(profile_url: str):
    """Update status of a connection to Accepted."""
    rows = load_tracker()
    updated = False
    for row in rows:
        if profile_url in row.get("profile_url", ""):
            row["status"] = "Accepted"
            updated = True
            break
    if updated:
        _write_all(rows)
        print(f"✅ Marked as Accepted: {profile_url}")
    else:
        print(f"❌ Profile not found in tracker")


def mark_replied(profile_url: str):
    """Update status of a connection to Replied."""
    rows = load_tracker()
    updated = False
    for row in rows:
        if profile_url in row.get("profile_url", ""):
            row["status"] = "Replied"
            updated = True
            break
    if updated:
        _write_all(rows)
        print(f"💬 Marked as Replied: {profile_url}")
    else:
        print(f"❌ Profile not found in tracker")


def _write_all(rows: list[dict]):
    with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "company", "name", "title", "profile_url", "status", "note_sent"
        ])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    print_summary()
