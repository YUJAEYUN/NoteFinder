from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "candidates" / "dart_search_candidates_20250729_20260729.csv"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "issued_note_2025-2026" / "final_dataset.json"

KEYWORD = "발행어음"
NUMBER = re.compile(r"(?<!\d)(-?\d{1,3}(?:,\d{3})+|-?\d+)(?!\d)")
UNIT_LABEL = re.compile(r"단위\s*[:：]?\s*(천원|백만원|억원|원|USD|달러)")
EXPLICIT_UNIT = re.compile(r"-?\d[\d,]*\s*(천원|백만원|억원|원|USD|달러)")
PERIOD = re.compile(r"\((\d{4}\.\d{2})\)")
CURRENT_HEADER = re.compile(r"당기|당분기|당반기|현재|기말|당년|202[5-6][./-]\d{1,2}")
PRIOR_HEADER = re.compile(r"전기|전년|전분기|전반기|202[0-4][./-]\d{1,2}")
AGGREGATE = re.compile(
    r"(?:채권|CP|RP|정기예금|기업어음|중금채|기타금융상품).{0,40}발행어음.{0,30}(?:등|포함|구성)"
    r"|발행어음.{0,40}(?:채권|CP|RP|정기예금|기업어음|중금채|기타금융상품).{0,30}(?:등|포함|구성)"
)
LIABILITY = re.compile(
    r"발행어음예수부채|발행어음\s*(?:발행|매출|판매|조달|상환|한도|수신)|"
    r"(?:예수부채|부채|조달|수신상품|자금조달).{0,50}발행어음|"
    r"발행어음.{0,20}(?:신탁계정|이자)|(?:신탁계정|이자비용).{0,20}발행어음"
)
HOLDING = re.compile(
    r"현금및현금성자산|단기금융상품|기타금융자산|상각후원가|금융상품|예치금|"
    r"취득원가|장부금액|장부가액|만기|개월|예.?적금|운용상품|투자자산"
)
GENERIC = {
    "수익증권", "외화증권", "채무증권", "지분증권", "파생결합증권",
    "유가증권", "증권",
}


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text(node: Tag) -> str:
    return clean(node.get_text(" ", strip=True))


def latest_filings() -> list[dict[str, str]]:
    rows = list(csv.DictReader(CANDIDATES.open(encoding="utf-8-sig")))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["corp_code"]].append(row)

    selected = []
    for items in grouped.values():
        available = [r for r in items if (RAW / f'{r["rcept_no"]}.zip').exists()]
        selected.append(max(
            available,
            key=lambda r: (
                PERIOD.search(r["report_nm"]).group(1) if PERIOD.search(r["report_nm"]) else "",
                r["rcept_dt"],
                r["rcept_no"],
            ),
        ))
    return sorted(selected, key=lambda r: r["corp_name"])


def direct_cells(row: Tag) -> list[Tag]:
    cells = row.find_all(["td", "th", "te"], recursive=False)
    return cells or row.find_all(["td", "th", "te"])


def table_grid(table: Tag) -> tuple[list[Tag], list[list[str]], list[list[Tag | None]]]:
    rows = table.find_all("tr", recursive=False) or table.find_all("tr")
    grid: list[list[str]] = []
    nodes: list[list[Tag | None]] = []
    spans: dict[int, tuple[int, str, Tag]] = {}
    for row in rows:
        values: list[str] = []
        refs: list[Tag | None] = []
        col = 0

        def consume_span() -> None:
            nonlocal col
            while col in spans:
                remaining, value, node = spans[col]
                values.append(value)
                refs.append(node)
                if remaining <= 1:
                    del spans[col]
                else:
                    spans[col] = (remaining - 1, value, node)
                col += 1

        consume_span()
        for cell in direct_cells(row):
            consume_span()
            value = text(cell)
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for offset in range(colspan):
                values.append(value)
                refs.append(cell)
                if rowspan > 1:
                    spans[col + offset] = (rowspan - 1, value, cell)
            col += colspan
        consume_span()
        grid.append(values)
        nodes.append(refs)
    width = max((len(row) for row in grid), default=0)
    for row, refs in zip(grid, nodes):
        row.extend([""] * (width - len(row)))
        refs.extend([None] * (width - len(refs)))
    return rows, grid, nodes


def nearby_context(table: Tag) -> str:
    parts: list[str] = []
    for node in table.find_all_previous(["p", "title", "tu", "td"], limit=18):
        value = text(node)
        if value and value not in parts:
            parts.append(value)
    return clean(" | ".join(reversed(parts[-12:])))


def issuer_names(value: str) -> list[str]:
    found: list[str] = []
    pattern = re.compile(
        r"(?<![가-힣A-Za-z0-9])(?:주식회사|㈜|\(주\))?\s*"
        r"([가-힣A-Za-z&]{1,18})\s*((?:투자)?증권)"
    )
    for match in pattern.finditer(value):
        candidate = clean(match.group(1) + match.group(2)).replace(" ", "")
        if (
            candidate in GENERIC
            or candidate.endswith("금융자산증권")
            or any(noise in candidate for noise in ("자본증권", "국채증권", "채무증권"))
        ):
            continue
        if candidate not in found:
            found.append(candidate)
    return found


def nearest_unit_text(table: Tag) -> str:
    for node in table.find_all_previous(string=True, limit=120):
        value = clean(str(node))
        if "단위" in value and UNIT_LABEL.search(value):
            return value
    return ""


def infer_unit(
    row_text: str,
    table_text: str,
    nearby: str,
    unit_text: str,
    numeric_node: Tag | None,
) -> str:
    if "USD" in row_text or "달러" in row_text:
        return "USD"
    for value in (row_text, table_text[:500], unit_text, nearby[-1500:]):
        matches = EXPLICIT_UNIT.findall(value) + UNIT_LABEL.findall(value)
        if matches:
            return matches[-1]
    if numeric_node and numeric_node.get("adecimal") == "-3":
        return "천원"
    if numeric_node and numeric_node.get("adecimal") == "-6":
        return "백만원"
    return "원문 단위 미표기"


def current_value_index(
    grid: list[list[str]], row_index: int, value_indices: list[int]
) -> tuple[int, str, bool]:
    header_by_col: dict[int, str] = {}
    for col in value_indices:
        header_by_col[col] = clean(" ".join(
            grid[r][col] for r in range(0, row_index)
            if grid[r][col] and not NUMBER.search(grid[r][col])
        ))
    current = [col for col in value_indices if CURRENT_HEADER.search(header_by_col[col])]
    non_prior_current = [
        col for col in current if not PRIOR_HEADER.search(header_by_col[col])
    ]
    if non_prior_current:
        col = non_prior_current[0]
        return col, header_by_col[col], True
    if current:
        col = current[0]
        return col, header_by_col[col], True
    numeric = [col for col in value_indices if NUMBER.search(grid[row_index][col])]
    col = numeric[0] if numeric else value_indices[0]
    prior_only = bool(PRIOR_HEADER.search(header_by_col[col])) and not bool(
        CURRENT_HEADER.search(header_by_col[col])
    )
    return col, header_by_col[col], not prior_only


def parse_archive(filing: dict[str, str]) -> list[dict]:
    archive = RAW / f'{filing["rcept_no"]}.zip'
    records: list[dict] = []
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            body = zf.read(member)
            if KEYWORD.encode() not in body:
                continue
            soup = BeautifulSoup(body, "html.parser")
            keyword_tables: list[Tag] = []
            seen_tables: set[int] = set()
            for string in soup.find_all(string=lambda value: value and KEYWORD in value):
                table = string.find_parent("table")
                if table is None or id(table) in seen_tables:
                    continue
                seen_tables.add(id(table))
                keyword_tables.append(table)
            for table_number, table in enumerate(keyword_tables, 1):
                rows, grid, nodes = table_grid(table)
                table_words = text(table)
                nearby = nearby_context(table)
                unit_text = nearest_unit_text(table)
                table_has_unit = bool(
                    UNIT_LABEL.search(table_words[:700])
                    or UNIT_LABEL.search(unit_text)
                    or UNIT_LABEL.search(nearby[-1500:])
                )
                for row_index, row in enumerate(rows):
                    row_text = clean(" | ".join(grid[row_index]))
                    if KEYWORD not in row_text or "미발행어음" in row_text:
                        continue
                    value_indices = [
                        col for col, value in enumerate(grid[row_index])
                        if col > 0 and (
                            ("," in value and NUMBER.search(value))
                            or value.strip() in {"-", "－"}
                            or (table_has_unit and NUMBER.fullmatch(value.strip()))
                        )
                    ]
                    amount = None
                    amount_col = None
                    header = ""
                    numeric_node = None
                    header_current = True
                    if value_indices:
                        amount_col, header, header_current = current_value_index(
                            grid, row_index, value_indices
                        )
                        match = NUMBER.search(grid[row_index][amount_col])
                        amount = int(match.group(1).replace(",", "")) if match else 0
                        numeric_node = nodes[row_index][amount_col]
                    combined = clean(f"{nearby} | {row_text}")
                    issuers = issuer_names(row_text)
                    aggregate = bool(AGGREGATE.search(row_text))
                    liability = bool(LIABILITY.search(combined))
                    holding = bool(HOLDING.search(combined))
                    if aggregate:
                        status = "제외"
                        reason = "여러 상품이 합산된 금액이라 발행어음 금액을 분리할 수 없음"
                    elif liability:
                        status = "제외"
                        reason = "회사의 발행·조달 또는 발행어음예수부채 공시로 보유자산이 아님"
                    elif amount is None:
                        status = "제외"
                        reason = "발행어음 언급은 있으나 연결된 금액 없음"
                    elif holding or clean(grid[row_index][0]).strip("-· ") == KEYWORD:
                        status = "포함"
                        reason = "자산·금융상품 표에서 발행어음 금액 확인"
                    else:
                        status = "검토"
                        reason = "원문 문맥 추가 확인 필요"
                    context_member = ""
                    if numeric_node:
                        context_member = numeric_node.get("acontext", "")
                    basis = (
                        "별도" if "SeparateMember" in context_member
                        else "연결" if "ConsolidatedMember" in context_member
                        else "원문 표"
                    )
                    period_status = (
                        "전기" if context_member.startswith("PFY")
                        else "당기" if context_member.startswith("CFY")
                        else "당기" if header_current
                        else "전기"
                    )
                    records.append({
                        **filing,
                        "source_file": member,
                        "table_number": table_number,
                        "row_number": row_index + 1,
                        "row_text": row_text,
                        "header": header,
                        "nearby": nearby,
                        "amount": amount,
                        "unit": infer_unit(
                            row_text, table_words, nearby, unit_text, numeric_node
                        ),
                        "issuer": ", ".join(issuers) if issuers else "공시 내 미표기",
                        "basis": basis,
                        "period_status": period_status,
                        "acontext": context_member,
                        "status": status,
                        "reason": reason,
                    })
    return records


def main() -> None:
    filings = latest_filings()
    records = []
    for index, filing in enumerate(filings, 1):
        records.extend(parse_archive(filing))
        print(f"[{index:03d}/{len(filings)}] {filing['corp_name']}: {len(records)} records")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"filings": filings, "records": records},
        ensure_ascii=False,
        indent=2,
    ), encoding="utf-8")
    print(f"Wrote {OUT} ({len(records)} records)")


if __name__ == "__main__":
    main()
