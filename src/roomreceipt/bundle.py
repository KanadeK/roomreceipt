"""Deterministic RoomReceipt bundle creation and verification."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from roomreceipt.compare import compare_case
from roomreceipt.media import sha256_file
from roomreceipt.models import Finding, RoomReceiptError, VerificationResult
from roomreceipt.paths import current_timestamp, load_case
from roomreceipt.report import build_report
from roomreceipt.seals import SEAL_DOMAIN, hash_records, seal_case, verify_directory

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_DOMAIN = b"roomreceipt-bundle-v1\n"


def _included_paths(root: Path) -> list[Path]:
    candidates = [root / "case.json", root / "seal.json", root / "comparison.json"]
    for directory in (root / "evidence", root / "comparison-assets", root / "report"):
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(candidates), key=lambda path: path.relative_to(root).as_posix())


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def create_bundle(root: str | Path, output: str | Path | None = None) -> Path:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    compare_case(resolved)
    if not verify_directory(resolved).ok:
        seal_case(resolved)
    build_report(resolved, "report")

    if output is None:
        output_path = resolved / f"{case.case_id}.roomreceipt.zip"
    else:
        output_path = Path(output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = _included_paths(resolved)
    records = [
        {
            "path": path.relative_to(resolved).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
        for path in files
    ]
    seal = json.loads((resolved / "seal.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "algorithm": "sha256",
        "case_id": case.case_id,
        "created_at": current_timestamp(),
        "case_root_sha256": seal["root_sha256"],
        "files": records,
        "root_sha256": hash_records(records, domain=BUNDLE_DOMAIN),
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    temporary = output_path.with_name(f".{output_path.name}.tmp")
    with zipfile.ZipFile(
        temporary, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for record, path in zip(records, files, strict=True):
            archive.writestr(_zip_info(str(record["path"])), path.read_bytes())
        archive.writestr(_zip_info("bundle-manifest.json"), manifest_bytes)
    temporary.replace(output_path)
    return output_path


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and "\\" not in name and not path.is_absolute() and ".." not in path.parts


def _validated_records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RoomReceiptError("bundle files must be an array")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise RoomReceiptError("bundle file record must be an object")
        path = item.get("path")
        digest = item.get("sha256")
        size = item.get("size")
        if not isinstance(path, str) or not _safe_member(path):
            raise RoomReceiptError(f"unsafe bundle path: {path!r}")
        if path in seen:
            raise RoomReceiptError(f"duplicate bundle path: {path}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RoomReceiptError(f"invalid SHA-256 for bundle path: {path}")
        if not isinstance(size, int) or size < 0:
            raise RoomReceiptError(f"invalid size for bundle path: {path}")
        seen.add(path)
        records.append({"path": path, "sha256": digest, "size": size})
    return records


def verify_bundle(target: str | Path) -> VerificationResult:
    path = Path(target).expanduser().resolve()
    findings: list[Finding] = []
    checked = 0
    root_sha256 = ""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                findings.append(Finding("error", "DUPLICATE_MEMBER", "bundle has duplicate names"))
            for name in names:
                if not _safe_member(name):
                    findings.append(Finding("error", "PATH_UNSAFE", "unsafe ZIP member", name))
            manifest_raw = archive.read("bundle-manifest.json")
            manifest: Any = json.loads(manifest_raw.decode("utf-8"))
            if not isinstance(manifest, dict):
                raise RoomReceiptError("bundle-manifest.json must contain an object")
            if (
                manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION
                or manifest.get("algorithm") != "sha256"
            ):
                raise RoomReceiptError("unsupported bundle schema or algorithm")
            records = _validated_records(manifest.get("files"))
            expected_names = {str(record["path"]) for record in records} | {"bundle-manifest.json"}
            for extra in sorted(set(names) - expected_names):
                findings.append(
                    Finding("error", "UNLISTED_MEMBER", "unlisted bundle member", extra)
                )
            for missing in sorted(expected_names - set(names)):
                findings.append(
                    Finding("error", "MEMBER_MISSING", "listed member is missing", missing)
                )

            for record in records:
                member = str(record["path"])
                if member not in names:
                    continue
                payload = archive.read(member)
                checked += 1
                if len(payload) != record["size"]:
                    findings.append(
                        Finding("error", "SIZE_MISMATCH", "bundle member size changed", member)
                    )
                if hashlib.sha256(payload).hexdigest() != record["sha256"]:
                    findings.append(
                        Finding("error", "HASH_MISMATCH", "bundle member bytes changed", member)
                    )

            root_sha256 = hash_records(records, domain=BUNDLE_DOMAIN)
            if manifest.get("root_sha256") != root_sha256:
                findings.append(
                    Finding("error", "ROOT_MISMATCH", "bundle root does not match its file records")
                )

            seal: Any = json.loads(archive.read("seal.json").decode("utf-8"))
            if not isinstance(seal, dict):
                raise RoomReceiptError("seal.json must contain an object")
            seal_records = _validated_records(seal.get("files"))
            seal_root = hash_records(seal_records, domain=SEAL_DOMAIN)
            if seal.get("root_sha256") != seal_root:
                findings.append(
                    Finding("error", "CASE_ROOT_MISMATCH", "embedded case seal root is invalid")
                )
            if manifest.get("case_root_sha256") != seal_root:
                findings.append(
                    Finding(
                        "error",
                        "CASE_ROOT_UNLINKED",
                        "bundle does not link to the embedded case seal",
                    )
                )
            for record in seal_records:
                member = str(record["path"])
                if member not in names:
                    findings.append(
                        Finding("error", "SEALED_MEMBER_MISSING", "sealed member is absent", member)
                    )
                    continue
                payload = archive.read(member)
                if hashlib.sha256(payload).hexdigest() != record["sha256"]:
                    findings.append(
                        Finding(
                            "error", "SEALED_HASH_MISMATCH", "sealed member bytes changed", member
                        )
                    )
    except FileNotFoundError:
        findings.append(Finding("error", "BUNDLE_MISSING", "bundle file does not exist", str(path)))
    except (
        zipfile.BadZipFile,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        RoomReceiptError,
    ) as exc:
        findings.append(Finding("error", "BUNDLE_INVALID", str(exc), str(path)))

    return VerificationResult(
        ok=not findings,
        target=str(path),
        root_sha256=root_sha256,
        checked_files=checked,
        findings=tuple(findings),
    )
