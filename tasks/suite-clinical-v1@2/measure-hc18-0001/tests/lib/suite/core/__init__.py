"""Shared core of the healthcare agent benchmark suite.

Modules:
- metrics:  pure numpy/scipy metric library (segmentation, registration, classification, measurement, statistics)
- geometry: NIfTI loading and grid validation against a reference image
- runner:   run a submitted pipeline on one hidden case under a hard wall-clock limit
- reward:   the fixed reward.json contract and metrics.json writer
- grading:  the verifier procedure shared by every family (stage, run, grade, aggregate, write)
- export:   write a Harbor/Valkyrie task folder from a family spec

Only relative imports are used inside this package and its only repository
dependency is pcnsl/imaging_eval.py + pcnsl/prediction_eval.py, so the exporter
can vendor the same files into tests/lib/ and the verifier imports them unchanged.
"""
