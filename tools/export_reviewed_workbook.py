from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from note_finder.pipeline import unique_receipts
from note_finder.review import export_reviewed_workbook


DEFAULT_PROCESSED = ROOT / "data" / "processed" / "issued_note_2025-2026"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="수동 검토가 끝난 발행어음 회사 목록을 최종 5열 엑셀로 내보냅니다"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_PROCESSED / "curated_final.json",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=(
            ROOT
            / "data"
            / "candidates"
            / "dart_search_candidates_20250729_20260729.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "final" / "발행어음_보유기업.xlsx",
    )
    parser.add_argument(
        "--search-result-count",
        type=int,
        help="DART 검색 화면의 원래 검색행 수",
    )
    args = parser.parse_args()

    curated = json.loads(args.input.read_text(encoding="utf-8"))
    with args.candidates.open(encoding="utf-8-sig", newline="") as stream:
        candidates = list(csv.DictReader(stream))
    receipts, _ = unique_receipts(candidates)
    export_reviewed_workbook(
        curated,
        args.output,
        candidate_rows=len(candidates),
        unique_receipts=len(receipts),
        search_result_count=args.search_result_count,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
