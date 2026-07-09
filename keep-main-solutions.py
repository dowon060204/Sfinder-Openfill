#!/usr/bin/env python3
"""Keep only one displayed setup result per main solution in setup.html."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


COUNT_RE = re.compile(r"<div>(\d+) solutions / \d+ sub solutions</div>")


def keep_main_solutions(html: str) -> str:
    output: list[str] = []
    in_section = False
    kept_section_link = False

    for line in html.splitlines(keepends=True):
        if "All solutions</a>" in line:
            continue

        count_match = COUNT_RE.search(line)
        if count_match:
            line = COUNT_RE.sub(r"<div>\1 main solutions</div>", line)

        if line.startswith("<section "):
            in_section = True
            kept_section_link = False
        elif line.startswith("</section>"):
            in_section = False

        if in_section and line.startswith("<div><a href="):
            if kept_section_link:
                continue
            kept_section_link = True

        output.append(line)

    return "".join(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "html",
        nargs="?",
        default="output/setup.html",
        help="setup HTML file to trim",
    )
    args = parser.parse_args()

    path = Path(args.html)
    html = path.read_text(encoding="utf-8")
    trimmed = keep_main_solutions(html)
    path.write_text(trimmed, encoding="utf-8", newline="")
    print(f"kept main solutions only: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
