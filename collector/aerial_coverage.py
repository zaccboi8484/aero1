#!/usr/bin/env python3
"""Uncapped, resumable MnGeo aerial coverage for every crawled parcel.

Replaces the 60-parcel ceiling in collect_mngeo_aerial.py for the autonomous
pipeline (that script still owns the original 60). Same approved WMS layers,
same JPEG validation, same rule: a valid JPEG proves the image is reachable,
NOT roof condition.

 * Spends the per-run budget where it matters first: verified single-family,
   then by residential_likelihood. Non-residential is never fetched.
 * Pixels are NOT committed (see docs/IMAGERY_SOURCE_LICENSE_GATE). The ledger
   stores sha256 + bytes + layer + bbox; URLs are rebuilt on demand. With
   --chip-dir the JPEG is written to a local, git-ignored directory for the
   feature step in the same job.
 * --both-vintages fetches met25 AND dak23 so year-over-year change can be
   measured. Without it the first layer that answers is used.
"""
import argparse, concurrent.futures as cf, datetime as dt, hashlib, json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
import collect_mngeo_aerial as mn  # noqa: E402  (approved layers + url builder)

DATA = ROOT / "evidence" / "data"
SRC = DATA / "autonomous_residential_discovery.json"
LEDGER = DATA / "aerial_coverage_ledger.json"
VINTAGES = ("met25", "dak23")  # 2025 metro 1 ft, 2023 Dakota 6 in
DEFAULT_PAD = (0.0007, 0.0004)


def bbox_of(rec):
    b = rec.get("bbox_4326")
    if isinstance(b, list) and len(b) == 4 and b[0] < b[2] and b[1] < b[3]:
        return b
    lat, lon = rec.get("center_lat"), rec.get("center_lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return [round(lon - DEFAULT_PAD[0], 7), round(lat - DEFAULT_PAD[1], 7),
                round(lon + DEFAULT_PAD[0], 7), round(lat + DEFAULT_PAD[1], 7)]
    return None


def order(records, ledger, now, refresh_days=180):
    """Pins to fetch, best first. Pure function so it is unit-testable."""
    cutoff = now - dt.timedelta(days=refresh_days)
    fresh, stale, missing = set(), [], []
    for r in records:
        pin = r.get("county_pin")
        if not pin or r.get("non_residential_verified") or r.get("residential_class") == "NONRESIDENTIAL":
            continue
        if bbox_of(r) is None:
            continue
        e = ledger.get(pin)
        if e is None:
            missing.append(r)
        else:
            try:
                ok = dt.datetime.fromisoformat(e["checked_at_utc"]) > cutoff
            except (KeyError, ValueError):
                ok = False
            (fresh.add(pin) if ok else stale.append(r))
    key = lambda r: (not r.get("single_family_verified"), -(r.get("residential_likelihood") or 0), r["county_pin"])
    return [r["county_pin"] for r in sorted(missing, key=key)] + [r["county_pin"] for r in sorted(stale, key=key)]


def fetch_chip(link, opener=urllib.request.urlopen):
    req = urllib.request.Request(link, headers={"User-Agent": "AeroLeadAI-SourceAudit/2.0", "Accept": "image/jpeg"})
    with opener(req, timeout=15) as r:
        payload = r.read(2500001)
    if not (150 < len(payload) <= 2500000 and payload[:3] == b"\xff\xd8\xff" and payload[-2:] == b"\xff\xd9"):
        raise ValueError("source response not a valid JPEG")
    return payload


def probe(rec, both, chip_dir, fetcher=fetch_chip):
    pin, bbox = rec["county_pin"], bbox_of(rec)
    entry = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "bbox_4326": bbox,
             "layers": {}, "preferred_layer": None, "status": "NOT_VERIFIED",
             "locally_downloaded": False, "resale_or_redistribution_rights_verified": False}
    for layer in VINTAGES:
        link = mn.url(bbox, layer)
        try:
            payload = fetcher(link)
            entry["layers"][layer] = {"status": "REMOTE_IMAGE_VERIFIED", "bytes": len(payload),
                                      "sha256": hashlib.sha256(payload).hexdigest()}
            entry["preferred_layer"] = entry["preferred_layer"] or layer
            if chip_dir:
                pathlib.Path(chip_dir).mkdir(parents=True, exist_ok=True)
                (pathlib.Path(chip_dir) / f"{pin}__{layer}.jpg").write_bytes(payload)
            if not both:
                break
        except Exception as exc:
            entry["layers"][layer] = {"status": "SOURCE_ERROR", "error": str(exc)[:120]}
    if entry["preferred_layer"]:
        entry["status"] = "REMOTE_IMAGE_VERIFIED"
    return pin, entry


def run(max_parcels, budget_seconds, workers, both, chip_dir, now=None, fetcher=fetch_chip):
    now = now or dt.datetime.now(dt.timezone.utc)
    recs = json.loads(SRC.read_text(encoding="utf-8"))["records"]
    by_pin = {r["county_pin"]: r for r in recs}
    try:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8")).get("records", {})
    except (OSError, ValueError):
        ledger = {}
    queue = order(recs, ledger, now)[:max_parcels]
    start, done, errors, consecutive = time.time(), 0, 0, 0
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(queue), workers * 4):
            if time.time() - start > budget_seconds or consecutive >= 8:  # budget / circuit breaker
                break
            futs = [pool.submit(probe, by_pin[p], both, chip_dir, fetcher) for p in queue[i:i + workers * 4]]
            for f in futs:
                pin, entry = f.result()
                ledger[pin] = entry
                done += 1
                if entry["status"] == "REMOTE_IMAGE_VERIFIED":
                    consecutive = 0
                else:
                    errors += 1
                    consecutive += 1
            time.sleep(0.2)
    out = {"format": "AERO_AERIAL_COVERAGE_LEDGER_V1", "generated_at_utc": now.isoformat(),
           "service_url": mn.BASE,
           "note": "A verified JPEG response proves a reachable government image, NOT roof, tree or driveway condition.",
           "verified": sum(e["status"] == "REMOTE_IMAGE_VERIFIED" for e in ledger.values()),
           "total_in_ledger": len(ledger), "records": ledger}
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(LEDGER)
    return {"probed_this_run": done, "errors": errors, "ledger_total": len(ledger), "verified": out["verified"],
            "still_unfetched": max(0, len(order(recs, ledger, now)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-parcels", type=int, default=400)
    ap.add_argument("--budget-seconds", type=int, default=480)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--both-vintages", action="store_true")
    ap.add_argument("--chip-dir", default=None)
    a = ap.parse_args()
    print(json.dumps(run(a.max_parcels, a.budget_seconds, a.workers, a.both_vintages, a.chip_dir)))


if __name__ == "__main__":
    main()
