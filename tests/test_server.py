import asyncio
import shutil

from mcp import Client

from ilac_mcp import db


def _call(name: str, args: dict | None = None):
    from ilac_mcp.server import server

    async def run():
        async with Client(server, raise_exceptions=True) as client:
            tools = await client.list_tools()
            result = await client.call_tool(name, args or {})
            return {t.name for t in tools.tools}, result

    return asyncio.run(run())


def test_tools_over_mcp(conn, tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(tmp_path / "ilac.db", data / "ilac.db")
    monkeypatch.setenv("ILAC_MCP_DATA_DIR", str(data))
    assert db.db_path() == data / "ilac.db"

    names, result = _call("ilac_ara", {"sorgu": "onadron", "sadece_aktif": True})
    assert {"ilac_ara", "ilac_detay", "esdeger_bul", "haftalik_degisiklikler", "veri_guncelle", "veri_durumu"} <= names
    out = result.structured_content
    assert out["adet"] == 1 and out["sonuclar"][0]["barkod"] == "8699508010134"
    assert out["ruhsatli_liste_tarihi"] == "2026-10-23"
    assert "tıbbi tavsiye değildir" in out["uyari"]

    _, result = _call("esdeger_bul", {"barkod": "8699508010134"})
    assert [e["barkod"] for e in result.structured_content["esdegerler"]] == ["8699000000011"]

    _, result = _call("ilac_detay", {"barkod": "123"})
    assert "bulunamadı" in result.structured_content["hata"]
