from __future__ import annotations

import io
import json
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

BASE = "https://opendart.fss.or.kr/api"


class DartError(RuntimeError):
    pass


@dataclass
class DartClient:
    api_key: str
    cache_dir: Path
    delay: float = 0.15

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "NoteFinder/0.1"

    def list_filings(self, begin: str, end: str, page: int = 1) -> dict:
        response = self.session.get(
            f"{BASE}/list.json",
            params={"crtfc_key": self.api_key, "bgn_de": begin, "end_de": end,
                    "pblntf_ty": "A", "page_no": page, "page_count": 100}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {"000", "013"}:
            raise DartError(f"DART list error {payload.get('status')}: {payload.get('message')}")
        return payload

    def iter_filings(self, begin: str, end: str):
        page = 1
        while True:
            payload = self.list_filings(begin, end, page)
            yield from payload.get("list", [])
            if page >= int(payload.get("total_page", 0)):
                break
            page += 1
            time.sleep(self.delay)

    def document(self, rcept_no: str) -> list[tuple[str, bytes]]:
        target = self.cache_dir / f"{rcept_no}.zip"
        if not target.exists():
            response = self.session.get(f"{BASE}/document.xml", params={"crtfc_key": self.api_key,
                                        "rcept_no": rcept_no}, timeout=60)
            response.raise_for_status()
            target.write_bytes(response.content)
            time.sleep(self.delay)
        try:
            with zipfile.ZipFile(io.BytesIO(target.read_bytes())) as archive:
                return [(name, archive.read(name)) for name in archive.namelist()]
        except zipfile.BadZipFile as exc:
            try:
                detail = json.loads(target.read_text())
            except (UnicodeDecodeError, json.JSONDecodeError):
                text = target.read_text(encoding="utf-8", errors="replace")
                match = re.search(r"<message>(.*?)</message>", text)
                detail = {"message": match.group(1) if match else "invalid document response"}
            # Do not permanently cache an API error body under a .zip filename.
            # A corrected filing can become downloadable later, and the next run
            # should retry it or fall back to the previous correction.
            target.unlink(missing_ok=True)
            raise DartError(f"DART document error: {detail.get('message')}") from exc
