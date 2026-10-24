# ilac-mcp

TİTCK ilaç listelerini MCP üzerinden sunan Python paketi (mcp SDK 2.x `MCPServer`, uv).

## Komutlar

- Test: `uv run pytest -q`
- Canlı veriyle deneme: `uv run ilac-mcp sync` ve `uv run ilac-mcp ara "<sorgu>"`
- Pre-commit kancası: `git config core.hooksPath .githooks`. Sırasıyla yasaklı dosyaları (`.env`, anahtar
  dosyaları, `*.xlsx`/`*.db`/`*.pdf`), gitleaks ile secret'ları ve testleri kontrol eder; biri başarısızsa
  commit durur. `--no-verify` kullanma. Gerekli araçlar: `uv`, `gitleaks` (`~/.local/bin` altında).

## Çalışma kuralları

- `main` dalına doğrudan push yok. Her değişiklik ayrı dalda yapılır ve PR ile birleşir.
- Dal adı: `<tür>/<kisa-ad>`; PR başlığı: `<tür>: <kısa açıklama>` (Türkçe, küçük harfle başlar, nokta yok).
  Türler: `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, `chore`.
- PR açıklaması kısa: bir satır özet, ardından değişiklikler madde madde.
- `main` korumalı: 4 test işi (ubuntu/windows × py3.11/py3.13) ve `gitleaks` secret taraması geçmeli,
  çözülmemiş yorum kalmamalı.
  PR'lar yalnızca squash ile birleşir; squash commit başlığı PR başlığıdır, dal birleşince silinir.
- TİTCK verisi (`*.xlsx`, `*.db`, PDF) repoya konmaz; testler sentetik örnek dosyalar kullanır.
