# Demo video

A 3 min 55 s animated explainer of the suite for the Vals AI hackathon demo (1920×1080, 30 fps), silent and
narrated versions.

| File | What it is |
|---|---|
| `index.src.html` | Editable source. All data, scene lengths and captions are in the JSON block at the top. |
| `build.py` | Inlines the Geist fonts and the Vals logo badge into the source and writes `index.html`. |
| `index.html` | Self-contained page. Open it to preview: it autoplays, Space pauses, arrow keys skip 5 s, `#t=60` starts at 60 s, `?with=models` includes the disabled round-4 scene. |
| `render.py` | Deterministic capture: `window.seek(t)` then a screenshot, for every frame, piped into ffmpeg. |
| `narration.json` | Narration text, per scene, as `[seconds into scene, text]`. |
| `narrate.py` | Synthesises the narration offline, checks timing, writes `narration.md` and `audio/narration.wav`, muxes `demo-narrated.mp4`. |
| `narration.md` | The script with absolute start and end times (generated; edit `narration.json`). |
| `demo.mp4` | Silent video (H.264, yuv420p, faststart). |
| `demo-narrated.mp4` | Same video with the narration (AAC 160 kb/s, 48 kHz, two-pass loudnorm to −14 LUFS, −1.5 dBTP). |
| `poster-pipeline.png` | 1920×1080 still of the pipeline scene. |
| `audio/clips/` | Cached per-segment WAVs, keyed by a hash of voice and text. |

## Scenes

| # | Scene | Start (s) | Length (s) |
|---|---|---|---|
| 1 | Title (Vals logo badge, lower right) | 0 | 8 |
| 2 | Why existing benchmarks fall short | 8 | 36 |
| 3 | The pipeline | 44 | 38 |
| 4 | The tasks: an intro, then one 10 s beat per family with its card highlighted | 82 | 75 |
| 5 | Results | 157 | 30 |
| – | Round 4 "More models" (disabled, 24 s, would start at 187) | – | – |
| 6 | Behaviour | 187 | 26 |
| 7 | Why it can be trusted | 213 | 14 |
| 8 | Close (Vals logo badge, lower right) | 227 | 8 |

## Voice

Kokoro-82M (`hexgrad/Kokoro-82M`, revision `f3ff357`), voice **`af_heart`** (American English, female), through the
`kokoro` 0.9.4 pip package with `misaki` 0.9.4 for phonemes. Model weights and voices are licensed **Apache-2.0**
(model card), as are both packages. Runs offline on CPU; no cloud TTS. The model files live in the env at
`$HOME/miniconda3/envs/vals-demo/hf-home` (via `HF_HOME`), not in `~/.cache`.

## Re-render

Uses the project conda env `vals-demo` (Python 3.11: Playwright with its Chromium inside the env, CPU-only torch,
kokoro, soundfile) and the system ffmpeg at `/usr/bin/ffmpeg`.

```bash
cd results/demo-video
export PLAYWRIGHT_BROWSERS_PATH=$HOME/miniconda3/envs/vals-demo/ms-playwright
export HF_HOME=$HOME/miniconda3/envs/vals-demo/hf-home
PY=$HOME/miniconda3/envs/vals-demo/bin/python

$PY build.py                              # index.src.html -> index.html
$PY render.py --stills 20,64,111,154      # QA stills in qa/
$PY render.py --poster pipeline:37        # poster-pipeline.png
$PY render.py --workers 6                 # demo.mp4 (about 3 min)
$PY narrate.py --check-only               # narration timing table, no mux
$PY narrate.py                            # narration.md, audio/narration.wav, demo-narrated.mp4
```

To recreate the env: `conda create -p $HOME/miniconda3/envs/vals-demo python=3.11 pip`, then
`$PY -m pip install playwright`, `$PY -m playwright install chromium` (with `PLAYWRIGHT_BROWSERS_PATH` set),
`$PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu` and `$PY -m pip install kokoro soundfile`.
The first Kokoro run downloads the model into `HF_HOME` and installs spaCy's `en_core_web_sm` into the env.

`build.py` reads the fonts from `~/.local/share/fonts/superstack-geist` (`--fonts DIR` otherwise) and the badge
from `results/brand/vals-logo-badge.png` (`--badge`). The badge (logo on an off-white panel) is used because the
green logo alone has a contrast ratio of 1.6 on the navy. It is 104 px tall with a 72 px margin, matching the
deck's title slide (0.95 in tall, 0.5 in margin on a 7.5 in slide). The first screenshot of a fresh headless
Chromium under WSL can take up to a minute; `render.py` takes one throwaway shot first.

## Narration rules

- A segment starts at its anchor, or 0.3 s after the previous segment ends if that is later, and must end 0.25 s
  before its scene ends. In `strict_scenes` (the tasks scene, where cards highlight on the anchors) it must also end
  before the next anchor. `narrate.py` exits with a list of problems otherwise; shorten the text, never the speed.
- Spoken forms: "E C G", "I C U", "M R I", "run dot S H". Numbers are spelled out.
- Every fact is from the source docs or already on screen.

## Editing

- Numbers: change them in the JSON block; each field names its source document.
- Timing: change a scene's `dur`; later scenes, captions and narration move with it. Animation times inside a
  scene are local to it. The tasks beats are at `tasks.beats.at`; keep `captions.tasks` and the tasks entries in
  `narration.json` on the same times.
- A new scene: add a `<section class="scene" id="s-NAME">`, an entry in `scenes`, its tweens after
  `OFF = SC.NAME.start;` in the script, and optionally `captions.NAME` and `narration.json` entries.

## Round 4 "More models" scene (prepared, not in the render)

The scene is in the source as `{"id": "models", "dur": 24, "enabled": false}`, placed after Results. It draws a
model × task grid from `models4` in the JSON block: six models (Opus 5.5, Sonnet 5.5, Fable 5.2, gpt-6-astra,
gpt-6.1-sol, gpt-6-luna), six tasks, a specialist row and one cell per model and task. Empty cells show "–".
To enable it once `docs/research/suite/hosted-models4.md` and `.json` exist:

1. Fill `models4.cells["<model>|<task>"] = {"value": 0..1, "label": "0.651", "gap": "3 of 3" or null}` and
   `models4.specialist["<task>"]` from those documents only. Set Fable 5.2's harness.
2. Write the round-4 captions (`captions.models`) and narration (`narration.json`, `models`) from the findings.
3. Set `"enabled": true` (or keep it disabled and pass `--with models` to both `render.py` and `narrate.py`).
4. `build.py`, `render.py --workers 6`, `narrate.py`. The video grows by 24 s.

## Sources for on-screen numbers

README.md (Results, Task families, Failure modes, Instruction tests, Cost), the family documents in
`docs/research/suite/` (`reg_resect.md`, `seg_spleen.md`, `measure_hc18.md`, `seg_vessel.md`, `ecg_ptbxl.md`,
`risk_icu.md`, `causal_ate.md`), `hosted-agents3.md`, `hosted-keepworking1.md`, `hosted-clockcheck1.md`,
`landscape.md` (MedQA figures) and `hosted-agents2.json` (the 83 per-image errors of Sonnet 5.5's run-2 fetal head
attempt, plotted in scene 2). The scene 2 accuracy, calibration and vessel panels are schematic illustrations,
not data.
