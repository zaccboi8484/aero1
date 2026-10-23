#!/usr/bin/env python3
"""New hail day -> targeted alert list, rescoring only what the storm touched.

Run after collector/hail_swath.py and scripts/roof_score_v2.py. A hail "event" is a processed MRMS
storm day; it is alerted once per event_id (state in evidence/data/storm_alerts_state.json).
Parcels qualify when their own grid cell's MESH >= MIN_IN. The list is a review/outreach ORDER,
not a damage list: every row carries the reminder.
"""
import csv, json, pathlib

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
MIN_IN = 1.0


def new_events(store, seen):
    ids = {e["event_id"] for evs in store.get("parcels", {}).values() for e in evs
           if (e.get("hail_inches") or 0) >= MIN_IN}
    return sorted(ids - set(seen))


def alerts(store, scores, event_ids, top=200):
    """Rows for tier A/B parcels hit by any of `event_ids`, best first."""
    by_pin = {r["county_pin"]: r for r in scores["records"] if r.get("prospecting_priority") is not None}
    rows = []
    for pin, evs in store.get("parcels", {}).items():
        hit = [e for e in evs if e["event_id"] in event_ids and (e.get("hail_inches") or 0) >= MIN_IN]
        s = by_pin.get(pin)
        if hit and s and s.get("tier") in ("A", "B"):
            rows.append({"county_pin": pin, "address": s.get("address"), "tier": s["tier"],
                         "prospecting_priority": s["prospecting_priority"], "event_id": hit[0]["event_id"],
                         "mrms_mesh_in": max(e["hail_inches"] for e in hit),
                         "note": "Radar-estimated hail at ~1 km cell; not damage, not a roof finding"})
    rows.sort(key=lambda r: (-r["prospecting_priority"], r["county_pin"]))
    return rows[:top]


def main():
    store = json.loads((DATA / "hail_exposure.json").read_text(encoding="utf-8"))
    scores = json.loads((DATA / "roof_priority_v2.json").read_text(encoding="utf-8"))
    sp = DATA / "storm_alerts_state.json"
    try:
        seen = json.loads(sp.read_text(encoding="utf-8")).get("seen", [])
    except (OSError, ValueError):
        seen = []
    fresh = new_events(store, seen)
    if not fresh:
        print(json.dumps({"new_events": 0}))
        return
    rows = alerts(store, scores, set(fresh))
    with (DATA / "storm_alerts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["county_pin", "address", "tier", "prospecting_priority", "event_id", "mrms_mesh_in", "note"])
        w.writeheader()
        w.writerows(rows)
    sp.write_text(json.dumps({"seen": sorted(set(seen) | set(fresh))}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"new_events": len(fresh), "alert_rows": len(rows)}))


if __name__ == "__main__":
    main()
