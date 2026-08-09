# RoomReceipt v0.1.0

The first public release turns paired move-in and move-out photos into an offline, tamper-evident evidence bundle.

## Included

- Original-byte image registration with SHA-256 fingerprints and capture metadata.
- Stable view slots for repeatable move-in and move-out pairing.
- Transparent pixel-difference aids and conservative `close-match` or `review` labels.
- Case audits, seals, printable local reports, and deterministic ZIP bundles.
- An independent verifier that rejects missing, changed, unlisted, duplicated, and path-unsafe members.
- Eight deterministic synthetic fixtures, a live demo, 48 tests, and a full reproducibility gate.

## Install

```bash
uv tool install "git+https://github.com/KanadeK/roomreceipt.git@v0.1.0"
roomreceipt --version
```

## Release assets

- `roomreceipt-0.1.0-py3-none-any.whl`
- `roomreceipt-0.1.0.tar.gz`
- `roomreceipt-v0.1.0-example.roomreceipt.zip`
- `SHA256SUMS`

The verifier proves that listed bytes still match the recorded seal. It does not prove capture time, authorship, cause, damage, or legal admissibility. See the [threat model](https://github.com/KanadeK/roomreceipt/blob/v0.1.0/docs/threat-model.md).
