"""Dependency-free accessibility and link checks for the generated static site."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str | None]] = []
        self.links: list[str] = []
        self.h1_count = 0
        self.has_viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "img":
            self.images.append(values)
        elif tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = True


def local_target(root: Path, page: Path, href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith(("#", "mailto:")):
        return None
    target = (page.parent / parsed.path).resolve()
    if parsed.path.endswith("/") or target.is_dir():
        target /= "index.html"
    try:
        target.relative_to(root)
    except ValueError:
        return Path("__unsafe__")
    return target


def check_site(root: Path) -> list[str]:
    failures: list[str] = []
    pages = sorted(root.rglob("*.html"))
    if not pages:
        return ["no HTML pages found"]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        relative = page.relative_to(root)
        if "\N{EM DASH}" in text or "\N{EN DASH}" in text:
            failures.append(f"dash character in {relative}")
        parser = PageParser()
        parser.feed(text)
        if parser.h1_count != 1:
            failures.append(f"{relative}: expected exactly one h1, got {parser.h1_count}")
        if not parser.has_viewport:
            failures.append(f"{relative}: missing viewport meta")
        for image in parser.images:
            if not image.get("src") or not image.get("alt"):
                failures.append(f"{relative}: image missing src or alt")
        for href in parser.links:
            target = local_target(root, page, href)
            if target is not None and not target.is_file():
                failures.append(f"{relative}: broken local link {href}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    root = args.site.resolve()
    failures = check_site(root)
    if failures:
        print("\n".join(failures))
        return 1
    print(f"site check passed: {len(list(root.rglob('*.html')))} HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
