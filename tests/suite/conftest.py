"""Shared fixtures for suite tests. Run: ~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
