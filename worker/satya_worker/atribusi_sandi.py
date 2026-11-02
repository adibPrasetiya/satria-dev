"""Fondasi uji kebijakan kata sandi yang TAJAM (AUTH-1.2/1.3).

Masalah yang diatasi: uji lama mengirim payload dengan field lain kosong (mis. `nama: ""`), lalu
menganggap status 400 apa pun sebagai "sandi lemah ditolak" → LULUS palsu, padahal penolakan bisa
karena field lain. Modul ini menyediakan:

  payload_valid()   — isi field non-sandi dengan nilai dummy VALID dari skema OpenAPI (+ AI bila perlu)
  sandi_kuat() / sandi_pendek() / sandi_tanpa_kombinasi() — variasi sandi uji
  atribusikan()     — tentukan PENYEBAB penolakan: kebijakan_sandi | field_lain | duplikasi | tidak_jelas,
                      dari uji pembanding (payload identik + sandi kuat), analisis body error, lalu AI.
  vonis()           — LULUS hanya bila penyebab = kebijakan_sandi; diterima → GAGAL; selain itu → tinjauan.

AI hanya membantu (mengisi nilai dummy, menafsirkan pesan error) dan selalu menerima METADATA tersamar:
nilai payload diganti placeholder, sandi/token tak pernah dikirim. Keputusan akhir tetap deterministik.
"""

from __future__ import annotations

import json
import re
import secrets
import string
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

STATUS_SUKSES = (200, 201, 202, 204)

# --------------------------------------------------------------------------- variasi sandi


def sandi_kuat() -> str:
    """≥16 karakter, empat kelas karakter, acak."""
    acak = secrets.token_urlsafe(9).replace("-", "x").replace("_", "y")
    return f"Satya#{acak}9Qz!"


def sandi_pendek(minimum: int) -> str:
    """Lengkap empat kelas karakter, tetapi SATU karakter di bawah panjang minimum."""
    n = max(4, minimum - 1)
    dasar = "Aa1!"
    return (dasar + "bC2@dE3#")[:n]


def sandi_tanpa_kombinasi(minimum: int) -> str:
    """Panjang cukup (minimum+4) tetapi hanya huruf kecil."""
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(max(minimum + 4, 12)))


def ciri_sandi(s: str) -> dict[str, Any]:
    """Ciri sandi untuk AI/bukti tanpa membocorkan nilai: panjang & kelas karakter."""
    return {
        "panjang": len(s),
        "huruf_besar": any(c.isupper() for c in s),
        "huruf_kecil": any(c.islower() for c in s),
        "angka": any(c.isdigit() for c in s),
        "simbol": any(not c.isalnum() for c in s),
    }


# --------------------------------------------------------------------------- payload valid

_UNIK = ("email", "surel", "username", "nrp", "nip", "nik", "nomor", "phone", "telp", "hp", "user")


def _hex(n: int = 6) -> str:
    return secrets.token_hex(n // 2 + 1)[:n]


def _digit(n: int) -> str:
    return str(secrets.choice("123456789")) + "".join(secrets.choice(string.digits) for _ in range(max(0, n - 1)))


def _panjang_pola(pola: str) -> Optional[int]:
    m = re.search(r"\\d\{(\d+)(?:,\s*(\d+))?\}", pola or "")
    return int(m.group(1)) if m else None


def nilai_dummy(nama: str, skema: dict[str, Any]) -> tuple[Any, bool]:
    """Nilai dummy VALID untuk satu field. Return (nilai, yakin) — yakin=False → kandidat AI."""
    n = nama.lower()
    tipe = str(skema.get("type") or "").lower()
    fmt = str(skema.get("format") or "").lower()
    mn = skema.get("minLength")
    mx = skema.get("maxLength")
    pola = str(skema.get("pattern") or "")

    def pas(s: str) -> str:
        if isinstance(mn, int) and len(s) < mn:
            s = s + "x" * (mn - len(s))
        if isinstance(mx, int) and len(s) > mx:
            s = s[:mx]
        return s

    if isinstance(skema.get("enum"), list) and skema["enum"]:
        return skema["enum"][0], True
    if tipe == "boolean":
        return True, True
    if tipe in ("integer", "number"):
        return max(int(skema.get("minimum") or 1), 1), True
    if tipe == "array":
        return [], True
    if fmt == "email" or "email" in n or "surel" in n:
        return f"satya-uji-{_hex(8)}@contoh.go.id", True
    if fmt == "uuid":
        return str(uuid.uuid4()), True
    if fmt == "date":
        return "1990-01-01", True
    if fmt == "date-time":
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat(), True
    # Nomor identitas berbentuk digit (NIP 18, NIK 16, NRP 8, telepon 12) — hormati pola/panjang skema.
    panjang_digit = _panjang_pola(pola)
    if panjang_digit or re.search(r"\b(nip|nik|nrp|nomor|no_|phone|telp|hp|nisn|npwp)\b|^(nip|nik|nrp|hp|telp)", n):
        bawaan = {"nip": 18, "nik": 16, "nrp": 8, "npwp": 15, "nisn": 10}
        k = panjang_digit or (mn if isinstance(mn, int) else None) or next((v for kk, v in bawaan.items() if kk in n), 12)
        nilai = _digit(k)
        if any(t in n for t in ("phone", "telp", "hp")):
            nilai = "08" + nilai[2:]
        return nilai, True
    if "username" in n or n in ("user", "login", "akun"):
        return pas(f"satya_uji_{_hex(6)}"), True
    if any(t in n for t in ("nama", "name", "fullname", "full_name")):
        return pas(f"Satya Uji {_hex(4)}"), True
    if "url" in n or fmt in ("uri", "url"):
        return "https://contoh.go.id", True
    if skema.get("example") not in (None, ""):
        return skema["example"], True
    if skema.get("default") not in (None, ""):
        return skema["default"], True
    if tipe == "string" or not tipe:
        return pas(f"uji satya {_hex(4)}"), False
    return None, False


def payload_valid(form: Any, *, field_sandi: Optional[str] = None, pakai_ai: bool = True) -> tuple[dict[str, Any], list[str]]:
    """Susun payload VALID untuk form (registrasi/ubah/reset), TANPA field sandi.

    Nilai manual di `field_dasar` (dikonfigurasi asesor) dihormati; nilai kosong diisi dari skema.
    Field unik (email/username/NIP…) selalu baru tiap panggilan. Return (payload, field_ditebak).
    """
    skema: dict[str, dict[str, Any]] = dict(getattr(form, "skema_field", {}) or {})
    sandi_set = {f for f in (field_sandi, getattr(form, "field_sandi", ""), getattr(form, "field_konfirmasi", ""),
                             getattr(form, "field_lama", ""), getattr(form, "field_baru", "")) if f}
    nama_field = list(dict.fromkeys(list((getattr(form, "field_dasar", {}) or {}).keys()) + list(skema.keys())))
    unik = set(getattr(form, "field_unik", []) or [])
    payload: dict[str, Any] = {}
    ditebak: list[str] = []
    for nama in nama_field:
        if nama in sandi_set or re.search(r"pass|sandi", nama, re.I):
            continue
        manual = (getattr(form, "field_dasar", {}) or {}).get(nama)
        sk = skema.get(nama, {})
        if manual not in (None, "") and nama not in unik and not any(u in nama.lower() for u in _UNIK):
            payload[nama] = manual
            continue
        nilai, yakin = nilai_dummy(nama, sk)
        if nilai is None and not sk.get("required", True):
            continue
        payload[nama] = nilai
        if not yakin and sk.get("required", True):
            ditebak.append(nama)
    if pakai_ai and ditebak:
        _isi_dengan_ai(payload, ditebak, skema)
    return payload, ditebak


def _isi_dengan_ai(payload: dict[str, Any], ditebak: list[str], skema: dict[str, dict[str, Any]], galat: str = "") -> None:
    from . import ai as ai_mod

    meta = {
        "field": [{"nama": f, "skema": skema.get(f, {})} for f in ditebak],
        "field_lain": [k for k in payload if k not in ditebak],
        "pesan_galat_server": galat[:1200],
    }
    hasil = ai_mod.isi_payload(meta)
    if not hasil:
        return
    for k, v in (hasil.get("nilai") or {}).items():
        if k in payload and not re.search(r"pass|sandi|token", k, re.I) and isinstance(v, (str, int, float, bool)):
            payload[k] = v


def nilai_field_endpoint(f: dict[str, Any]) -> Any:
    """Nilai VALID untuk satu field inventaris endpoint: contoh nilai dari lalu lintas nyata (bila
    ada & bukan field unik) → kendala skema OpenAPI → tebakan dari nama field."""
    nama = str(f.get("nama", ""))
    if "contoh" in f and f["contoh"] not in (None, "") and not any(u in nama.lower() for u in _UNIK):
        return f["contoh"]
    skema = dict(f.get("skema") or {})
    tipe = str(f.get("tipe") or "")
    if tipe and "type" not in skema:
        skema["type"] = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}.get(tipe, tipe)
    nilai, _ = nilai_dummy(nama, skema)
    if nilai is None and skema.get("type") == "object":
        return {}
    return nilai if nilai is not None else "satya-uji"


def payload_endpoint(ep: dict[str, Any], lokasi: str = "body") -> dict[str, Any]:
    """Payload VALID untuk endpoint inventaris (semua field `lokasi`), tanpa field kredensial — dasar
    uji yang memvariasikan SATU field (mis. validasi input) agar penolakan tak disebabkan field lain."""
    out: dict[str, Any] = {}
    for f in ep.get("request_fields") or []:
        nama = f.get("nama")
        if not nama or f.get("lokasi") != lokasi or re.search(r"pass|sandi|token|secret", nama, re.I):
            continue
        out[nama] = nilai_field_endpoint(f)
    return out


def field_disebut_galat(resp: Any, payload: dict[str, Any]) -> set[str]:
    """Nama field yang disebut error terstruktur respons (untuk atribusi penolakan per field)."""
    _, obj = _teks_galat(resp)
    return _field_disebut(obj, list(payload.keys())) if obj is not None else set()


def segarkan_unik(payload: dict[str, Any], form: Any) -> dict[str, Any]:
    """Salinan payload dengan field unik (email/username/NIP) dibuat baru → hindari 'sudah terdaftar'."""
    baru = dict(payload)
    skema = getattr(form, "skema_field", {}) or {}
    for k in list(baru):
        if k in (getattr(form, "field_unik", []) or []) or any(u in k.lower() for u in _UNIK):
            nilai, _ = nilai_dummy(k, skema.get(k, {}))
            if nilai is not None:
                baru[k] = nilai
    return baru


def pasang_sandi(payload: dict[str, Any], form: Any, sandi: str, field: Optional[str] = None) -> dict[str, Any]:
    p = dict(payload)
    p[field or getattr(form, "field_sandi", "password")] = sandi
    konf = getattr(form, "field_konfirmasi", "")
    if konf:
        p[konf] = sandi
    return p


# --------------------------------------------------------------------------- atribusi

_KW_SANDI = re.compile(r"pass(word)?|sandi|kata\s*sandi|passwd", re.I)
_KW_KEBIJAKAN = re.compile(
    r"min(imal|imum)?|karakter|character|length|panjang|huruf|upper|lower|kapital|besar|kecil|angka|digit|number|"
    r"simbol|symbol|special|khusus|kuat|strong|weak|lemah|complex|kombinasi|policy|kebijakan|too short|terlalu pendek",
    re.I,
)
_KW_DUPLIKASI = re.compile(r"sudah\s+(terdaftar|digunakan|ada)|already|exists|duplicate|telah\s+digunakan|taken|terpakai", re.I)


def _teks_galat(resp: Any) -> tuple[str, Any]:
    teks = (getattr(resp, "text", "") or "")[:4000]
    try:
        return teks, json.loads(teks)
    except ValueError:
        return teks, None


def _field_disebut(obj: Any, nama_field: list[str]) -> set[str]:
    """Nama field yang disebut pada error terstruktur: {errors:[{field|path|param}]}, {password:[..]}, dll."""
    out: set[str] = set()

    def jalan(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if k in nama_field and v not in (None, "", [], {}):
                    out.add(k)
                if k in ("field", "path", "param", "property", "loc", "key", "context") and isinstance(v, (str, list)):
                    vals = v if isinstance(v, list) else [v]
                    for item in vals:
                        if not isinstance(item, str) or not item:
                            continue
                        cocok = [f for f in nama_field if item == f or item.endswith("." + f) or item.endswith("/" + f)]
                        # Field yang disebut error tetapi tak ada di payload (field wajib terlewat) tetap dicatat.
                        out.update(cocok or [item.rsplit(".", 1)[-1].rsplit("/", 1)[-1]])
                jalan(v)
        elif isinstance(x, list):
            for i in x:
                jalan(i)

    jalan(obj)
    return out


def analisis_body(resp: Any, field_sandi: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Atribusi deterministik dari isi respons error."""
    teks, obj = _teks_galat(resp)
    nama_field = list(payload.keys())
    disebut = _field_disebut(obj, nama_field) if obj is not None else set()
    lain = sorted(f for f in disebut if f != field_sandi and not _KW_SANDI.search(f))
    if _KW_DUPLIKASI.search(teks):
        return {"penyebab": "duplikasi", "alasan": "Respons menyebut data sudah terdaftar/digunakan."}
    if field_sandi in disebut or any(_KW_SANDI.search(f) for f in disebut):
        if not lain:
            return {"penyebab": "kebijakan_sandi", "alasan": f"Error terstruktur menunjuk field sandi '{field_sandi}'."}
    if lain:
        return {"penyebab": "field_lain", "alasan": f"Error menunjuk field lain: {', '.join(lain)}.", "field": lain}
    # Teks bebas: kata sandi + kata kebijakan, tanpa menyebut field lain.
    sebut_lain = [f for f in nama_field if f != field_sandi and re.search(rf"\b{re.escape(f)}\b", teks, re.I)]
    if _KW_SANDI.search(teks) and _KW_KEBIJAKAN.search(teks) and not sebut_lain:
        return {"penyebab": "kebijakan_sandi", "alasan": "Pesan error membahas aturan kata sandi."}
    if sebut_lain:
        return {"penyebab": "field_lain", "alasan": f"Pesan error menyebut field: {', '.join(sebut_lain)}.", "field": sebut_lain}
    return {"penyebab": "tidak_jelas", "alasan": "Pesan error tidak menyebut penyebab yang jelas."}


def _redaksi_body(teks: str, payload: dict[str, Any], sandi: list[str]) -> str:
    """Body untuk AI: semua nilai payload & sandi diganti placeholder."""
    t = teks[:1500]
    for s in sandi:
        if s:
            t = t.replace(s, "[SANDI]")
    for k, v in payload.items():
        if isinstance(v, str) and len(v) >= 3:
            t = t.replace(v, f"[{k}]")
    return t


def atribusikan(
    resp_lemah: Any,
    *,
    field_sandi: str,
    payload: dict[str, Any],
    sandi_lemah: str,
    resp_kuat: Any = None,
    status_sukses: tuple[int, ...] | list[int] = STATUS_SUKSES,
    pakai_ai: bool = True,
) -> dict[str, Any]:
    """Tentukan penyebab hasil uji sandi lemah. Return {penyebab, alasan, sumber, keyakinan}."""
    sukses = set(status_sukses)
    if resp_lemah.status_code in sukses:
        return {"penyebab": "diterima", "alasan": f"Sandi lemah diterima (HTTP {resp_lemah.status_code}).", "sumber": "status", "keyakinan": "tinggi"}
    kuat_ok = resp_kuat is not None and resp_kuat.status_code in sukses
    if kuat_ok:
        return {
            "penyebab": "kebijakan_sandi",
            "alasan": f"Payload identik dengan sandi kuat diterima (HTTP {resp_kuat.status_code}), sandi lemah ditolak (HTTP {resp_lemah.status_code}).",
            "sumber": "pembanding",
            "keyakinan": "tinggi",
        }
    a = analisis_body(resp_lemah, field_sandi, payload)
    if resp_kuat is not None and a["penyebab"] in ("kebijakan_sandi", "tidak_jelas"):
        # Sandi kuat pun ditolak → payload kemungkinan belum valid; atribusi ke sandi tidak bisa dipastikan.
        b = analisis_body(resp_kuat, field_sandi, payload)
        if b["penyebab"] in ("field_lain", "duplikasi"):
            return {**b, "sumber": "pembanding", "keyakinan": "sedang"}
        if a["penyebab"] == "tidak_jelas":
            a = {"penyebab": "tidak_jelas", "alasan": f"Sandi kuat pun ditolak (HTTP {resp_kuat.status_code}); payload kemungkinan belum valid."}
    if a["penyebab"] != "tidak_jelas" or not pakai_ai:
        return {**a, "sumber": "analisis_body", "keyakinan": "sedang" if a["penyebab"] == "kebijakan_sandi" else "rendah"}
    from . import ai as ai_mod

    teks, _ = _teks_galat(resp_lemah)
    meta = {
        "status": resp_lemah.status_code,
        "body_error": _redaksi_body(teks, payload, [sandi_lemah]),
        "field_payload": list(payload.keys()),
        "field_yang_divariasikan": field_sandi,
        "ciri_nilai_lemah": ciri_sandi(sandi_lemah),
        "status_pembanding_kuat": getattr(resp_kuat, "status_code", None),
    }
    h = ai_mod.atribusi_penolakan(meta)
    if h and h.get("penyebab") in ("kebijakan_sandi", "field_lain", "duplikasi", "tidak_jelas"):
        return {"penyebab": h["penyebab"], "alasan": f"AI ({h.get('provider')}): {str(h.get('alasan', ''))[:200]}", "sumber": "ai", "keyakinan": "sedang"}
    return {**a, "sumber": "analisis_body", "keyakinan": "rendah"}


def vonis(atribusi: dict[str, Any]) -> str:
    """Status metode dari atribusi: lulus | gagal | tidak_dapat_diverifikasi."""
    p = atribusi.get("penyebab")
    if p == "diterima":
        return "gagal"
    if p == "kebijakan_sandi":
        return "lulus"
    return "tidak_dapat_diverifikasi"
