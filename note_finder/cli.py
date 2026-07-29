import argparse
import csv
import json
import os
from pathlib import Path

from .dart import DartClient
from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDART 발행어음 증거 수집 하네스")
    parser.add_argument("--begin", help="검색 시작일 YYYYMMDD")
    parser.add_argument("--end", help="검색 종료일 YYYYMMDD")
    parser.add_argument("--candidates", type=Path,
                        help="DART 본문검색 결과 CSV (rcept_no 필수). 지정하면 전체 공시 목록 수집을 건너뜁니다")
    parser.add_argument("--keyword", default="발행어음")
    parser.add_argument("--output", type=Path, default=Path("issued_note_report.xlsx"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--search-result-count",
        type=int,
        help="DART 화면에 표시된 검색행 수. 후보 CSV 행 수와 별도로 감사 로그에 기록합니다",
    )
    parser.add_argument(
        "--all-filings",
        action="store_true",
        help="회사별 최신 공시 1건이 아니라 정정 중복 제거 후 모든 공시를 분석합니다",
    )
    args = parser.parse_args()
    api_key = os.environ.get("OPENDART_API_KEY")
    if not api_key:
        parser.error("OPENDART_API_KEY 환경 변수가 필요합니다")
    if not args.candidates and not (args.begin and args.end):
        parser.error("--candidates 또는 --begin/--end가 필요합니다")
    candidates = None
    if args.candidates:
        with args.candidates.open(encoding="utf-8-sig", newline="") as stream:
            candidates = list(csv.DictReader(stream))
        if not candidates or "rcept_no" not in candidates[0]:
            parser.error("후보 CSV에는 rcept_no 열이 필요합니다")
    print(json.dumps(run(DartClient(api_key, args.cache_dir), args.begin or "", args.end or "",
                         args.output, args.keyword, candidates,
                         latest_per_company=not args.all_filings,
                         search_result_count=args.search_result_count),
                     ensure_ascii=False, indent=2))
