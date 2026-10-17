#!/usr/bin/env python3
"""Discover official MetroGIS municipality boundaries and order metro territories in rings."""
import json,math,datetime,pathlib,urllib.parse,urllib.request
BASE="https://arcgis.metc.state.mn.us/arcgis/rest/services/LPH/Administrative_Library/FeatureServer/3/query"
ORIGIN=(44.817,-93.168)
RADII=(10,20,35,55,80)
def distance(a,b):
 x,y=map(math.radians,a);u,v=map(math.radians,b)
 return 12742.0176*math.asin(min(1,math.sqrt(math.sin((u-x)/2)**2+math.cos(x)*math.cos(u)*math.sin((v-y)/2)**2)))
def main():
 params={"f":"json","where":"1=1","outFields":"*","outSR":"4326","returnGeometry":"true","resultRecordCount":2000}
 url=BASE+"?"+urllib.parse.urlencode(params)
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-Regional-Index/1.0"}),timeout=60) as response:result=json.load(response)
 if result.get("error") or result.get("exceededTransferLimit"):raise RuntimeError("GIS returned error/incomplete municipalities")
 items=[];seen=set()
 for feature in result.get("features",[]):
  attrs=feature.get("attributes",{});name=str(attrs.get("CTU_NAME") or "").strip()
  points=[p for ring in feature.get("geometry",{}).get("rings",[]) for p in ring]
  if not name or not points:continue
  mid=((min(p[1] for p in points)+max(p[1] for p in points))/2,(min(p[0] for p in points)+max(p[0] for p in points))/2)
  km=distance(ORIGIN,mid);ring=next((i+1 for i,radius in enumerate(RADII) if km<=radius),None)
  if ring is None or name.lower() in seen:continue
  seen.add(name.lower())
  items.append({"municipality":name,"distance_km":round(km,2),"ring":ring,"source":url,"permit_route":"NEEDS_JURISDICTION_VALIDATION","status":"DISCOVERY_ONLY"})
 items.sort(key=lambda r:(0 if r["municipality"].lower()=="eagan" else 1 if r["municipality"].lower()=="burnsville" else r["ring"]+1,r["distance_km"]))
 dst=pathlib.Path("evidence/data/metro_expansion_manifest.json");dst.parent.mkdir(parents=True,exist_ok=True)
 dst.write_text(json.dumps({"fetched_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"count":len(items),"properties_confirmed":0,"records":items},indent=2)+"\n")
 print("Official municipalities indexed:",len(items))
if __name__=="__main__":main()
