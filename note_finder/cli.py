import argparse
import json
import os
from pathlib import Path

from .dart import DartClient
from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDART 발행어음 증거 수집 하네스")
    parser.add_argument("--begin", required=True, help="검색 시작일 YYYYMMDD")
    parser.add_argument("--end", required=True, help="검색 종료일 YYYYMMDD")
    parser.add_argument("--keyword", default="발행어음")
    parser.add_argument("--output", type=Path, default=Path("issued_note_report.xlsx"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    api_key = os.environ.get("OPENDART_API_KEY")
    if not api_key:
        parser.error("OPENDART_API_KEY 환경 변수가 필요합니다")
    print(json.dumps(run(DartClient(api_key, args.cache_dir), args.begin, args.end,
                         args.output, args.keyword), ensure_ascii=False, indent=2))

