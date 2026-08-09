"""SHA-256 case seals and directory verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from roomreceipt.media import sha256_file
from roomreceipt.models import Finding, RoomReceiptError, VerificationResult
from roomreceipt.paths import current_timestamp, load_case, read_json, resolve_case_path, write_json

SEAL_SCHEMA_VERSION = 1
SEAL_DOMAIN = b"roomreceipt-case-seal-v1\n"


def hash_records(records: list[dict[str, object]], *, domain: bytes = SEAL_DOMAIN) -> str:
    digest = hashlib.sha256(domain)
    for record in sorted(records, key=lambda item: str(item["path"])):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _case_records(root: Path) -> list[dict[str, object]]:
    case = load_case(root)
    paths = ["case.json", *(entry.path for entry in case.entries)]
    records: list[dict[str, object]] = []
    for relative in sorted(set(paths)):
        path = resolve_case_path(root, relative)
        if not path.is_file():
            raise RoomReceiptError(f"cannot seal missing file: {relative}")
        records.append({"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size})
    return records


def seal_case(root: str | Path) -> dict[str, object]:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    records = _case_records(resolved)
    seal: dict[str, object] = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "algorithm": "sha256",
        "case_id": case.case_id,
        "created_at": current_timestamp(),
        "files": records,
        "root_sha256": hash_records(records),
        "claims": {
            "proves": "The listed bytes match this seal at verification time.",
            "does_not_prove": "Capture time, authorship, legal admissibility, or absence of edits before sealing.",
        },
    }
    write_json(resolved / "seal.json", seal)
    return seal


def _seal_records(data: object) -> list[dict[str, object]]:
    if not isinstance(data, list):
        raise RoomReceiptError("seal files must be an array")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise RoomReceiptError("seal file record must be an object")
        path = item.get("path")
        sha256 = item.get("sha256")
        size = item.get("size")
        if not isinstance(path, str) or not path:
            raise RoomReceiptError("seal file path must be a non-empty string")
        if path in seen:
            raise RoomReceiptError(f"duplicate seal path: {path}")
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise RoomReceiptError(f"invalid seal SHA-256 for {path}")
        if not isinstance(size, int) or size < 0:
            raise RoomReceiptError(f"invalid seal size for {path}")
        seen.add(path)
        records.append({"path": path, "sha256": sha256, "size": size})
    return records


def verify_directory(root: str | Path) -> VerificationResult:
    resolved = Path(root).expanduser().resolve()
    findings: list[Finding] = []
    seal_path = resolved / "seal.json"
    if not seal_path.is_file():
        return VerificationResult(
            ok=False,
            target=str(resolved),
            root_sha256="",
            checked_files=0,
            findings=(Finding("error", "SEAL_MISSING", "seal.json is missing"),),
        )
    try:
        seal: Any = read_json(seal_path)
        if not isinstance(seal, dict):
            raise RoomReceiptError("seal.json must contain an object")
        if seal.get("schema_version") != SEAL_SCHEMA_VERSION or seal.get("algorithm") != "sha256":
            raise RoomReceiptError("unsupported seal schema or algorithm")
        records = _seal_records(seal.get("files"))
    except RoomReceiptError as exc:
        return VerificationResult(
            ok=False,
            target=str(resolved),
            root_sha256="",
            checked_files=0,
            findings=(Finding("error", "SEAL_INVALID", str(exc), "seal.json"),),
        )

    checked = 0
    for record in records:
        relative = str(record["path"])
        try:
            path = resolve_case_path(resolved, relative)
        except RoomReceiptError as exc:
            findings.append(Finding("error", "PATH_UNSAFE", str(exc), relative))
            continue
        if not path.is_file():
            findings.append(Finding("error", "FILE_MISSING", "sealed file is missing", relative))
            continue
        checked += 1
        actual_size = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if actual_size != record["size"]:
            findings.append(Finding("error", "SIZE_MISMATCH", "sealed file size changed", relative))
        if actual_sha256 != record["sha256"]:
            findings.append(
                Finding("error", "HASH_MISMATCH", "sealed file bytes changed", relative)
            )

    expected_root = hash_records(records)
    recorded_root = seal.get("root_sha256")
    if recorded_root != expected_root:
        findings.append(
            Finding(
                "error", "ROOT_MISMATCH", "seal root does not match its file records", "seal.json"
            )
        )
    return VerificationResult(
        ok=not findings,
        target=str(resolved),
        root_sha256=expected_root,
        checked_files=checked,
        findings=tuple(findings),
    )
