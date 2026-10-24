"""TİTCK sayfalarından güncel liste dosyalarını bulup indirme."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx2 as httpx

from .normalize import to_iso_date

BASE = "https://www.titck.gov.tr"
RUHSATLI_PAGE = f"{BASE}/dinamikmodul/85"
ERECETE_PAGE = f"{BASE}/dinamikmodul/43"

USER_AGENT = "ilac-mcp (+https://github.com/dckaratas/ilac-mcp)"
_ROW = re.compile(r"<tr\b.*?</tr>", re.DOTALL | re.IGNORECASE)
_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_XLSX = re.compile(r'href="([^"]+\.xlsx)"', re.IGNORECASE)


@dataclass(frozen=True)
class Attachment:
    url: str
    date: str  # ISO


def latest_attachment(html: str) -> Attachment:
    """Dinamik modül sayfasındaki en yeni tarihli XLSX bağlantısını döner."""
    found: list[Attachment] = []
    for row in _ROW.findall(html):
        link, when = _XLSX.search(row), _DATE.search(row)
        if link and when and (iso := to_iso_date(when.group(1))):
            found.append(Attachment(url=link.group(1).replace(" ", "%20"), date=iso))
    if not found:
        raise RuntimeError("Sayfada XLSX bağlantısı bulunamadı; TİTCK sayfa yapısı değişmiş olabilir.")
    return max(found, key=lambda a: a.date)


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60)


def _get(client: httpx.Client, url: str, attempts: int = 4) -> httpx.Response:
    # TİTCK sunucusu art arda isteklerde bağlantıyı sıfırlayabiliyor; artan beklemeyle yeniden dene.
    for i in range(attempts):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError):
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))
    raise AssertionError("unreachable")


def fetch_latest(page_url: str, dest_dir: Path) -> tuple[Path, Attachment]:
    """Sayfadaki en güncel dosyayı dest_dir altına indirir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        att = latest_attachment(_get(client, page_url).text)
        time.sleep(1)
        data = _get(client, att.url).content
    path = dest_dir / f"{page_url.rsplit('/', 1)[-1]}_{att.date}.xlsx"
    path.write_bytes(data)
    return path, att
