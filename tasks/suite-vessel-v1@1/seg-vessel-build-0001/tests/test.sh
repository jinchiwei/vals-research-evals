#!/bin/bash
set -u
exec /opt/benchmark-venv/bin/python -I -B /tests/grade.py
