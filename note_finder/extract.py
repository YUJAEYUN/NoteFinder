from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from bs4 import BeautifulSoup

BROKERS = {
    "NH투자증권": re.compile(r"(?:NH|엔에이치)\s*투자증권"),
    "한국투자증권": re.compile(r"(?:한국|한투)\s*투자증권"),
    "KB증권": re.compile(r"(?:KB|케이비)\s*증권"),
    "미래에셋증권": re.compile(r"미래에셋\s*(?:대우|증권)"),
}
NOISE = ("가입대상", "인가 확대", "법규상의 규제", "불특정금전신탁", "상품설명")
AMOUNT = re.compile(r"(?<![\d.])(-?\d{1,3}(?:,\d{3})+|-?\d+)\s*(백만원|천원|억원|원)?")


@dataclass
class Evidence:
    source_file: str
    context: str
    broker: str
    raw_amount: str
    raw_unit: str
    amount_thousand_won: int | None
    classification: str
    reason: str

    def dict(self) -> dict:
        return asdict(self)


def _to_thousand(value: int, unit: str) -> int | None:
    return {"천원": value, "백만원": value * 1000, "억원": value * 100_000,
            "원": round(value / 1000)}.get(unit)


def extract_document(name: str, body: bytes, keyword: str = "발행어음") -> list[Evidence]:
    soup = BeautifulSoup(body, "html.parser")
    # Table rows preserve the strongest relationship between label, counterparty and value.
    chunks = [row.get_text(" ", strip=True) for row in soup.find_all("tr")]
    chunks += [text.parent.get_text(" ", strip=True) for text in soup.find_all(string=lambda x: x and keyword in x)]
    results, seen = [], set()
    for context in chunks:
        context = re.sub(r"\s+", " ", context).strip()
        if keyword not in context or context in seen:
            continue
        seen.add(context)
        broker = next((canonical for canonical, pattern in BROKERS.items() if pattern.search(context)), "미정")
        amounts = [(m.group(1), m.group(2) or "") for m in AMOUNT.finditer(context)]
        explicit_amounts = [(v, u) for v, u in amounts if u or "," in v]
        aggregate = bool(re.search(r"중금채|기타금융상품|등으로 구성|등", context))
        noisy = any(term in context for term in NOISE)
        if noisy and not explicit_amounts:
            kind, reason = "EXCLUDED", "상품·제도 설명이며 연결된 금액 없음"
        elif aggregate:
            kind, reason = "B", "복수 상품 합산액으로 분리 필요"
        elif broker != "미정" and explicit_amounts:
            kind, reason = "A", "증권사·발행어음·금액이 동일 문맥에 명시"
        else:
            kind, reason = "REVIEW", "금액 또는 증권사 연결 관계 수동 확인 필요"
        if explicit_amounts:
            for raw, unit in explicit_amounts:
                value = int(raw.replace(",", ""))
                results.append(Evidence(name, context, broker, raw, unit,
                                        _to_thousand(value, unit), kind, reason))
        else:
            results.append(Evidence(name, context, broker, "", "", None, kind, reason))
    return results

