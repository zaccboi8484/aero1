#!/usr/bin/env python3
"""EXPERIMENTAL aerial chip features. Ranking inputs only, never a condition score.

Aerial orthophotos can show gross things: a tarp, a recent color/texture change
(often a reroof), a missing section. They cannot show hail bruising or granule
loss (see roof_evidence_score.py). Accordingly every output here is a *flag for
human review* with a low weight in scoring v2, and `condition_claim` is NONE.

Input : <chip-dir>/<county_pin>__met25.jpg and optionally __dak23.jpg
Output: evidence/data/roof_chip_features.json (features only, no pixels)

Method (deliberately simple and explainable):
  * Roof proxy = central 50% of the chip (the bbox is built around the parcel
    centroid; this is a proxy, NOT a roof mask. A footprint layer would replace it).
  * blue_tarp_fraction : strongly blue, saturated pixels in the proxy.
  * texture            : std-dev of luminance (very smooth = new/clean surface or flat).
  * change_score       : mean abs luminance difference between vintages after
                         mean/std matching, so a global brightness shift between
                         flights does not look like a roof change.
"""
import argparse, json, pathlib, datetime as dt
import numpy as np
from PIL import Image

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
CHANGE_FLAG = 0.28   # uncalibrated; tune against reviewed pairs
TARP_FLAG = 0.04


def center_crop(arr, frac=0.5):
    h, w = arr.shape[:2]
    dh, dw = int(h * (1 - frac) / 2), int(w * (1 - frac) / 2)
    return arr[dh:h - dh, dw:w - dw]


def load(path, size=(300, 233)):
    return np.asarray(Image.open(path).convert("RGB").resize(size), dtype=np.float32) / 255.0


def luminance(rgb):
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def blue_tarp_fraction(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return float(((b > r + 0.12) & (b > g + 0.05) & (sat > 0.35) & (mx > 0.3)).mean())


def change_score(a_rgb, b_rgb, mask=None):
    a, b = (luminance(a_rgb[mask]), luminance(b_rgb[mask])) if mask is not None else (luminance(center_crop(a_rgb)), luminance(center_crop(b_rgb)))
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    return float(np.clip(np.abs(a - b).mean() / 2.0, 0, 1))  # 0 identical .. ~1 unrelated


def features_for(new_path, old_path=None, mask=None):
    new = load(new_path)
    if mask is not None:
        mask = np.asarray(mask, dtype=bool)
        if mask.shape != new.shape[:2] or mask.sum() < 16:
            raise ValueError("Roof mask must match image dimensions and contain at least 16 pixels")
    c = new[mask] if mask is not None else center_crop(new)
    out = {"blue_tarp_fraction": round(blue_tarp_fraction(c), 4),
           "texture_std": round(float(luminance(c).std()), 4),
           "mean_rgb": [round(float(x), 3) for x in c.reshape(-1, 3).mean(0)]}
    out["possible_tarp"] = out["blue_tarp_fraction"] >= TARP_FLAG
    if old_path and pathlib.Path(old_path).exists():
        out["change_score"] = round(change_score(new, load(old_path), mask), 4)
        out["possible_roof_change"] = out["change_score"] >= CHANGE_FLAG
    else:
        out["change_score"], out["possible_roof_change"] = None, None
    out.update(condition_claim="NONE", experimental=True,
               region_basis="BUILDING_FOOTPRINT_CANDIDATE" if mask is not None else "CENTER_CROP_PROXY",
               analyzed_pixels=int(mask.sum()) if mask is not None else int(c.shape[0] * c.shape[1]),
               meaning="Review flag from an orthophoto region. Not roof condition, not hail, not a reroof finding.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip-dir", required=True)
    ap.add_argument("--out", default=str(DATA / "roof_chip_features.json"))
    ap.add_argument("--footprints", default=str(DATA / "building_footprints.json"))
    ap.add_argument("--ledger", default=str(DATA / "aerial_coverage_ledger.json"))
    a = ap.parse_args()
    footprints = json.loads(pathlib.Path(a.footprints).read_text())["records"] if pathlib.Path(a.footprints).exists() else {}
    ledger = json.loads(pathlib.Path(a.ledger).read_text())["records"] if footprints else {}
    d = pathlib.Path(a.chip_dir)
    try:
        existing = json.loads(pathlib.Path(a.out).read_text(encoding="utf-8")).get("records", {})
    except (OSError, ValueError):
        existing = {}
    for new in sorted(d.glob("*__met25.jpg")):
        pin = new.name.split("__")[0]
        try:
            mask = None
            fp = footprints.get(pin, {})
            if fp.get("footprint_status") == "NEAREST_BUILDING_REVIEW_REQUIRED":
                from footprints import roof_mask
                mask = roof_mask(fp["footprint_geometry_4326"], ledger[pin]["bbox_4326"])
            existing[pin] = {**features_for(new, d / f"{pin}__dak23.jpg", mask=mask),
                             "computed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        except Exception as exc:
            existing[pin] = {"error": str(exc)[:120], "condition_claim": "NONE"}
    body = {"format": "AERO_CHIP_FEATURES_V1_EXPERIMENTAL", "count": len(existing), "records": existing}
    pathlib.Path(a.out).write_text(json.dumps(body, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"features": len(existing)}))


if __name__ == "__main__":
    main()
