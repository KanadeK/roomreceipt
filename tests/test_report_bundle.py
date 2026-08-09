from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Callable
from pathlib import Path

from roomreceipt.bundle import create_bundle, verify_bundle
from roomreceipt.casework import add_evidence, add_expected_slot, init_case
from roomreceipt.compare import compare_case
from roomreceipt.report import build_report
from roomreceipt.seals import seal_case


def _paired_case(tmp_path: Path, image_factory: Callable[..., Path]) -> Path:
    root = tmp_path / "case"
    init_case(root, title="<Bright & Ready>", property_label="14 Bright Street", unit="4B")
    before = image_factory(tmp_path / "before.jpg")
    after = image_factory(tmp_path / "after.jpg", marker=(180, 40, 20))
    for phase, source in (("move-in", before), ("move-out", after)):
        add_evidence(
            root,
            phase=phase,
            source=source,
            slot="north-wall",
            room="Living room",
            item="North wall",
            view="Wide",
            captured_at="2026-03-01T09:00:00Z",
        )
    add_expected_slot(root, slot="door", room="Entry", item="Door", view="Wide")
    return root


def test_compare_creates_pairs_diffs_and_unpaired(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _paired_case(tmp_path, image_factory)
    result = compare_case(root)
    assert len(result["pairs"]) == 1
    assert result["pairs"][0]["classification"] == "review"
    assert result["unpaired"] == [{"slot": "door", "missing": "move-in"}]
    assert (root / result["pairs"][0]["diff"]).is_file()


def test_report_is_printable_escaped_and_has_no_em_dash(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _paired_case(tmp_path, image_factory)
    compare_case(root)
    seal_case(root)
    report = build_report(root)
    page = report.read_text(encoding="utf-8")
    assert "&lt;Bright &amp; Ready&gt;" in page
    assert "Print report" in page
    assert "Difference aid" in page
    assert "\N{EM DASH}" not in page and "\N{EN DASH}" not in page
    assert (report.parent / "report.json").is_file()
    assert len(list((report.parent / "assets").glob("*.jpg"))) == 3


def test_bundle_is_deterministic_and_verifiable(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _paired_case(tmp_path, image_factory)
    first = create_bundle(root, tmp_path / "first.zip")
    second = create_bundle(root, tmp_path / "second.zip")
    assert first.read_bytes() == second.read_bytes()
    verified = verify_bundle(first)
    assert verified.ok is True
    assert verified.checked_files > 5
    with zipfile.ZipFile(first) as archive:
        assert "bundle-manifest.json" in archive.namelist()
        assert "report/index.html" in archive.namelist()


def test_bundle_verifier_detects_changed_and_unlisted_members(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _paired_case(tmp_path, image_factory)
    original = create_bundle(root, tmp_path / "original.zip")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith("north-wall.jpg"):
                payload += b"changed"
            target.writestr(name, payload)
        target.writestr("unlisted.txt", b"surprise")
    result = verify_bundle(tampered)
    codes = {finding.code for finding in result.findings}
    assert "HASH_MISMATCH" in codes
    assert "UNLISTED_MEMBER" in codes
    assert "SEALED_HASH_MISMATCH" in codes


def test_bundle_verifier_rejects_missing_and_unsafe_archives(tmp_path: Path) -> None:
    missing = verify_bundle(tmp_path / "missing.zip")
    assert missing.ok is False
    assert missing.findings[0].code == "BUNDLE_MISSING"
    unsafe = tmp_path / "unsafe.zip"
    manifest = {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": [{"path": "../escape", "sha256": hashlib.sha256(b"x").hexdigest(), "size": 1}],
        "root_sha256": "0" * 64,
    }
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape", b"x")
        archive.writestr("bundle-manifest.json", json.dumps(manifest))
    result = verify_bundle(unsafe)
    assert result.ok is False
    assert any(finding.code in {"PATH_UNSAFE", "BUNDLE_INVALID"} for finding in result.findings)


def test_bundle_verifier_rejects_bad_zip_and_bad_manifest(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_text("not a zip", encoding="utf-8")
    assert verify_bundle(bad_zip).findings[0].code == "BUNDLE_INVALID"

    missing_manifest = tmp_path / "missing-manifest.zip"
    with zipfile.ZipFile(missing_manifest, "w") as archive:
        archive.writestr("case.json", "{}")
    assert verify_bundle(missing_manifest).findings[0].code == "BUNDLE_INVALID"


def test_bundle_verifier_detects_manifest_root_change(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    root = _paired_case(tmp_path, image_factory)
    original = create_bundle(root, tmp_path / "original-root.zip")
    changed = tmp_path / "changed-root.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(changed, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "bundle-manifest.json":
                manifest = json.loads(payload)
                manifest["root_sha256"] = "0" * 64
                payload = json.dumps(manifest).encode()
            target.writestr(name, payload)
    result = verify_bundle(changed)
    assert any(finding.code == "ROOT_MISMATCH" for finding in result.findings)
