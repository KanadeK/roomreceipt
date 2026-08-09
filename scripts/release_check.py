"""Run the complete local release gate for RoomReceipt."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"
SITE = ROOT / ".site-build"
SOURCE_DATE_EPOCH = "1772323200"


def run(label: str, command: list[str], *, env: dict[str, str]) -> None:
    print(f"\n==> {label}", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def remove_generated(path: Path) -> None:
    resolved = path.resolve()
    if ROOT not in resolved.parents or resolved.name not in {"build", "dist", ".site-build"}:
        raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one(pattern: str) -> Path:
    matches = sorted(ROOT.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one {pattern}, found {len(matches)}")
    return matches[0]


def verify_checksum_manifest() -> None:
    manifest = DIST / "SHA256SUMS"
    expected: dict[str, str] = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name:
            raise RuntimeError(f"invalid SHA256SUMS line: {line!r}")
        expected[name] = digest
    assets = {path.name: sha256(path) for path in DIST.iterdir() if path.name != manifest.name}
    if assets != expected:
        raise RuntimeError(f"SHA256SUMS mismatch: expected {expected}, got {assets}")
    print(f"checksum manifest verified: {len(assets)} assets")


def venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    started = time.monotonic()
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required; install it from https://docs.astral.sh/uv/")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    python = sys.executable

    for path in (BUILD, DIST, SITE):
        remove_generated(path)
    BUILD.mkdir()

    run("Ruff lint", [uv, "run", "ruff", "check", "."], env=env)
    run("Ruff format", [uv, "run", "ruff", "format", "--check", "."], env=env)
    run("Strict mypy", [uv, "run", "mypy", "src"], env=env)
    run(
        "Tests and branch coverage",
        [uv, "run", "pytest", "--cov=roomreceipt", "--cov-report=term-missing"],
        env=env,
    )
    run(
        "Deterministic fixture check",
        [uv, "run", "python", "scripts/generate_example_data.py", "--check"],
        env=env,
    )
    run("Secret pattern scan", [uv, "run", "python", "scripts/secret_scan.py"], env=env)

    first_case = BUILD / "repro-a"
    second_case = BUILD / "repro-b"
    run(
        "First reproducibility build",
        [uv, "run", "python", "scripts/build_example.py", "--output", str(first_case)],
        env=env,
    )
    time.sleep(2.1)
    run(
        "Second reproducibility build after a clock boundary",
        [uv, "run", "python", "scripts/build_example.py", "--output", str(second_case)],
        env=env,
    )
    first_bundle = one("build/repro-a/*.roomreceipt.zip")
    second_bundle = one("build/repro-b/*.roomreceipt.zip")
    if first_bundle.read_bytes() != second_bundle.read_bytes():
        raise RuntimeError(
            f"deterministic bundle mismatch: {sha256(first_bundle)} != {sha256(second_bundle)}"
        )
    print(f"deterministic bundle verified: {sha256(first_bundle)}")
    run(
        "Directory verification",
        [uv, "run", "python", "-m", "roomreceipt", "verify", str(first_case)],
        env=env,
    )
    run(
        "ZIP verification",
        [uv, "run", "python", "-m", "roomreceipt", "verify", str(first_bundle)],
        env=env,
    )

    run(
        "Static site build",
        [uv, "run", "python", "scripts/build_site.py", "--output", str(SITE)],
        env=env,
    )
    run(
        "Static site accessibility and link checks",
        [uv, "run", "python", "scripts/site_check.py", str(SITE)],
        env=env,
    )

    run("Build wheel and source distribution", [uv, "run", "python", "-m", "build"], env=env)
    distributions = sorted(str(path) for path in DIST.glob("roomreceipt-0.1.0*"))
    if len(distributions) != 2:
        raise RuntimeError(f"expected wheel and sdist, found: {distributions}")
    run("Twine package metadata", [uv, "run", "twine", "check", *distributions], env=env)
    run(
        "Assemble release assets",
        [uv, "run", "python", "scripts/package_release.py", "--dist", str(DIST)],
        env=env,
    )
    verify_checksum_manifest()
    release_example = DIST / "roomreceipt-v0.1.0-example.roomreceipt.zip"
    run(
        "Release example verification",
        [uv, "run", "python", "-m", "roomreceipt", "verify", str(release_example)],
        env=env,
    )

    smoke = BUILD / "wheel-smoke"
    run(
        "Create clean wheel smoke environment",
        [uv, "venv", "--python", python, "--clear", str(smoke)],
        env=env,
    )
    wheel = one("dist/roomreceipt-0.1.0-*.whl")
    smoke_python = venv_python(smoke)
    run(
        "Install wheel in clean environment",
        [uv, "pip", "install", "--python", str(smoke_python), str(wheel)],
        env=env,
    )
    run("Installed CLI smoke test", [str(smoke_python), "-m", "roomreceipt", "--version"], env=env)

    if (ROOT / ".git").is_dir():
        run("Git whitespace check", ["git", "diff", "--check"], env=env)

    elapsed = time.monotonic() - started
    print(f"\nROOMRECEIPT_RELEASE_GATE=PASS ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
