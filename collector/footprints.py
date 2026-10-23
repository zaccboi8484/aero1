#!/usr/bin/env python3
"""Local building footprints for Minnesota: proximity is a candidate match, not ownership proof."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sys
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, mapping, shape
from rasterio.features import rasterize
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pipeline_io import atomic_json
MATCHED = 'NEAREST_BUILDING_REVIEW_REQUIRED'


def attach(recs, footprints_path, max_distance=40, pitch_factor=1.12):
    """Return copies, one per input. Reject ties/shared buildings; EPSG:26915 is MN-specific."""
    if not math.isfinite(max_distance) or max_distance <= 0:
        raise ValueError('max_distance must be positive metres')
    if not math.isfinite(pitch_factor) or not 1 <= pitch_factor <= 2:
        raise ValueError('pitch_factor must be between 1 and 2')
    fp = gpd.read_file(footprints_path)
    if fp.crs is None:
        raise ValueError('Footprint dataset must declare its CRS')
    fp = fp[fp.geometry.notna() & ~fp.geometry.is_empty & fp.geometry.is_valid &
            fp.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])].to_crs(26915).reset_index(drop=True)
    owned = ('roof_footprint_m2', 'roof_area_m2_est', 'footprint_compactness',
             'footprint_geometry_4326', 'footprint_distance_m', 'roof_pitch_factor_assumed')
    out = [{k: v for k, v in r.items() if k not in owned} for r in recs]
    valid = []
    for i, r in enumerate(out):
        lon, lat = r.get('center_lon'), r.get('center_lat')
        # This local projection is deliberately limited to Minnesota's geographic extent.
        ok = (isinstance(lon, (int, float)) and isinstance(lat, (int, float)) and
              math.isfinite(lon) and math.isfinite(lat) and -98 <= lon <= -89 and 43 <= lat <= 50)
        r['footprint_status'] = 'NO_MATCH_WITHIN_DISTANCE' if ok else 'INVALID_OR_OUT_OF_REGION_COORDINATES'
        if ok: valid.append(i)
    if not valid or fp.empty:
        return out
    pts = gpd.GeoDataFrame({'record_index': valid}, geometry=[Point(out[i]['center_lon'], out[i]['center_lat'])
                            for i in valid], crs=4326).to_crs(26915)
    joined = gpd.sjoin_nearest(pts, fp[['geometry']], how='left', max_distance=max_distance, distance_col='distance_m')
    candidates = {}
    for i, group in joined.groupby('record_index'):
        group = group.dropna(subset=['index_right'])
        if len(group) > 1:
            out[i]['footprint_status'] = 'AMBIGUOUS_NEAREST_BUILDINGS'
        elif len(group) == 1:
            row = group.iloc[0]
            candidates[i] = (int(row['index_right']), float(row['distance_m']))
    counts = {}
    for idx, _ in candidates.values(): counts[idx] = counts.get(idx, 0) + 1
    geographic = fp.to_crs(4326)
    for i, (idx, distance) in candidates.items():
        if counts[idx] > 1:
            out[i]['footprint_status'] = 'BUILDING_SHARED_BY_MULTIPLE_PARCELS'
            continue
        poly = fp.loc[idx, 'geometry']
        out[i].update(footprint_status=MATCHED, footprint_distance_m=round(distance, 2),
                      roof_footprint_m2=round(poly.area, 1), roof_area_m2_est=round(poly.area * pitch_factor, 1),
                      roof_pitch_factor_assumed=pitch_factor,
                      footprint_compactness=round(4 * math.pi * poly.area / poly.length**2, 3),
                      footprint_geometry_4326=mapping(geographic.loc[idx, 'geometry']))
    return out


def roof_mask(poly_4326, bbox, size=(300, 233)):
    poly = shape(poly_4326) if isinstance(poly_4326, dict) else poly_4326
    if poly.is_empty or not poly.is_valid or poly.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Expected a valid nonempty building polygon')
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox) or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
        raise ValueError('Expected WGS84 bounds: west, south, east, north')
    if len(size) != 2 or any(not isinstance(v, int) or v <= 0 for v in size):
        raise ValueError('size must be positive width, height')
    return rasterize([(poly, 1)], out_shape=size[::-1], transform=from_bounds(*bbox, *size), dtype='uint8').astype(bool)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--footprints', required=True, help='Local GeoJSON/GPKG with declared CRS; subset to MN first')
    parser.add_argument('--source', required=True, help='Dataset source/version and license reference')
    parser.add_argument('--records', default=str(ROOT/'evidence/data/autonomous_residential_discovery.json'))
    parser.add_argument('--out', default=str(ROOT/'evidence/data/building_footprints.json'))
    args = parser.parse_args()
    recs = json.loads(Path(args.records).read_text())['records']
    pins = [r['county_pin'] for r in recs]
    if len(pins) != len(set(pins)): raise ValueError('Duplicate parcel PINs')
    matched = attach(recs, args.footprints)
    keys = ('footprint_status', 'footprint_distance_m', 'roof_footprint_m2', 'roof_area_m2_est',
            'roof_pitch_factor_assumed', 'footprint_compactness', 'footprint_geometry_4326')
    digest = hashlib.sha256()
    with open(args.footprints, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
    body = {'format': 'AERO_BUILDING_FOOTPRINTS_V1', 'source': args.source, 'sha256': digest.hexdigest(),
            'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'metric_crs': 'EPSG:26915',
            'not_a_damage_score': True, 'condition_claim': 'NONE',
            'records': {r['county_pin']: {k: r[k] for k in keys if k in r} for r in matched}}
    atomic_json(args.out, body)
    print(json.dumps({'parcels': len(matched), 'candidate_matches': sum(r['footprint_status'] == MATCHED for r in matched)}))

if __name__ == '__main__': main()
