"""Yerel SQLite veritabanı: şema, yükleme ve sorgular."""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from .normalize import dosage_form, fold, strength
from .parsers import Record

SCHEMA = """
CREATE TABLE urun (
    barkod TEXT PRIMARY KEY,
    ad TEXT NOT NULL,
    etkin_madde TEXT,
    atc TEXT,
    atc_adi TEXT,
    firma TEXT,
    recete_turu TEXT,
    durum TEXT,
    temel_ilac INTEGER,
    cocuk_temel_ilac INTEGER,
    yenidogan_temel_ilac INTEGER,
    ruhsat_no TEXT,
    ruhsat_tarihi TEXT,
    askida_durum TEXT,
    askiya_alinma_tarihi TEXT,
    degisiklik_tarihi TEXT,
    ruhsatli INTEGER NOT NULL DEFAULT 0,
    doz TEXT,
    form TEXT,
    ad_fold TEXT NOT NULL,
    etkin_fold TEXT
);
CREATE INDEX urun_atc ON urun(atc);
CREATE INDEX urun_etkin ON urun(etkin_fold);
CREATE VIRTUAL TABLE urun_fts USING fts5(
    ad_fold, etkin_fold, barkod UNINDEXED, tokenize = 'trigram'
);
CREATE TABLE degisiklik (
    barkod TEXT, ad TEXT, tur TEXT, aciklama TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

COLUMNS = [
    "barkod", "ad", "etkin_madde", "atc", "atc_adi", "firma", "recete_turu", "durum",
    "temel_ilac", "cocuk_temel_ilac", "yenidogan_temel_ilac", "ruhsat_no", "ruhsat_tarihi",
    "askida_durum", "askiya_alinma_tarihi", "degisiklik_tarihi", "ruhsatli", "doz", "form",
    "ad_fold", "etkin_fold",
]


def data_dir() -> Path:
    return Path(os.environ.get("ILAC_MCP_DATA_DIR") or user_data_dir("ilac-mcp", appauthor=False))


def db_path() -> Path:
    return data_dir() / "ilac.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Bağlantıyı açıp iş bitince kapatır.

    sqlite3.Connection'ın kendi `with` bloğu yalnızca transaction'ı yönetir,
    bağlantıyı kapatmaz; Windows'ta açık kalan bağlantı veritabanı dosyasının
    sync sırasında değiştirilmesini engeller.
    """
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def merge(ruhsatli: Iterable[Record], erecete: dict[str, list[Record]]) -> dict[str, Record]:
    """İki listeyi barkod üzerinden birleştirir.

    Ruhsat bilgisi ruhsatlı listeden; durum, reçete türü ve ATC adı e-reçete
    listesinden gelir. Sadece e-reçetede olan ürünler (ör. ruhsatı iptal
    edilmiş pasifler) de korunur.
    """
    urunler: dict[str, Record] = {}
    for rec in ruhsatli:
        urunler[rec["barkod"]] = {
            "barkod": rec["barkod"],
            "ad": rec["ad"],
            "etkin_madde": rec.get("etkin_madde"),
            "atc": rec.get("atc"),
            "firma": rec.get("ruhsat_sahibi"),
            "ruhsat_no": rec.get("ruhsat_no"),
            "ruhsat_tarihi": rec.get("ruhsat_tarihi"),
            "askida_durum": rec.get("askida_durum"),
            "askiya_alinma_tarihi": rec.get("askiya_alinma_tarihi"),
            "degisiklik_tarihi": rec.get("degisiklik_tarihi"),
            "ruhsatli": 1,
        }
    for durum_key in ("pasif", "aktif"):  # aktif sonra yazılır, çakışmada kazanır
        for rec in erecete.get(durum_key, []):
            u = urunler.setdefault(rec["barkod"], {"barkod": rec["barkod"], "ad": rec["ad"], "ruhsatli": 0})
            u["durum"] = durum_key
            u["recete_turu"] = rec.get("recete_turu")
            u["atc_adi"] = rec.get("atc_adi")
            u["atc"] = u.get("atc") or (rec.get("atc") or "").upper() or None
            u["firma"] = u.get("firma") or rec.get("firma")
            for flag in ("temel_ilac", "cocuk_temel_ilac", "yenidogan_temel_ilac"):
                if flag in rec:
                    u[flag] = int(rec[flag])
    for u in urunler.values():
        u["doz"] = strength(u["ad"])
        u["form"] = dosage_form(u["ad"])
        u["ad_fold"] = fold(u["ad"])
        u["etkin_fold"] = fold(u.get("etkin_madde") or u.get("atc_adi")) or None
    return urunler


def build(path: Path, urunler: dict[str, Record], erecete: dict[str, list[Record]], meta: dict[str, str]) -> None:
    """Veritabanını geçici dosyada kurup atomik olarak yerine koyar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(SCHEMA)
        placeholders = ", ".join("?" for _ in COLUMNS)
        conn.executemany(
            f"INSERT INTO urun ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            ([u.get(c) for c in COLUMNS] for u in urunler.values()),
        )
        conn.execute("INSERT INTO urun_fts (ad_fold, etkin_fold, barkod) SELECT ad_fold, etkin_fold, barkod FROM urun")
        for tur in ("yeni", "degisen"):
            conn.executemany(
                "INSERT INTO degisiklik VALUES (?, ?, ?, ?)",
                ((r["barkod"], r["ad"], tur, r.get("aciklama")) for r in erecete.get(tur, [])),
            )
        conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, path)


# --- sorgular ---------------------------------------------------------------

_BARKOD = re.compile(r"^\d{8,14}$")
_ATC = re.compile(r"^[A-Za-z]\d{2}([A-Za-z]{1,2}(\d{1,2})?)?$")
_ORDER = "CASE durum WHEN 'aktif' THEN 0 WHEN 'pasif' THEN 2 ELSE 1 END, ad"


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    out = []
    for row in cur.fetchall():
        d = {k: row[k] for k in row.keys() if not k.endswith("_fold") and row[k] is not None}
        for flag in ("temel_ilac", "cocuk_temel_ilac", "yenidogan_temel_ilac", "ruhsatli"):
            if flag in d:
                d[flag] = bool(d[flag])
        out.append(d)
    return out


def search(conn: sqlite3.Connection, query: str, limit: int = 20, sadece_aktif: bool = False) -> list[dict[str, Any]]:
    q = query.strip()
    aktif = " AND durum = 'aktif'" if sadece_aktif else ""
    if _BARKOD.match(q):
        return _rows(conn.execute(f"SELECT * FROM urun WHERE barkod LIKE ?{aktif} ORDER BY {_ORDER} LIMIT ?", (q + "%", limit)))
    if _ATC.match(q):
        return _rows(conn.execute(f"SELECT * FROM urun WHERE atc LIKE ?{aktif} ORDER BY {_ORDER} LIMIT ?", (q.upper() + "%", limit)))
    terms = fold(q).split()
    if not terms:
        return []
    if all(len(t) >= 3 for t in terms):
        match = " AND ".join('"' + t.replace('"', "") + '"' for t in terms)
        sql = (
            f"SELECT u.* FROM urun u JOIN (SELECT DISTINCT barkod FROM urun_fts WHERE urun_fts MATCH ?) f "
            f"ON f.barkod = u.barkod WHERE 1=1{aktif} ORDER BY {_ORDER} LIMIT ?"
        )
        return _rows(conn.execute(sql, (match, limit)))
    like = " AND ".join("(ad_fold LIKE ? OR etkin_fold LIKE ?)" for _ in terms)
    params = [p for t in terms for p in (f"%{t}%", f"%{t}%")]
    return _rows(conn.execute(f"SELECT * FROM urun WHERE {like}{aktif} ORDER BY {_ORDER} LIMIT ?", (*params, limit)))


def get(conn: sqlite3.Connection, barkod: str) -> dict[str, Any] | None:
    rows = _rows(conn.execute("SELECT * FROM urun WHERE barkod = ?", (barkod.strip(),)))
    return rows[0] if rows else None


def equivalents(conn: sqlite3.Connection, barkod: str, sadece_aktif: bool = True, limit: int = 50) -> dict[str, Any] | None:
    """Eşdeğer adayları: aynı ATC kodu (5. seviye = aynı etkin madde/kombinasyon).

    "esdegerler" aynı doz ve aynı form grubundakileri, "farkli_doz" aynı etkin
    maddenin diğer doz ve formlarını içerir.
    """
    base = get(conn, barkod)
    if base is None:
        return None
    if not base.get("atc"):
        return {"urun": base, "esdegerler": [], "farkli_doz": []}
    aktif = " AND durum = 'aktif'" if sadece_aktif else ""
    query = f"SELECT * FROM urun WHERE atc = ? AND barkod != ?{aktif} AND {{}} ORDER BY {_ORDER} LIMIT ?"
    if base.get("doz"):
        cond, params = "doz IS ? AND form IS ?", (base["doz"], base.get("form"))
    else:
        cond, params = "0", ()
    args = (base["atc"], base["barkod"])
    same = _rows(conn.execute(query.format(cond), (*args, *params, limit)))
    other = _rows(conn.execute(query.format(f"NOT ({cond})"), (*args, *params, limit)))
    return {"urun": base, "esdegerler": same, "farkli_doz": other}


def changes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM degisiklik ORDER BY tur, ad")]


def meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
