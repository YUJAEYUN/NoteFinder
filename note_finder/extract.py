from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from bs4 import BeautifulSoup

# This is deliberately not an issuer allowlist. Disclosures can name a distributor,
# counterparty, former corporate name, or an overseas securities firm. Preserve the
# spelling in the source; canonicalization belongs in a separately maintained entity
# registry, not in extraction rules.
BROKER_NAME = re.compile(r"(?<![가-힣A-Za-z0-9])(?:주식회사|㈜|\(주\))?\s*([가-힣A-Za-z&]{2,24}(?:투자)?증권)")
NOISE = ("가입대상", "인가 확대", "법규상의 규제", "불특정금전신탁", "상품설명")
AMOUNT = re.compile(r"(?<![\d.])(-?\d{1,3}(?:,\d{3})+|-?\d+)\s*(백만원|천원|억원|원)?")
GENERIC_SECURITIES = {
    "수익증권", "파생결합증권", "외화증권", "지분증권", "채무증권",
    "전환증권", "단기매매증권", "매도가능증권", "만기보유증권",
}
HOLDING_CONTEXT = re.compile(
    r"(?:현금및현금성자산|단기투자자산|단기금융상품|기타단기금융상품|"
    r"기타금융자산|상각후원가|공정가치측정금융자산|금융상품|예치금|"
    r"사외적립자산|장부금액|장부가액|취득원가).{0,60}발행어음|"
    r"발행어음.{0,50}(?:원금|평가금액|운용금액|만기|개월|단기금융상품)"
)
AGGREGATE_CONTEXT = re.compile(
    r"(?:채권|CP|RP|정기예금|중금채|기업어음|기타금융상품).{0,40}"
    r"발행어음.{0,30}(?:등|포함|구성)|"
    r"발행어음.{0,40}(?:채권|CP|RP|정기예금|중금채|기업어음|"
    r"기타금융상품).{0,30}(?:등|포함|구성)"
)
TRUST_CONTEXT = re.compile(
    r"신탁계정|금전신탁|신탁자금|매입어음"
)
INDIRECT_CONTEXT = re.compile(
    r"MMT|발행어음.{0,50}(?:매매에\s*운용|구성자산)|"
    r"(?:매매에\s*운용|구성자산).{0,50}발행어음"
)
LIABILITY_CONTEXT = re.compile(
    r"발행어음예수부채|"
    r"발행어음\s*(?:발행액|매출액|판매액|조달액|상환액|발행잔액)|"
    r"(?:예수부채|자금조달|수신상품|이자비용).{0,60}발행어음|"
    r"발행어음.{0,40}(?:예수부채|자금조달|수신상품|이자비용)"
)


@dataclass
class Evidence:
    source_file: str
    context: str
    broker: str
    raw_amount: str
    raw_unit: str
    amount_thousand_won: int | None
    classification: str
    exposure_type: str
    reason: str

    def dict(self) -> dict:
        return asdict(self)


def _to_thousand(value: int, unit: str) -> int | None:
    return {"천원": value, "백만원": value * 1000, "억원": value * 100_000,
            "원": round(value / 1000)}.get(unit)


def find_brokers(context: str) -> list[str]:
    """Return every explicit *증권 company name exactly as disclosed."""
    found: list[str] = []
    for candidate in BROKER_NAME.findall(context):
        if candidate in GENERIC_SECURITIES:
            continue
        if candidate not in found:
            found.append(candidate)
    return found


def extract_document(name: str, body: bytes, keyword: str = "발행어음") -> list[Evidence]:
    soup = BeautifulSoup(body, "html.parser")
    # Table rows preserve the strongest relationship between label, counterparty and value.
    chunks = [row.get_text(" ", strip=True) for row in soup.find_all("tr")]
    # A keyword inside a table row is already represented by that row. Adding its
    # parent cell/table as prose creates broader duplicate evidence with weaker
    # label-to-value relationships.
    chunks += [
        text.parent.get_text(" ", strip=True)
        for text in soup.find_all(string=lambda x: x and keyword in x)
        if text.find_parent("tr") is None
    ]
    results, seen = [], set()
    for context in chunks:
        context = re.sub(r"\s+", " ", context).strip()
        if keyword not in context or context in seen:
            continue
        seen.add(context)
        brokers = find_brokers(context)
        broker = ", ".join(brokers) if brokers else "미정"
        amounts = [(m.group(1), m.group(2) or "") for m in AMOUNT.finditer(context)]
        explicit_amounts = [(v, u) for v, u in amounts if u or "," in v]
        aggregate = bool(AGGREGATE_CONTEXT.search(context))
        trust = bool(TRUST_CONTEXT.search(context))
        indirect = bool(INDIRECT_CONTEXT.search(context))
        liability = bool(LIABILITY_CONTEXT.search(context))
        noisy = any(term in context for term in NOISE)
        holding = bool(HOLDING_CONTEXT.search(context))
        if "미발행어음" in context:
            kind, exposure, reason = (
                "EXCLUDED",
                "NOT_ISSUED",
                "미발행어음 표현으로 발행어음 투자·보유 내역이 아님",
            )
        elif liability and not trust:
            kind, exposure, reason = (
                "EXCLUDED",
                "LIABILITY",
                "자사 발행·조달 또는 발행어음 예수부채 문맥으로 보유자산이 아님",
            )
        elif noisy and not explicit_amounts:
            kind, exposure, reason = (
                "EXCLUDED",
                "DESCRIPTION",
                "상품·제도 설명이며 연결된 금액 없음",
            )
        elif trust:
            broker = broker if broker != "미정" else "공시 내 미표기"
            kind = "A" if explicit_amounts else "REVIEW"
            exposure = "TRUST"
            reason = (
                "신탁계정의 발행어음 금액이 확인됨"
                if explicit_amounts
                else "신탁계정에서 발행어음 존재는 확인되나 잔액은 공시 미표기"
            )
        elif indirect:
            broker = broker if broker != "미정" else "공시 내 미표기"
            kind, exposure, reason = (
                "B" if explicit_amounts else "REVIEW",
                "INDIRECT",
                "MMT 등 간접 운용 문맥으로 발행어음 단독금액 확인이 필요",
            )
        elif aggregate:
            broker = broker if broker != "미정" else "공시 내 미표기"
            kind, exposure, reason = (
                "B",
                "AGGREGATE",
                "복수 상품 합산액으로 발행어음 단독금액을 분리할 수 없음",
            )
        elif broker != "미정" and explicit_amounts:
            kind, exposure, reason = (
                "A",
                "DIRECT",
                "증권사·발행어음·금액이 동일 문맥에 명시",
            )
        elif holding and explicit_amounts:
            broker = "공시 내 미표기"
            kind, exposure, reason = (
                "A",
                "DIRECT",
                "발행어음 보유 문맥과 금액은 명시됐으나 증권사명은 공시 내 미표기",
            )
        elif holding:
            broker = broker if broker != "미정" else "공시 내 미표기"
            kind, exposure, reason = (
                "REVIEW",
                "EXISTENCE",
                "보유 문맥에서 발행어음 존재는 확인되나 금액은 공시 미표기",
            )
        elif not explicit_amounts:
            kind, exposure, reason = (
                "EXCLUDED",
                "MENTION",
                "발행어음 언급은 있으나 보유·신탁·간접 운용 근거가 없음",
            )
        else:
            kind, exposure, reason = (
                "REVIEW",
                "UNKNOWN",
                "금액 또는 보유 관계의 수동 확인 필요",
            )
        if explicit_amounts:
            for raw, unit in explicit_amounts:
                value = int(raw.replace(",", ""))
                results.append(Evidence(name, context, broker, raw, unit,
                                        _to_thousand(value, unit), kind, exposure, reason))
        else:
            results.append(Evidence(
                name, context, broker, "", "", None, kind, exposure, reason
            ))
    return results
