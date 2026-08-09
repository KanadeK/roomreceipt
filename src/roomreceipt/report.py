"""Self-contained, printable HTML report generation."""

from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from roomreceipt.compare import compare_case
from roomreceipt.models import EvidenceEntry
from roomreceipt.paths import (
    current_timestamp,
    load_case,
    read_json,
    resolve_case_path,
    slugify,
    write_json,
)
from roomreceipt.seals import verify_directory


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _thumbnail(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1200, 900), Image.Resampling.LANCZOS)
        image.save(destination, format="JPEG", quality=86, optimize=False, progressive=False)


def _entry_thumbnail(root: Path, output: Path, entry: EvidenceEntry) -> str:
    relative = f"assets/{entry.phase}-{slugify(entry.slot)}-{entry.sha256[:8]}.jpg"
    destination = output / relative
    _thumbnail(resolve_case_path(root, entry.path), destination)
    return relative


def _pair_markup(
    pair: dict[str, Any], thumbnails: dict[tuple[str, str], str], output: Path, root: Path
) -> str:
    slot = str(pair["slot"])
    before = thumbnails[(slot, "move-in")]
    after = thumbnails[(slot, "move-out")]
    diff_source = resolve_case_path(root, str(pair["diff"]))
    diff_relative = f"assets/{slugify(slot)}-diff.jpg"
    shutil.copyfile(diff_source, output / diff_relative)
    classification = str(pair["classification"])
    review_copy = "Review suggested" if classification == "review" else "Close visual match"
    return f"""
      <article class="comparison" id="slot-{_escape(slugify(slot))}">
        <header class="comparison-head">
          <div>
            <p class="room">{_escape(pair["room"])}</p>
            <h3>{_escape(pair["item"])}</h3>
            <p>{_escape(pair["view"])}</p>
          </div>
          <div class="review-state" data-state="{_escape(classification)}">{_escape(review_copy)}</div>
        </header>
        <div class="image-grid">
          <figure><img src="{_escape(before)}" alt="Move-in view for {_escape(slot)}"><figcaption>Move-in</figcaption></figure>
          <figure><img src="{_escape(after)}" alt="Move-out view for {_escape(slot)}"><figcaption>Move-out</figcaption></figure>
          <figure><img src="{_escape(diff_relative)}" alt="Pixel difference view for {_escape(slot)}"><figcaption>Difference aid</figcaption></figure>
        </div>
        <dl class="metrics">
          <div><dt>Normalized difference</dt><dd>{float(pair["difference_score"]):.3%}</dd></div>
          <div><dt>Changed pixels</dt><dd>{float(pair["changed_pixel_ratio"]):.3%}</dd></div>
          <div><dt>Perceptual hash distance</dt><dd>{int(pair["dhash_distance"])} / 64</dd></div>
        </dl>
      </article>
    """


def _evidence_rows(entries: list[EvidenceEntry], thumbnails: dict[tuple[str, str], str]) -> str:
    rows: list[str] = []
    for entry in entries:
        captured = entry.captured_at or "Not recorded"
        timezone = "timezone included" if entry.timezone_known else "timezone not recorded"
        rows.append(
            f"""
            <tr>
              <td><a href="{_escape(thumbnails[(entry.slot, entry.phase)])}">{_escape(entry.slot)}</a></td>
              <td>{_escape(entry.phase)}</td>
              <td>{_escape(entry.room)} / {_escape(entry.item)} / {_escape(entry.view)}</td>
              <td>{_escape(captured)}<small>{_escape(entry.capture_source)}, {_escape(timezone)}</small></td>
              <td><code>{_escape(entry.sha256[:16])}</code><small>{entry.width}x{entry.height}, {entry.size:,} bytes</small></td>
            </tr>
            """
        )
    return "".join(rows)


def _styles() -> str:
    return """
    :root {
      color-scheme: light dark;
      --paper: #f2f4f3;
      --surface: #fbfcfb;
      --ink: #192024;
      --muted: #5b676d;
      --line: #cfd5d3;
      --accent: #b74f2c;
      --accent-ink: #ffffff;
      --soft: #e6eae8;
      --radius: 14px;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --paper: #171b1d;
        --surface: #202629;
        --ink: #edf1ef;
        --muted: #a8b3b7;
        --line: #3d474a;
        --accent: #d56c43;
        --accent-ink: #16191b;
        --soft: #2a3235;
      }
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--paper); color: var(--ink); line-height: 1.55; }
    a { color: var(--accent); text-underline-offset: 3px; }
    button { font: inherit; }
    .shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
    .topbar { min-height: 64px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); }
    .brand { color: var(--ink); font-weight: 780; text-decoration: none; letter-spacing: -0.03em; }
    .print { border: 1px solid var(--line); border-radius: 999px; padding: 9px 16px; color: var(--ink); background: var(--surface); cursor: pointer; }
    .print:hover, .print:focus-visible { border-color: var(--accent); }
    .print:active { transform: translateY(1px); }
    .hero { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(250px, .5fr); gap: 48px; padding: 64px 0 52px; align-items: end; }
    .kicker, .room { color: var(--accent); font-size: .78rem; font-weight: 760; letter-spacing: .12em; text-transform: uppercase; }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 16px; max-width: 13ch; font-size: clamp(2.7rem, 7vw, 5.6rem); line-height: .96; letter-spacing: -.065em; }
    .lede { max-width: 58ch; color: var(--muted); font-size: 1.04rem; }
    .seal-box { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 20px; }
    .seal-box strong { display: block; margin-bottom: 7px; }
    .seal-box code { display: block; overflow-wrap: anywhere; font-size: .72rem; color: var(--muted); }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); margin: 0 0 74px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
    .stats div { padding: 20px 16px 20px 0; }
    .stats dt { color: var(--muted); font-size: .78rem; }
    .stats dd { margin: 4px 0 0; font-size: 1.65rem; font-weight: 720; letter-spacing: -.04em; }
    section { margin: 0 0 86px; }
    section > header { max-width: 720px; margin-bottom: 30px; }
    h2 { margin-bottom: 10px; font-size: clamp(2rem, 4vw, 3.4rem); line-height: 1; letter-spacing: -.05em; }
    h3 { margin-bottom: 4px; font-size: 1.3rem; letter-spacing: -.025em; }
    section > header p, .comparison-head p { color: var(--muted); }
    .comparison { margin-bottom: 34px; padding: 24px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
    .comparison-head { display: flex; justify-content: space-between; gap: 28px; align-items: start; margin-bottom: 18px; }
    .comparison-head p { margin-bottom: 0; }
    .review-state { flex: 0 0 auto; padding: 7px 11px; border: 1px solid var(--line); border-radius: 999px; font-size: .78rem; font-weight: 740; }
    .review-state[data-state="review"] { border-color: var(--accent); color: var(--accent); }
    .image-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
    figure { margin: 0; }
    figure img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: calc(var(--radius) - 5px); background: var(--soft); }
    figcaption { padding-top: 7px; color: var(--muted); font-size: .76rem; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); margin: 20px 0 0; padding-top: 18px; border-top: 1px solid var(--line); }
    .metrics div { padding-right: 16px; }
    .metrics dt { color: var(--muted); font-size: .76rem; }
    .metrics dd { margin: 3px 0 0; font-variant-numeric: tabular-nums; font-weight: 720; }
    .empty { padding: 24px; border: 1px dashed var(--line); border-radius: var(--radius); color: var(--muted); }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
    table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    th, td { padding: 15px 16px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }
    tr:last-child td { border-bottom: 0; }
    th { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
    td small { display: block; margin-top: 4px; color: var(--muted); }
    code { font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace; }
    .limits { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: var(--line); }
    .limits article { padding: 24px; background: var(--surface); }
    .limits h3 { color: var(--accent); }
    footer { padding: 30px 0 48px; border-top: 1px solid var(--line); color: var(--muted); font-size: .82rem; }
    @media (max-width: 760px) {
      .shell { width: min(100% - 24px, 1180px); }
      .hero { grid-template-columns: 1fr; gap: 24px; padding-top: 38px; }
      h1 { max-width: none; }
      .stats { grid-template-columns: 1fr 1fr; }
      .image-grid { grid-template-columns: 1fr; }
      .comparison-head { display: grid; }
      .metrics { grid-template-columns: 1fr; gap: 12px; }
      .limits { grid-template-columns: 1fr; }
    }
    @media print {
      :root { color-scheme: light; --paper: #ffffff; --surface: #ffffff; --ink: #111111; --muted: #444444; --line: #cccccc; }
      .print { display: none; }
      .shell { width: 100%; }
      .hero { padding-top: 28px; }
      .comparison { break-inside: avoid; box-shadow: none; }
      a { color: inherit; text-decoration: none; }
    }
    """


def build_report(root: str | Path, output: str | Path = "report") -> Path:
    resolved = Path(root).expanduser().resolve()
    case = load_case(resolved)
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = resolved / output_path
    output_path = output_path.resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "assets").mkdir(parents=True, exist_ok=True)

    comparison_path = resolved / "comparison.json"
    comparison = read_json(comparison_path) if comparison_path.is_file() else compare_case(resolved)
    if not isinstance(comparison, dict):
        comparison = compare_case(resolved)
    raw_pairs = comparison.get("pairs", [])
    pairs = (
        [pair for pair in raw_pairs if isinstance(pair, dict)]
        if isinstance(raw_pairs, list)
        else []
    )

    thumbnails: dict[tuple[str, str], str] = {}
    for entry in case.entries:
        thumbnails[(entry.slot, entry.phase)] = _entry_thumbnail(resolved, output_path, entry)

    pair_markup = "".join(_pair_markup(pair, thumbnails, output_path, resolved) for pair in pairs)
    if not pair_markup:
        pair_markup = (
            '<div class="empty"><strong>No paired views yet.</strong> Add move-in and move-out '
            "evidence with the same slot name, then run the comparison again.</div>"
        )

    seal_result = verify_directory(resolved)
    seal_label = "Verified" if seal_result.ok else "Not verified"
    root_hash = seal_result.root_sha256 or "No current seal"
    rooms = len({entry.room for entry in case.entries})
    review_count = sum(pair.get("classification") == "review" for pair in pairs)
    generated_at = current_timestamp()
    unit_copy = f" / Unit {case.unit}" if case.unit else ""

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{_escape(case.title)} | RoomReceipt</title>
  <style>{_styles()}</style>
</head>
<body>
  <nav class="topbar shell" aria-label="Report controls">
    <a class="brand" href="#top">RoomReceipt</a>
    <button class="print" type="button" onclick="window.print()">Print report</button>
  </nav>
  <main class="shell" id="top">
    <header class="hero">
      <div>
        <p class="kicker">Property condition record</p>
        <h1>{_escape(case.title)}</h1>
        <p class="lede">{_escape(case.property_label + unit_copy)}. This local report links each view to its stored bytes and keeps automated visual metrics separate from human judgment.</p>
      </div>
      <aside class="seal-box" aria-label="Seal status">
        <strong>{_escape(seal_label)} case seal</strong>
        <code>{_escape(root_hash)}</code>
      </aside>
    </header>
    <dl class="stats">
      <div><dt>Evidence files</dt><dd>{len(case.entries)}</dd></div>
      <div><dt>Rooms</dt><dd>{rooms}</dd></div>
      <div><dt>Paired views</dt><dd>{len(pairs)}</dd></div>
      <div><dt>Review flags</dt><dd>{review_count}</dd></div>
    </dl>

    <section aria-labelledby="comparison-title">
      <header>
        <h2 id="comparison-title">Before and after</h2>
        <p>Every pair uses the same named slot. Difference images and metrics are review aids, not findings of damage or responsibility.</p>
      </header>
      {pair_markup}
    </section>

    <section aria-labelledby="evidence-title">
      <header>
        <h2 id="evidence-title">Evidence register</h2>
        <p>Paths, capture metadata, dimensions, byte counts, and truncated SHA-256 fingerprints for every imported image.</p>
      </header>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Slot</th><th>Phase</th><th>Subject</th><th>Capture time</th><th>File identity</th></tr></thead>
          <tbody>{_evidence_rows(case.entries, thumbnails)}</tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="limits-title">
      <header>
        <h2 id="limits-title">Integrity boundaries</h2>
        <p>Use the independent verifier before relying on a copied directory or bundle.</p>
      </header>
      <div class="limits">
        <article><h3>What verification checks</h3><p>The listed file size and SHA-256 value still match the seal. It also checks the seal root and rejects unsafe bundle paths.</p></article>
        <article><h3>What it cannot establish</h3><p>Capture time, authorship, legal admissibility, image truthfulness, or whether a file was edited before it was first sealed.</p></article>
      </div>
    </section>
  </main>
  <footer class="shell">Generated {_escape(generated_at)} from case {_escape(case.case_id)}. RoomReceipt is documentation software, not legal advice.</footer>
</body>
</html>
"""
    (output_path / "index.html").write_text(page, encoding="utf-8", newline="\n")
    write_json(
        output_path / "report.json",
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "generated_at": generated_at,
            "seal_verified": seal_result.ok,
            "seal_root_sha256": seal_result.root_sha256,
            "evidence_entries": len(case.entries),
            "paired_views": len(pairs),
            "rooms": sorted({entry.room for entry in case.entries}),
        },
    )
    return output_path / "index.html"
