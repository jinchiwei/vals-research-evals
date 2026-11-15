# Benchmark work instructions

- Install every new dependency or CLI inside a project-specific virtualenv or conda environment, on every machine. No global/system installs, `pip --user`, or `uv tool install`. Valkyrie is in `.venv-valkyrie`; invoke its executable explicitly.
- Preserve the configured human Git identity. Never add AI authors, coauthors or attribution footers to commits.
- Keep patient rows, labels, private crosswalks, model payloads containing rows and individual predictions on FAC/SCS. Only code, schemas and aggregate evidence belong in this repository.
- Follow `docs/research/hackathon-prompt.md`; Jin must personally write the submission's opening overview paragraph.
- Existing all-pass synthetic repair results are distinct from actual mutation prediction experiments. Do not claim a frontier failure without measured, appropriately controlled evidence.
- All slide authoring goes to Claude Code using Jin's build-pptx skill. Prefer Claude Opus 5.5 high for delegated work when available and record the actual model.
