#!/usr/bin/env python3
"""Discover source catalogs, real official GIS subdivision matches, and permit access limits.
No invented permits, imagery, boundary membership, or condition findings.
"""
import csv, html.parser, json, pathlib, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
ROOT.mkdir(parents=True,exist_ok=True)
BASE="https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer"
DASH="https://eagan.onlama.com/Dashboard.aspx"
SOURCES=[
 ("eagan_subdivisions",BASE+"/9"),
 ("eagan_parcels",BASE+"/19"),
 ("eagan_addresses",BASE+"/3"),
]
class Anchors(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.anchors=[];self.href=None;self.title=[]
 def handle_starttag(self,t,a):
  if t.lower()=="a":self.href=dict(a).get("href");self.title=[]
 def handle_data(self,d):
  if self.href is not None:self.title.append(d)
 def handle_endtag(self,t):
  if t.lower()=="a" and self.href is not None:
   self.anchors.append({"title":" ".join(" ".join(self.title).split()),"url":urllib.parse.urljoin(DASH,self.href)})
   self.href=None
def fetch(url,json_mode=True):
 req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-OfficialRecords/1.0","Accept":"application/json" if json_mode else "text/html"})
 with urllib.request.urlopen(req,timeout=30) as response:
  body=response.read(5_000_000)
 return json.loads(body) if json_mode else body.decode("utf-8","replace")
out={"checked_utc":datetime.now(timezone.utc).isoformat(),"source_catalogs":[],"permit_report_links":[],"subdivision_candidates":[],"verified_permit_matches":0,"image_attachments":0,"warnings":[]}
for name,url in SOURCES:
 record={"name":name,"official_url":url}
 try:
  data=fetch(url+"?f=json")
  if data.get("error"):raise ValueError(str(data["error"]))
  record["fields"]=[{"name":f.get("name"),"alias":f.get("alias"),"type":f.get("type")} for f in data.get("fields",[])]
  record["display_field"]=data.get("displayField")
  record["supports_query"]=bool(data.get("advancedQueryCapabilities") or data.get("capabilities","").find("Query")>=0)
  if name=="eagan_subdivisions":
   fields=record["fields"]
   candidate_fields=[f["name"] for f in fields if re.search(r"(plat|subdiv|name)",f["name"] or "",re.I) and f["type"]=="esriFieldTypeString"]
   record["name_field_candidates"]=candidate_fields
   for field in candidate_fields[:3]:
    try:
     p={"f":"json","where":"UPPER("+field+") LIKE '%KINGS WOOD%'","outFields":"*","returnGeometry":"false","resultRecordCount":100}
     data=fetch(url+"/query?"+urllib.parse.urlencode(p))
     if data.get("error"):raise ValueError(str(data["error"]))
     for feature in data.get("features",[]):
      attrs=feature.get("attributes",{})
      # only data actually returned by GIS
      if attrs and attrs not in [x["attributes"] for x in out["subdivision_candidates"]]:
       out["subdivision_candidates"].append({"attributes":attrs,"layer_url":url,"query_field":field})
    except Exception as e:out["warnings"].append(field+": subdivision query unavailable: "+str(e)[:180])
 except Exception as e:record["error"]=str(e)[:240];out["warnings"].append(name+": "+str(e)[:180])
 out["source_catalogs"].append(record)
 time.sleep(.5)
try:
 page=fetch(DASH,False)
 parser=Anchors();parser.feed(page)
 out["permit_report_links"]=[a for a in parser.anchors if any(k in a["title"].lower() for k in ["permit","report","open data","building"])]
 out["permit_catalog_status"]="INDEX_ONLY_NO_ADDRESS_MATCHES"
 if not out["permit_report_links"]:out["warnings"].append("City permit portal rendered no report download links to basic HTML client; interactive export may require browser session.")
except Exception as e:out["warnings"].append("Eagan permit dashboard fetch unavailable: "+str(e)[:200])
with (ROOT/"official_source_discovery.json").open("w",encoding="utf-8") as file:json.dump(out,file,indent=2,default=str)
print("Official catalogs:",len(out["source_catalogs"]),"subdivision candidate records:",len(out["subdivision_candidates"]),"permit links:",len(out["permit_report_links"]))
