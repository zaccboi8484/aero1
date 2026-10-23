#!/usr/bin/env python3
"""Tamper-evident history: each run appends {file hashes, prev_hash, entry_hash} to a JSONL chain.
Editing or deleting an earlier entry breaks every later hash; `verify` detects it."""
import datetime as dt, hashlib, json, pathlib, sys

DATA = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "data"
CHAIN = DATA / "provenance_chain.jsonl"
TRACKED = ("aerial_coverage_ledger.json", "roof_priority_v2.json", "hail_exposure.json",
           "autonomous_residential_discovery.json", "reroof_timeline.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def entry_hash(prev, files, ts):
    return hashlib.sha256((prev + json.dumps(files, sort_keys=True) + ts).encode()).hexdigest()


def read_chain(path=CHAIN):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def append(path=CHAIN, files=None, ts=None):
    chain = read_chain(path)
    files = files if files is not None else {n: sha(DATA / n) for n in TRACKED}
    if chain and chain[-1]["files"] == files:
        return None                                             # nothing changed: no noise commit
    prev = chain[-1]["entry_hash"] if chain else "GENESIS"
    ts = ts or dt.datetime.now(dt.timezone.utc).isoformat()
    e = {"ts": ts, "files": files, "prev_hash": prev, "entry_hash": entry_hash(prev, files, ts)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, sort_keys=True) + "\n")
    return e


def verify(path=CHAIN):
    prev = "GENESIS"
    for i, e in enumerate(read_chain(path)):
        if e["prev_hash"] != prev or e["entry_hash"] != entry_hash(prev, e["files"], e["ts"]):
            return {"ok": False, "broken_at": i}
        prev = e["entry_hash"]
    return {"ok": True}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        r = verify(); print(json.dumps(r)); sys.exit(0 if r["ok"] else 1)
    print(json.dumps({"appended": bool(append())}))
