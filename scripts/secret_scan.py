"""Small repository secret scan used by the local and CI release gates."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_PARTS = {".git", ".venv", ".pytest-tmp", "build", "dist", "htmlcov"}
TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "OpenAI key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    checked = 0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE"}:
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {path.relative_to(root)}")
    if findings:
        print("potential secrets detected:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"secret scan passed: {checked} text files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
