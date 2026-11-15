"""Score every record in INPUT_DIR; write OUTPUT_DIR/predictions.csv (RecordID,risk)."""
import csv, os, pickle, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import feature_matrix
from records import list_records
import numpy as np

def main(inp, out, transform=None):
    with open(os.path.join(HERE, "model.pkl"), "rb") as h:
        bundle = pickle.load(h)
    ids, names, X = feature_matrix(list_records(inp))
    assert names == bundle["names"], "feature mismatch"
    p = bundle["model"].predict_proba(X)[:, 1]
    mode = os.environ.get("RISK_ICU_TRANSFORM", transform or "")
    if mode == "overconfident":  # failure pipeline: same ranking, logits x3
        q = np.clip(p, 1e-4, 1 - 1e-4); lo = np.log(q / (1 - q)) * 3.0; p = 1 / (1 + np.exp(-lo))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "predictions.csv"), "w", newline="") as h:
        w = csv.writer(h); w.writerow(["RecordID", "risk"])
        for i, v in zip(ids, p):
            w.writerow([i, f"{float(v):.6f}"])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
