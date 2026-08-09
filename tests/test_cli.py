from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from roomreceipt.cli import main


def test_cli_end_to_end(
    tmp_path: Path, image_factory: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "case"
    before = image_factory(tmp_path / "before.jpg")
    after = image_factory(tmp_path / "after.jpg", marker=(200, 20, 20))
    assert main(["init", str(root), "--title", "Case", "--property", "Property"]) == 0
    for phase, source in (("move-in", before), ("move-out", after)):
        assert (
            main(
                [
                    "add",
                    str(root),
                    phase,
                    str(source),
                    "--slot",
                    "wall",
                    "--room",
                    "Living",
                    "--item",
                    "Wall",
                    "--view",
                    "Wide",
                    "--captured-at",
                    "2026-03-01T09:00:00Z",
                ]
            )
            == 0
        )
    assert main(["compare", str(root), "--json"]) == 0
    assert main(["seal", str(root)]) == 0
    assert main(["audit", str(root), "--strict"]) == 0
    bundle = tmp_path / "case.zip"
    assert main(["bundle", str(root), "--output", str(bundle)]) == 0
    assert main(["verify", str(bundle), "--json"]) == 0
    assert main(["report", str(root), "--output", "printable"]) == 0
    output = capsys.readouterr().out
    assert "compared" not in output
    assert '"classification": "review"' in output
    assert '"ok": true' in output


def test_cli_strict_audit_and_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "case"
    assert main(["init", str(root), "--title", "Case", "--property", "Property"]) == 0
    assert (
        main(
            [
                "expect",
                str(root),
                "--slot",
                "wall",
                "--room",
                "Living",
                "--item",
                "Wall",
                "--view",
                "Wide",
            ]
        )
        == 0
    )
    assert main(["audit", str(root)]) == 1
    assert main(["verify", str(root)]) == 1
    assert (
        main(
            [
                "add",
                str(root),
                "move-in",
                "missing.jpg",
                "--slot",
                "x",
                "--room",
                "R",
                "--item",
                "I",
                "--view",
                "V",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "MOVE_IN_MISSING" in captured.out
    assert "verification failed" in captured.err
    assert "error:" in captured.err


def test_cli_version_raises_clean_system_exit(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "roomreceipt 0.1.0" in capsys.readouterr().out
