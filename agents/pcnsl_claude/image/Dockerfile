# Base image recipe for PCNSL tasks run with the pcnsl_claude agent.
# NOT BUILT: teal has no Docker. Both FROM lines are mutable tags; resolve them to
# digests and record the built image digest before any task references this image.
#
#   docker build -f agents/pcnsl_claude/image/Dockerfile -t pcnsl-agent-base agents/pcnsl_claude
#
# Layout (no apt, no npm -g, no pip outside a venv, nothing under ~/.local or /usr/local/bin):
#   /opt/benchmark-venv  Python venv for the task, oracle and verifier, and the wrapper itself
#   /opt/agent-env       Node runtime + pinned Claude Code, installed with a local npm prefix
# No model weights or TabPFN checkpoints are included.

ARG NODE_IMAGE=node:22.12.0-bookworm-slim
ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm

FROM ${NODE_IMAGE} AS node

FROM ${PYTHON_IMAGE}
ARG CLAUDE_CODE_VERSION=2.1.325

# Node binary and npm copied into the agent prefix (multistage; nothing from the node
# image lands on a system path).
COPY --from=node /usr/local/bin/node /opt/agent-env/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /opt/agent-env/lib/node_modules/npm

# Network is used here, at image build time only, never during a task.
RUN set -eu; \
    export npm_config_cache=/tmp/npm-cache npm_config_update_notifier=false; \
    /opt/agent-env/bin/node /opt/agent-env/lib/node_modules/npm/bin/npm-cli.js install \
        --prefix /opt/agent-env --save-exact --no-fund --no-audit \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"; \
    ln -s ../node_modules/.bin/claude /opt/agent-env/bin/claude; \
    rm -rf /tmp/npm-cache

RUN set -eu; \
    python3 -m venv /opt/benchmark-venv; \
    /opt/benchmark-venv/bin/python -m pip install --no-cache-dir \
        numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 scikit-learn==1.5.2 nibabel==5.3.2

ENV PATH=/opt/benchmark-venv/bin:$PATH \
    PIP_NO_INDEX=1 \
    DISABLE_AUTOUPDATER=1

# Fail the build unless the same check the agent's install_cmd runs passes, and the
# task Python is the venv.
COPY run_agent.py /tmp/pcnsl-check/run_agent.py
RUN set -eu; \
    /opt/benchmark-venv/bin/python -I /tmp/pcnsl-check/run_agent.py check; \
    python3 -c "import sys; assert sys.prefix == '/opt/benchmark-venv', sys.prefix; \
import numpy, scipy, pandas, sklearn, nibabel"; \
    rm -rf /tmp/pcnsl-check
