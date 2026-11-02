"""Varian tak valid per field sesuai profil validasinya.

Kelompok varian:
  validasi  tipe_salah, format, rentang, panjang, enum, kosong (field wajib)   → INPV-4.1/4.2/4.4
  injeksi   sqli (penanda kutip), ssti ({{7*7}}), xss (tag penanda unik), traversal → INPV-4.5–4.8
Penanda injeksi berupa string inert: tak menjalankan apa pun, hanya mengungkap error DB,
evaluasi template, atau pantulan mentah. Nilai sandi/token tak pernah dibuat di sini.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any


@dataclass
class Varian:
    jenis: str          # tipe_salah | format | rentang | panjang | enum | kosong | sqli | ssti | xss | traversal | ai
    kelompok: str       # validasi | injeksi
    nilai: Any
    penanda: str = ""   # string yang dicari pada respons (xss/ssti)


def maks_varian() -> int:
    try:
        return max(2, int(os.environ.get("INPV_MAKS_VARIAN", "6")))
    except ValueError:
        return 6


def _format_salah(fmt: str) -> Any:
    return {
        "email": "bukan-email-satya",
        "date": "2024-13-45",
        "date-time": "bukan-tanggal",
        "uuid": "bukan-uuid-satya",
        "url": "bukan url satya",
        "uri": "bukan url satya",
        "digits": "12ab34cd",
        "slug": "slug tidak valid!",
        "kata": "satya_kolom_tak_ada",
    }.get(fmt, "")


def varian_field(p: dict[str, Any], tok: str) -> list[Varian]:
    """Varian berurutan menurut prioritas; dipangkas ke `INPV_MAKS_VARIAN`."""
    tipe = str(p.get("tipe") or "string")
    out: list[Varian] = []
    # 1) Tipe salah (paling informatif untuk validasi positif).
    if tipe in ("integer", "number", "id"):
        out.append(Varian("tipe_salah", "validasi", "satya-bukan-angka"))
    elif tipe == "boolean":
        out.append(Varian("tipe_salah", "validasi", "satya-bukan-boolean"))
    elif tipe in ("array", "object"):
        out.append(Varian("tipe_salah", "validasi", "satya-bukan-" + tipe))
    else:
        out.append(Varian("tipe_salah", "validasi", {"satya": 1}))
    # 2) Format.
    fs = _format_salah(str(p.get("format") or ""))
    if fs:
        out.append(Varian("format", "validasi", fs))
    # 3) Enum / rentang.
    if isinstance(p.get("enum"), list) and p["enum"]:
        out.append(Varian("enum", "validasi", "satya-di-luar-enum"))
    if tipe in ("integer", "number", "id"):
        mx = p.get("max")
        out.append(Varian("rentang", "validasi", (mx + 1) if isinstance(mx, (int, float)) else -999999999))
    # 4) Saran AI (nilai tak valid spesifik domain), bila ada.
    for v in p.get("invalid_ai") or []:
        out.append(Varian("ai", "validasi", v))
    # 5) Injeksi untuk field teks.
    if tipe in ("string", "", "id"):
        out.append(Varian("sqli", "injeksi", f"satya{tok}'\"`"))
        out.append(Varian("xss", "injeksi", f"<satya{tok}>", penanda=f"<satya{tok}>"))
        out.append(Varian("ssti", "injeksi", f"satya{tok}{{{{7*7}}}}${{7*7}}", penanda=f"satya{tok}49"))
    # 6) Panjang & kosong.
    mxl = p.get("max_len")
    out.append(Varian("panjang", "validasi", "A" * ((mxl + 1) if isinstance(mxl, int) and mxl < 5000 else 5000)))
    if p.get("wajib"):
        out.append(Varian("kosong", "validasi", None))
    return _pangkas(out, maks_varian())


def varian_path(tok: str) -> list[Varian]:
    """Segmen `{id}` tak valid (GET/DELETE)."""
    return _pangkas([
        Varian("tipe_salah", "validasi", "satya-bukan-id"),
        Varian("rentang", "validasi", "-1"),
        Varian("sqli", "injeksi", f"1'satya{tok}"),
        Varian("traversal", "injeksi", "..%2f..%2fsatya"),
        Varian("panjang", "validasi", "9" * 300),
    ], maks_varian())


def varian_tanpa_input(tok: str) -> list[Varian]:
    """Endpoint tanpa parameter: satu parameter tak dikenal berisi penanda (pantulan/crash)."""
    return [Varian("xss", "injeksi", f"<satya{tok}>", penanda=f"<satya{tok}>")]


def _pangkas(v: list[Varian], n: int) -> list[Varian]:
    """Pertahankan keragaman: utamakan satu varian per jenis, lalu isi sisa kuota."""
    pilih: list[Varian] = []
    jenis: set[str] = set()
    for x in v:
        if x.jenis not in jenis and len(pilih) < n:
            pilih.append(x)
            jenis.add(x.jenis)
    for x in v:
        if len(pilih) >= n:
            break
        if x not in pilih:
            pilih.append(x)
    return pilih


def token() -> str:
    return secrets.token_hex(3)
