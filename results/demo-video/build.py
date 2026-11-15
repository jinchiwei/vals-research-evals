"""Inline the Geist fonts into index.src.html and write a self-contained index.html.

Usage: python build.py [--fonts DIR]
DIR holds Geist-Regular.ttf, Geist-Bold.ttf, GeistMono-Regular.ttf, GeistMono-Bold.ttf
(default: ~/.local/share/fonts/superstack-geist; Geist is SIL OFL 1.1).
"""
import argparse
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACES = [
    ("Geist", 400, "Geist-Regular.ttf"),
    ("Geist", 700, "Geist-Bold.ttf"),
    ("Geist Mono", 400, "GeistMono-Regular.ttf"),
    ("Geist Mono", 700, "GeistMono-Bold.ttf"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=str(Path.home() / ".local/share/fonts/superstack-geist"))
    ap.add_argument("--badge", default=str(HERE.parent / "brand" / "vals-logo-badge.png"))
    args = ap.parse_args()
    css = []
    for family, weight, fname in FACES:
        data = base64.b64encode((Path(args.fonts) / fname).read_bytes()).decode()
        css.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:normal;"
            f"src:url(data:font/ttf;base64,{data}) format('truetype');}}"
        )
    src = (HERE / "index.src.html").read_text(encoding="utf-8")
    assert "/*@@FONTS@@*/" in src
    out = src.replace("/*@@FONTS@@*/", "\n".join(css))
    # Vals logo badge (logo on an off-white panel; the bare green logo is too low-contrast on navy).
    badge = base64.b64encode(Path(args.badge).read_bytes()).decode()
    out = out.replace("@@VALS_BADGE@@", f"data:image/png;base64,{badge}")
    (HERE / "index.html").write_text(out, encoding="utf-8")
    print(f"wrote {HERE / 'index.html'} ({len(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
