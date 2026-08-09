from __future__ import annotations

from pathlib import Path

import pytest

from roomreceipt.models import (
    CaseFile,
    EvidenceEntry,
    ExpectedSlot,
    Finding,
    RoomReceiptError,
    VerificationResult,
)
from roomreceipt.paths import (
    canonical_json_bytes,
    case_root,
    current_timestamp,
    read_json,
    relative_posix,
    resolve_case_path,
    slugify,
    write_json,
)


def test_slugify_normalizes_and_has_fallback() -> None:
    assert slugify(" Living Room / North Wall ") == "living-room-north-wall"
    assert slugify("谱校", fallback="record") == "record"
    assert len(slugify("a" * 100)) == 80


def test_current_timestamp_uses_source_date_epoch() -> None:
    assert current_timestamp() == "2026-03-01T00:00:00Z"


def test_current_timestamp_rejects_invalid_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-an-integer")
    with pytest.raises(RoomReceiptError, match="integer Unix timestamp"):
        current_timestamp()


def test_current_timestamp_uses_clock_without_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH")
    value = current_timestamp()
    assert value.endswith("Z") and "T" in value


def test_canonical_json_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "value.json"
    write_json(path, {"z": 1, "a": "值"})
    assert path.read_bytes() == canonical_json_bytes({"z": 1, "a": "值"})
    assert read_json(path) == {"a": "值", "z": 1}


def test_read_json_errors_are_actionable(tmp_path: Path) -> None:
    with pytest.raises(RoomReceiptError, match="missing file"):
        read_json(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(RoomReceiptError, match="invalid JSON"):
        read_json(broken)


def test_case_root_and_relative_path_errors(tmp_path: Path) -> None:
    with pytest.raises(RoomReceiptError, match="not a RoomReceipt case"):
        case_root(tmp_path)
    outside = tmp_path.parent / "outside.jpg"
    with pytest.raises(RoomReceiptError, match="outside"):
        relative_posix(tmp_path, outside)


@pytest.mark.parametrize("relative", ["../escape.jpg", "folder\\escape.jpg", ""])
def test_resolve_case_path_rejects_unsafe_paths(tmp_path: Path, relative: str) -> None:
    with pytest.raises(RoomReceiptError, match=r"unsafe|escapes"):
        resolve_case_path(tmp_path, relative)


def test_case_model_round_trip_and_duplicate_validation() -> None:
    entry = EvidenceEntry(
        id="entry",
        phase="move-in",
        slot="wall",
        room="Living room",
        item="Wall",
        view="Wide",
        note="",
        path="evidence/move-in/living-room/wall.jpg",
        sha256="a" * 64,
        size=1,
        mime="image/jpeg",
        width=10,
        height=10,
        captured_at="",
        capture_source="unknown",
        timezone_known=False,
        gps_present=False,
        imported_at="2026-03-01T00:00:00Z",
    )
    case = CaseFile(
        case_id="case",
        title="Title",
        property_label="Property",
        unit="",
        created_at="2026-03-01T00:00:00Z",
        expected_slots=[ExpectedSlot("wall", "Living room", "Wall", "Wide")],
        entries=[entry],
    )
    assert CaseFile.from_dict(case.to_dict()).to_dict() == case.to_dict()
    case.entries.append(entry)
    with pytest.raises(RoomReceiptError, match="phase and slot"):
        case.validate_uniqueness()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "unsupported schema"),
        ({"schema_version": 1}, "property"),
        (
            {
                "schema_version": 1,
                "case_id": "case",
                "title": "Title",
                "property": {"label": "Property"},
                "created_at": "now",
                "expected_slots": {},
                "entries": [],
            },
            "must be arrays",
        ),
    ],
)
def test_case_model_rejects_invalid_shapes(data: object, message: str) -> None:
    with pytest.raises(RoomReceiptError, match=message):
        CaseFile.from_dict(data)


def _entry_data() -> dict[str, object]:
    return {
        "id": "entry",
        "phase": "move-in",
        "slot": "wall",
        "room": "Living",
        "item": "Wall",
        "view": "Wide",
        "note": "",
        "path": "evidence/move-in/wall.jpg",
        "sha256": "a" * 64,
        "size": 1,
        "mime": "image/jpeg",
        "width": 10,
        "height": 10,
        "captured_at": "",
        "capture_source": "unknown",
        "timezone_known": False,
        "gps_present": False,
        "imported_at": "2026-03-01T00:00:00Z",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("phase", "during", "one of"),
        ("size", -1, "non-negative"),
        ("width", 0, "positive"),
        ("height", 0, "positive"),
        ("timezone_known", "no", "flags"),
        ("note", 4, "must be a string"),
    ],
)
def test_entry_model_rejects_bad_fields(field: str, value: object, message: str) -> None:
    data = _entry_data()
    data[field] = value
    with pytest.raises(RoomReceiptError, match=message):
        EvidenceEntry.from_dict(data)


def test_small_model_shapes_and_serializers() -> None:
    with pytest.raises(RoomReceiptError, match="expected slot"):
        ExpectedSlot.from_dict([])
    with pytest.raises(RoomReceiptError, match="entry must"):
        EvidenceEntry.from_dict([])
    finding = Finding("error", "BROKEN", "Broken", "case.json")
    result = VerificationResult(False, "case", "", 0, (finding,))
    assert finding.to_dict()["code"] == "BROKEN"
    assert result.to_dict()["findings"] == [finding.to_dict()]
