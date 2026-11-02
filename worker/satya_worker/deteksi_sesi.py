"""Deteksi token/sesi berbasis BENTUK-NILAI — lepas dari nama key.

Pendekatan lama (`sesi._KUNCI_TOKEN`) mencocokkan substring nama key (accessToken,
token, …). Itu rapuh: aplikasi yang menamai tokennya dengan prefiks sendiri
(mis. `cuti.session`, `myapp.auth`) tak akan terdeteksi.

Modul ini mengenali token dari BENTUK NILAI-nya (JWT / UUID / string opaque
berentropi), apa pun nama key-nya, plus utilitas diff (nilai baru setelah login)
dan pembangun metadata non-sensitif untuk arbiter AI (TANPA mengirim nilai token).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# JWT: tiga segmen base64url dipisah titik.
_RE_JWT = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}$")
# UUID v1–v5.
_RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
# String opaque: charset token-ish, cukup panjang.
_RE_OPAQUE = re.compile(r"^[A-Za-z0-9._~+/=-]{20,}$")

# Hint nama key (sinyal tambahan, BUKAN syarat) — mencakup pola sesi/berberek aplikasi.
_HINT_KEY = ("token", "accesstoken", "access_token", "jwt", "idtoken", "id_token",
             "auth", "session", "sess", "sid", "bearer", "credential", "kredensial")

# Bobot keyakinan bentuk.
_BOBOT = {"jwt": 4, "uuid": 3, "opaque": 2}


def bentuk_token(nilai: str) -> Optional[str]:
    """Klasifikasi bentuk sebuah string: 'jwt' | 'uuid' | 'opaque' | None."""
    if not isinstance(nilai, str):
        return None
    v = nilai.strip().strip('"')
    if not v or len(v) > 4096:
        return None
    if _RE_JWT.match(v):
        return "jwt"
    if _RE_UUID.match(v):
        return "uuid"
    if len(v) >= 20 and _RE_OPAQUE.match(v) and _berentropi(v):
        return "opaque"
    return None


def _berentropi(v: str) -> bool:
    """Saring kata/slug biasa: butuh digit, campuran huruf besar-kecil, atau simbol base64.

    `-` dan `.` TIDAK dihitung entropi (lazim pada slug & path, mis. 'beranda-pengguna').
    """
    ada_digit = any(c.isdigit() for c in v)
    ada_besar = any(c.isupper() for c in v)
    ada_kecil = any(c.islower() for c in v)
    ada_simbol = any(c in "_~+/=" for c in v)
    return ada_digit or (ada_besar and ada_kecil) or ada_simbol


def _skor_kandidat(key: str, nilai: str) -> Optional[tuple[int, str]]:
    """Return (skor, token) bila `nilai` (atau isi JSON-nya) berbentuk token."""
    bentuk = bentuk_token(nilai)
    token = nilai.strip().strip('"') if bentuk else None
    # Nilai yang berupa JSON → cari token di dalamnya (mis. {"token":"..."}).
    if bentuk is None and isinstance(nilai, str) and nilai.strip()[:1] in "{[":
        dalam = _token_dalam_json(nilai)
        if dalam:
            bentuk, token = dalam
    if bentuk is None or not token:
        return None
    skor = _BOBOT.get(bentuk, 1)
    if any(h in (key or "").lower() for h in _HINT_KEY):
        skor += 2  # nama key memperkuat, tak menentukan
    return skor, token


def _token_dalam_json(teks: str) -> Optional[tuple[str, str]]:
    try:
        obj = json.loads(teks)
    except (ValueError, TypeError):
        return None
    terbaik: Optional[tuple[int, str, str]] = None
    pile: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        pile = list(obj.items())
    elif isinstance(obj, list):
        pile = [("", x) for x in obj]
    for k, v in pile:
        if isinstance(v, str):
            b = bentuk_token(v)
            if b:
                s = _BOBOT.get(b, 1) + (2 if any(h in str(k).lower() for h in _HINT_KEY) else 0)
                if terbaik is None or s > terbaik[0]:
                    terbaik = (s, b, v.strip())
    return (terbaik[1], terbaik[2]) if terbaik else None


def _ratakan(storage: dict) -> list[tuple[str, str]]:
    """Ratakan {localStorage:{...}, sessionStorage:{...}} → [(key, nilai)]."""
    out: list[tuple[str, str]] = []
    for bag in (storage or {}).values():
        if isinstance(bag, dict):
            for k, v in bag.items():
                if isinstance(v, str):
                    out.append((k, v))
    return out


def cari_token_nilai(storage: dict) -> Optional[str]:
    """Token terkuat dari storage berdasarkan bentuk-nilai (abaikan nama key)."""
    terbaik: Optional[tuple[int, str]] = None
    for k, v in _ratakan(storage):
        kand = _skor_kandidat(k, v)
        if kand and (terbaik is None or kand[0] > terbaik[0]):
            terbaik = kand
    return terbaik[1] if terbaik else None


def token_baru(sebelum: dict, sesudah: dict) -> Optional[str]:
    """Token yang MUNCUL/berubah antara snapshot `sebelum` dan `sesudah` (sinyal kuat login)."""
    lama = {(k, v) for k, v in _ratakan(sebelum)}
    terbaik: Optional[tuple[int, str]] = None
    for k, v in _ratakan(sesudah):
        if (k, v) in lama:
            continue  # tak berubah
        kand = _skor_kandidat(k, v)
        if kand and (terbaik is None or kand[0] > terbaik[0]):
            terbaik = kand
    return terbaik[1] if terbaik else None


def metadata_storage(storage: dict) -> list[dict[str, Any]]:
    """Metadata NON-sensitif tiap entri storage untuk arbiter AI (tanpa nilai token).

    Hanya: nama key, panjang nilai, bentuk terdeteksi. Nilai asli TIDAK disertakan.
    """
    out: list[dict[str, Any]] = []
    for k, v in _ratakan(storage):
        out.append({"key": k, "panjang": len(v), "bentuk": bentuk_token(v) or "lainnya"})
    return out
