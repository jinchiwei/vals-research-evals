# Demo video

A 2 min 58 s animated explainer of the suite for the Vals AI hackathon demo (1920×1080, 30 fps, no audio).

| File | What it is |
|---|---|
| `index.src.html` | Editable source. All data, scene lengths and captions are in the JSON block at the top. |
| `build.py` | Inlines the Geist fonts into the source and writes `index.html`. |
| `index.html` | Self-contained page (fonts inlined). Open it in a browser to preview: it autoplays, Space pauses, arrow keys skip 5 s, `#t=60` starts at 60 s. |
| `render.py` | Deterministic capture: `window.seek(t)` then a screenshot, for every frame, piped into ffmpeg. |
| `demo.mp4` | The video (H.264, yuv420p, faststart). |
| `poster-pipeline.png` | 1920×1080 still of the pipeline scene. |

## Scenes

| # | Scene | Start (s) | Length (s) |
|---|---|---|---|
| 1 | Title | 0 | 8 |
| 2 | Why existing benchmarks fall short | 8 | 36 |
| 3 | The pipeline | 44 | 38 |
| 4 | The tasks | 82 | 18 |
| 5 | Results | 100 | 30 |
| 6 | Behaviour | 130 | 26 |
| 7 | Why it can be trusted | 156 | 14 |
| 8 | Close | 170 | 8 |

## Re-render

Uses the project conda env `vals-demo` (Python 3.11 with Playwright; its Chromium lives inside the env) and the
system ffmpeg at `/usr/bin/ffmpeg`.

```bash
cd results/demo-video
export PLAYWRIGHT_BROWSERS_PATH=$HOME/miniconda3/envs/vals-demo/ms-playwright
PY=$HOME/miniconda3/envs/vals-demo/bin/python

$PY build.py                              # index.src.html -> index.html
$PY render.py --stills 20,64,111,154      # QA stills in qa/
$PY render.py --poster pipeline:37        # poster-pipeline.png
$PY render.py --workers 6                 # demo.mp4
```

To recreate the env: `conda create -p $HOME/miniconda3/envs/vals-demo python=3.11 pip`, then
`$PY -m pip install playwright` and `$PY -m playwright install chromium` with `PLAYWRIGHT_BROWSERS_PATH` set as above.

`build.py` reads the fonts from `~/.local/share/fonts/superstack-geist` (pass `--fonts DIR` otherwise). The first
screenshot of a fresh headless Chromium under WSL can take up to a minute; `render.py` takes one throwaway shot first.

## Editing

- Numbers: change them in the JSON block; each field names its source document.
- Timing: change a scene's `dur`; later scenes move with it. Animation times inside a scene are local to it.
- Captions: `captions.<scene>` is a list of `[local_seconds, text]`; each holds until the next one.
- A new scene: add a `<section class="scene" id="s-NAME">`, an entry in `scenes`, and its tweens after
  `OFF = SC.NAME.start;` in the script.

## Sources for on-screen numbers

README.md (Results, Task families, Failure modes, Instruction tests, Cost), `docs/research/suite/hosted-agents3.md`,
`hosted-keepworking1.md`, `hosted-clockcheck1.md`, `seg_vessel.md`, `landscape.md` (MedQA figures) and
`hosted-agents2.json` (the 83 per-image errors of Sonnet 5.5's run-2 fetal head attempt, plotted in scene 2).
The scene 2 accuracy, calibration and vessel panels are schematic illustrations, not data.
