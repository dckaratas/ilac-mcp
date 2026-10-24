"""Türkçe metin normalleştirme ve TİTCK dosyalarındaki değerleri temizleme."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

_ASCII = str.maketrans({"ı": "i", "ç": "c", "ğ": "g", "ö": "o", "ş": "s", "ü": "u"})
_NON_WORD = re.compile(r"[^0-9a-z%.,/+ ]+")
_SPACES = re.compile(r"\s+")


def fold(text: str | None) -> str:
    """Arama için katlanmış biçim: küçük harf, aksansız ASCII, tek boşluk.

    "İ" ve "I" ikisi de "i" olur; böylece "MİKAFUNGUS", "Mikafungus" ve
    OCR'dan gelen "MIKAFUNGUS" aynı anahtara düşer.
    """
    if not text:
        return ""
    s = str(text).replace("İ", "i").replace("I", "i").lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_ASCII)
    s = _NON_WORD.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


def clean(value: object) -> str | None:
    """Hücre değerini kırpılmış metne çevirir; boşsa None döner."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = _SPACES.sub(" ", str(value)).strip()
    return s or None


_EXCEL_EPOCH = date(1899, 12, 30)
_DMY = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")


def to_iso_date(value: object) -> str | None:
    """Excel seri numarası, datetime ya da gg.aa.yyyy metnini ISO tarihe çevirir."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        if 1 <= value < 100000:
            return (_EXCEL_EPOCH + timedelta(days=int(value))).isoformat()
        return None
    s = str(value).strip()
    if s.isdigit():
        return to_iso_date(int(s))
    m = _DMY.match(s)
    if m:
        d, mth, y = map(int, m.groups())
        try:
            return date(y, mth, d).isoformat()
        except ValueError:
            return None
    return None


_NUM = r"\d+(?:[.,]\d+)?"
_STRENGTH = re.compile(
    rf"({_NUM}(?:\s*/\s*{_NUM})*)\s*(mg|mcg|µg|g|iu|ui|%)(?:\s*/\s*({_NUM})?\s*(ml|mg|mcg|g|doz|saat))?\b",
    re.IGNORECASE,
)


_PACK_SEP = re.compile(r"(?<!\d),|,(?!\d)")


def _head(name: str) -> str:
    """Ambalaj bilgisinden önceki kısım; "28,5 MG" gibi ondalık virgüller ayırıcı sayılmaz."""
    return _PACK_SEP.split(name, 1)[0]


def _num(s: str) -> str:
    s = re.sub(r"\s+", "", s).replace(",", ".")
    return re.sub(r"(\.\d*?)0+\b", r"\1", s).replace("./", "/").rstrip(".")


def strength(name: str | None) -> str | None:
    """Ürün adından doz bilgisini çıkarır.

    "VERMIDON 500/30 MG TABLET" -> "500/30 mg", "PAROL 250 MG/5 ML SUSPANSIYON" -> "250 mg/5 ml".
    Ambalaj miktarı ("20 TABLET", "150 ML") genellikle virgülden sonra geldiği
    için yalnızca ilk virgülden önceki kısma bakılır.
    """
    if not name:
        return None
    head = _head(name)
    m = _STRENGTH.search(head)
    if not m:
        return None
    out = f"{_num(m.group(1))} {m.group(2).lower()}"
    if m.group(4):
        denom = f"{_num(m.group(3))} " if m.group(3) else ""
        out += f"/{denom}{m.group(4).lower()}"
    return out


# Kaba farmasötik form grupları; sıra önemli (önce özgül olanlar).
_FORMS = [
    ("efervesan", "efervesan"),
    ("agizda dagilan", "agizda dagilan"),
    ("tablet", "tablet"), ("draje", "tablet"),
    ("kapsul", "kapsul"),
    ("surup", "sivi oral"), ("suspansiyon", "sivi oral"), ("oral cozelti", "sivi oral"), ("oral damla", "sivi oral"),
    ("sase", "sase"), ("granul", "sase"), ("toz", "toz"),
    ("enjeksiyon", "parenteral"), ("infuzyon", "parenteral"), ("ampul", "parenteral"), ("flakon", "parenteral"),
    ("kalem", "parenteral"),
    ("goz damla", "goz"), ("goz merhem", "goz"), ("kulak", "kulak"),
    ("nazal", "nazal"), ("burun", "nazal"),
    ("inhal", "inhaler"), ("aerosol", "inhaler"),
    ("krem", "topikal"), ("pomad", "topikal"), ("merhem", "topikal"), ("jel", "topikal"), ("losyon", "topikal"),
    ("fitil", "rektal"), ("supozituar", "rektal"), ("ovul", "vajinal"), ("vajinal", "vajinal"),
    ("bant", "transdermal"), ("flaster", "transdermal"), ("transdermal", "transdermal"),
    ("sprey", "sprey"), ("damla", "damla"),
]


def dosage_form(name: str | None) -> str | None:
    """Ürün adından kaba form grubunu çıkarır: tablet, kapsul, sivi oral, parenteral..."""
    f = _head(fold(name))
    if not f:
        return None
    for needle, group in _FORMS:
        if needle in f:
            return group
    return None
