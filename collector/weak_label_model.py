#!/usr/bin/env python3
"""Calibrate scoring v2 against REAL outcomes. Refuses to train on thin data.

Weak label: a parcel with a verified final reroof permit in year Y is a
positive example; features are computed AS OF Y-1 and WITHOUT permit knowledge
(no leakage). Parcels with no permit are only "unknown", so they are used as
negatives only when the permit source actually covered them (`covered_pins`),
and the model is reported as a ranking aid, never as a probability of damage.

Today the repo has ~18 permit-matched properties, far below MIN_PER_CLASS, so
this exits with a clear message. It becomes useful once the municipal permit
export (Eagan, Burnsville, ...) is connected for thousands of parcels.
"""
import datetime as dt, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
MIN_PER_CLASS = 150
FEATURES = ("p_age", "storm_mult", "value_factor", "age")


def build_rows(records, ctx, reroof_years, covered_pins, score_parcel):
    X, y = [], []
    for r in records:
        pin = r["county_pin"]
        if pin not in covered_pins:
            continue
        label_year = reroof_years.get(pin)
        asof = dt.datetime(label_year - 1 if label_year else dt.datetime.now().year, 12, 31, tzinfo=dt.timezone.utc)
        s = score_parcel(r, ctx, now=asof, use_permits=False)
        if s.get("prospecting_priority") is None:
            continue
        f = s["factors"]
        X.append([f["p_age"], f["storm_mult"], f["value_factor"], f["roof_age_years"] or 0])
        y.append(1 if label_year else 0)
    return X, y


def train(X, y):
    pos, neg = sum(y), len(y) - sum(y)
    if pos < MIN_PER_CLASS or neg < MIN_PER_CLASS:
        return {"trained": False, "reason": f"need >= {MIN_PER_CLASS} per class; have {pos} positive / {neg} negative"}
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import roc_auc_score
    import numpy as np
    X, y = np.array(X), np.array(y)
    p = cross_val_predict(GradientBoostingClassifier(max_depth=2, n_estimators=120, learning_rate=.05),
                          X, y, cv=StratifiedKFold(5, shuffle=True, random_state=7), method="predict_proba")[:, 1]
    k = max(1, len(y) // 10)
    top = np.argsort(-p)[:k]
    base = roc_auc_score(y, X[:, 0])  # AUC of the hand-set age prior alone
    return {"trained": True, "n": int(len(y)), "positives": int(pos), "cv_auc_model": round(float(roc_auc_score(y, p)), 3),
            "cv_auc_age_prior_only": round(float(base), 3), "precision_at_top_decile": round(float(y[top].mean()), 3),
            "base_rate": round(float(y.mean()), 3), "features": list(FEATURES),
            "use": "Ranking aid. Adopt only if it beats the age prior out-of-sample."}


def main():
    import roof_score_v2 as v2
    ctx = v2.build_context()
    recs = v2._read("autonomous_residential_discovery.json", {}).get("records", [])
    bf = v2._read("roof_permit_backfill_2025.json", {})
    covered = {r["county_pin"] for r in bf.get("records", [])} if bf.get("municipal_export_connected") else set()
    X, y = build_rows(recs, ctx, ctx["reroof_year"], covered, v2.score_parcel)
    rep = train(X, y)
    (v2.DATA / "weak_label_model_report.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rep))


if __name__ == "__main__":
    main()
