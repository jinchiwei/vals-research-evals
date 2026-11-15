"""Deterministic frame capture of index.html to MP4.

Every frame is produced by calling window.seek(t) and taking a screenshot, so
the output does not depend on machine speed. Frames are piped as PNG into
ffmpeg (H.264, yuv420p). Work is split into chunks rendered in parallel and
joined losslessly with ffmpeg's concat demuxer.

Usage:
  python render.py                       # full video -> demo.mp4
  python render.py --stills 40,60        # PNG stills at those seconds (QA)
  python render.py --poster pipeline:37  # poster PNG at scene-local time
"""
import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG = "/usr/bin/ffmpeg"
W, H = 1920, 1080


def open_page(pw):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    page.goto((HERE / "index.html").as_uri() + "?capture")
    page.wait_for_function("window.seek && document.fonts.status === 'loaded'")
    page.evaluate("document.fonts.ready")
    # The first screenshot of a fresh headless browser can take many seconds
    # (compositor warm-up under WSL); take one throwaway shot with a long timeout.
    page.screenshot(type="png", timeout=180_000)
    return browser, page


def shot(page, t):
    page.evaluate(f"window.seek({t:.6f})")
    return page.screenshot(type="png", full_page=False, timeout=120_000)


def render_chunk(job):
    idx, f0, f1, fps, tmp = job
    from playwright.sync_api import sync_playwright

    out = Path(tmp) / f"seg{idx:03d}.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
           "-c:v", "png", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-tune", "animation", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        browser, page = open_page(pw)
        for f in range(f0, f1):
            ff.stdin.write(shot(page, f / fps))
        browser.close()
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on chunk {idx}")
    return str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(HERE / "demo.mp4"))
    ap.add_argument("--stills", help="comma-separated seconds; writes qa/still_<t>.png")
    ap.add_argument("--poster", help="scene:local_seconds, e.g. pipeline:37")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    if args.stills or args.poster:
        with sync_playwright() as pw:
            browser, page = open_page(pw)
            if args.stills:
                qa = HERE / "qa"
                qa.mkdir(exist_ok=True)
                for s in args.stills.split(","):
                    (qa / f"still_{float(s):06.1f}.png").write_bytes(shot(page, float(s)))
            if args.poster:
                scene, lt = args.poster.split(":")
                start = page.evaluate(f"window.SCENES['{scene}'].start")
                (HERE / "poster-pipeline.png").write_bytes(shot(page, start + float(lt)))
            browser.close()
        return

    with sync_playwright() as pw:
        browser, page = open_page(pw)
        duration = page.evaluate("window.DURATION")
        browser.close()
    n = int(round(duration * args.fps))
    step = -(-n // args.workers)
    with tempfile.TemporaryDirectory(dir=HERE) as tmp:
        jobs = [(i, i * step, min(n, (i + 1) * step), args.fps, tmp) for i in range(args.workers) if i * step < n]
        with ProcessPoolExecutor(len(jobs)) as ex:
            segs = list(ex.map(render_chunk, jobs))
        lst = Path(tmp) / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", "-movflags", "+faststart", args.out], check=True)
    print(f"wrote {args.out}: {n} frames, {duration:.1f} s, {os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
