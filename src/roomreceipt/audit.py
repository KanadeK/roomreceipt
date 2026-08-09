"""Evidence coverage and integrity audit."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from roomreceipt.media import sha256_file
from roomreceipt.models import Finding, RoomReceiptError
from roomreceipt.paths import load_case, resolve_case_path
from roomreceipt.seals import verify_directory


def audit_case(root: str | Path) -> dict[str, object]:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    findings: list[Finding] = []
    entry_keys = {(entry.phase, entry.slot) for entry in case.entries}

    if not case.expected_slots:
        findings.append(
            Finding("warning", "NO_EXPECTED_SLOTS", "no expected photo slots are defined")
        )
    for expected in case.expected_slots:
        if ("move-in", expected.slot) not in entry_keys:
            findings.append(
                Finding(
                    "error",
                    "MOVE_IN_MISSING",
                    f"move-in evidence is missing for {expected.room} / {expected.item} / {expected.view}",
                    expected.slot,
                )
            )
        if ("move-out", expected.slot) not in entry_keys:
            findings.append(
                Finding(
                    "warning",
                    "MOVE_OUT_MISSING",
                    f"move-out evidence is not present for {expected.room} / {expected.item} / {expected.view}",
                    expected.slot,
                )
            )

    hashes: defaultdict[str, list[str]] = defaultdict(list)
    for entry in case.entries:
        hashes[entry.sha256].append(f"{entry.phase}:{entry.slot}")
        try:
            path = resolve_case_path(resolved, entry.path)
        except RoomReceiptError as exc:
            findings.append(Finding("error", "PATH_UNSAFE", str(exc), entry.path))
            continue
        if not path.is_file():
            findings.append(
                Finding("error", "FILE_MISSING", "evidence file is missing", entry.path)
            )
            continue
        if path.stat().st_size != entry.size:
            findings.append(
                Finding("error", "SIZE_MISMATCH", "evidence file size changed", entry.path)
            )
        if sha256_file(path) != entry.sha256:
            findings.append(
                Finding("error", "HASH_MISMATCH", "evidence file bytes changed", entry.path)
            )
        if not entry.captured_at:
            findings.append(
                Finding(
                    "warning",
                    "CAPTURE_TIME_MISSING",
                    "no capture time was provided and none was found in EXIF",
                    entry.path,
                )
            )
        elif not entry.timezone_known:
            findings.append(
                Finding(
                    "warning",
                    "TIMEZONE_UNKNOWN",
                    "capture time has no timezone; keep corroborating records",
                    entry.path,
                )
            )
        if entry.width < 640 or entry.height < 420:
            findings.append(
                Finding(
                    "warning",
                    "LOW_RESOLUTION",
                    f"image resolution is only {entry.width}x{entry.height}",
                    entry.path,
                )
            )

    for digest, labels in hashes.items():
        if len(labels) > 1:
            findings.append(
                Finding(
                    "warning",
                    "DUPLICATE_BYTES",
                    f"identical image bytes are used by {', '.join(labels)}",
                    digest,
                )
            )

    seal_result = verify_directory(resolved)
    if not seal_result.ok:
        for finding in seal_result.findings:
            level = "warning" if finding.code == "SEAL_MISSING" else finding.level
            findings.append(Finding(level, finding.code, finding.message, finding.path))

    counts = {
        "errors": sum(item.level == "error" for item in findings),
        "warnings": sum(item.level == "warning" for item in findings),
        "info": sum(item.level == "info" for item in findings),
    }
    return {
        "ok": counts["errors"] == 0,
        "case_id": case.case_id,
        "expected_slots": len(case.expected_slots),
        "evidence_entries": len(case.entries),
        "counts": counts,
        "findings": [item.to_dict() for item in findings],
    }
