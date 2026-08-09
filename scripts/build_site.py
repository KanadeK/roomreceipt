"""Build the static landing page, live report, and downloadable sample bundle."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from build_example import build_example


def build_site(output: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    if output == root or root not in output.parents:
        raise ValueError("site output must be a directory inside the repository")
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1772323200")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(root / "site", output)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "downloads").mkdir(parents=True, exist_ok=True)
    build_root = root / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="site-example-", dir=build_root) as temporary:
        case = Path(temporary) / "case"
        bundle = build_example(case, root / "examples" / "bright-street")
        shutil.copytree(case / "report", output / "demo")
        shutil.copyfile(
            bundle,
            output / "downloads" / "roomreceipt-v0.1.0-example.roomreceipt.zip",
        )
        assets = output / "assets"
        shutil.copyfile(
            root / "examples" / "bright-street" / "source" / "move-in" / "living-north-wall.jpg",
            assets / "before.jpg",
        )
        shutil.copyfile(
            root / "examples" / "bright-street" / "source" / "move-out" / "living-north-wall.jpg",
            assets / "after.jpg",
        )
        shutil.copyfile(
            case / "comparison-assets" / "living-north-wall-diff.jpg", assets / "diff.jpg"
        )
    return output / "index.html"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".site-build"))
    args = parser.parse_args()
    print(build_site(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
