from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from roomreceipt.media import compare_images, difference_hash, inspect_image, sha256_file
from roomreceipt.models import RoomReceiptError


def test_inspect_image_prefers_provided_timestamp(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    image = image_factory(tmp_path / "photo.jpg")
    metadata = inspect_image(image, captured_at="2026-03-01T09:15:00+08:00")
    assert metadata.capture_source == "provided"
    assert metadata.timezone_known is True
    assert metadata.captured_at.endswith("+08:00")
    assert metadata.mime == "image/jpeg"
    assert metadata.sha256 == sha256_file(image)


def test_inspect_image_handles_unknown_capture_time(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    image = image_factory(tmp_path / "photo.jpg", captured="")
    metadata = inspect_image(image)
    assert metadata.captured_at == ""
    assert metadata.capture_source == "unknown"
    assert metadata.timezone_known is False


def test_inspect_image_rejects_bad_timestamp(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    image = image_factory(tmp_path / "photo.jpg")
    with pytest.raises(RoomReceiptError, match="captured-at"):
        inspect_image(image, captured_at="last Tuesday")


def test_hash_and_comparison_distinguish_changed_image(
    tmp_path: Path, image_factory: Callable[..., Path]
) -> None:
    before = image_factory(tmp_path / "before.jpg")
    same = image_factory(tmp_path / "same.jpg")
    changed = image_factory(tmp_path / "changed.jpg", marker=(180, 20, 20))
    assert difference_hash(before) == difference_hash(same)
    close = compare_images(before, same)
    assert close.classification == "close-match"
    diff = tmp_path / "diff.jpg"
    review = compare_images(before, changed, diff_output=diff)
    assert review.classification == "review"
    assert review.changed_pixel_ratio > close.changed_pixel_ratio
    assert diff.is_file()
