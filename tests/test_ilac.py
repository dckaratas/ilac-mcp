from ilac_mcp import db
from ilac_mcp.normalize import dosage_form, fold, strength, to_iso_date
from ilac_mcp.parsers import parse_erecete, parse_ruhsatli
from ilac_mcp.sources import latest_attachment


def test_fold_turkish():
    assert fold("MİKAFUNGUS  50 MG I.V. INFüZYONLUK") == "mikafungus 50 mg i.v. infuzyonluk"
    assert fold("İlaç") == fold("ILAÇ") == fold("ilac") == "ilac"
    assert fold("Şurup Ğ Ö") == "surup g o"


def test_dates():
    assert to_iso_date(22190) == "1960-10-01"
    assert to_iso_date("12.08.2022") == "2022-08-12"
    assert to_iso_date("23/10/2026") == "2026-10-23"
    assert to_iso_date("") is None


def test_strength():
    assert strength("ONADRON 0.75 MG TABLET, 100 TABLET") == "0.75 mg"
    assert strength("VERMİDON 500/30 MG TABLET, 20 TABLET") == "500/30 mg"
    assert strength("GALVIKS 1000 MG + 200 MG/10 ML ORAL") == "1000 mg"
    assert strength("% 0,4 LIDODEKS %5 DEKSTROZ") is None  # yüzde öne yazılmış; doz çıkarılamaz
    # konsantrasyon dozun parçası: şurup ile tablet aynı sayılmamalı
    assert strength("PAROL 250 MG/5 ML 150 ML PLUS SUSPANSIYON") == "250 mg/5 ml"
    assert strength("DEKORT 4 MG/ML ENJEKSİYONLUK ÇÖZELTİ") == "4 mg/ml"
    assert strength("AKLAV BID 200 MG/28,5 MG PEDİYATRİK") == "200 mg/28.5 mg"  # kombinasyon


def test_dosage_form():
    assert dosage_form("ARVELES 25 MG FİLM KAPLI TABLET, 20 ADET") == "tablet"
    assert dosage_form("A-FERİN 120 MG/5 ML PEDİATRİK ŞURUP") == "sivi oral"
    assert dosage_form("ARVELES 50 MG/2 ML IM/IV ENJEKSİYONLUK ÇÖZELTİ, 6 AMPUL") == "parenteral"
    assert dosage_form("MAJEZİK 100 MG EFERVESAN TABLET") == "efervesan"
    assert dosage_form("BİLİNMEYEN ÜRÜN") is None


def test_parse_ruhsatli(ruhsatli_xlsx):
    recs = parse_ruhsatli(ruhsatli_xlsx)
    assert len(recs) == 5
    first = recs[0]
    assert first["barkod"] == "8699508010752"
    assert first["etkin_madde"] == "dekzametazon"
    assert first["ruhsat_tarihi"] == "1960-10-01"
    assert first["askida_durum"] is None
    assert recs[2]["atc"] == "H02AB02"  # sondaki boşluk temizlenir
    assert recs[2]["askida_durum"] == "Farmakovijilans gerekçeli askıda"


def test_parse_erecete(erecete_xlsx):
    data = parse_erecete(erecete_xlsx)
    assert len(data["aktif"]) == 4
    assert len(data["pasif"]) == 1  # "PASİFE ALINACAK" sayfası karışmaz
    assert data["aktif"][0]["barkod"] == "8699508010134"
    assert data["aktif"][0]["temel_ilac"] is True
    assert data["aktif"][0]["liste_tarihi"] == "2026-10-20"
    assert len(data["yeni"]) == 1


def test_merge_and_search(conn):
    assert db.meta(conn)["urun_sayisi"] == "6"
    # Türkçe karakter ve büyük/küçük harf duyarsız
    names = [r["ad"] for r in db.search(conn, "vermidon")]
    assert names == ["VERMİDON 500/30 MG TABLET, 20 TABLET"]
    # aktif ürünler önce, pasifler sonda
    res = db.search(conn, "onadron")
    assert [r["durum"] for r in res] == ["aktif", "pasif"]
    assert db.search(conn, "onadron", sadece_aktif=True)[0]["barkod"] == "8699508010134"
    # etkin madde, barkod, ATC
    assert len(db.search(conn, "dekzametazon")) == 4
    assert db.search(conn, "8699000000035")[0]["atc"] == "N02BE51"
    assert {r["barkod"] for r in db.search(conn, "c10aa")} == {"8699000000042"}
    # kısa terim LIKE yoluna düşer
    assert db.search(conn, "mg 4")


def test_detail_merges_sources(conn):
    u = db.get(conn, "8699508010134")
    assert u["ruhsat_no"] == "55/44"  # ruhsatlı listeden
    assert u["durum"] == "aktif" and u["recete_turu"] == "Normal"  # e-reçeteden
    assert u["temel_ilac"] is True
    only_erecete = db.get(conn, "8699000000042")
    assert only_erecete["ruhsatli"] is False and "etkin_madde" not in only_erecete  # boş alanlar çıktıya konmaz


def test_equivalents(conn):
    res = db.equivalents(conn, "8699508010134")
    assert [e["barkod"] for e in res["esdegerler"]] == ["8699000000011"]  # aynı doz, aktif
    assert [e["barkod"] for e in res["farkli_doz"]] == ["8699000000028"]
    res_all = db.equivalents(conn, "8699508010134", sadece_aktif=False)
    assert "8699508010752" in [e["barkod"] for e in res_all["esdegerler"]]
    assert db.equivalents(conn, "0000000000000") is None


def test_changes(conn):
    ch = db.changes(conn)
    assert ch[0]["tur"] == "yeni" and ch[0]["barkod"] == "8699000000042"


def test_latest_attachment():
    html = """
    <table><tbody>
    <tr><td><div class="cell">Ruhsatlı Liste</div></td><td><i></i>16/10/2026</td>
        <td><a href="https://titck.gov.tr/storage/Archive/2026/a_16.xlsx">XLSX</a></td></tr>
    <tr><td><div class="cell">Ruhsatlı Liste</div></td><td><i></i>23/10/2026</td>
        <td><a href="https://titck.gov.tr/storage/Archive/2026/a 23.xlsx">XLSX</a></td></tr>
    </tbody></table>"""
    att = latest_attachment(html)
    assert att.date == "2026-10-23"
    assert att.url.endswith("a%2023.xlsx")
