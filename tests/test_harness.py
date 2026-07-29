import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from note_finder.extract import extract_document
from note_finder.pipeline import deduplicate, write_excel


class HarnessTests(unittest.TestCase):
    def test_classifies_explicit_and_aggregate_without_dropping(self):
        html = """<table><tr><td>NH투자증권</td><td>발행어음</td><td>11,200 천원</td></tr>
        <tr><td>기타금융상품(중금채, 발행어음 등)</td><td>35,960,207 천원</td></tr></table>"""
        rows = extract_document("sample.xml", html.encode())
        self.assertEqual([row.classification for row in rows], ["A", "B"])
        self.assertEqual(rows[0].amount_thousand_won, 11200)

    def test_keeps_latest_correction_and_logs_old_receipt(self):
        filings = [{"corp_code": "1", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260301", "rcept_no": "old"},
                   {"corp_code": "1", "report_nm": "[기재정정] 사업보고서 (2025.12)", "rcept_dt": "20260401", "rcept_no": "new"}]
        kept, log = deduplicate(filings)
        self.assertEqual(kept[0]["rcept_no"], "new")
        self.assertEqual(log[0]["dropped"], "old")

    def test_writes_auditable_workbook(self):
        row = dict.fromkeys(__import__("note_finder.pipeline", fromlist=["FIELDS"]).FIELDS, "")
        row.update(classification="A", context="NH투자증권 발행어음 11,200천원")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.xlsx"
            write_excel(path, [row], [])
            wb = load_workbook(path)
            self.assertEqual(wb.sheetnames, ["confirmed", "needs_review", "excluded", "dedup_log"])
            self.assertEqual(wb["confirmed"].max_row, 2)


if __name__ == "__main__":
    unittest.main()
