# Contributing

Thank you for improving RoomReceipt.

## Setup

```bash
uv sync --all-extras
uv run python scripts/release_check.py
```

## Pull requests

- Keep changes focused.
- Add tests for success and failure paths.
- Do not weaken ZIP path safety or SHA-256 verification.
- Do not add automatic damage, liability, fraud, or legal-admissibility verdicts.
- Preserve original imported bytes.
- Update the case schema version only with migration documentation.
- Regenerate deterministic fixtures only when the generator change is intentional and reviewed.
- Include a repair step for every new failure users may encounter.

Commit messages should be short and imperative. Do not include generated co-author trailers.

## Reporting a bug

Include:

- RoomReceipt and Python versions;
- operating system;
- exact command and exit code;
- redacted error text;
- whether the failure affects a directory, bundle, report, or example.

Do not attach real rental photos or unredacted addresses to a public issue.
