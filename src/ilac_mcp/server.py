"""MCP sunucusu: TİTCK ilaç listeleri üzerinde arama araçları."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import db
from .sync import sync

UYARI = (
    "Bu bilgi TİTCK'nın kamuya açık listelerinden derlenmiştir ve tıbbi tavsiye değildir. "
    "İlaç kullanımı ve değişikliği için hekim veya eczacıya danışın."
)

INSTRUCTIONS = """\
Türkiye'de ruhsatlı beşeri ilaçlar için TİTCK verisi: barkod, etkin madde, ATC kodu,
ruhsat ve askı durumu, e-reçete aktif/pasif durumu, reçete türü ve temel ilaç listeleri.
Eşdeğer önerileri aynı ATC kodu ve ürün adındaki doz bilgisine dayanır; farmasötik form
(tablet, şurup vb.) ayrıca kontrol edilmelidir. Yanıtlarda kaynak ve liste tarihini belirtin.
"""

server = MCPServer("ilac-mcp", title="Türkiye İlaç Verisi (TİTCK)", instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def _conn():
    if not db.db_path().exists():
        sync()
    return db.session()


def _kaynak(conn) -> dict[str, Any]:
    m = db.meta(conn)
    return {
        "ruhsatli_liste_tarihi": m.get("ruhsatli_liste_tarihi"),
        "erecete_liste_tarihi": m.get("erecete_liste_tarihi"),
        "kaynak": "TİTCK (titck.gov.tr)",
        "uyari": UYARI,
    }


@server.tool(annotations=READ_ONLY)
def ilac_ara(sorgu: str, limit: int = 20, sadece_aktif: bool = False) -> dict[str, Any]:
    """İlaç arar. Sorgu ürün adı, etkin madde, barkod (8-14 hane) ya da ATC kodu (ör. N02BE01) olabilir.

    Türkçe karakterler ve büyük/küçük harf fark etmez. Aktif ürünler önce listelenir.
    """
    with _conn() as conn:
        sonuclar = db.search(conn, sorgu, limit=max(1, min(limit, 100)), sadece_aktif=sadece_aktif)
        return {"sonuclar": sonuclar, "adet": len(sonuclar), **_kaynak(conn)}


@server.tool(annotations=READ_ONLY)
def ilac_detay(barkod: str) -> dict[str, Any]:
    """Barkodla tek bir ilacın tüm bilgilerini getirir: ruhsat, askı durumu, reçete türü, temel ilaç listeleri."""
    with _conn() as conn:
        urun = db.get(conn, barkod)
        if not urun:
            return {"hata": f"{barkod} barkodlu ürün bulunamadı. Önce ilac_ara ile arayın.", **_kaynak(conn)}
        return {"urun": urun, **_kaynak(conn)}


@server.tool(annotations=READ_ONLY)
def esdeger_bul(barkod: str, sadece_aktif: bool = True) -> dict[str, Any]:
    """Bir ilacın eşdeğerlerini bulur: aynı ATC kodu ve aynı doz.

    "farkli_doz" aynı etkin maddenin başka dozlarını içerir. Farmasötik form ve
    SGK geri ödeme durumu ayrıca kontrol edilmelidir.
    """
    with _conn() as conn:
        sonuc = db.equivalents(conn, barkod, sadece_aktif=sadece_aktif)
        if sonuc is None:
            return {"hata": f"{barkod} barkodlu ürün bulunamadı.", **_kaynak(conn)}
        return {**sonuc, **_kaynak(conn)}


@server.tool(annotations=READ_ONLY)
def haftalik_degisiklikler() -> dict[str, Any]:
    """Son e-reçete listesinde yeni eklenen ve değişiklik yapılan ürünleri listeler."""
    with _conn() as conn:
        return {"degisiklikler": db.changes(conn), **_kaynak(conn)}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=True))
def veri_guncelle() -> dict[str, Any]:
    """TİTCK'dan en güncel listeleri indirip yerel veritabanını yeniden kurar (yaklaşık 4 MB indirme)."""
    stats = sync()
    with db.session() as conn:
        return {"istatistik": stats, **_kaynak(conn)}


@server.tool(annotations=READ_ONLY)
def veri_durumu() -> dict[str, Any]:
    """Yerel verinin hangi tarihli TİTCK listelerinden kurulduğunu gösterir."""
    if not db.db_path().exists():
        return {"durum": "Veri henüz indirilmedi. veri_guncelle aracını çalıştırın.", "konum": str(db.db_path())}
    with db.session() as conn:
        return {"meta": db.meta(conn), "konum": str(db.db_path())}
