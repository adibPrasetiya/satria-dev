"""Profil validasi per field: tipe, format, rentang, panjang, enum yang SEHARUSNYA ditegakkan server.

Deterministik dulu (skema OpenAPI → tipe/contoh inventaris → aturan nama field). Field yang
masih ambigu (string tanpa skema & nama tak dikenali) dikumpulkan; AI dipanggil SEKALI untuk
semuanya (lihat `ai_inpv.profil_validasi`) dan hasilnya di-cache persisten per signature field.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlsplit

_TIPE = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}

# (regex nama field, profil) — dicoba berurutan.
_ATURAN: list[tuple[re.Pattern[str], dict[str, Any]]] = [
    (re.compile(r"(^|_)(e-?mail|surel)($|_)|email", re.I), {"tipe": "string", "format": "email"}),
    (re.compile(r"(^|_)(page|halaman|limit|offset|per_?page|size|count|jumlah|qty|quantity|kuantitas)$", re.I), {"tipe": "integer", "min": 0}),
    (re.compile(r"(^|_)(id|uuid)$|Id$|_id$", re.I), {"tipe": "id"}),
    (re.compile(r"(tanggal|tgl|date|_at$|birth|lahir)", re.I), {"tipe": "string", "format": "date"}),
    (re.compile(r"(phone|telp|telepon|hp|whatsapp|wa)$", re.I), {"tipe": "string", "format": "digits", "min": 8, "max": 15}),
    (re.compile(r"^(nik)$", re.I), {"tipe": "string", "format": "digits", "min": 16, "max": 16}),
    (re.compile(r"^(nip)$", re.I), {"tipe": "string", "format": "digits", "min": 18, "max": 18}),
    (re.compile(r"(url|link|website|redirect|callback|return_?to|next)$", re.I), {"tipe": "string", "format": "url"}),
    (re.compile(r"^(sort|order|sort_?by|order_?by|urut)$", re.I), {"tipe": "string", "format": "kata"}),
    (re.compile(r"(slug)$", re.I), {"tipe": "string", "format": "slug"}),
    (re.compile(r"(price|harga|amount|nominal|total|rating|score|nilai)$", re.I), {"tipe": "number", "min": 0}),
    (re.compile(r"^(is_|has_)|(aktif|active|enabled)$", re.I), {"tipe": "boolean"}),
]


def signature(f: dict[str, Any], path_template: str) -> str:
    """Kunci dedup/cache: nama|tipe|segmen-sumber (mis. 'email|string|users'). Tanpa nilai."""
    seg = [s for s in (path_template or "").split("/") if s and s != "api" and not s.startswith("{") and not re.fullmatch(r"v\d+", s)]
    return f"{str(f.get('nama', '')).lower()}|{_TIPE.get(str(f.get('tipe') or ''), str(f.get('tipe') or 'string'))}|{seg[0] if seg else ''}"


def bentuk_contoh(nilai: Any) -> Optional[str]:
    """Bentuk nilai contoh tanpa isinya: huruf→a, angka→9 (mis. 'ab@cd.ef', '9999-99-99')."""
    if nilai in (None, "") or isinstance(nilai, (dict, list)):
        return None
    s = str(nilai)[:24]
    return re.sub(r"[0-9]", "9", re.sub(r"[A-Za-z]", "a", s))


def profil(f: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (profil, yakin). yakin=False → kandidat AI."""
    sk = dict(f.get("skema") or {})
    tipe = str(sk.get("type") or _TIPE.get(str(f.get("tipe") or ""), str(f.get("tipe") or ""))).lower()
    p: dict[str, Any] = {"tipe": tipe or "string", "wajib": bool(f.get("wajib") or sk.get("required"))}
    for a, b in (("format", "format"), ("minimum", "min"), ("maximum", "max"), ("minLength", "min_len"), ("maxLength", "max_len"), ("enum", "enum"), ("pattern", "pola")):
        if sk.get(a) not in (None, ""):
            p[b] = sk[a]
    nama = str(f.get("nama", ""))
    for rx, aturan in _ATURAN:
        if rx.search(nama):
            for k, v in aturan.items():
                if k != "tipe":
                    p.setdefault(k, v)
                elif p["tipe"] in ("", "string"):
                    p["tipe"] = v
            return p, True
    contoh = f.get("contoh")
    if isinstance(contoh, bool):
        p["tipe"] = "boolean"
    elif isinstance(contoh, (int, float)) and p["tipe"] in ("", "string"):
        p["tipe"] = "integer" if isinstance(contoh, int) else "number"
    yakin = p["tipe"] not in ("", "string") or any(k in p for k in ("format", "enum", "max_len", "pola"))
    return p, yakin


def gabung_ai(p: dict[str, Any], dari_ai: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Lengkapi profil deterministik dengan saran AI (tak menimpa kendala skema)."""
    if not isinstance(dari_ai, dict):
        return p
    out = dict(p)
    for k in ("tipe", "format", "min", "max", "min_len", "max_len", "enum"):
        if k in dari_ai and dari_ai[k] not in (None, "", []) and (k not in out or (k == "tipe" and out[k] in ("", "string"))):
            out[k] = dari_ai[k]
    inv = [v for v in (dari_ai.get("invalid") or []) if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 200]
    if inv:
        out["invalid_ai"] = inv[:3]
    return out


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()
