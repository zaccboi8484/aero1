"""Synthetic geometry and masked imagery regression tests, no remote datasets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import geopandas as gpd
import numpy as np
from PIL import Image
from shapely.geometry import Point, box
ROOT = Path(__file__).resolve().parents[1]
for sub in ('collector', 'scripts'): sys.path.insert(0, str(ROOT/sub))
import footprints as fp
import roof_chip_features as chips
import roof_score_v2 as score

class Footprints(unittest.TestCase):
    def test_match_area_no_match_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            center = gpd.GeoSeries([Point(-93.1,44.8)], crs=4326).to_crs(26915).iloc[0]
            poly = box(center.x-10,center.y-5,center.x+10,center.y+5)
            path = Path(d)/'buildings.geojson'
            gpd.GeoDataFrame(geometry=[poly], crs=26915).to_crs(4326).to_file(path, driver='GeoJSON')
            rows = fp.attach([{'county_pin':'a','center_lon':-93.1,'center_lat':44.8},
                              {'county_pin':'b','center_lon':-93.2,'center_lat':44.8},
                              {'county_pin':'c','center_lon':None}],path)
            self.assertEqual(rows[0]['roof_footprint_m2'],200)
            self.assertEqual(rows[0]['roof_area_m2_est'],224)
            self.assertNotIn('roof_area_m2_est',rows[1])
            self.assertEqual(rows[2]['footprint_status'],'INVALID_OR_OUT_OF_REGION_COORDINATES')
            shared = fp.attach([{'center_lon':-93.1,'center_lat':44.8}]*2,path)
            self.assertTrue(all(r['footprint_status']=='BUILDING_SHARED_BY_MULTIPLE_PARCELS' for r in shared))

    def test_tied_intersections_not_arbitrary(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'buildings.geojson'
            poly=box(-93.101,44.799,-93.099,44.801)
            gpd.GeoDataFrame(geometry=[poly,poly],crs=4326).to_file(path,driver='GeoJSON')
            r=fp.attach([{'center_lon':-93.1,'center_lat':44.8}],path)[0]
            self.assertEqual(r['footprint_status'],'AMBIGUOUS_NEAREST_BUILDINGS')
            self.assertNotIn('roof_area_m2_est',r)

    def test_raster_orientation_and_holes(self):
        poly=box(0,1,1,2)
        mask=fp.roof_mask(poly,[0,0,2,2],size=(10,8))
        self.assertEqual(mask.shape,(8,10))
        self.assertTrue(mask[:4,:5].all());self.assertFalse(mask[4:,:].any())
        hole=box(0,0,2,2).difference(box(.5,.5,1.5,1.5))
        mask=fp.roof_mask(hole,[0,0,2,2],size=(20,20))
        self.assertFalse(mask[10,10]);self.assertTrue(mask[1,1])

    def test_mask_excludes_blue_background_and_change(self):
        with tempfile.TemporaryDirectory() as d:
            a=np.full((233,300,3),[30,60,200],dtype=np.uint8)
            a[50:180,80:220]=[120,120,120]
            b=a.copy();b[:50]=[255,0,0]
            new=Path(d)/'new.png';old=Path(d)/'old.png'
            Image.fromarray(a).save(new);Image.fromarray(b).save(old)
            mask=np.zeros((233,300),bool);mask[60:170,90:210]=True
            result=chips.features_for(new,old,mask=mask)
            self.assertFalse(result['possible_tarp']);self.assertFalse(result['possible_roof_change'])
            self.assertEqual(result['region_basis'],'BUILDING_FOOTPRINT_CANDIDATE')
            with self.assertRaises(ValueError): chips.features_for(new,mask=np.zeros((233,300),bool))

    def test_area_factor_is_capped_and_flagged(self):
        ctx={'building_value':{},'year_built':{},'storm_zips':set(),'storms':{},'reroof_year':{},'chips':{},'aerial':{}}
        rec={'county_pin':'p','year_built':1996,'residential_class':'SINGLE_FAMILY','single_family_verified':True}
        for area,expected in [(100,.8),(350,1.05),(900,1.3)]:
            ctx['footprints']={'p':{'footprint_status':fp.MATCHED,'roof_area_m2_est':area}}
            result=score.score_parcel(rec,ctx)
            self.assertEqual(result['factors']['value_factor'],expected)
            self.assertIn('ROOF_AREA_ASSUMED_PITCH',result['flags'])
            self.assertEqual(result['condition_claim'],'NONE')
        ctx['footprints']['p']['footprint_status']='AMBIGUOUS_NEAREST_BUILDINGS'
        self.assertEqual(score.score_parcel(rec,ctx)['factors']['value_factor'],1.0)

if __name__=='__main__':unittest.main()
