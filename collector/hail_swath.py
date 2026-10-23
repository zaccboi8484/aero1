#!/usr/bin/env python3
"""Per-parcel hail exposure from NOAA MRMS MESH (radar-estimated hail size).

WHERE THE DATA COMES FROM
  Bucket   : s3://noaa-mrms-pds  (NOAA Open Data Dissemination, anonymous/public HTTPS)
  Product  : CONUS/MESH_Max_1440min_00.50/<YYYYMMDD>/MRMS_MESH_Max_1440min_00.50_<YYYYMMDD>-<HHMMSS>.grib2.gz
             = running 24-hour maximum of MESH, millimetres, 0.01 degree (~1 km) grid, every file gzip-compressed
  Listing  : https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&prefix=CONUS/MESH_Max_1440min_00.50/<YYYYMMDD>/
  Decoding : gunzip, then cfgrib/eccodes (pip install xarray cfgrib; apt install libeccodes-dev)

STORM-DAY DEFINITION
  The 1440-min max valid at ~12:00 UTC on day D+1 covers 12Z(D)..12Z(D+1) = 7 am..7 am Central,
  i.e. a whole afternoon/evening convective day. We use that file for "storm day D".

WHICH DAYS WE FETCH
  Not every day (1,800 files per 5 years). Candidate days = days with a NOAA Storm Events HAIL report
  in scope (evidence/data/noaa_storm_events_scoped.json). Add SPC same-day reports for the newest days
  that NCEI has not published yet (see spc_hail_days, format handled defensively).

HONESTY RULES
  MESH is a radar ESTIMATE on a ~1 km grid, not a measurement at a roof. Every record says so,
  and the value is only ever a modest, capped input to a ranking (see roof_score_v2.storm_factor).
"""
import argparse, datetime as dt, gzip, json, pathlib, re, sys, tempfile, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "evidence" / "data"
BUCKET = "https://noaa-mrms-pds.s3.amazonaws.com"
PRODUCT = "CONUS/MESH_Max_1440min_00.50"
OUT = DATA / "hail_exposure.json"
MIN_REPORT_IN = 0.25      # do not store trace values
MM_PER_IN = 25.4


def list_keys(day, opener=urllib.request.urlopen):
    """All object keys for one UTC day. S3 ListObjectsV2 XML over public HTTPS."""
    q = urllib.parse.urlencode({"list-type": "2", "prefix": f"{PRODUCT}/{day:%Y%m%d}/"})
    with opener(f"{BUCKET}/?{q}", timeout=30) as r:
        root = ET.fromstring(r.read())
    ns = {"s": root.tag.split("}")[0].strip("{")}
    return [k.text for k in root.findall(".//s:Contents/s:Key", ns)]


def pick_key(keys, hhmmss="120000"):
    """File whose timestamp is nearest the requested UTC time of day."""
    best, best_d = None, None
    for k in keys:
        m = re.search(r"_(\d{8})-(\d{6})\.grib2\.gz$", k)
        if not m:
            continue
        t = int(m[2][:2]) * 3600 + int(m[2][2:4]) * 60 + int(m[2][4:])
        want = int(hhmmss[:2]) * 3600 + int(hhmmss[2:4]) * 60 + int(hhmmss[4:])
        if best is None or abs(t - want) < best_d:
            best, best_d = k, abs(t - want)
    return best


def storm_day_key(day, lister=list_keys):
    """Key valid ~12Z on D+1 for storm day D (see module docstring)."""
    return pick_key(lister(day + dt.timedelta(days=1)))


def read_mesh_grib(path):
    """Decode one gunzipped MRMS GRIB2 -> (values_mm[lat,lon], lats, lons). Needs xarray + cfgrib."""
    import xarray as xr
    ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    da = ds[next(iter(ds.data_vars))]
    lats, lons = da["latitude"].values, da["longitude"].values
    lons = np.where(lons > 180, lons - 360, lons)
    return np.asarray(da.values, dtype=np.float32), np.asarray(lats), np.asarray(lons)


def download_grid(key, opener=urllib.request.urlopen):
    with tempfile.TemporaryDirectory() as d:
        gz = pathlib.Path(d) / "m.grib2.gz"
        with opener(f"{BUCKET}/{key}", timeout=120) as r:
            gz.write_bytes(r.read())
        raw = pathlib.Path(d) / "m.grib2"
        raw.write_bytes(gzip.decompress(gz.read_bytes()))
        return read_mesh_grib(str(raw))


def sample_points(values_mm, lats, lons, pts):
    """Nearest-cell MESH at (pin, lon, lat) points. Negative = MRMS no-data/no-coverage -> 0.
    Returns {pin: (center_in, max3x3_in)}. Pure numpy, no I/O: unit-testable."""
    lat_desc = lats[0] > lats[-1]
    out = {}
    for pin, lon, lat in pts:
        i = int(np.abs(lats - lat).argmin())
        j = int(np.abs(lons - lon).argmin())
        if abs(lats[i] - lat) > 0.02 or abs(lons[j] - lon) > 0.02:   # point is outside the grid
            continue
        win = values_mm[max(0, i - 1):i + 2, max(0, j - 1):j + 2]
        win = np.where(win < 0, 0, win)
        c = float(max(values_mm[i, j], 0))
        out[pin] = (round(c / MM_PER_IN, 2), round(float(win.max()) / MM_PER_IN, 2))
    return out


def merge_day(store, day, sampled, key):
    """Record only parcels with a non-trace value; mark the day as processed either way."""
    store["processed_days"][day.isoformat()] = {"key": key}
    for pin, (c, m) in sampled.items():
        if max(c, m) >= MIN_REPORT_IN:
            store["parcels"].setdefault(pin, []).append(
                {"event_id": f"MRMS-{day:%Y%m%d}", "date": day.isoformat(), "hail_inches": c,
                 "hail_inches_max3x3": m, "wind_mph": None})
    return store


def candidate_days(events_doc, since=None):
    days = set()
    for e in events_doc.get("events", []):
        if e.get("kind") != "HAIL":
            continue
        try:
            d = dt.date.fromisoformat(str(e.get("sort_key"))[:10])
        except ValueError:
            continue
        if since is None or d >= since:
            days.add(d)
    return sorted(days)


def spc_hail_days(day, opener=urllib.request.urlopen, state="MN"):
    """Same-day hail reports from the Storm Prediction Center, for days NCEI has not published.
    URL pattern https://www.spc.noaa.gov/climo/reports/YYMMDD_rpts_hail.csv (verify before relying on it).
    Returns the number of reports in `state`; >0 makes the day a candidate."""
    url = f"https://www.spc.noaa.gov/climo/reports/{day:%y%m%d}_rpts_hail.csv"
    try:
        with opener(url, timeout=30) as r:
            lines = r.read().decode("utf-8", "replace").splitlines()
    except Exception:
        return 0
    return sum(1 for ln in lines[1:] if ln.strip().split(",")[-3:-2] == [state] or f",{state}," in ln)


def load_store():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"format": "AERO_HAIL_EXPOSURE_V1", "parcels": {}, "processed_days": {}}


def run(max_days, lookback_years, grid_fetch=download_grid, lister=list_keys, today=None):
    today = today or dt.date.today()
    store = load_store()
    events = json.loads((DATA / "noaa_storm_events_scoped.json").read_text(encoding="utf-8"))
    recs = json.loads((DATA / "autonomous_residential_discovery.json").read_text(encoding="utf-8"))["records"]
    pts = [(r["county_pin"], r["center_lon"], r["center_lat"]) for r in recs
           if isinstance(r.get("center_lat"), (int, float)) and isinstance(r.get("center_lon"), (int, float))]
    since = today - dt.timedelta(days=int(365.25 * lookback_years))
    todo = [d for d in candidate_days(events, since) if d.isoformat() not in store["processed_days"]
            and d < today - dt.timedelta(days=1)][:max_days]
    done = 0
    for d in todo:
        key = storm_day_key(d, lister)
        if not key:
            continue                                  # not published yet: stays unprocessed, retried next run
        vals, lats, lons = grid_fetch(key)
        merge_day(store, d, sample_points(vals, lats, lons, pts), key)
        done += 1
    days = sorted(store["processed_days"])
    # Coverage = every candidate hail day in [since, through] is processed. Days with no hail report are
    # "no candidate", which is what we scan on; it is not a claim that nothing fell elsewhere.
    pending = [d for d in candidate_days(events, since) if d.isoformat() not in store["processed_days"]]
    through = (today - dt.timedelta(days=2)) if not pending else (min(pending) - dt.timedelta(days=1))
    store.update(coverage_from=since.isoformat(), coverage_through=through.isoformat(),
                 pending_candidate_days=len(pending))
    store.update(generated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 product=PRODUCT + " valid ~12Z next day (7am-7am Central storm day)",
                 meaning="Radar-ESTIMATED max hail size at the parcel's ~1 km grid cell. Not a roof strike, not damage.",
                 candidate_basis="NOAA Storm Events HAIL report days in scope",
                 processed_from=days[0] if days else None, processed_to=days[-1] if days else None)
    OUT.write_text(json.dumps(store, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"days_processed_this_run": done, "days_total": len(days), "parcels_with_hail": len(store["parcels"])}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-days", type=int, default=6)
    ap.add_argument("--lookback-years", type=int, default=5)
    a = ap.parse_args()
    print(json.dumps(run(a.max_days, a.lookback_years)))
