# Bright Street synthetic fixture

This example contains eight deterministic JPEG images and two CSV manifests. Every address, room, note, and visual is synthetic.

Regenerate the committed files:

```bash
uv run python scripts/generate_example_data.py
```

Check them without writing:

```bash
uv run python scripts/generate_example_data.py --check
```

Build the complete case:

```bash
uv run python scripts/build_example.py --output build/bright-street
uv run roomreceipt verify build/bright-street/bright-street-demo.roomreceipt.zip
```

Expected results:

- four paired slots;
- two close visual matches;
- two human-review flags;
- a verified case seal;
- a printable report;
- a deterministic portable bundle.
