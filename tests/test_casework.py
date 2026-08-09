from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

import pytest

from roomreceipt.casework import add_evidence, add_expected_slot, import_manifest, init_case
from roomreceipt.models import RoomReceiptError
from roomreceipt.paths import load_case


def _case(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    init_case(root, title="Bright Street", property_label="14 Bright Street", unit="4B")
    return root


def test_init_case_creates_structure_and_rejects_nonempty(tmp_path: Path) -> None:
    root = _case(tmp_path)
    case = load_case(root)
    assert case.case_id == "bright-street"
    assert (root / "evidence" / "move-in").is_dir()
    with pytest.raises(RoomReceiptError, match="not empty"):
        init_case(root, title="Again", property_label="Again")


def test_expected_slot_is_idempotent_but_conflicts_are_rejected(tmp_path: Path) -> None:
    root = _case(tmp_path)
    first = add_expected_slot(root, slot="Wall North", room="Living", item="Wall", view="Wide")
    second = add_expected_slot(root, slot="wall-north", room="Living", item="Wall", view="Wide")
    assert first == second
    with pytest.raises(RoomReceiptError, match="different"):
        add_expected_slot(root, slot="wall-north", room="Kitchen", item="Wall", view="Wide")


def test_add_evidence_copies_and_extracts_exif(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _case(tmp_path)
    source = image_factory(tmp_path / "source.jpg")
    entry = add_evidence(
        root,
        phase="move-in",
        source=source,
        slot="north-wall",
        room="Living room",
        item="North wall",
        view="Wide",
        note="Small scuff",
    )
    assert entry.capture_source == "exif"
    assert entry.captured_at == "2026-03-01T09:15:00"
    assert (root / entry.path).read_bytes() == source.read_bytes()
    case = load_case(root)
    assert len(case.expected_slots) == 1
    assert len(case.entries) == 1


def test_add_evidence_requires_replace_and_removes_old_path(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _case(tmp_path)
    first = image_factory(tmp_path / "first.jpg", marker=(10, 20, 30))
    second = image_factory(tmp_path / "second.png", marker=(200, 20, 30))
    original = add_evidence(
        root,
        phase="move-in",
        source=first,
        slot="wall",
        room="Living",
        item="Wall",
        view="Wide",
    )
    with pytest.raises(RoomReceiptError, match="--replace"):
        add_evidence(
            root,
            phase="move-in",
            source=second,
            slot="wall",
            room="Living",
            item="Wall",
            view="Wide",
        )
    replacement = add_evidence(
        root,
        phase="move-in",
        source=second,
        slot="wall",
        room="Living",
        item="Wall",
        view="Wide",
        replace=True,
    )
    assert replacement.sha256 != original.sha256
    assert not (root / original.path).exists()
    assert (root / replacement.path).is_file()


def test_add_evidence_rejects_bad_phase_and_nonimage(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _case(tmp_path)
    image = image_factory(tmp_path / "image.jpg")
    with pytest.raises(RoomReceiptError, match="phase"):
        add_evidence(
            root,
            phase="during",
            source=image,
            slot="wall",
            room="Living",
            item="Wall",
            view="Wide",
        )
    text = tmp_path / "not-image.txt"
    text.write_text("not an image", encoding="utf-8")
    with pytest.raises(RoomReceiptError, match="invalid image"):
        add_evidence(
            root,
            phase="move-in",
            source=text,
            slot="wall",
            room="Living",
            item="Wall",
            view="Wide",
        )


def _write_manifest(
    path: Path, rows: list[dict[str, str]], fields: list[str] | None = None
) -> None:
    fieldnames = fields or ["source", "slot", "room", "item", "view", "note", "captured_at"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_import_manifest_is_relative_and_batch_atomic(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _case(tmp_path)
    source_dir = tmp_path / "batch"
    image_factory(source_dir / "wall.jpg")
    image_factory(source_dir / "counter.jpg", marker=(80, 40, 20))
    manifest = source_dir / "manifest.csv"
    _write_manifest(
        manifest,
        [
            {
                "source": "wall.jpg",
                "slot": "wall",
                "room": "Living",
                "item": "Wall",
                "view": "Wide",
            },
            {
                "source": "counter.jpg",
                "slot": "counter",
                "room": "Kitchen",
                "item": "Counter",
                "view": "Wide",
            },
        ],
    )
    entries = import_manifest(root, phase="move-in", manifest=manifest)
    assert [entry.slot for entry in entries] == ["wall", "counter"]
    assert len(load_case(root).entries) == 2

    duplicate_manifest = source_dir / "duplicate.csv"
    _write_manifest(
        duplicate_manifest,
        [
            {"source": "wall.jpg", "slot": "door", "room": "Entry", "item": "Door", "view": "Wide"},
            {
                "source": "counter.jpg",
                "slot": "door",
                "room": "Entry",
                "item": "Door",
                "view": "Wide",
            },
        ],
    )
    before = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
    with pytest.raises(RoomReceiptError, match="duplicates"):
        import_manifest(root, phase="move-out", manifest=duplicate_manifest)
    after = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
    assert after == before


def test_import_manifest_validates_columns_and_rows(tmp_path: Path) -> None:
    root = _case(tmp_path)
    missing = tmp_path / "missing.csv"
    _write_manifest(missing, [], fields=["source", "slot"])
    with pytest.raises(RoomReceiptError, match="missing columns"):
        import_manifest(root, phase="move-in", manifest=missing)
    empty = tmp_path / "empty.csv"
    _write_manifest(empty, [])
    with pytest.raises(RoomReceiptError, match="no evidence rows"):
        import_manifest(root, phase="move-in", manifest=empty)
