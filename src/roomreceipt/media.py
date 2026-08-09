"""Image inspection and deterministic visual comparison."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from PIL import ExifTags, Image, ImageChops, ImageOps, ImageStat, UnidentifiedImageError

from roomreceipt.models import RoomReceiptError

DATE_TIME_ORIGINAL = 36867
GPS_INFO = 34853


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    sha256: str
    size: int
    mime: str
    width: int
    height: int
    captured_at: str
    capture_source: str
    timezone_known: bool
    gps_present: bool


@dataclass(frozen=True, slots=True)
class ImageComparison:
    difference_score: float
    changed_pixel_ratio: float
    dhash_distance: int
    classification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "difference_score": self.difference_score,
            "changed_pixel_ratio": self.changed_pixel_ratio,
            "dhash_distance": self.dhash_distance,
            "classification": self.classification,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_capture(value: str) -> tuple[str, bool]:
    candidate = value.strip()
    if not candidate:
        return "", False
    try:
        if len(candidate) == 19 and candidate[4] == ":":
            instant = datetime.strptime(candidate, "%Y:%m:%d %H:%M:%S")
            return instant.isoformat(), False
        normalized = candidate.replace("Z", "+00:00")
        instant = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RoomReceiptError(
            "captured-at must be ISO 8601 or an EXIF YYYY:MM:DD HH:MM:SS timestamp"
        ) from exc
    timezone_known = instant.tzinfo is not None
    if timezone_known:
        return instant.isoformat(), True
    return instant.replace(microsecond=0).isoformat(), False


def inspect_image(path: Path, *, captured_at: str = "") -> ImageMetadata:
    if not path.is_file():
        raise RoomReceiptError(f"image does not exist: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = ImageOps.exif_transpose(image).size
            exif = image.getexif()
            exif_capture = str(exif.get(DATE_TIME_ORIGINAL, "")).strip()
            gps_present = bool(exif.get(GPS_INFO))
            image_format = image.format
    except (UnidentifiedImageError, OSError) as exc:
        raise RoomReceiptError(f"unsupported or invalid image: {path}") from exc

    if captured_at:
        normalized_capture, timezone_known = _normalize_capture(captured_at)
        capture_source = "provided"
    elif exif_capture:
        normalized_capture, timezone_known = _normalize_capture(exif_capture)
        capture_source = "exif"
    else:
        normalized_capture, timezone_known = "", False
        capture_source = "unknown"

    mime = Image.MIME.get(image_format or "") or mimetypes.guess_type(path.name)[0]
    return ImageMetadata(
        sha256=sha256_file(path),
        size=path.stat().st_size,
        mime=mime or "application/octet-stream",
        width=width,
        height=height,
        captured_at=normalized_capture,
        capture_source=capture_source,
        timezone_known=timezone_known,
        gps_present=gps_present,
    )


def _normalized_image(path: Path, size: tuple[int, int] = (512, 384)) -> Image.Image:
    with Image.open(path) as source:
        oriented = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.pad(oriented, size, color=(238, 239, 237), method=Image.Resampling.LANCZOS)


def difference_hash(path: Path, hash_size: int = 8) -> int:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("L")
        pixels = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        modern_getter = getattr(pixels, "get_flattened_data", None)
        values = (
            list(cast(Any, modern_getter)()) if callable(modern_getter) else list(pixels.getdata())
        )
    result = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for column in range(hash_size):
            result = (result << 1) | int(values[offset + column] > values[offset + column + 1])
    return result


def compare_images(
    before: Path, after: Path, *, diff_output: Path | None = None
) -> ImageComparison:
    before_image = _normalized_image(before)
    after_image = _normalized_image(after)
    difference = ImageChops.difference(before_image, after_image)
    statistics = ImageStat.Stat(difference)
    difference_score = sum(statistics.mean) / (3 * 255)
    grayscale = difference.convert("L")
    histogram = grayscale.histogram()
    changed_pixels = sum(histogram[25:])
    total_pixels = grayscale.width * grayscale.height
    changed_ratio = changed_pixels / total_pixels
    dhash_distance = (difference_hash(before) ^ difference_hash(after)).bit_count()

    classification = (
        "close-match"
        if difference_score < 0.018 and changed_ratio < 0.08 and dhash_distance <= 8
        else "review"
    )

    if diff_output is not None:
        diff_output.parent.mkdir(parents=True, exist_ok=True)
        amplified = grayscale.point(lambda value: min(255, value * 4))
        heatmap = ImageOps.colorize(amplified, black="#202426", white="#c95e35")
        overlay = Image.blend(before_image, heatmap, 0.56)
        overlay.save(diff_output, format="JPEG", quality=88, optimize=False, progressive=False)

    return ImageComparison(
        difference_score=round(difference_score, 6),
        changed_pixel_ratio=round(changed_ratio, 6),
        dhash_distance=dhash_distance,
        classification=classification,
    )


def exif_tag_name(tag: int) -> str:
    return str(ExifTags.TAGS.get(tag, tag))
