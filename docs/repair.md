# Repair playbook

## Start from a known baseline

```bash
git status --short
uv sync --all-extras
uv run roomreceipt --version
```

Do not delete a case, regenerate evidence, or reseal until you understand the mismatch.

## Dependency or Python failure

```bash
uv python install 3.12
uv sync --refresh --all-extras
```

If network access is restricted, rerun when the package index is reachable. Do not use `--no-verify`, forced legacy resolution, or an unreviewed dependency downgrade.

## Test temporary-directory permission failure on Windows

The repository already pins pytest temporary files to `.pytest-tmp`. Confirm that the directory is inside the clone:

```powershell
Resolve-Path .pytest-tmp -ErrorAction SilentlyContinue
uv run pytest
```

If a stale process holds it, stop only the RoomReceipt pytest process and retry. Do not recursively delete a broad system temp directory.

## Evidence hash failure

```bash
roomreceipt verify CASE --json
roomreceipt audit CASE --json
```

For each mismatch:

1. Compare the case copy to the independently retained original.
2. Restore the intended bytes if the case copy changed accidentally.
3. Document and review an intentional replacement.
4. Use `roomreceipt add ... --replace` for that exact phase and slot.
5. Rerun compare and audit.
6. Seal only after review.

Never reseal first. That destroys the signal that the prior bytes changed.

## Missing or unpaired slot

Inspect `case.json` and the source manifest. The same stable `slot` must be used at both phases.

```bash
roomreceipt import CASE move-out corrected-move-out.csv
roomreceipt compare CASE
roomreceipt audit CASE
```

## Metadata warning

Many EXIF timestamps lack a timezone. Keep corroborating records or supply an explicit offset when importing:

```bash
roomreceipt add CASE move-in PHOTO.jpg \
  --slot SLOT --room ROOM --item ITEM --view VIEW \
  --captured-at "2026-03-01T09:12:00-08:00" \
  --replace
```

Supplying a time does not make it trusted. It only records the operator-provided value.

## Example fixture mismatch

Check without writes:

```bash
uv run python scripts/generate_example_data.py --check
```

If generator code intentionally changed, regenerate and review all binary diffs:

```bash
uv run python scripts/generate_example_data.py
uv run python scripts/generate_example_data.py --check
```

## Packaging mismatch

Build twice with a fixed epoch and compare hashes:

```bash
$env:SOURCE_DATE_EPOCH = "1772323200"
uv run python scripts/build_example.py --output build/example-a
uv run python scripts/build_example.py --output build/example-b
Get-FileHash build/example-a/*.zip -Algorithm SHA256
Get-FileHash build/example-b/*.zip -Algorithm SHA256
```

Different hashes mean release is blocked. Inspect JSON timestamps, file order, ZIP timestamps, permissions, and compressed bytes.

## Invalid distribution metadata

The isolated builder can otherwise resolve a newer backend than the development environment. A new backend may emit a Core Metadata version that the current validation or upload path does not yet accept.

```bash
uv lock --check
uv sync --locked --all-extras
uv run python -m build
uv run twine check dist/*
```

Keep the exact, verified Hatchling version in both `[build-system].requires` and the development dependencies. Upgrade it only in a reviewed change that passes Twine locally and in CI. Do not remove `twine check`, use `--no-verify`, or publish an asset that failed metadata validation.

## Downloaded Release asset fails verification

```bash
Get-FileHash roomreceipt-v0.1.0-example.roomreceipt.zip -Algorithm SHA256
Get-Content SHA256SUMS
roomreceipt verify roomreceipt-v0.1.0-example.roomreceipt.zip
```

Re-download once. If the hash still differs, report the exact asset name and digest through GitHub Issues.

## GitHub Actions failure

```bash
gh run list --repo KanadeK/roomreceipt --limit 10
gh run view RUN_ID --repo KanadeK/roomreceipt --log-failed
```

Run the failing local command exactly. A green local check does not override a red remote check.
