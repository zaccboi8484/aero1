#!/usr/bin/env python3
"""GateKeeper pure security/deduplication tests. No network calls."""
import sys,pathlib,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"collector"))
from gatekeeper_fetch import validate_url,FetchRejected
from evidence_audit import load,review,record
assert validate_url("https://eagan.onlama.com/Search.aspx").startswith("https://")
for url in ["http://eagan.onlama.com/Search.aspx","https://evil.example/x",
            "https://eagan.onlama.com.evil.example/x","https://user:pass@eagan.onlama.com/"]:
 try:validate_url(url);raise AssertionError("Unsafe source accepted: "+url)
 except FetchRejected:pass
db=load(pathlib.Path("/nonexistent/aero-do-not-create.json"))
url="https://eagan.onlama.com/Search.aspx"
r=review(db,source="eagan-permits",source_id="P-123",url=url,territory="kings-wood-001",min_hours=24)
assert r["action"]=="FETCH"
sha=hashlib.sha256(b"real-content").hexdigest()
assert record(db,source="eagan-permits",source_id="P-123",url=url,territory="kings-wood-001",status="ACQUIRED",sha256=sha,size=12)
r=review(db,source="eagan-permits",source_id="P-123",url=url,territory="burnsville-expansion",sha256=sha)
assert r["action"]=="SKIP_UNCHANGED"
assert len(db["sources"])==1 and len(db["sources"][r["key"]]["territories"])==2
print("GateKeeper allowlist, identity, and cross-territory reuse tests: PASS")
