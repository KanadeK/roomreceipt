"""Pair move-in and move-out evidence and create review-only visual diffs."""

from __future__ import annotations

from pathlib import Path

from roomreceipt.media import compare_images
from roomreceipt.models import EvidenceEntry
from roomreceipt.paths import current_timestamp, load_case, resolve_case_path, slugify, write_json

COMPARISON_SCHEMA_VERSION = 1


def compare_case(root: str | Path) -> dict[str, object]:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    by_slot: dict[str, dict[str, EvidenceEntry]] = {}
    for entry in case.entries:
        by_slot.setdefault(entry.slot, {})[entry.phase] = entry

    results: list[dict[str, object]] = []
    unpaired: list[dict[str, str]] = []
    assets = resolved / "comparison-assets"
    for expected in case.expected_slots:
        phases = by_slot.get(expected.slot, {})
        before = phases.get("move-in")
        after = phases.get("move-out")
        if before is None or after is None:
            missing = "move-in" if before is None else "move-out"
            unpaired.append({"slot": expected.slot, "missing": missing})
            continue
        before_path = resolve_case_path(resolved, before.path)
        after_path = resolve_case_path(resolved, after.path)
        diff_relative = f"comparison-assets/{slugify(expected.slot)}-diff.jpg"
        comparison = compare_images(
            before_path,
            after_path,
            diff_output=resolve_case_path(resolved, diff_relative),
        )
        results.append(
            {
                "slot": expected.slot,
                "room": expected.room,
                "item": expected.item,
                "view": expected.view,
                "before": before.path,
                "after": after.path,
                "diff": diff_relative,
                **comparison.to_dict(),
            }
        )

    comparison_data: dict[str, object] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "case_id": case.case_id,
        "generated_at": current_timestamp(),
        "notice": (
            "Pixel metrics flag images for human review. They do not identify damage, cause, "
            "authorship, or legal responsibility."
        ),
        "pairs": results,
        "unpaired": unpaired,
    }
    write_json(resolved / "comparison.json", comparison_data)
    if not results and assets.exists() and not any(assets.iterdir()):
        assets.rmdir()
    return comparison_data
