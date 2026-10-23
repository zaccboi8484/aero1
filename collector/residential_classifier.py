#!/usr/bin/env python3
"""Residential classification from SOURCE parcel attributes.

Why this exists: the autonomous crawler asked the Met Council parcel layer for
LAND_USE / USE_CODE / PROPERTY_TYPE. All 4,430 crawled records came back blank,
so nothing could ever be "single_family_verified". This module discovers which
use-type fields the layer REALLY exposes (from its own ?f=json metadata) and
classifies from those values.

Gate rules kept from the rest of the repo:
  * VERIFIED means the source text/units say so. Never inferred.
  * `residential_likelihood` is a separate, unverified 0-1 ranking aid.
  * Nothing here says anything about roof condition.
"""
import datetime as dt
import json
import pathlib
import re
import urllib.parse
import urllib.request

LAYER = "https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2"
SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data" / "parcel_schema.json"

# Field-name fragments that usually carry use/dwelling type. Matched against
# name AND alias of the fields the layer actually reports.
USE_FIELD_HINTS = ("USECLASS", "USE_CLASS", "USE1", "USE2", "USE_DESC", "LAND_USE", "LANDUSE",
                   "PROPERTY_TYPE", "PROP_TYPE", "PROPTYPE", "DWELL", "BLDG_TYPE", "BUILDING_TYPE",
                   "PARC_CODE", "PROP_CLASS", "CLASS_CODE", "HOMESTEAD", "NUM_UNITS", "UNITS")
EXCLUDE_FIELD_HINTS = ("SHAPE", "OBJECTID", "GLOBALID", "PIN", "OWNER", "ADD_L", "PHONE", "SALE")
MAX_USE_FIELDS = 12

NONRES = ("COMMERCIAL", "INDUSTRIAL", "SCHOOL", "WAREHOUSE", "OFFICE", "RETAIL", "CHURCH",
          "RELIGIOUS", "EXEMPT", "GOVERNMENT", "PUBLIC", "PARK", "UTILITY", "RAILROAD",
          "AGRICULT", "GOLF", "HOSPITAL", "HOTEL", "MOTEL", "CEMETERY", "INSTITUTION",
          "CHARITABLE", "RECREATION", "WETLAND")
MULTI = ("APARTMENT", "MULTI", "MULTIFAMILY", "TRIPLEX", "FOURPLEX", "4-PLEX", "3-PLEX", "4 PLEX")
TOWN = ("TOWNHOME", "TOWNHOUSE", "TOWN HOUSE", "TWNHM", "TWNHSE", "ROW HOUSE")
CONDO = ("CONDO", "COOP", "CO-OP")
DUPLEX = ("DUPLEX", "TWO FAMILY", "2 FAMILY", "TWO-FAMILY", "DOUBLE BUNGALOW")
SINGLE = ("SINGLE FAMILY", "SINGLE-FAMILY", "SINGLE FAM", "SFR", "SF DETACHED", "1 FAMILY",
          "ONE FAMILY", "ONE-FAMILY", "1-FAMILY")
VACANT = ("VACANT", "UNIMPROVED", "UNDEVELOPED")


def _has(text, tokens):
    for t in tokens:
        s = t.strip()
        pat = (r"(?<![A-Z0-9])" + re.escape(s) + r"(?![A-Z0-9])") if len(s) <= 4 else re.escape(s)
        if re.search(pat, text):
            return t
    return None


def choose_use_fields(fields):
    """fields: [{'name':..., 'alias':...}] from layer metadata -> ordered list of names."""
    picked = []
    for f in fields:
        name = str(f.get("name") or "")
        label = (name + " " + str(f.get("alias") or "")).upper().replace(" ", "_")
        if any(x in label for x in EXCLUDE_FIELD_HINTS):
            continue
        if any(h in label for h in USE_FIELD_HINTS):
            picked.append(name)
    return picked[:MAX_USE_FIELDS]


def fetch_layer_fields(layer=LAYER, opener=urllib.request.urlopen):
    req = urllib.request.Request(layer + "?f=json", headers={"User-Agent": "AeroLeadAI-public-data-research/1.0"})
    with opener(req, timeout=35) as r:
        meta = json.load(r)
    if meta.get("error") or not meta.get("fields"):
        raise RuntimeError("layer metadata unavailable: " + str(meta.get("error"))[:200])
    return meta["fields"]


def load_or_discover(path=SCHEMA_PATH, layer=LAYER, fetch=fetch_layer_fields, max_age_days=30, now=None):
    """Cached schema. Re-discovers monthly so a renamed field is noticed."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        cached = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        age = now - dt.datetime.fromisoformat(cached["discovered_at_utc"])
        if age.days < max_age_days and cached.get("layer") == layer:
            return cached
    except (OSError, ValueError, KeyError):
        pass
    fields = fetch(layer)
    schema = {"layer": layer, "discovered_at_utc": now.isoformat(),
              "all_field_names": [f.get("name") for f in fields],
              "use_fields": choose_use_fields(fields),
              "warning": None}
    if not schema["use_fields"]:
        schema["warning"] = ("No use-type field found on this layer. Nothing can be source-verified as "
                             "residential from it; join the Eagan city layer or a county class-code table.")
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return schema


def _units(attrs, use_fields):
    for k in use_fields:
        if "UNIT" in k.upper():
            try:
                v = float(attrs.get(k))
                if v >= 0:
                    return int(v)
            except (TypeError, ValueError):
                pass
    return None


def classify(attrs, use_fields, year_built=None, now_year=None):
    """Return a classification dict. `attrs` is the raw source attribute dict."""
    now_year = now_year or dt.datetime.now().year
    values = {k: attrs.get(k) for k in use_fields if attrs.get(k) not in (None, "")}
    text = " ".join(str(v) for v in values.values()).upper().strip()
    units = _units(attrs, use_fields)
    out = {"residential_class": "UNKNOWN", "basis": "NO_SOURCE_FIELDS", "matched": None,
           "single_family_verified": False, "non_residential_verified": False,
           "use_attrs": values}
    if text:
        out["basis"] = "SOURCE_TEXT"
        for cls, toks in (("NONRESIDENTIAL", NONRES), ("MULTIFAMILY", MULTI), ("TOWNHOME", TOWN),
                          ("CONDO", CONDO), ("DUPLEX", DUPLEX), ("VACANT_OR_UNIMPROVED", VACANT),
                          ("SINGLE_FAMILY", SINGLE)):
            hit = _has(text, toks)
            if hit:
                out.update(residential_class=cls, matched=hit.strip())
                break
        else:
            if "RESIDENTIAL" in text or re.search(r"\bRES\b", text):
                out.update(residential_class="RESIDENTIAL_UNSPECIFIED", matched="RESIDENTIAL")
    if out["residential_class"] in ("UNKNOWN", "RESIDENTIAL_UNSPECIFIED") and units is not None:
        out["basis"] = "SOURCE_UNITS"
        if units == 2:
            out.update(residential_class="DUPLEX", matched="UNITS=2")
        elif units >= 3:
            out.update(residential_class="MULTIFAMILY", matched="UNITS>=3")
    cls = out["residential_class"]
    out["single_family_verified"] = cls == "SINGLE_FAMILY"
    out["non_residential_verified"] = cls == "NONRESIDENTIAL"
    out["residential_likelihood"] = likelihood(cls, year_built, now_year)
    if cls == "RESIDENTIAL_UNSPECIFIED" and units == 1:
        # One unit on a residential parcel is probable, not proof (a townhome is also 1 unit).
        out["residential_likelihood"] = 0.85
    return out


def likelihood(cls, year_built, now_year):
    """UNVERIFIED 0-1 ranking aid. Not a verification and never shown as one."""
    base = {"SINGLE_FAMILY": 0.97, "TOWNHOME": 0.9, "DUPLEX": 0.85, "CONDO": 0.85,
            "RESIDENTIAL_UNSPECIFIED": 0.7, "MULTIFAMILY": 0.5, "VACANT_OR_UNIMPROVED": 0.05,
            "NONRESIDENTIAL": 0.0}.get(cls)
    if base is not None:
        return base
    known = isinstance(year_built, (int, float)) and 1800 <= year_built <= now_year
    return 0.55 if known else 0.25


if __name__ == "__main__":
    s = load_or_discover()
    print(json.dumps({"use_fields": s["use_fields"], "warning": s["warning"],
                      "fields_seen": len(s["all_field_names"])}, indent=2))
