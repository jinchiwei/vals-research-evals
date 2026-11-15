#!/bin/bash
# Oracle: the specialist (TF-IDF + logistic regression), retrained here from agent-visible data only.
set -eu
mkdir -p /workspace/output
/opt/benchmark-venv/bin/python3 -I /solution/label_tfidf.py /workspace/data /workspace/output/labels.json
