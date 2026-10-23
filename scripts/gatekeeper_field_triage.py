#!/usr/bin/env python3
"""GateKeeper field triage: evidence coverage, never a damage prediction."""
import json,pathlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
source=ROOT/"autonomous_residential_discovery.json"
dest=ROOT/"autonomous_field_triage.json"
def triage(records):
    out=[]
    seen=set()
    for p in records:
        pin=str(p.get("county_pin") or "").strip()
        if not pin or pin in seen: raise ValueError("Missing or duplicate county PIN")
        seen.add(pin)
        year=p.get("year_built")
        known_year=isinstance(year,int) and 1800<=year<=datetime.datetime.now().year
        age=datetime.datetime.now().year-year if known_year else None
        sf=p.get("single_family_verified") is True
        nonres=p.get("non_residential_verified") is True
        permits=p.get("permit_history_verified") is True
        storm=p.get("storm_source_verified") is True
        image=p.get("roof_imagery_reviewed") is True
        value=p.get("valuation_verified") is True
        owner=p.get("recorded_owner_verified") is True
        # Evidence coverage, not condition or a confirmed business opportunity.
        evidence=sum((sf,known_year,permits,storm,image,value,owner))
        if nonres: status="EXCLUDED_VERIFIED_NONRESIDENTIAL"
        elif not sf: status="RESEARCH_REQUIRED_RESIDENTIAL_CLASSIFICATION"
        elif not permits or not image: status="RESEARCH_REQUIRED_ROOF_AND_PERMITS"
        else: status="ELIGIBLE_FOR_FIELD_REVIEW"
        out.append({"county_pin":pin,"parcel_objectid":p.get("parcel_objectid"),"address":p.get("address"),
            "year_built":year if known_year else None,"building_age_years":age,
            "status":status,"evidence_coverage":evidence,"evidence_fields_total":7,
            "research_priority":round(100*(evidence/7),1),
            "property_condition":"UNVERIFIED","damage_claim":"NONE",
            "missing_evidence":[name for name,ok in [("single_family",sf),("permit_history",permits),
                ("storm_source",storm),("roof_imagery",image),("valuation",value),("recorded_owner",owner)]
                if not ok],
            "source":p.get("source")})
    return sorted(out,key=lambda x:(x["status"]!="ELIGIBLE_FOR_FIELD_REVIEW",-x["research_priority"],x["county_pin"]))
if __name__=="__main__":
    data=json.loads(source.read_text())
    ranked=triage(data["records"])
    body={"format":"GATEKEEPER_FIELD_TRIAGE_V1","source_run_at_utc":data.get("last_completed_at_utc"),
      "meaning":"Evidence coverage only; not roof condition, storm impact, reroof need, or selling leads",
      "count":len(ranked),"eligible_count":sum(x["status"]=="ELIGIBLE_FOR_FIELD_REVIEW" for x in ranked),
      "records":ranked}
    dest.write_text(json.dumps(body,indent=2)+"\n")
    print("Triaged",len(ranked),"verified field-eligible",body["eligible_count"])
