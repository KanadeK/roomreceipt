"""RoomReceipt command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from roomreceipt import __version__
from roomreceipt.audit import audit_case
from roomreceipt.bundle import create_bundle, verify_bundle
from roomreceipt.casework import add_evidence, add_expected_slot, import_manifest, init_case
from roomreceipt.compare import compare_case
from roomreceipt.models import RoomReceiptError
from roomreceipt.report import build_report
from roomreceipt.seals import seal_case, verify_directory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roomreceipt",
        description="Build and verify offline move-in and move-out photo evidence bundles.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create an empty case directory")
    init.add_argument("case")
    init.add_argument("--title", required=True)
    init.add_argument("--property", dest="property_label", required=True)
    init.add_argument("--unit", default="")
    init.add_argument("--case-id", default="")

    expect = commands.add_parser("expect", help="Declare one repeatable photo slot")
    expect.add_argument("case")
    _add_slot_arguments(expect)

    add = commands.add_parser("add", help="Copy one image into a case")
    add.add_argument("case")
    add.add_argument("phase", choices=("move-in", "move-out"))
    add.add_argument("source")
    _add_slot_arguments(add)
    add.add_argument("--note", default="")
    add.add_argument("--captured-at", default="")
    add.add_argument("--replace", action="store_true")

    batch = commands.add_parser("import", help="Import images from a CSV manifest")
    batch.add_argument("case")
    batch.add_argument("phase", choices=("move-in", "move-out"))
    batch.add_argument("manifest")

    compare = commands.add_parser("compare", help="Compare matching move-in and move-out slots")
    compare.add_argument("case")
    compare.add_argument("--json", action="store_true")

    audit = commands.add_parser("audit", help="Audit coverage, hashes, metadata, and seal state")
    audit.add_argument("case")
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--strict", action="store_true", help="Treat warnings as a failed audit")

    seal = commands.add_parser("seal", help="Write a SHA-256 case seal")
    seal.add_argument("case")
    seal.add_argument("--json", action="store_true")

    report = commands.add_parser("report", help="Generate a printable local HTML report")
    report.add_argument("case")
    report.add_argument("--output", default="report")

    bundle = commands.add_parser("bundle", help="Create a deterministic .roomreceipt.zip bundle")
    bundle.add_argument("case")
    bundle.add_argument("--output")

    verify = commands.add_parser("verify", help="Verify a case directory or bundle")
    verify.add_argument("target")
    verify.add_argument("--json", action="store_true")
    return parser


def _add_slot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slot", required=True, help="Stable key reused at move-in and move-out")
    parser.add_argument("--room", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--view", required=True)


def _json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _print_audit(data: dict[str, object]) -> None:
    counts = data["counts"]
    assert isinstance(counts, dict)
    print(
        f"case {data['case_id']}: {data['evidence_entries']} evidence files, "
        f"{counts['errors']} errors, {counts['warnings']} warnings"
    )
    findings = data["findings"]
    assert isinstance(findings, list)
    for finding in findings:
        assert isinstance(finding, dict)
        level = str(finding["level"])
        print(
            f"[{level.upper()}] {finding['code']}: {finding['message']}"
            + (f" ({finding['path']})" if finding["path"] else "")
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            case = init_case(
                args.case,
                title=args.title,
                property_label=args.property_label,
                unit=args.unit,
                case_id=args.case_id,
            )
            print(f"created {Path(args.case).resolve()} for case {case.case_id}")
        elif args.command == "expect":
            slot = add_expected_slot(
                args.case, slot=args.slot, room=args.room, item=args.item, view=args.view
            )
            print(f"expected slot: {slot.slot}")
        elif args.command == "add":
            entry = add_evidence(
                args.case,
                phase=args.phase,
                source=args.source,
                slot=args.slot,
                room=args.room,
                item=args.item,
                view=args.view,
                note=args.note,
                captured_at=args.captured_at,
                replace=args.replace,
            )
            print(f"added {entry.phase} / {entry.slot}: {entry.sha256}")
        elif args.command == "import":
            entries = import_manifest(args.case, phase=args.phase, manifest=args.manifest)
            print(f"imported {len(entries)} evidence files")
        elif args.command == "compare":
            comparison = compare_case(args.case)
            if args.json:
                _json(comparison)
            else:
                pairs = comparison["pairs"]
                unpaired = comparison["unpaired"]
                assert isinstance(pairs, list) and isinstance(unpaired, list)
                print(f"compared {len(pairs)} pairs; {len(unpaired)} slots remain unpaired")
        elif args.command == "audit":
            audit = audit_case(args.case)
            if args.json:
                _json(audit)
            else:
                _print_audit(audit)
            counts = audit["counts"]
            assert isinstance(counts, dict)
            if int(counts["errors"]) or (args.strict and int(counts["warnings"])):
                return 1
        elif args.command == "seal":
            seal = seal_case(args.case)
            if args.json:
                _json(seal)
            else:
                files = seal["files"]
                assert isinstance(files, list)
                print(f"sealed {len(files)} files: {seal['root_sha256']}")
        elif args.command == "report":
            report = build_report(args.case, args.output)
            print(f"wrote {report}")
        elif args.command == "bundle":
            bundle = create_bundle(args.case, args.output)
            print(f"wrote {bundle}")
        elif args.command == "verify":
            target = Path(args.target)
            result = verify_directory(target) if target.is_dir() else verify_bundle(target)
            if args.json:
                _json(result.to_dict())
            elif result.ok:
                print(f"verified {result.checked_files} files: {result.root_sha256}")
            else:
                print(f"verification failed: {result.target}", file=sys.stderr)
                for finding in result.findings:
                    print(
                        f"[{finding.code}] {finding.message} {finding.path}".rstrip(),
                        file=sys.stderr,
                    )
            return 0 if result.ok else 1
        else:
            raise AssertionError(f"unhandled command: {args.command}")
    except RoomReceiptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
