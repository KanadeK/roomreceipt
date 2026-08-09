# Case and bundle formats

The current `schema_version` is `1`.

## `case.json`

```json
{
  "schema_version": 1,
  "case_id": "bright-street-demo",
  "title": "Bright Street move-in and move-out",
  "property": {"label": "14 Bright Street", "unit": "4B"},
  "created_at": "2026-03-01T00:00:00Z",
  "expected_slots": [
    {"slot": "living-north-wall", "room": "Living room", "item": "North wall", "view": "Wide"}
  ],
  "entries": []
}
```

Each evidence entry records:

- deterministic entry ID;
- `move-in` or `move-out` phase;
- stable slot, room, item, and view;
- user note;
- safe case-relative path;
- SHA-256 and byte size;
- MIME type and dimensions;
- capture time, its source, and whether a timezone is known;
- whether GPS metadata is present;
- import time.

## `seal.json`

The case seal contains `case.json` plus every registered evidence file. Each leaf is serialized as:

```text
path NUL sha256 NUL size LF
```

Sorted leaf records are hashed after the domain prefix `roomreceipt-case-seal-v1`.

The seal intentionally excludes `comparison.json`, difference images, and the report. They are derived outputs.

## Bundle

The ZIP contains:

- case and evidence files;
- case seal;
- comparison JSON and difference images;
- report HTML, JSON, and thumbnails;
- `bundle-manifest.json`.

The bundle manifest hashes all members except itself with the domain prefix `roomreceipt-bundle-v1`. It also stores the embedded case root, connecting derived outputs to the evidence set.

ZIP verification rejects:

- absolute paths;
- backslashes;
- `..` path components;
- duplicate member names;
- members absent from the manifest;
- manifest members absent from the archive;
- size or SHA-256 changes;
- an invalid embedded case seal;
- a bundle root that does not link to the case root.

## Reproducibility

ZIP timestamps are normalized to the earliest portable ZIP timestamp. File order and permissions are fixed. `SOURCE_DATE_EPOCH` controls generated JSON timestamps during reproducibility checks.
