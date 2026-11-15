"""Fit the simple reference on the agent-visible development set only; write ROOT/work/simple_pipeline/.

    conda run -n vals-suite-ecg_ptbxl python suite/families/ecg_ptbxl/train_simple.py --root /home/jkwei/data/vals-suite/ecg_ptbxl
"""
import argparse
import importlib.util
import json
import pickle
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ecg_simple", HERE / "simple_ref" / "predict.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
SEED = 20261114


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    a = ap.parse_args()
    dev = a.root / "work" / "dev"
    meta = pd.read_csv(dev / "meta.csv")
    lab = pd.read_csv(dev / "labels.csv")
    assert (meta["record_id"] == lab["record_id"]).all()
    t0 = time.time()
    X = R.feature_matrix(np.load(dev / "signals.npz")["signals"], meta["age"].to_numpy(float), meta["sex"].to_numpy())
    t_feat = time.time() - t0
    models = []
    for c in R.CLASSES:
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                           random_state=SEED)
        m.fit(X, lab[c].to_numpy())
        models.append(m)
    out = a.root / "work" / "simple_pipeline"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "model.pkl").write_bytes(pickle.dumps(models))
    shutil.copy(HERE / "simple_ref" / "predict.py", out / "predict.py")
    shutil.copy(HERE / "simple_ref" / "run.sh", out / "run.sh")
    info = {"n_dev": int(len(X)), "n_features": int(X.shape[1]), "feature_seconds": t_feat,
            "total_seconds": time.time() - t0, "model": "HistGradientBoostingClassifier per class, 300 iters, lr 0.05"}
    (out / "model.json").write_text(json.dumps(info, indent=1))
    print(info)


if __name__ == "__main__":
    main()
