"""Build the deterministic example bundle and SHA256SUMS release manifest."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
from pathlib import Path

from build_example import build_example


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dist = args.dist.resolve()
    dist.mkdir(parents=True, exist_ok=True)
    build_root = root / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-example-", dir=build_root) as temporary:
        bundle = build_example(Path(temporary) / "case", root / "examples" / "bright-street")
        destination = dist / "roomreceipt-v0.1.0-example.roomreceipt.zip"
        shutil.copyfile(bundle, destination)

    assets = sorted(path for path in dist.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    lines = [f"{sha256(path)}  {path.name}" for path in assets]
    (dist / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    print(f"release assets: {len(assets)} plus SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
