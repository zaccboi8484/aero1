#!/usr/bin/env python3
"""Offline deployment checks. Exit 2 means installation is incomplete; no network calls."""
import argparse
import importlib.util
import json
from pathlib import Path
from pipeline_io import load_suppression

BASE_FILES = (
    "collector/collect_mngeo_aerial.py", "collector/roof_evidence_score.py",
    "scripts/gatekeeper_field_triage.py", "tests/test_roof_evidence_score.py",
    "tests/test_permit_matching.py", "tests/test_gatekeeper_fetch.py",
)
PACKAGES = ("numpy", "PIL", "scipy", "xarray", "cfgrib", "eccodes", "geopandas", "rasterio")


def inspect(root, check_packages=True):
    root = Path(root)
    missing = [p for p in BASE_FILES if not (root / p).is_file()]
    dependencies = [p for p in PACKAGES if importlib.util.find_spec(p) is None] if check_packages else []
    errors = []
    data_dir = root / "evidence" / "data"
    for path in sorted(data_dir.glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append({"file": path.name, "error": str(exc)})
    try:
        suppression = load_suppression(data_dir / "outreach_suppression.json")
    except (OSError, ValueError) as exc:
        errors.append({"file": "outreach_suppression.json", "error": str(exc)})
        suppression = set()
    return {"status": "BLOCKED" if missing or dependencies or errors else "OFFLINE_CHECKS_PASSED",
            "missing_base_files": missing, "missing_python_packages": dependencies,
            "data_errors": errors, "suppressed_parcels": len(suppression),
            "live_services_verified": False,
            "note": "Offline checks cannot certify feeds, imagery rights, credentials, or production readiness."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = inspect(args.root)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
