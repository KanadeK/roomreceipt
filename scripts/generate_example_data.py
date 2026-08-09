"""Generate deterministic, synthetic RoomReceipt example photos and manifests."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


@dataclass(frozen=True, slots=True)
class Scene:
    phase: str
    slot: str
    room: str
    item: str
    view: str
    note: str
    captured: str
    change: str


SCENES = (
    Scene(
        "move-in",
        "entry-door-wide",
        "Entry",
        "Front door",
        "Wide",
        "Small paint nick beside lower hinge",
        "2026:03:01 09:05:00",
        "door-nick",
    ),
    Scene(
        "move-in",
        "living-north-wall",
        "Living room",
        "North wall",
        "Wide",
        "Light scuff above baseboard",
        "2026:03:01 09:12:00",
        "wall-scuff",
    ),
    Scene(
        "move-in",
        "kitchen-counter-wide",
        "Kitchen",
        "Counter",
        "Wide",
        "Counter clear; faint mark near sink",
        "2026:03:01 09:20:00",
        "counter-mark",
    ),
    Scene(
        "move-in",
        "bathroom-vanity-front",
        "Bathroom",
        "Vanity",
        "Front",
        "Minor finish wear on left door",
        "2026:03:01 09:27:00",
        "vanity-wear",
    ),
    Scene(
        "move-out",
        "entry-door-wide",
        "Entry",
        "Front door",
        "Wide",
        "Same lower hinge paint nick visible",
        "2027:02:28 16:05:00",
        "door-nick",
    ),
    Scene(
        "move-out",
        "living-north-wall",
        "Living room",
        "North wall",
        "Wide",
        "Additional dark mark requires human review",
        "2027:02:28 16:12:00",
        "wall-new-mark",
    ),
    Scene(
        "move-out",
        "kitchen-counter-wide",
        "Kitchen",
        "Counter",
        "Wide",
        "Counter cleared; lighting differs",
        "2027:02:28 16:20:00",
        "counter-mark",
    ),
    Scene(
        "move-out",
        "bathroom-vanity-front",
        "Bathroom",
        "Vanity",
        "Front",
        "New chip-like visual requires human review",
        "2027:02:28 16:27:00",
        "vanity-new-mark",
    ),
)


def _base_room(draw: ImageDraw.ImageDraw, slot: str) -> None:
    draw.rectangle((0, 0, 960, 442), fill=(224, 228, 226))
    draw.rectangle((0, 442, 960, 640), fill=(173, 143, 108))
    draw.line((0, 442, 960, 442), fill=(92, 88, 82), width=5)
    draw.rectangle((0, 410, 960, 444), fill=(242, 243, 240))
    draw.line((0, 410, 960, 410), fill=(178, 182, 179), width=2)
    if slot.startswith("entry"):
        draw.rectangle((276, 72, 680, 443), fill=(111, 119, 122), outline=(65, 70, 73), width=6)
        draw.rectangle((303, 100, 653, 441), fill=(187, 190, 187))
        draw.ellipse((610, 264, 632, 286), fill=(84, 78, 68))
        draw.line((276, 330, 303, 330), fill=(68, 70, 70), width=6)
    elif slot.startswith("kitchen"):
        draw.rectangle((105, 292, 850, 445), fill=(82, 89, 91))
        draw.rectangle((80, 260, 875, 308), fill=(211, 208, 200), outline=(120, 116, 108), width=3)
        draw.rectangle((476, 268, 636, 300), fill=(132, 142, 145))
        draw.arc((515, 204, 598, 285), 180, 360, fill=(80, 85, 86), width=8)
        for x in (120, 355, 650):
            draw.line((x, 310, x, 442), fill=(49, 54, 56), width=3)
    elif slot.startswith("bathroom"):
        draw.rectangle((272, 208, 690, 445), fill=(184, 184, 178), outline=(104, 105, 100), width=4)
        draw.rectangle((250, 184, 712, 224), fill=(218, 216, 207), outline=(118, 116, 108), width=3)
        draw.ellipse((410, 186, 550, 220), fill=(240, 241, 237), outline=(136, 138, 134), width=2)
        draw.line((481, 224, 481, 443), fill=(100, 100, 96), width=3)
        draw.ellipse((446, 310, 458, 322), fill=(91, 86, 76))
        draw.ellipse((510, 310, 522, 322), fill=(91, 86, 76))
    else:
        draw.rectangle((680, 78, 875, 320), fill=(196, 215, 221), outline=(109, 119, 122), width=6)
        draw.line((777, 80, 777, 318), fill=(128, 137, 139), width=3)


def _apply_change(draw: ImageDraw.ImageDraw, change: str) -> None:
    if change == "door-nick":
        draw.rectangle((291, 342, 311, 355), fill=(82, 83, 80))
    elif change == "wall-scuff":
        draw.arc((188, 354, 292, 402), 190, 345, fill=(141, 134, 126), width=5)
    elif change == "wall-new-mark":
        draw.arc((188, 354, 292, 402), 190, 345, fill=(141, 134, 126), width=5)
        draw.line((474, 292, 548, 325), fill=(95, 84, 78), width=12)
        draw.line((486, 316, 554, 282), fill=(95, 84, 78), width=8)
    elif change == "counter-mark":
        draw.line((724, 279, 755, 283), fill=(126, 117, 105), width=4)
    elif change == "vanity-wear":
        draw.arc((302, 363, 347, 405), 180, 315, fill=(126, 121, 112), width=5)
    elif change == "vanity-new-mark":
        draw.arc((302, 363, 347, 405), 180, 315, fill=(126, 121, 112), width=5)
        draw.polygon(((614, 279), (642, 271), (631, 301)), fill=(106, 101, 92))


def image_bytes(scene: Scene) -> bytes:
    image = Image.new("RGB", (960, 640), (224, 228, 226))
    draw = ImageDraw.Draw(image)
    _base_room(draw, scene.slot)
    _apply_change(draw, scene.change)
    if scene.phase == "move-out":
        overlay = Image.new("RGB", image.size, (238, 231, 218))
        image = Image.blend(image, overlay, 0.035)
    exif = Image.Exif()
    exif[36867] = scene.captured
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=91, subsampling=0, optimize=False, exif=exif)
    return buffer.getvalue()


def manifest_bytes(phase: str) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["source", "slot", "room", "item", "view", "note", "captured_at"],
        lineterminator="\n",
    )
    writer.writeheader()
    for scene in SCENES:
        if scene.phase == phase:
            writer.writerow(
                {
                    "source": f"source/{scene.phase}/{scene.slot}.jpg",
                    "slot": scene.slot,
                    "room": scene.room,
                    "item": scene.item,
                    "view": scene.view,
                    "note": scene.note,
                    "captured_at": "",
                }
            )
    return buffer.getvalue().encode("utf-8")


def expected_files() -> dict[str, bytes]:
    files = {f"source/{scene.phase}/{scene.slot}.jpg": image_bytes(scene) for scene in SCENES}
    files["move-in.csv"] = manifest_bytes("move-in")
    files["move-out.csv"] = manifest_bytes("move-out")
    return files


def write_example(output: Path) -> None:
    for relative, payload in expected_files().items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def check_example(output: Path) -> bool:
    ok = True
    for relative, expected in expected_files().items():
        path = output / relative
        if not path.is_file():
            print(f"missing example file: {relative}", file=sys.stderr)
            ok = False
        elif path.read_bytes() != expected:
            print(f"example file differs from deterministic generator: {relative}", file=sys.stderr)
            ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("examples/bright-street"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.check:
        if not check_example(output):
            return 1
        print(f"deterministic example data verified: {output}")
    else:
        write_example(output)
        print(f"wrote deterministic example data: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
