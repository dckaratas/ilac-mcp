"""TİTCK listelerini indirip yerel veritabanını yeniden kurma."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import db
from .parsers import parse_erecete, parse_ruhsatli
from .sources import ERECETE_PAGE, RUHSATLI_PAGE, fetch_latest


def build_from_files(ruhsatli_xlsx: Path, erecete_xlsx: Path, target: Path, meta: dict[str, str] | None = None) -> dict[str, int]:
    ruhsatli = parse_ruhsatli(ruhsatli_xlsx)
    erecete = parse_erecete(erecete_xlsx)
    urunler = db.merge(ruhsatli, erecete)
    info = {
        "urun_sayisi": str(len(urunler)),
        "guncelleme_zamani": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **(meta or {}),
    }
    db.build(target, urunler, erecete, info)
    return {
        "urun": len(urunler),
        "ruhsatli": len(ruhsatli),
        "erecete_aktif": len(erecete["aktif"]),
        "erecete_pasif": len(erecete["pasif"]),
    }


def sync(target: Path | None = None) -> dict[str, int]:
    target = target or db.db_path()
    downloads = target.parent / "downloads"
    ruhsatli_path, ruhsatli_att = fetch_latest(RUHSATLI_PAGE, downloads)
    erecete_path, erecete_att = fetch_latest(ERECETE_PAGE, downloads)
    stats = build_from_files(
        ruhsatli_path,
        erecete_path,
        target,
        {
            "ruhsatli_liste_tarihi": ruhsatli_att.date,
            "ruhsatli_kaynak": ruhsatli_att.url,
            "erecete_liste_tarihi": erecete_att.date,
            "erecete_kaynak": erecete_att.url,
        },
    )
    for old in downloads.glob("*.xlsx"):
        if old not in (ruhsatli_path, erecete_path):
            old.unlink(missing_ok=True)
    return stats
