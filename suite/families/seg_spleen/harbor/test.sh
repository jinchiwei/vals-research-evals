#!/usr/bin/env bash
# Verifier entry (separate mode, no network). Hidden cases, specialist summary and
# grader.py live in /tests and are made root-only before the agent's pipeline runs.
exec /opt/benchmark-venv/bin/python -I /tests/grade_entry.py
