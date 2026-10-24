# ilac-mcp

TİTCK ilaç listelerini MCP üzerinden sunan Python paketi (mcp SDK 2.x `MCPServer`, uv).

## Komutlar

- Test: `uv run pytest -q`
- Canlı veriyle deneme: `uv run ilac-mcp sync` ve `uv run ilac-mcp ara "<sorgu>"`
- Pre-commit kancası: `git config core.hooksPath .githooks` (testler geçmezse commit durur; `--no-verify` kullanma)

## Çalışma kuralları

- `main` dalına doğrudan push yok. Her değişiklik ayrı dalda yapılır ve PR ile birleşir.
- Dal adı: `<tür>/<kisa-ad>`; PR başlığı: `<tür>: <kısa açıklama>` (Türkçe, küçük harfle başlar, nokta yok).
  Türler: `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, `chore`.
- PR açıklaması kısa: bir satır özet, ardından değişiklikler madde madde.
- TİTCK verisi (`*.xlsx`, `*.db`, PDF) repoya konmaz; testler sentetik örnek dosyalar kullanır.
