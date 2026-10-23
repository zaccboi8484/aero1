#!/usr/bin/env python3
"""Join source-backed parcel evidence into one Mindex property card per county PIN.
No inferred roof damage, ownership, permit, or value is represented as verified.
"""
import datetime as dt
import json
import pathlib
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "evidence" / "data"

def read(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default

def as_records(doc):
    rows = doc.get("records", []) if isinstance(doc, dict) else []
    if isinstance(rows, dict):
        return [dict(v, county_pin=k) for k, v in rows.items() if isinstance(v, dict)]
    return rows if isinstance(rows, list) else []

def index(doc):
    return {str(r["county_pin"]): r for r in as_records(doc) if r.get("county_pin")}

def status(value, source=None):
    if value is None or value == "" or value == "NOT_VERIFIED":
        return {"status": "UNKNOWN", "value": None, "source": source}
    return {"status": "SOURCE_RECORDED", "value": value, "source": source}

def street_view(lat, lon):
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=" + urllib.parse.quote(f"{lat},{lon}")

def run():
    discovery = index(read("autonomous_residential_discovery.json", {}))
    scored = index(read("roof_priority_v2.json", {}))
    aerial = index(read("aerial_coverage_ledger.json", {}))
    enrichment = index(read("live_property_enrichment.json", {}))
    permits = index(read("roof_permit_backfill_2025.json", {}))
    storms = read("zcta_storm_index.json", {})
    storm_by_zip = {str(x.get("zcta")): x.get("reports", []) for x in storms.get("events_by_zip", []) if isinstance(x, dict)}
    covered_zip = {str(x.get("zcta")) for x in storms.get("zip_areas", []) if isinstance(x, dict)}
    footprints = read("building_footprints.json", {}).get("records", {})
    aerial_source = read("aerial_coverage_ledger.json", {}).get("service_url")
    cards = []
    for pin, p in sorted(discovery.items()):
        lat, lon = p.get("center_lat"), p.get("center_lon")
        s, a, e, perm = scored.get(pin, {}), aerial.get(pin, {}), enrichment.get(pin, {}), permits.get(pin, {})
        valuation = e.get("valuation") if isinstance(e.get("valuation"), dict) else {}
        owner = e.get("ownership") if isinstance(e.get("ownership"), dict) else {}
        zip_code = str(p.get("zip") or "")
        scored_priority = s.get("prospecting_priority")
        card = {
            "county_pin": pin, "parcel_objectid": p.get("parcel_objectid"), "address": p.get("address"),
            "location": {"lat": lat, "lon": lon, "bbox_4326": p.get("bbox_4326")},
            "street_view_url": street_view(lat, lon),
            "residential": {"class": p.get("residential_class", "UNKNOWN"),
                            "verified_single_family": p.get("single_family_verified") is True,
                            "source_attributes": p.get("use_attrs") or {},
                            "source": p.get("source")},
            "mindex": {"prospecting_priority": scored_priority, "tier": s.get("tier"), "rank": s.get("rank"),
                       "confidence": s.get("confidence"), "factors": s.get("factors") or {},
                       "flags": s.get("flags") or [], "not_a_damage_score": True,
                       "condition_claim": "NONE"},
            "imagery": {"status": a.get("status", "NOT_VERIFIED"), "preferred_layer": a.get("preferred_layer"),
                        "layers": a.get("layers") or {}, "source": aerial_source},
            "permit": {"status": "SOURCE_RECORDED" if perm.get("matched_roof_permits") else "UNKNOWN",
                       "matched_roof_permits": perm.get("matched_roof_permits") or [],
                       "note": "No match does not establish that no permit exists."},
            "storm": {"status": "ZIP_REPORTS_AVAILABLE" if zip_code in covered_zip else "UNKNOWN",
                      "zip": zip_code, "reports": storm_by_zip.get(zip_code, []),
                      "note": "ZIP-level event proximity does not establish parcel damage."},
            "ownership": status(owner.get("recorded_owner") if owner else None),
            "valuation": status(valuation if valuation.get("gatekeeper") == "SOURCE_RECORDED" else None),
            "building_footprint": footprints.get(pin, {}),
            "roof_condition": {"status": "NOT_VERIFIED", "note": "Human-reviewed close-range evidence required."},
            "source_recorded_at_utc": p.get("last_seen_utc")
        }
        cards.append(card)
    assert len(cards) == len(discovery), "Parcel deduplication failed"
    assert all(c["county_pin"] and c["mindex"]["condition_claim"] == "NONE" for c in cards)
    result = {"format": "AERO_MINDEX_PROPERTY_CARDS_V1", "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "count": len(cards), "ranked": sum(c["mindex"]["prospecting_priority"] is not None for c in cards),
              "imagery_verified": sum(c["imagery"]["status"] == "REMOTE_IMAGE_VERIFIED" for c in cards),
              "cards": cards}
    out = DATA / "mindex_property_cards.json"
    out.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return {k: result[k] for k in ("count", "ranked", "imagery_verified")}

if __name__ == "__main__":
    print(json.dumps(run()))
