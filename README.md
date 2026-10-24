# ilac-mcp

Türkiye'de ruhsatlı beşeri ilaçlar için [TİTCK](https://www.titck.gov.tr) verisini yapay zekâ asistanlarına
açan bir [Model Context Protocol](https://modelcontextprotocol.io) sunucusu.

*An MCP server exposing Turkish Medicines and Medical Devices Agency (TİTCK) drug lists: search,
generic equivalents, licence and e-prescription status.*

> ⚠️ **Tıbbi tavsiye değildir.** Veriler TİTCK'nın kamuya açık listelerinden derlenir. İlaç kullanımı
> veya değişikliği için hekim ya da eczacıya danışın.

## Neler yapabilir?

| Araç | Açıklama |
|---|---|
| `ilac_ara` | Ürün adı, etkin madde, barkod ya da ATC koduyla arama. Türkçe karakter ve büyük/küçük harf fark etmez. |
| `ilac_detay` | Barkodla tek ürün: ruhsat no/tarihi, askı durumu, reçete türü, temel ilaç listeleri. |
| `esdeger_bul` | Aynı ATC kodu, aynı doz ve aynı form grubundaki ürünler; diğer doz/formlar ayrıca listelenir. |
| `haftalik_degisiklikler` | Son e-reçete listesinde yeni eklenen ve değişen ürünler. |
| `veri_guncelle` | TİTCK'dan güncel listeleri indirip yerel veritabanını yeniden kurar. |
| `veri_durumu` | Yerel verinin hangi tarihli listelerden kurulduğu. |

Örnek sorular: *"Parol 500 mg tabletin eşdeğerleri neler?"*, *"8699522095650 barkodlu ilaç e-reçetede aktif mi?"*,
*"Bu hafta e-reçete listesine hangi ilaçlar eklendi?"*

## Kurulum

[uv](https://docs.astral.sh/uv/) gerekir.

```bash
git clone https://github.com/dckaratas/ilac-mcp
cd ilac-mcp
uv run ilac-mcp sync    # TİTCK listelerini indirir (~4 MB, ~20 sn)
```

### Claude Desktop / Cursor / VS Code

İstemcinin MCP yapılandırmasına ekleyin (yolu kendi klasörünüzle değiştirin):

```json
{
  "mcpServers": {
    "ilac": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\Dev\\mcp\\ilac-mcp", "ilac-mcp"]
    }
  }
}
```

İlk çağrıda veri yoksa sunucu listeleri kendisi indirir.

### Komut satırı

```bash
uv run ilac-mcp ara "majezik"
uv run ilac-mcp sync
```

## Veri kaynakları

| Liste | Güncellenme | Kullanılan alanlar |
|---|---|---|
| [Ruhsatlı Beşeri Tıbbi Ürünler Listesi](https://www.titck.gov.tr/dinamikmodul/85) | Haftalık (cuma) | Barkod, ürün adı, etkin madde, ATC, ruhsat sahibi/no/tarihi, askı durumu |
| [SKRS E-Reçete İlaç Listesi](https://www.titck.gov.tr/dinamikmodul/43) | Haftalık (salı) | Aktif/pasif, reçete türü, ATC adı, temel ilaç listeleri, haftalık değişiklikler |

İki liste barkod üzerinden birleştirilir. Veri yerelde saklanır (Windows: `%LOCALAPPDATA%\ilac-mcp`);
konumu `ILAC_MCP_DATA_DIR` ortam değişkeniyle değiştirilebilir.

### Veri ve lisans

Bu repo **yalnızca kodu** içerir ve MIT lisanslıdır. TİTCK verisi repoda dağıtılmaz; her kullanıcının
makinesinde doğrudan titck.gov.tr'den indirilir. Yanıtlar kaynak ve liste tarihini içerir.

## Bilinen sınırlar

- **Eşdeğerlik sezgiseldir.** Doz ve form ürün adından çıkarılır; ürünlerin ~%28'inde doz, ~%19'unda form
  tespit edilemiyor. Bu ürünler `farkli_doz` altında görünür.
- **Fiyat yok.** TİTCK'nın güncel fiyat listesi giriş gerektiriyor; kamuya açık referans fiyat listesi
  düzensiz yayımlanıyor.
- **Prospektüs (KT/KÜB) henüz yok.** Yol haritasında.

## Yol haritası

- [ ] KT/KÜB metinlerinden bölüm getirme (endikasyon, doz, yan etki, uyarılar)
- [ ] Referans fiyat listesi ve fiyat geçmişi
- [ ] Ruhsat iptal listesi ve geri çekme duyuruları
- [ ] PyPI yayını (`uvx ilac-mcp`)

## Geliştirme

```bash
uv run pytest
git config core.hooksPath .githooks   # her commit öncesi testleri çalıştırır (bir kez)
```

Testler gerçek TİTCK dosyalarının başlık ve sayfa yapısını taklit eden küçük örnek dosyalar kullanır.
