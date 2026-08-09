"""Case creation and transactional evidence import."""

from __future__ import annotations

import csv
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from roomreceipt.media import ImageMetadata, inspect_image
from roomreceipt.models import PHASES, CaseFile, EvidenceEntry, ExpectedSlot, RoomReceiptError
from roomreceipt.paths import current_timestamp, load_case, relative_posix, save_case, slugify


@dataclass(frozen=True, slots=True)
class _PreparedEntry:
    source: Path
    destination: Path
    entry: EvidenceEntry
    expected_slot: ExpectedSlot


def init_case(
    root: str | Path,
    *,
    title: str,
    property_label: str,
    unit: str = "",
    case_id: str = "",
) -> CaseFile:
    destination = Path(root).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise RoomReceiptError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "evidence" / "move-in").mkdir(parents=True, exist_ok=True)
    (destination / "evidence" / "move-out").mkdir(parents=True, exist_ok=True)
    case = CaseFile(
        case_id=slugify(case_id or title),
        title=title.strip(),
        property_label=property_label.strip(),
        unit=unit.strip(),
        created_at=current_timestamp(),
    )
    if not case.title or not case.property_label:
        raise RoomReceiptError("title and property label must not be empty")
    save_case(destination, case)
    return case


def add_expected_slot(
    root: str | Path, *, slot: str, room: str, item: str, view: str
) -> ExpectedSlot:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    expected = ExpectedSlot(
        slot=slugify(slot, fallback="slot"),
        room=room.strip(),
        item=item.strip(),
        view=view.strip(),
    )
    if not expected.room or not expected.item or not expected.view:
        raise RoomReceiptError("room, item, and view must not be empty")
    existing = next((value for value in case.expected_slots if value.slot == expected.slot), None)
    if existing is not None:
        if existing != expected:
            raise RoomReceiptError(
                f"slot {expected.slot!r} already exists with different room, item, or view"
            )
        return existing
    case.expected_slots.append(expected)
    case.expected_slots.sort(key=lambda value: value.slot)
    save_case(resolved, case)
    return expected


def _validate_phase(phase: str) -> str:
    normalized = phase.strip().lower()
    if normalized not in PHASES:
        raise RoomReceiptError(f"phase must be one of {', '.join(PHASES)}")
    return normalized


def _destination_for(root: Path, phase: str, slot: str, room: str, source: Path) -> Path:
    suffix = source.suffix.lower() or ".img"
    return root / "evidence" / phase / slugify(room, fallback="room") / f"{slot}{suffix}"


def _entry_id(phase: str, slot: str, sha256: str) -> str:
    return hashlib.sha256(f"{phase}\0{slot}\0{sha256}".encode()).hexdigest()[:20]


def _prepare_entry(
    root: Path,
    *,
    phase: str,
    source: Path,
    slot: str,
    room: str,
    item: str,
    view: str,
    note: str,
    captured_at: str,
    imported_at: str,
) -> _PreparedEntry:
    normalized_phase = _validate_phase(phase)
    normalized_slot = slugify(slot, fallback="slot")
    source_path = source.expanduser().resolve()
    metadata: ImageMetadata = inspect_image(source_path, captured_at=captured_at)
    expected = ExpectedSlot(
        slot=normalized_slot,
        room=room.strip(),
        item=item.strip(),
        view=view.strip(),
    )
    if not expected.room or not expected.item or not expected.view:
        raise RoomReceiptError("room, item, and view must not be empty")
    destination = _destination_for(
        root, normalized_phase, normalized_slot, expected.room, source_path
    )
    entry = EvidenceEntry(
        id=_entry_id(normalized_phase, normalized_slot, metadata.sha256),
        phase=normalized_phase,
        slot=normalized_slot,
        room=expected.room,
        item=expected.item,
        view=expected.view,
        note=note.strip(),
        path=relative_posix(root, destination),
        sha256=metadata.sha256,
        size=metadata.size,
        mime=metadata.mime,
        width=metadata.width,
        height=metadata.height,
        captured_at=metadata.captured_at,
        capture_source=metadata.capture_source,
        timezone_known=metadata.timezone_known,
        gps_present=metadata.gps_present,
        imported_at=imported_at,
    )
    return _PreparedEntry(source_path, destination, entry, expected)


def _assert_slot_compatible(case: CaseFile, expected: ExpectedSlot) -> None:
    existing = next((value for value in case.expected_slots if value.slot == expected.slot), None)
    if existing is not None and existing != expected:
        raise RoomReceiptError(
            f"slot {expected.slot!r} already uses {existing.room} / {existing.item} / {existing.view}"
        )


def add_evidence(
    root: str | Path,
    *,
    phase: str,
    source: str | Path,
    slot: str,
    room: str,
    item: str,
    view: str,
    note: str = "",
    captured_at: str = "",
    replace: bool = False,
) -> EvidenceEntry:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    prepared = _prepare_entry(
        resolved,
        phase=phase,
        source=Path(source),
        slot=slot,
        room=room,
        item=item,
        view=view,
        note=note,
        captured_at=captured_at,
        imported_at=current_timestamp(),
    )
    _assert_slot_compatible(case, prepared.expected_slot)
    existing = next(
        (
            value
            for value in case.entries
            if value.phase == prepared.entry.phase and value.slot == prepared.entry.slot
        ),
        None,
    )
    if existing is not None and not replace:
        raise RoomReceiptError(
            f"{prepared.entry.phase} evidence already exists for slot {prepared.entry.slot!r}; "
            "use --replace to replace it"
        )

    prepared.destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = prepared.destination.with_name(f".{prepared.destination.name}.importing")
    shutil.copyfile(prepared.source, temporary)
    temporary.replace(prepared.destination)

    if existing is not None:
        case.entries.remove(existing)
        old_path = resolved / Path(existing.path)
        if old_path != prepared.destination and old_path.is_file():
            old_path.unlink()
    if not any(value.slot == prepared.expected_slot.slot for value in case.expected_slots):
        case.expected_slots.append(prepared.expected_slot)
    case.entries.append(prepared.entry)
    case.expected_slots.sort(key=lambda value: value.slot)
    case.entries.sort(key=lambda value: (value.slot, value.phase))
    save_case(resolved, case)
    return prepared.entry


def import_manifest(root: str | Path, *, phase: str, manifest: str | Path) -> list[EvidenceEntry]:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    manifest_path = Path(manifest).expanduser().resolve()
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"source", "slot", "room", "item", "view"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                missing = sorted(required - set(reader.fieldnames or []))
                raise RoomReceiptError(f"manifest is missing columns: {', '.join(missing)}")
            rows = list(reader)
    except FileNotFoundError as exc:
        raise RoomReceiptError(f"manifest does not exist: {manifest_path}") from exc
    if not rows:
        raise RoomReceiptError("manifest has no evidence rows")

    imported_at = current_timestamp()
    prepared_entries: list[_PreparedEntry] = []
    seen_keys = {(entry.phase, entry.slot) for entry in case.entries}
    seen_destinations: set[Path] = set()
    for index, row in enumerate(rows, start=2):
        source_value = (row.get("source") or "").strip()
        source_path = Path(source_value)
        if not source_path.is_absolute():
            source_path = manifest_path.parent / source_path
        prepared = _prepare_entry(
            resolved,
            phase=phase,
            source=source_path,
            slot=row.get("slot") or "",
            room=row.get("room") or "",
            item=row.get("item") or "",
            view=row.get("view") or "",
            note=row.get("note") or "",
            captured_at=row.get("captured_at") or "",
            imported_at=imported_at,
        )
        key = (prepared.entry.phase, prepared.entry.slot)
        if key in seen_keys:
            raise RoomReceiptError(
                f"manifest row {index} duplicates existing phase and slot: {key[0]} / {key[1]}"
            )
        if prepared.destination in seen_destinations or prepared.destination.exists():
            raise RoomReceiptError(
                f"manifest row {index} would overwrite an existing file: {prepared.destination}"
            )
        _assert_slot_compatible(case, prepared.expected_slot)
        seen_keys.add(key)
        seen_destinations.add(prepared.destination)
        prepared_entries.append(prepared)

    copied: list[Path] = []
    try:
        for prepared in prepared_entries:
            prepared.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(prepared.source, prepared.destination)
            copied.append(prepared.destination)
        known_slots = {value.slot for value in case.expected_slots}
        for prepared in prepared_entries:
            if prepared.expected_slot.slot not in known_slots:
                case.expected_slots.append(prepared.expected_slot)
                known_slots.add(prepared.expected_slot.slot)
            case.entries.append(prepared.entry)
        case.expected_slots.sort(key=lambda value: value.slot)
        case.entries.sort(key=lambda value: (value.slot, value.phase))
        save_case(resolved, case)
    except Exception:
        for path in copied:
            path.unlink(missing_ok=True)
        raise
    return [value.entry for value in prepared_entries]
