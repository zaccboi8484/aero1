#!/usr/bin/env python3
"""Export prioritised parcel prospects with evidence completeness flags; never fabricate contact details."""
import csv
import json
from pathlib import Path
from pipeline_io import load_suppression

BASE = Path(__file__).resolve().parents[1] / "evidence" / "data"
HEADERS = ["county_pin","address","priority","tier","confidence","residential_class","verified_single_family","aerial_status","permit_status","storm_status","owner_status","valuation_status","street_view_url","missing_evidence","qualification"]

def rows_for(cards, suppressed=()):
    for card in cards:
        if card.get("county_pin") in suppressed: continue
        m=card.get("mindex") or {}
        if m.get("prospecting_priority") is None: continue
        missing=[]
        for label,key in [("aerial","imagery"),("permit","permit"),("storm","storm"),("owner","ownership"),("valuation","valuation")]:
            state=(card.get(key) or {}).get("status")
            if state not in ("REMOTE_IMAGE_VERIFIED","SOURCE_RECORDED","ZIP_REPORTS_AVAILABLE"):
                missing.append(label)
        residential=card.get("residential") or {}
        ready=bool(residential.get("verified_single_family") and not missing)
        yield {"county_pin":card.get("county_pin"),"address":card.get("address"),
               "priority":m.get("prospecting_priority"),"tier":m.get("tier"),"confidence":m.get("confidence"),
               "residential_class":residential.get("class"),"verified_single_family":residential.get("verified_single_family"),
               "aerial_status":(card.get("imagery") or {}).get("status"),
               "permit_status":(card.get("permit") or {}).get("status"),
               "storm_status":(card.get("storm") or {}).get("status"),
               "owner_status":(card.get("ownership") or {}).get("status"),
               "valuation_status":(card.get("valuation") or {}).get("status"),
               "street_view_url":card.get("street_view_url"),"missing_evidence":";".join(missing),
               "qualification":"EVIDENCE_COMPLETE_FOR_REVIEW" if ready else "RESEARCH_REQUIRED"}

def run():
    path=BASE/"mindex_property_cards.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    suppressed=load_suppression(BASE/"outreach_suppression.json")
    rec=list(rows_for(data["cards"], suppressed))
    rec.sort(key=lambda x:(-float(x["priority"]),str(x["county_pin"])))
    output=BASE/"mindex_lead_export.csv"
    with output.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader();w.writerows(rec)
    expected=sum(c.get("mindex",{}).get("prospecting_priority") is not None and c.get("county_pin") not in suppressed for c in data["cards"])
    assert len(rec)==expected, "lead export must contain every unsuppressed ranked property"
    return {"exported":len(rec),"review_ready":sum(x["qualification"]=="EVIDENCE_COMPLETE_FOR_REVIEW" for x in rec)}
if __name__=="__main__":print(json.dumps(run()))
