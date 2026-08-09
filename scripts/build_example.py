"""Build the committed Bright Street fixture into a complete RoomReceipt case."""

from __future__ import annotations

import argparse
from pathlib import Path

from roomreceipt.bundle import create_bundle
from roomreceipt.casework import import_manifest, init_case
from roomreceipt.compare import compare_case
from roomreceipt.report import build_report
from roomreceipt.seals import seal_case


def build_example(output: Path, source: Path) -> Path:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"example output must be empty: {output}")
    init_case(
        output,
        title="Bright Street move-in and move-out",
        property_label="14 Bright Street",
        unit="4B",
        case_id="bright-street-demo",
    )
    import_manifest(output, phase="move-in", manifest=source / "move-in.csv")
    import_manifest(output, phase="move-out", manifest=source / "move-out.csv")
    compare_case(output)
    seal_case(output)
    build_report(output)
    return create_bundle(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("examples/bright-street"))
    args = parser.parse_args()
    bundle = build_example(args.output, args.source.resolve())
    print(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
