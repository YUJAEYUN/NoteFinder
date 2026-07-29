from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from .dart import DartClient, DartError
from .extract import extract_document

FIELDS = ["rcept_dt", "rcept_no", "corp_name", "corp_code", "report_nm", "source_file",
          "context", "broker", "raw_amount", "raw_unit", "amount_thousand_won",
          "classification", "reason"]


def deduplicate(filings: list[dict]) -> tuple[list[dict], list[dict]]:
    kept, removed = {}, []
    for filing in sorted(filings, key=lambda x: (x.get("rcept_dt", ""), x["rcept_no"])):
        report = filing.get("report_nm", "").replace("[기재정정]", "").strip()
        key = (filing.get("corp_code") or filing.get("corp_name"), report)
        if key in kept:
            removed.append({"dropped": kept[key]["rcept_no"], "kept": filing["rcept_no"], "key": str(key)})
        kept[key] = filing
    return list(kept.values()), removed


def correction_fallbacks(filings: list[dict]) -> dict[str, list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for filing in sorted(filings, key=lambda x: (x.get("rcept_dt", ""), x["rcept_no"])):
        report = filing.get("report_nm", "").replace("[기재정정]", "").strip()
        key = (filing.get("corp_code") or filing.get("corp_name"), report)
        groups.setdefault(key, []).append(filing)
    return {
        group[-1]["rcept_no"]: list(reversed(group[:-1]))
        for group in groups.values()
        if len(group) > 1
    }


def run(client: DartClient, begin: str, end: str, output: Path, keyword: str = "발행어음",
        candidate_filings: list[dict] | None = None) -> dict:
    raw = candidate_filings if candidate_filings is not None else list(client.iter_filings(begin, end))
    filings, dedup_log = deduplicate(raw)
    fallbacks = correction_fallbacks(raw)
    rows, document_errors, correction_fallback_log = [], [], []
    for filing in filings:
        selected, documents = filing, None
        for choice in [filing, *fallbacks.get(filing["rcept_no"], [])]:
            try:
                documents = client.document(choice["rcept_no"])
                selected = choice
                if choice is not filing:
                    correction_fallback_log.append({
                        "unavailable": filing["rcept_no"],
                        "used": choice["rcept_no"],
                    })
                break
            except DartError as exc:
                document_errors.append({"rcept_no": choice["rcept_no"], "error": str(exc)})
        if documents is None:
            continue
        for name, body in documents:
            for evidence in extract_document(name, body, keyword):
                rows.append({**{k: selected.get(k, "") for k in FIELDS[:5]}, **evidence.dict()})
    write_excel(output, rows, dedup_log)
    audit = output.with_suffix(".audit.json")
    audit.write_text(json.dumps({"query": {"begin": begin, "end": end, "keyword": keyword,
                                           "source": "candidate_file" if candidate_filings is not None else "opendart_list"},
                                 "filings_seen": len(raw), "filings_scanned": len(filings),
                                 "evidence_rows": len(rows), "dedup_log": dedup_log,
                                 "document_errors": document_errors,
                                 "correction_fallback_log": correction_fallback_log},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return {"filings": len(filings), "rows": len(rows), "document_errors": len(document_errors),
            "output": str(output), "audit": str(audit)}


def write_excel(path: Path, rows: list[dict], dedup_log: list[dict]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    groups = {"confirmed": "A", "needs_review": None, "excluded": "EXCLUDED"}
    for sheet_name, classification in groups.items():
        ws = wb.create_sheet(sheet_name)
        ws.append(FIELDS)
        selected = [r for r in rows if (r["classification"] == classification if classification else r["classification"] in {"B", "REVIEW"})]
        for row in selected:
            ws.append([row.get(field) for field in FIELDS])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    ws = wb.create_sheet("dedup_log")
    ws.append(["dropped", "kept", "key"])
    for row in dedup_log:
        ws.append([row["dropped"], row["kept"], row["key"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
