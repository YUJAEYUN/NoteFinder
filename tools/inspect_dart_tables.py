from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def cell_text(cell: Tag) -> str:
    return clean(cell.get_text(" ", strip=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--keyword", default="발행어음")
    parser.add_argument("--preceding", type=int, default=5)
    args = parser.parse_args()

    for archive in args.archives:
        print(f"\n### {archive}")
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                body = zf.read(member)
                if args.keyword.encode("utf-8") not in body:
                    continue
                soup = BeautifulSoup(body, "html.parser")
                hits = [
                    row for row in soup.find_all("tr")
                    if args.keyword in cell_text(row)
                ]
                print(f"\n## {member}: {len(hits)} keyword rows")
                for hit_index, row in enumerate(hits, 1):
                    table = row.find_parent("table")
                    rows = table.find_all("tr", recursive=False) if table else []
                    if not rows and table:
                        rows = table.find_all("tr")
                    try:
                        row_index = rows.index(row)
                    except ValueError:
                        row_index = 0
                    start = max(0, row_index - args.preceding)
                    print(f"\n-- hit {hit_index}, table row {row_index + 1}/{len(rows)}")
                    for index in range(start, min(len(rows), row_index + 2)):
                        cells = rows[index].find_all(["td", "th", "te"], recursive=False)
                        if not cells:
                            cells = rows[index].find_all(["td", "th", "te"])
                        values = []
                        for cell in cells:
                            attrs = []
                            for name in ("rowspan", "colspan", "acode", "acontext"):
                                if cell.get(name):
                                    attrs.append(f"{name}={cell.get(name)}")
                            suffix = f" ({'; '.join(attrs)})" if attrs else ""
                            values.append(cell_text(cell) + suffix)
                        marker = ">>" if index == row_index else "  "
                        print(f"{marker} {index + 1}: {values}")


if __name__ == "__main__":
    main()
