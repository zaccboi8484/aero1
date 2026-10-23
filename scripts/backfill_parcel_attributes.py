#!/usr/bin/env python3
"""Backfill source use-type attributes, ZIP and an imagery bbox onto parcels the
crawler stored BEFORE schema discovery existed (all had blank land_use).

Resumable by construction: a record is "done" once it has `class_basis`. Each
run handles as many as the time budget allows, so the 15-minute cron drains the
backlog on its own. Writes atomically; never invents a value.
"""
import argparse, json, pathlib, sys, time, urllib.parse, urllib.request, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
import residential_classifier as rc  # noqa: E402

OUT = ROOT / "evidence" / "data" / "autonomous_residential_discovery.json"
QUERY = rc.LAYER + "/query"
PAD_LON, PAD_LAT, MAX_HW, MAX_HH = 0.00035, 0.00025, 0.0006, 0.00045


def fetch(pins, out_fields):
    quoted = ",".join("'" + p.replace("'", "") + "'" for p in pins)
    params = {"f": "json", "where": f"COUNTY_PIN IN ({quoted})", "outFields": out_fields,
              "returnGeometry": "true", "outSR": "4326"}
    req = urllib.request.Request(QUERY + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "AeroLeadAI-public-data-research/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                v = json.load(r)
            if v.get("error"):
                raise RuntimeError(str(v["error"])[:200])
            return v.get("features", [])
        except Exception as exc:  # network, JSON, ArcGIS error: retry then give up on this batch
            if attempt == 2:
                print("batch failed:", type(exc).__name__, exc, flush=True)
                return None
            time.sleep(3 * 2 ** attempt)


def apply(rec, feature, use_fields):
    a = feature.get("attributes") or {}
    pts = [(x, y) for ring in (feature.get("geometry") or {}).get("rings", []) for x, y in ring]
    cls = rc.classify(a, use_fields, rec.get("year_built") or a.get("YEAR_BUILT"))
    rec.update(use_attrs=cls["use_attrs"], residential_class=cls["residential_class"],
               class_basis=cls["basis"], residential_likelihood=cls["residential_likelihood"],
               single_family_verified=cls["single_family_verified"],
               non_residential_verified=cls["non_residential_verified"])
    z = str(a.get("ZIP") or "").strip()[:5]
    if z:
        rec["zip"] = z
    if pts and not rec.get("bbox_4326"):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        lon, lat = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        hw = min((max(xs) - min(xs)) / 2 + PAD_LON, MAX_HW)
        hh = min((max(ys) - min(ys)) / 2 + PAD_LAT, MAX_HH)
        rec["bbox_4326"] = [round(lon - hw, 7), round(lat - hh, 7), round(lon + hw, 7), round(lat + hh, 7)]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-seconds", type=int, default=420)
    ap.add_argument("--batch", type=int, default=100)
    a = ap.parse_args()
    schema = rc.load_or_discover()
    use_fields = schema["use_fields"]
    if not use_fields:
        print("No use-type fields on the layer; nothing to backfill.", schema["warning"])
        return 0
    out_fields = ",".join(["OBJECTID", "COUNTY_PIN", "ZIP", "YEAR_BUILT"] + use_fields)
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    recs = {r["county_pin"]: r for r in doc["records"]}
    todo = [p for p, r in recs.items() if "class_basis" not in r]
    start, done = time.time(), 0
    for i in range(0, len(todo), a.batch):
        if time.time() - start > a.budget_seconds:
            break
        pins = todo[i:i + a.batch]
        feats = fetch(pins, out_fields)
        if feats is None:
            continue
        seen = set()
        for f in feats:
            pin = str((f.get("attributes") or {}).get("COUNTY_PIN") or "").strip()
            if pin in recs:
                apply(recs[pin], f, use_fields)
                seen.add(pin)
        for pin in pins:  # source returned nothing: record that, so it is not retried forever
            if pin not in seen:
                recs[pin].update(class_basis="SOURCE_RETURNED_NO_ROW", residential_class="UNKNOWN",
                                 residential_likelihood=rc.likelihood("UNKNOWN", recs[pin].get("year_built"), dt.datetime.now().year))
        done += len(pins)
        time.sleep(0.25)
    doc["records"] = sorted(recs.values(), key=lambda r: r["county_pin"])
    doc["schema_use_fields"] = use_fields
    doc["backfill_remaining"] = sum("class_basis" not in r for r in doc["records"])
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    by = {}
    for r in doc["records"]:
        by[r.get("residential_class", "UNCLASSIFIED")] = by.get(r.get("residential_class", "UNCLASSIFIED"), 0) + 1
    print(json.dumps({"processed": done, "remaining": doc["backfill_remaining"], "classes": by}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
