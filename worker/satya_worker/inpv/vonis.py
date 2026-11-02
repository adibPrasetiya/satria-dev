"""Observasi respons → kategori vonis (deterministik). Isi respons tak disimpan — hanya fitur ringkas.

Kategori:
  ditolak_tepat        400/422 (atau 4xx validasi) dan galat menyebut field uji / tanpa field spesifik
  payload_belum_valid  400/422 yang menyebut field LAIN → bukan bukti validasi field uji
  diterima             2xx atas input tak valid (diproses/diabaikan → dinilai lanjut, lihat `ambigu`)
  crash                5xx atau stack trace bocor
  indikasi_sqli        signature galat basis data pada respons
  indikasi_ssti        ekspresi template dievaluasi (penanda 49)
  refleksi             penanda XSS terpantul MENTAH (tanpa encoding) di respons HTML/teks
  terblokir_auth       401/403 → lapisan validasi tak tercapai
  tidak_ditemukan      404 (wajar untuk ID fiktif/tak valid; netral)
  lain                 status lain (405/409/429/3xx …)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

_SQL = re.compile(
    r"(SQL syntax|mysql_|MySqlException|SQLSTATE\[|ORA-\d{5}|PG::|psycopg2|pg_query|SQLite|sqlite3\.|"
    r"unterminated quoted string|syntax error at or near|Microsoft OLE DB|ODBC SQL|SequelizeDatabaseError|"
    r"QueryFailedError|PrismaClientKnownRequestError|ER_PARSE_ERROR|ER_BAD_FIELD_ERROR)",
    re.IGNORECASE,
)
_TRACE = re.compile(
    r"(Traceback \(most recent call last\)|at [\w$.]+\([\w./\\-]+:\d+:\d+\)|node_modules[/\\]|"
    r"Exception in thread|java\.lang\.|System\.\w+Exception|Stack trace:|\bfatal error\b|Whoops!)",
    re.IGNORECASE,
)
_HTML = re.compile(r"text/html|text/plain|application/xhtml", re.IGNORECASE)


@dataclass
class Observasi:
    endpoint: str
    field: str            # nama field ('{id}' untuk segmen path, '?' untuk parameter tak dikenal)
    lokasi: str           # body | query | path
    jenis: str            # jenis varian
    kelompok: str
    status: Optional[int]
    kategori: str
    content_type: str = ""
    panjang: int = 0
    beda_baseline: Optional[float] = None   # selisih panjang relatif terhadap baseline (0 = sama)
    status_baseline: Optional[int] = None
    disebut: list[str] = field(default_factory=list)
    catatan: str = ""
    bukti_idx: int = -1   # indeks bukti request di klien (untuk lampiran temuan)
    ai: str = ""          # penilaian AI atas kasus ambigu: diproses|disanitasi|diabaikan|tak_pasti
    asal_form: bool = False

    @property
    def ringkas(self) -> str:
        return f"{self.endpoint} [{self.lokasi}:{self.field}·{self.jenis}] → {self.status if self.status is not None else 'galat'}"


def nilai(resp: Any, *, field_uji: str, disebut: set[str], penanda: str, jenis: str) -> tuple[str, str]:
    """Return (kategori, catatan) untuk satu respons varian."""
    sc = resp.status_code
    teks = resp.text[:200_000] if resp is not None else ""
    ct = resp.headers.get("content-type", "")
    if _SQL.search(teks):
        return "indikasi_sqli", "signature galat basis data"
    if jenis == "ssti" and penanda and penanda in teks:
        return "indikasi_ssti", "ekspresi template dievaluasi (7*7=49)"
    if jenis == "xss" and penanda and penanda in teks and (_HTML.search(ct) or "<" in teks[:50]):
        return "refleksi", "penanda terpantul tanpa encoding"
    if 500 <= sc < 600:
        return "crash", f"HTTP {sc}" + (" + stack trace" if _TRACE.search(teks) else "")
    if _TRACE.search(teks):
        return "crash", "stack trace bocor pada respons"
    if sc in (401, 403):
        return "terblokir_auth", ""
    if sc == 404:
        return "tidak_ditemukan", ""
    if sc in (400, 413, 415, 422) or (sc == 409 and field_uji in disebut):
        if disebut and field_uji not in disebut:
            return "payload_belum_valid", "galat menunjuk field: " + ", ".join(sorted(disebut))
        return "ditolak_tepat", "galat menunjuk field uji" if field_uji in disebut else ""
    if 200 <= sc < 300:
        return "diterima", ""
    return "lain", f"HTTP {sc}"


def selisih(panjang: int, dasar: Optional[int]) -> Optional[float]:
    if dasar is None:
        return None
    return round(abs(panjang - dasar) / max(dasar, 1), 3)


def diterima_diproses(o: Observasi, metode_http: str) -> Optional[bool]:
    """Apakah input tak valid yang diterima (2xx) benar-benar DIPROSES?
    True = diproses (gagal validasi); False = diabaikan/disanitasi; None = tak pasti.

    AI (bila menilai) menang. Tanpa AI: mutasi (POST/PUT/PATCH) 2xx/201 → diproses;
    GET dengan respons identik baseline → filter diabaikan (tak pasti, bukan gagal)."""
    if o.kategori != "diterima":
        return False
    if o.ai in ("diproses",):
        return True
    if o.ai in ("disanitasi", "diabaikan"):
        return False
    if o.ai == "tak_pasti":
        return None
    if metode_http.upper() in ("POST", "PUT", "PATCH"):
        return True
    if o.beda_baseline is not None and o.beda_baseline < 0.02 and o.status == o.status_baseline:
        return None
    return None
