from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


@pytest.fixture(autouse=True)
def fixed_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1772323200")


@pytest.fixture
def image_factory() -> Iterator[Callable[..., Path]]:
    created: list[Path] = []

    def make(
        path: Path,
        *,
        color: tuple[int, int, int] = (210, 214, 210),
        marker: tuple[int, int, int] | None = None,
        size: tuple[int, int] = (720, 480),
        captured: str = "2026:03:01 09:15:00",
    ) -> Path:
        image = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, int(size[1] * 0.72), size[0], size[1]), fill=(166, 139, 105))
        draw.line(
            (0, int(size[1] * 0.72), size[0], int(size[1] * 0.72)), fill=(94, 88, 80), width=4
        )
        if marker is not None:
            draw.rectangle(
                (size[0] // 2, size[1] // 3, size[0] // 2 + 90, size[1] // 3 + 55), fill=marker
            )
        exif = Image.Exif()
        if captured:
            exif[36867] = captured
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="JPEG", quality=92, subsampling=0, optimize=False, exif=exif)
        created.append(path)
        return path

    yield make
