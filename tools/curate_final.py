from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from note_finder.pipeline import dart_url


PROCESSED = ROOT / "data" / "processed" / "issued_note_2025-2026"
SOURCE = PROCESSED / "final_dataset.json"
OUTPUT = PROCESSED / "curated_final.json"


def detail(
    company: str,
    amount_won: int | None,
    issuer: str,
    product: str,
    expression: str,
    basis: str = "원문 표",
    note: str = "",
    evidence_type: str = "DIRECT",
) -> dict:
    return {
        "corp_name": company,
        "amount_won": amount_won,
        "issuer": issuer,
        "product": product,
        "expression": expression,
        "basis": basis,
        "note": note,
        "evidence_type": evidence_type,
    }


DETAILS = [
    detail("E1", 110_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 110,000,000 (단위: 천원)", "연결",
           "연결재무제표의 현금및예치금 내역", evidence_type="INDIRECT"),
    detail("HD현대마린솔루션", 30_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 원금 30,000 | 평가금액 30,000 (단위: 백만원)"),
    detail("LS증권", 110_000_000_000, "공시 내 미표기", "발행어음",
           "현금및현금성자산 | 발행어음 | 110,000,000 (단위: 천원)", "별도"),
    detail("NC", 80_000_000_000, "공시 내 미표기", "발행어음",
           "금융자산(상각후원가) | 발행어음 | 80,000,000 (단위: 천원)", "연결"),
    detail("NICE", 12_518_047_000, "공시 내 미표기", "발행어음",
           "발행어음 | 12,518,047 (단위: 천원)"),
    detail("SBS", 20_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 20,000 | 계약기간 12개월 (단위: 백만원)"),
    detail("SK바이오사이언스", 10_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 당반기말 10,000,000 (단위: 천원)"),
    detail("SK케미칼", 9_928_751_000, "공시 내 미표기", "발행어음",
           "단기금융상품 | 발행어음 | 9,928,751 (단위: 천원)", "연결",
           evidence_type="INDIRECT"),
    detail("나노엔텍", 3_448_251_000, "공시 내 미표기", "발행어음",
           "발행어음 | 3,448,251 (단위: 천원)"),
    detail("뉴로핏", 5_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 당분기말 5,000,000 (단위: 천원)"),
    detail("리딩투자증권", 80_000_000_000, "공시 내 미표기", "발행어음",
           "현금및현금성자산 | 발행어음 | 당기말 80,000,000 (단위: 천원)", "별도"),
    detail("더본코리아", 46_340_000_000, "한국투자증권",
           "한국투자증권 퍼스트 발행어음",
           "기업어음(한국투자증권 퍼스트 발행어음) | 46,340 (단위: 백만원)"),
    detail("더본코리아", 5_000_000_000, "NH투자증권",
           "NH투자증권 QV 발행어음",
           "기업어음(NH투자증권 QV 발행어음) | 5,000 (단위: 백만원)"),
    detail("더코디", 1_300_000_000, "공시 내 미표기", "발행어음 특판형_법인",
           "발행어음 | 발행어음 특판형_법인 | 1,300,000 (단위: 천원)"),
    detail("데브시스터즈", 765_019_000, "공시 내 미표기",
           "당기손익-공정가치측정 발행어음",
           "발행어음 | 당분기말 765,019 (단위: 천원)", "별도"),
    detail("데브시스터즈", 2_619_695_000, "공시 내 미표기",
           "상각후원가측정 발행어음",
           "발행어음 | 당분기말 2,619,695 (단위: 천원)", "별도"),
    detail("데이원컴퍼니", 3_000_000_000, "NH투자증권", "NH투자증권 발행어음",
           "NH투자증권 발행어음 | 원금 3,000 | 평가금액 3,021 (단위: 백만원)"),
    detail("딥노이드", 3_000_000_000, "미래에셋증권", "미래에셋증권 원화 발행어음",
           "미래에셋증권 원화 발행어음 | 3,000 (단위: 백만원)"),
    detail("메타바이오메드", 10_000_000_000, "공시 내 미표기", "원화발행어음",
           "원화발행어음 | 10,000 | 9개월 (단위: 백만원)"),
    detail("문배철강", 1_000_000_000, "공시 내 미표기",
           "퇴직급여 사외적립자산 내 발행어음",
           "발행어음, 전체 사외적립자산에서 차지하는 금액 | 1,000,000 (단위: 천원)",
           "별도", "일반 운전자금이 아니라 퇴직급여 사외적립자산"),
    detail("바이오비쥬", 1_016_000_000, "공시 내 미표기", "증권사 발행어음",
           "증권사 발행어음 | 원금 1,000 | 평가금액 1,016 (단위: 백만원)",
           note="평가금액을 보유금액으로 사용"),
    detail("비씨엔씨", 2_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 당분기말 유동 2,000,000 (단위: 천원)", "별도"),
    detail("씨앤씨인터내셔널", 12_914_000_000, "공시 내 미표기", "발행어음",
           "어음 | 발행어음 | 12,914 | 3개월 (단위: 백만원)"),
    detail("씽크풀", 900_000_000, "미래에셋증권", "미래에셋증권 발행어음",
           "발행어음 | 미래에셋증권 발행어음 | 900,000,000 (단위: 원)"),
    detail("아리바이오LAB", 5_000_000_000, "NH투자증권", "NH QV 발행어음",
           "NH QV 발행어음 (NH투자증권) | 5,000 (단위: 백만원)"),
    detail("아이디스", 1_000_000_000, "공시 내 미표기", "발행어음",
           "기타단기금융상품 1,000,000,000원 / 발행어음으로 구성"),
    detail("아이디피", 4_000_000_000, "NH증권", "NH증권 발행어음",
           "NH증권 발행어음 | 원금 4,000 | 평가금액 4,019 (단위: 백만원)"),
    detail("아이디피", 1_526_000_000, "KB증권", "KB증권 발행어음",
           "KB증권 발행어음 | 원금 1,526 | 평가금액 1,572 (단위: 백만원)"),
    detail("아이씨티케이", 7_000_000_000, "NH투자증권", "NH투자증권 발행어음",
           "NH투자증권 발행어음 | 원금 7,000 | 평가금액 7,177 (단위: 백만원)"),
    detail("아이언디바이스", 3_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 원금 3,000 | 평가금액 3,000 (단위: 백만원)"),
    detail("아이톡시", 100_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 100 (단위: 백만원)"),
    detail("아이티아이즈", 1_007_073_445, "공시 내 미표기", "발행어음",
           "당기손익-공정가치측정금융자산 | 발행어음 | 1,007,073,445 (단위: 원)",
           "별도"),
    detail("안랩", 97_500_000_000, "공시 내 미표기", "발행어음",
           "단기투자자산 | 발행어음 | 당분기말 97,500,000 (단위: 천원, 연결)",
           "연결"),
    detail("에스제이엠", 6_000_000_000, "KB증권", "KB증권 발행어음(스텝업)",
           "KB증권 발행어음(스텝업) | 6,000,000,000 (단위: 원)"),
    detail("에스제이엠", 2_000_000_000, "KB증권", "KB증권 발행어음",
           "KB증권 발행어음 | 2,000,000,000 (단위: 원)"),
    detail("에코프로에이치엔", 20_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 20,000 | 10개월 (단위: 백만원)"),
    detail("엔시스", 1_600_539_000, "공시 내 미표기", "발행어음(수시형)",
           "발행어음(수시형) | 당분기말 1,600,539 (단위: 천원)",
           "연결"),
    detail("옵티코어", 1_002_879_165, "공시 내 미표기", "발행어음",
           "유동항목 | 발행어음 | 1,002,879,165 (단위: 원)", "별도"),
    detail("우리로", 9_463_000_000, "공시 내 미표기", "MMT(발행어음 운용)",
           "MMT상품 9,463백만원 / 1일 만기 발행어음 매매에 운용",
           note="직접 발행어음 계정이 아닌 MMT를 통한 간접 운용",
           evidence_type="INDIRECT"),
    detail("일신레져", 2_000_000_000, "공시 내 미표기", "발행어음",
           "단기금융상품 | 발행어음 | 당기 2,000,000,000 (단위: 원)"),
    detail("제이씨현시스템", 11_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 11,000,000,000 (단위: 원)"),
    detail("조일알미늄", 4_405_719_000, "공시 내 미표기", "외화발행어음",
           "현금및현금성자산 | 외화발행어음 | 당분기말 4,405,719 (단위: 천원)"),
    detail("지구홀딩스", 3_005_959_000, "NH농협증권", "발행어음",
           "발행어음 | NH농협증권 | 3,005,959 (단위: 천원)"),
    detail("지니언스", 3_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 원금 3,000 | 평가금액 3,000 (단위: 백만원)"),
    detail("퀄리타스반도체", 15_000_000_000, "공시 내 미표기", "NH QV 발행어음",
           "단기금융상품 | NH QV 발행어음 | 당분기말 15,000,000,000 (단위: 원)",
           note="상품명에는 NH QV가 있으나 증권사 법인명은 공시 내 미표기"),
    detail("툴젠", 10_408_000_000, "KB증권", "KB증권 종합위탁-발행어음 3건",
           "KB증권(종합위탁-발행어음) | 4,000 + 4,000 + 2,408 (단위: 백만원)"),
    detail("파로스아이바이오", 1_403_000_000, "공시 내 미표기", "발행어음(외화) USD",
           "발행어음(외화) USD | 운용금액 1,403 (표 단위: 백만원)",
           note="USD는 상품명이고 금액 열의 표 단위는 백만원"),
    detail("파마리서치", 49_942_200_000, "공시 내 미표기", "발행어음",
           "발행어음 | 49,942,200,000 (단위: 원)", "별도"),
    detail("퓨쳐켐", 5_000_000_000, "KB증권", "KB증권 발행어음",
           "KB증권 발행어음 | 5,000,000 (단위: 천원)"),
    detail("하츠", 5_000_000_000, "공시 내 미표기", "발행어음",
           "단기금융상품 | 발행어음 | 5,000,000,000 (단위: 원)"),
    detail("한국첨단소재", 12_000_000_000, "공시 내 미표기", "발행어음(6개월 만기) 2건",
           "발행어음(6개월 만기) | 1,000 + 11,000 (단위: 백만원)"),
    detail("화승엔터프라이즈", 10_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 10,000 | 수시 입출금 (단위: 백만원)"),
    detail("화승인더스트리", 10_000_000_000, "공시 내 미표기", "발행어음",
           "발행어음 | 10,000 | 수시 입출금 (단위: 백만원)",
           evidence_type="INDIRECT"),
]

# Browser review and table-level rechecks added these companies after the first
# 49-company direct-holding pass. Keep them as reviewed evidence rather than
# teaching the automatic extractor that every trust/aggregate mention is final.
DETAILS += [
    detail("경동제약", 8_999_388_000, "공시 내 미표기", "채권·CP/RP·발행어음 등",
           "채권·CP/RP·발행어음 등 | 8,999,388천원",
           evidence_type="AGGREGATE"),
    detail("NH투자증권", 646_220_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "금전신탁 자금운용현황 - 발행어음 | 금전신탁합계 646,220백만원",
           evidence_type="TRUST"),
    detail("빅솔론", 4_000_000_000, "공시 내 미표기", "기타단기금융상품",
           "기타단기금융상품 4,000,000,000원 | 중금채·발행어음 등으로 구성",
           evidence_type="AGGREGATE"),
    detail("에스디바이오센서", 80_000_000_000, "공시 내 미표기", "금융상품",
           "금융상품 | 발행어음 등 | 80,000,000천원",
           evidence_type="AGGREGATE"),
    detail("에이루트", 2_273_279_000, "공시 내 미표기", "MMT",
           "MMT 2,273,279천원 | 구성자산은 발행어음과 RP",
           evidence_type="INDIRECT"),
    detail("오성첨단소재", 17_999_999_000, "공시 내 미표기", "발행어음 외 3건",
           "발행어음 외 3건 | 4,999,999 + 7,000,000 + 6,000,000천원",
           evidence_type="AGGREGATE"),
    detail("한국지주", 8_891_647_000, "NH투자증권(주) 외", "발행어음 등",
           "발행어음 등 | NH투자증권(주) 외 | 8,891,647천원",
           evidence_type="AGGREGATE"),
    detail("DB증권", 12_196_547_000, "공시 내 미표기", "신탁계정 발행어음",
           "발행어음, 신탁계정 | 12,196,547천원", evidence_type="TRUST"),
    detail("교보증권", 10_000_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 10,000백만원", evidence_type="TRUST"),
    detail("대신증권", 318_187_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 318,187백만원", evidence_type="TRUST"),
    detail("미래에셋증권", 73_726_553_318, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 73,726,553,318원", evidence_type="TRUST"),
    detail("삼성증권", 250_000_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 250,000백만원", evidence_type="TRUST"),
    detail("아이비케이투자증권", 167_413_904_532, "공시 내 미표기",
           "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 167,413,904,532원",
           evidence_type="TRUST"),
    detail("신한투자증권", 1_176_715_312_586, "공시 내 미표기",
           "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 1,176,715,312,586원",
           evidence_type="TRUST"),
    detail("현대차증권", 130_000_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 130,000,000,000원",
           evidence_type="TRUST"),
    detail("하나증권", 264_670_000_000, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 매입어음 - 발행어음 | 264,670백만원", evidence_type="TRUST"),
    detail("유진증권", None, "공시 내 미표기", "신탁계정 발행어음",
           "신탁계정 발행어음이자 52백만원 | 잔액은 공시 미표기",
           evidence_type="TRUST"),
    detail("티비씨", None, "공시 내 미표기", "발행어음 운용",
           "유동자산을 금융기관 발행 예금·금융채·발행어음 등에 운용 | 단독금액 미표기",
           evidence_type="EXISTENCE"),
    detail("한국금융지주", 2_660_753_000_000, "공시 내 미표기",
           "한국투자증권 신탁계정 발행어음",
           "한국투자증권 신탁계정 발행어음 | 2,660,753백만원 | 연결·간접 반영",
           evidence_type="INDIRECT"),
    detail("한국투자증권", 2_660_753_000_000, "공시 내 미표기",
           "신탁계정 발행어음",
           "금전신탁 자금운용현황 - 발행어음 | 2,660,753백만원",
           evidence_type="TRUST"),
    detail("한화", 177_872_000_000, "공시 내 미표기",
           "한화투자증권 신탁계정 발행어음",
           "한화투자증권 신탁계정 발행어음 | 177,872백만원 | 연결·간접 반영",
           evidence_type="INDIRECT"),
    detail("한화생명", 177_872_000_000, "공시 내 미표기",
           "한화투자증권 신탁계정 발행어음",
           "한화투자증권 신탁계정 발행어음 | 177,872백만원 | 연결·간접 반영",
           evidence_type="INDIRECT"),
    detail("한화투자증권", 177_872_000_000, "공시 내 미표기",
           "신탁계정 발행어음",
           "금전신탁 자금운용현황 - 발행어음 | 177,872백만원",
           evidence_type="TRUST"),
]

ZERO_COMPANIES = {"네오크레마", "비비씨", "동서", "메카로", "알에프텍"}
AGGREGATE_COMPANIES = {
    "JB금융지주", "경동제약", "광주은행", "국민은행", "빅솔론",
    "에스디바이오센서", "에이루트", "오성첨단소재", "한국지주",
}
NOT_HOLDING_COMPANIES = {
    "BNK투자증권", "DB증권", "KG케미칼", "NH투자증권", "교보증권",
    "농협금융지주", "다올투자증권", "다우기술", "다우데이타", "대신증권",
    "로스웰", "미래에셋증권", "미래에셋캐피탈", "삼성증권", "삼성카드",
    "신한은행", "신한지주", "신한투자증권", "아이비케이투자증권",
    "우리금융지주", "우리투자증권", "케이비증권", "케이프", "키움증권",
    "하나증권", "한국금융지주", "한국증권금융", "한국투자증권",
    "현대차증권",
}


def period_from_report(report: str) -> str:
    match = re.search(r"\((\d{4}\.\d{2})\)", report)
    return match.group(1) if match else ""


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    filings = {item["corp_name"]: item for item in source["filings"]}
    evidence_by_company: dict[str, list[dict]] = defaultdict(list)
    for row in source["records"]:
        evidence_by_company[row["corp_name"]].append(row)

    enriched_details = []
    for row in DETAILS:
        filing = filings[row["corp_name"]]
        enriched_details.append({
            **row,
            "corp_code": filing["corp_code"],
            "rcept_no": filing["rcept_no"],
            "rcept_dt": filing["rcept_dt"],
            "report_nm": filing["report_nm"],
            "report_period": period_from_report(filing["report_nm"]),
            "dart_url": dart_url(filing["rcept_no"]),
        })

    company_rows = []
    by_company: dict[str, list[dict]] = defaultdict(list)
    for row in enriched_details:
        by_company[row["corp_name"]].append(row)
    for company, rows in sorted(by_company.items()):
        filing = filings[company]
        issuers = sorted({row["issuer"] for row in rows})
        products = [row["product"] for row in rows]
        company_rows.append({
            "corp_name": company,
            "corp_code": filing["corp_code"],
            "report_period": period_from_report(filing["report_nm"]),
            "report_nm": filing["report_nm"],
            "rcept_no": filing["rcept_no"],
            "amount_won": (
                sum(row["amount_won"] for row in rows if row["amount_won"] is not None)
                if any(row["amount_won"] is not None for row in rows)
                else None
            ),
            "issuer": ", ".join(issuers),
            "product": " / ".join(products),
            "expression": " || ".join(row["expression"] for row in rows),
            "basis": ", ".join(sorted({row["basis"] for row in rows})),
            "evidence_type": ", ".join(sorted({row["evidence_type"] for row in rows})),
            "status": "보유 확인",
            "note": " / ".join(row["note"] for row in rows if row["note"]),
            "dart_url": rows[0]["dart_url"],
        })

    excluded = []
    holding_names = set(by_company)
    for company, filing in sorted(filings.items()):
        if company in holding_names:
            continue
        evidence = evidence_by_company.get(company, [])
        expression = next(
            (row["row_text"] for row in evidence if row.get("row_text")),
            "발행어음 검색어는 확인되나 보유금액 표시는 없음",
        )
        if company in ZERO_COMPANIES:
            status = "현재 잔액 0"
            reason = "당기 열이 '-' 또는 0이거나 변동표 기말잔액이 0"
        elif company in AGGREGATE_COMPANIES:
            status = "금액 분리 불가"
            reason = "발행어음이 다른 상품과 합산되어 단독 금액을 확정할 수 없음"
        elif company in NOT_HOLDING_COMPANIES:
            status = "보유자산 아님"
            reason = "자사 발행·조달, 예수부채, 신탁계정 또는 지급어음 관련 공시"
        else:
            status = "보유금액 공시 없음"
            reason = "상품 설명·미발행어음·업황 설명만 있고 현재 보유금액이 없음"
        excluded.append({
            "corp_name": company,
            "corp_code": filing["corp_code"],
            "report_period": period_from_report(filing["report_nm"]),
            "report_nm": filing["report_nm"],
            "rcept_no": filing["rcept_no"],
            "status": status,
            "reason": reason,
            "expression": expression[:800],
            "dart_url": dart_url(filing["rcept_no"]),
        })

    audit = {
        "latest_filings": len(filings),
        "holding_companies": len(company_rows),
        "holding_details": len(enriched_details),
        "excluded_companies": len(excluded),
        "unclassified_companies": sorted(
            set(filings) - holding_names - {row["corp_name"] for row in excluded}
        ),
        "simple_total_won": sum(
            row["amount_won"] for row in company_rows if row["amount_won"] is not None
        ),
    }
    OUTPUT.write_text(json.dumps({
        "audit": audit,
        "company_rows": company_rows,
        "detail_rows": enriched_details,
        "excluded_rows": excluded,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
