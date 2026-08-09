from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from roomreceipt.audit import audit_case
from roomreceipt.casework import add_evidence, add_expected_slot, init_case
from roomreceipt.paths import load_case, save_case
from roomreceipt.seals import seal_case, verify_directory


def _complete_case(tmp_path: Path, image_factory: Callable[..., Path]) -> Path:
    root = tmp_path / "case"
    init_case(root, title="Case", property_label="Property")
    before = image_factory(tmp_path / "before.jpg")
    after = image_factory(tmp_path / "after.jpg", marker=(92, 88, 80))
    for phase, source, capture in (
        ("move-in", before, "2026-03-01T09:00:00Z"),
        ("move-out", after, "2027-02-28T09:00:00Z"),
    ):
        add_evidence(
            root,
            phase=phase,
            source=source,
            slot="wall",
            room="Living",
            item="Wall",
            view="Wide",
            captured_at=capture,
        )
    return root


def test_seal_and_verify_directory(tmp_path: Path, image_factory: Callable[..., Path]) -> None:
    root = _complete_case(tmp_path, image_factory)
    seal = seal_case(root)
    result = verify_directory(root)
    assert result.ok is True
    assert result.checked_files == 3
    assert result.root_sha256 == seal["root_sha256"]


def test_verify_detects_tampering_and_missing_seal(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _complete_case(tmp_path, image_factory)
    missing = verify_directory(root)
    assert missing.ok is False
    assert missing.findings[0].code == "SEAL_MISSING"
    seal_case(root)
    evidence = root / load_case(root).entries[0].path
    evidence.write_bytes(evidence.read_bytes() + b"tampered")
    result = verify_directory(root)
    assert result.ok is False
    assert {finding.code for finding in result.findings} >= {"SIZE_MISMATCH", "HASH_MISMATCH"}


def test_verify_rejects_invalid_and_unsafe_seals(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _complete_case(tmp_path, image_factory)
    (root / "seal.json").write_text("[]", encoding="utf-8")
    invalid = verify_directory(root)
    assert invalid.findings[0].code == "SEAL_INVALID"
    unsafe = {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": [{"path": "../outside", "sha256": "a" * 64, "size": 1}],
        "root_sha256": "b" * 64,
    }
    (root / "seal.json").write_text(json.dumps(unsafe), encoding="utf-8")
    result = verify_directory(root)
    assert any(finding.code == "PATH_UNSAFE" for finding in result.findings)


def test_verify_rejects_malformed_seal_records(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _complete_case(tmp_path, image_factory)
    variants: list[object] = [
        {},
        ["not-an-object"],
        [{"path": "", "sha256": "a" * 64, "size": 1}],
        [
            {"path": "case.json", "sha256": "a" * 64, "size": 1},
            {"path": "case.json", "sha256": "a" * 64, "size": 1},
        ],
        [{"path": "case.json", "sha256": "short", "size": 1}],
        [{"path": "case.json", "sha256": "a" * 64, "size": -1}],
    ]
    for files in variants:
        seal = {"schema_version": 1, "algorithm": "sha256", "files": files}
        (root / "seal.json").write_text(json.dumps(seal), encoding="utf-8")
        result = verify_directory(root)
        assert result.ok is False
        assert result.findings[0].code == "SEAL_INVALID"


def test_audit_reports_coverage_metadata_duplicates_and_seal(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = tmp_path / "case"
    init_case(root, title="Case", property_label="Property")
    add_expected_slot(root, slot="wall", room="Living", item="Wall", view="Wide")
    add_expected_slot(root, slot="door", room="Entry", item="Door", view="Wide")
    low = image_factory(tmp_path / "low.jpg", size=(320, 200), captured="")
    for slot, room, item in (("wall", "Living", "Wall"), ("door", "Entry", "Door")):
        add_evidence(
            root,
            phase="move-in",
            source=low,
            slot=slot,
            room=room,
            item=item,
            view="Wide",
        )
    audit = audit_case(root)
    codes = {finding["code"] for finding in audit["findings"]}
    assert {
        "MOVE_OUT_MISSING",
        "CAPTURE_TIME_MISSING",
        "LOW_RESOLUTION",
        "DUPLICATE_BYTES",
        "SEAL_MISSING",
    } <= codes
    assert audit["ok"] is True


def test_audit_clean_case_and_stale_seal(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _complete_case(tmp_path, image_factory)
    seal_case(root)
    clean = audit_case(root)
    assert clean["ok"] is True
    assert clean["counts"] == {"errors": 0, "warnings": 0, "info": 0}
    case = load_case(root)
    case.title = "Changed after sealing"
    save_case(root, case)
    stale = audit_case(root)
    assert stale["ok"] is False
    assert any(item["code"] == "HASH_MISMATCH" for item in stale["findings"])
