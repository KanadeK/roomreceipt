"""Validated, dependency-free data models for the RoomReceipt case format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
PHASES = ("move-in", "move-out")


class RoomReceiptError(ValueError):
    """Raised for an invalid case, unsafe path, or failed verification."""


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoomReceiptError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RoomReceiptError(f"{field_name} must be a string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class ExpectedSlot:
    slot: str
    room: str
    item: str
    view: str

    @classmethod
    def from_dict(cls, data: object) -> ExpectedSlot:
        if not isinstance(data, dict):
            raise RoomReceiptError("expected slot must be an object")
        return cls(
            slot=_require_text(data.get("slot"), "expected_slots.slot"),
            room=_require_text(data.get("room"), "expected_slots.room"),
            item=_require_text(data.get("item"), "expected_slots.item"),
            view=_require_text(data.get("view"), "expected_slots.view"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"slot": self.slot, "room": self.room, "item": self.item, "view": self.view}


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    id: str
    phase: str
    slot: str
    room: str
    item: str
    view: str
    note: str
    path: str
    sha256: str
    size: int
    mime: str
    width: int
    height: int
    captured_at: str
    capture_source: str
    timezone_known: bool
    gps_present: bool
    imported_at: str

    @classmethod
    def from_dict(cls, data: object) -> EvidenceEntry:
        if not isinstance(data, dict):
            raise RoomReceiptError("entry must be an object")
        phase = _require_text(data.get("phase"), "entries.phase")
        if phase not in PHASES:
            raise RoomReceiptError(f"entries.phase must be one of {', '.join(PHASES)}")
        size = data.get("size")
        width = data.get("width")
        height = data.get("height")
        if not isinstance(size, int) or size < 0:
            raise RoomReceiptError("entries.size must be a non-negative integer")
        if not isinstance(width, int) or width <= 0:
            raise RoomReceiptError("entries.width must be a positive integer")
        if not isinstance(height, int) or height <= 0:
            raise RoomReceiptError("entries.height must be a positive integer")
        timezone_known = data.get("timezone_known")
        gps_present = data.get("gps_present")
        if not isinstance(timezone_known, bool) or not isinstance(gps_present, bool):
            raise RoomReceiptError("entry metadata flags must be booleans")
        return cls(
            id=_require_text(data.get("id"), "entries.id"),
            phase=phase,
            slot=_require_text(data.get("slot"), "entries.slot"),
            room=_require_text(data.get("room"), "entries.room"),
            item=_require_text(data.get("item"), "entries.item"),
            view=_require_text(data.get("view"), "entries.view"),
            note=_optional_text(data.get("note"), "entries.note"),
            path=_require_text(data.get("path"), "entries.path"),
            sha256=_require_text(data.get("sha256"), "entries.sha256"),
            size=size,
            mime=_require_text(data.get("mime"), "entries.mime"),
            width=width,
            height=height,
            captured_at=_optional_text(data.get("captured_at"), "entries.captured_at"),
            capture_source=_require_text(data.get("capture_source"), "entries.capture_source"),
            timezone_known=timezone_known,
            gps_present=gps_present,
            imported_at=_require_text(data.get("imported_at"), "entries.imported_at"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "phase": self.phase,
            "slot": self.slot,
            "room": self.room,
            "item": self.item,
            "view": self.view,
            "note": self.note,
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "mime": self.mime,
            "width": self.width,
            "height": self.height,
            "captured_at": self.captured_at,
            "capture_source": self.capture_source,
            "timezone_known": self.timezone_known,
            "gps_present": self.gps_present,
            "imported_at": self.imported_at,
        }


@dataclass(slots=True)
class CaseFile:
    case_id: str
    title: str
    property_label: str
    unit: str
    created_at: str
    expected_slots: list[ExpectedSlot] = field(default_factory=list)
    entries: list[EvidenceEntry] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: object) -> CaseFile:
        if not isinstance(data, dict):
            raise RoomReceiptError("case.json must contain an object")
        schema_version = data.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise RoomReceiptError(
                f"unsupported schema_version {schema_version!r}; expected {SCHEMA_VERSION}"
            )
        property_data = data.get("property")
        if not isinstance(property_data, dict):
            raise RoomReceiptError("property must be an object")
        raw_slots = data.get("expected_slots", [])
        raw_entries = data.get("entries", [])
        if not isinstance(raw_slots, list) or not isinstance(raw_entries, list):
            raise RoomReceiptError("expected_slots and entries must be arrays")
        case = cls(
            schema_version=SCHEMA_VERSION,
            case_id=_require_text(data.get("case_id"), "case_id"),
            title=_require_text(data.get("title"), "title"),
            property_label=_require_text(property_data.get("label"), "property.label"),
            unit=_optional_text(property_data.get("unit"), "property.unit"),
            created_at=_require_text(data.get("created_at"), "created_at"),
            expected_slots=[ExpectedSlot.from_dict(item) for item in raw_slots],
            entries=[EvidenceEntry.from_dict(item) for item in raw_entries],
        )
        case.validate_uniqueness()
        return case

    def validate_uniqueness(self) -> None:
        slots = [item.slot for item in self.expected_slots]
        if len(slots) != len(set(slots)):
            raise RoomReceiptError("expected slot names must be unique")
        entry_keys = [(item.phase, item.slot) for item in self.entries]
        if len(entry_keys) != len(set(entry_keys)):
            raise RoomReceiptError("each phase and slot pair may have only one evidence entry")
        entry_ids = [item.id for item in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise RoomReceiptError("entry ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "title": self.title,
            "property": {"label": self.property_label, "unit": self.unit},
            "created_at": self.created_at,
            "expected_slots": [item.to_dict() for item in self.expected_slots],
            "entries": [item.to_dict() for item in self.entries],
        }


@dataclass(frozen=True, slots=True)
class Finding:
    level: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    target: str
    root_sha256: str
    checked_files: int
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": self.target,
            "root_sha256": self.root_sha256,
            "checked_files": self.checked_files,
            "findings": [item.to_dict() for item in self.findings],
        }
