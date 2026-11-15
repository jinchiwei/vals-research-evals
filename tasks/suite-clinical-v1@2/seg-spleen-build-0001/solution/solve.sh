#!/bin/bash
# Oracle: install the reference pipeline built only from agent-visible material.
set -eu
mkdir -p /workspace/output
rm -rf /workspace/output/pipeline
cp -r /solution/pipeline /workspace/output/pipeline
chmod -R a+rX /workspace/output/pipeline
