"""Filesystem safety and canonical JSON helpers."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from roomreceipt.models import CaseFile, RoomReceiptError


def slugify(value: str, *, fallback: str = "case") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return (slug or fallback)[:80]


def current_timestamp() -> str:
    source_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_epoch:
        try:
            instant = datetime.fromtimestamp(int(source_epoch), tz=UTC)
        except (ValueError, OSError) as exc:
            raise RoomReceiptError("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from exc
    else:
        instant = datetime.now(tz=UTC)
    return instant.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(canonical_json_bytes(data))
    temporary.replace(path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoomReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoomReceiptError(f"invalid JSON in {path}: {exc}") from exc


def case_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not (root / "case.json").is_file():
        raise RoomReceiptError(f"not a RoomReceipt case: {root}")
    return root


def load_case(root: str | Path) -> CaseFile:
    resolved = case_root(root)
    return CaseFile.from_dict(read_json(resolved / "case.json"))


def save_case(root: Path, case: CaseFile) -> None:
    case.validate_uniqueness()
    write_json(root / "case.json", case.to_dict())


def resolve_case_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative:
        raise RoomReceiptError(f"unsafe case-relative path: {relative!r}")
    candidate = (root / Path(relative)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RoomReceiptError(f"path escapes the case directory: {relative}") from exc
    return candidate


def relative_posix(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise RoomReceiptError(f"path is outside the case directory: {path}") from exc
