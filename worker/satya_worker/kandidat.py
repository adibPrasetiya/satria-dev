"""Pemetaan KANDIDAT UJI dari inventaris discovery.

Setelah discovery menyatukan endpoint (`endpoints_lengkap`), modul ini memetakan
tiap endpoint menjadi kandidat uji untuk fungsi keamanan katalog BSSN:
  AUTH (Autentikasi), SESS (Manajemen Sesi), ACCS (Kontrol Akses),
  INPV (Validasi Input), ERRL (Penanganan Error & Log), DATA (Proteksi Data),
  COMM (Keamanan Komunikasi), FILE (Berkas), APIS (Keamanan API), CONF (Konfigurasi).

Tujuan: tool/check fungsi tinggal MEMBACA kandidat (tak perlu mengklasifikasi ulang).
Pemetaan deterministik dulu; `kelengkapan` menandai info yang kurang. AI (opsional,
lewat `ai.lengkapi_kandidat`) menyempurnakan kategori & mengisi gap — hanya dari
METADATA (nama field, bukan nilainya).
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlsplit

# Field yang menandai data sensitif (untuk kandidat DATA & tingkat sensitivitas INPV).
_FIELD_SENSITIF = re.compile(
    r"(pass|sandi|token|secret|auth|cookie|session|otp|mfa|nik|nip|nrp|email|"
    r"telepon|phone|hp|alamat|address|tgl_?lahir|birth|kartu|card|cvv|pin|gaji|saldo)",
    re.IGNORECASE,
)
_METODE_TULIS = {"POST", "PUT", "PATCH", "DELETE"}
_METODE_BERBODI = {"POST", "PUT", "PATCH"}


def _origin(url: str) -> str:
    s = urlsplit(url)
    return f"{s.scheme}://{s.netloc}" if s.scheme else ""


def _punya_field(ep: dict, lokasi: tuple[str, ...]) -> bool:
    return any(f.get("lokasi") in lokasi for f in ep.get("request_fields", []))


def _field_sensitif(ep: dict) -> list[str]:
    out = []
    for f in ep.get("request_fields", []):
        nama = f.get("nama", "")
        if nama and _FIELD_SENSITIF.search(nama):
            out.append(nama)
    return out


def _kelengkapan(ep: dict, kategori: list[str]) -> dict[str, Any]:
    """Analisis kekurangan info deterministik untuk endpoint ini."""
    kurang: list[str] = []
    metode = ep.get("metode_http", "GET").upper()
    if metode in _METODE_BERBODI and not _punya_field(ep, ("body",)):
        kurang.append("field_body_tak_diketahui")
    if metode in _METODE_BERBODI and not ep.get("content_type"):
        kurang.append("content_type_tak_diketahui")
    if not ep.get("status_terlihat"):
        kurang.append("perilaku_respons_belum_teramati")
    if ep.get("butuh_autentikasi") and "ACCS" in kategori:
        kurang.append("butuh_akun_uji_untuk_verifikasi_akses")
    skor = round(max(0.0, 1.0 - 0.25 * len(kurang)), 2)
    return {"skor": skor, "kurang": kurang}


def _kategori_endpoint(ep: dict) -> dict[str, str]:
    """Kembalikan {kode_fungsi: alasan} kandidat untuk satu endpoint (deterministik)."""
    metode = ep.get("metode_http", "GET").upper()
    path = ep.get("path_template", "")
    titik = (ep.get("titik_uji") or "").lower()
    ct = (ep.get("content_type") or "").lower()
    butuh_auth = bool(ep.get("butuh_autentikasi"))
    low = path.lower()
    kat: dict[str, str] = {}

    # AUTH — titik autentikasi.
    if titik in ("login", "registrasi", "reset_password", "ubah_password", "logout") or re.search(r"/(login|auth|register|signin|logout|password)", low):
        kat["AUTH"] = f"Endpoint autentikasi ({titik or 'pola path'})."
    # SESS — sesi: login/logout atau endpoint terproteksi (bergantung sesi).
    if titik in ("login", "logout") or butuh_auth:
        kat["SESS"] = "Menerbitkan/memakai sesi." if titik in ("login", "logout") else "Akses bergantung sesi (terproteksi)."
    # ACCS — kontrol akses: terproteksi, resource ber-{id} (IDOR), atau admin.
    if butuh_auth or "{id}" in path or titik == "admin" or "/admin" in low:
        sebab = []
        if "{id}" in path: sebab.append("resource ber-{id} (uji IDOR)")
        if butuh_auth: sebab.append("butuh autentikasi")
        if titik == "admin" or "/admin" in low: sebab.append("antarmuka admin (privilege)")
        kat["ACCS"] = "; ".join(sebab) or "akses terbatas"
    # INPV — ada field input (body/query).
    if _punya_field(ep, ("body", "query")):
        kat["INPV"] = "Menerima parameter input (fuzz/boundary/injeksi)."
    # ERRL — endpoint tulis / berbodi → uji penanganan error (payload malformed).
    if metode in _METODE_BERBODI:
        kat["ERRL"] = "Uji penanganan error pada input malformed."
    # DATA — field sensitif pada request.
    fs = _field_sensitif(ep)
    if fs:
        kat["DATA"] = f"Memproses field sensitif: {', '.join(fs[:6])}."
    # FILE — unggah/unduh berkas.
    if titik in ("unggah_file", "unduh_file") or "multipart/form-data" in ct or re.search(r"/(upload|unggah|download|unduh|file|berkas)", low):
        kat["FILE"] = "Operasi berkas (unggah/unduh)."
    # APIS — endpoint API/web service.
    if "/api" in low or titik == "api":
        kat["APIS"] = "Endpoint API/web service."
    return kat


def petakan_kandidat(
    endpoints_lengkap: list[dict[str, Any]],
    flows: Optional[list[dict[str, Any]]] = None,
    test_points: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Peta kandidat uji per-endpoint + kandidat global (CONF/COMM per origin)."""
    per_endpoint: list[dict[str, Any]] = []
    ringkas: dict[str, int] = {}
    origin_set: set[str] = set()

    for ep in endpoints_lengkap or []:
        kat_map = _kategori_endpoint(ep)
        kategori = sorted(kat_map.keys())
        for k in kategori:
            ringkas[k] = ringkas.get(k, 0) + 1
        o = _origin(ep.get("url", ""))
        if o:
            origin_set.add(o)
        per_endpoint.append({
            "endpoint": f"{ep.get('metode_http', 'GET')} {ep.get('path_template', '')}",
            "metode_http": ep.get("metode_http", "GET"),
            "path_template": ep.get("path_template", ""),
            "url": ep.get("url", ""),
            "butuh_autentikasi": bool(ep.get("butuh_autentikasi")),
            "titik_uji": ep.get("titik_uji") or "",
            "request_fields": ep.get("request_fields", []),
            "kategori": kategori,
            "alasan": kat_map,
            "sumber_kategori": "heuristik",
            "kelengkapan": _kelengkapan(ep, kategori),
        })

    # Kandidat global per origin: konfigurasi (header/TLS) & komunikasi (HTTPS).
    global_: list[dict[str, Any]] = []
    for o in sorted(origin_set):
        global_.append({"kategori": "CONF", "ruang": "origin", "origin": o,
                        "alasan": "Uji header keamanan, cookie flags, TLS, info versi."})
        global_.append({"kategori": "COMM", "ruang": "origin", "origin": o,
                        "alasan": "Uji HTTPS/redirect, sertifikat, protokol."})
        ringkas["CONF"] = ringkas.get("CONF", 0) + 1
        ringkas["COMM"] = ringkas.get("COMM", 0) + 1

    return {
        "versi": 1,
        "per_endpoint": per_endpoint,
        "global": global_,
        "ringkas_kategori": dict(sorted(ringkas.items())),
        "jumlah_endpoint": len(per_endpoint),
    }


def metadata_untuk_ai(kandidat: dict[str, Any], batas: int = 120) -> list[dict[str, Any]]:
    """Ringkasan NON-sensitif per endpoint untuk penyempurnaan AI (nama field, bukan nilai)."""
    out: list[dict[str, Any]] = []
    for e in (kandidat.get("per_endpoint") or [])[:batas]:
        out.append({
            "endpoint": e["endpoint"],
            "butuh_autentikasi": e["butuh_autentikasi"],
            "titik_uji": e["titik_uji"],
            "field": [f.get("nama", "") for f in e.get("request_fields", []) if f.get("nama")],
            "kategori": e["kategori"],
            "kelengkapan_kurang": e["kelengkapan"]["kurang"],
        })
    return out


def gabung_saran_ai(kandidat: dict[str, Any], saran: list[dict[str, Any]]) -> int:
    """Gabungkan saran AI (per endpoint) ke kandidat. Return jumlah endpoint diperbarui.

    Saran per item: { endpoint, tambah_kategori?: [..], info_kurang?: [..], catatan?: str }.
    Kategori baru ditandai `sumber_kategori` memuat 'ai'; gap tambahan masuk `kelengkapan.kurang`.
    """
    idx = {e["endpoint"]: e for e in kandidat.get("per_endpoint", [])}
    n = 0
    for s in saran or []:
        e = idx.get(s.get("endpoint"))
        if not e:
            continue
        diubah = False
        for k in s.get("tambah_kategori", []) or []:
            if k and k not in e["kategori"]:
                e["kategori"].append(k)
                e["alasan"][k] = (s.get("catatan") or "Saran AI.")[:200]
                diubah = True
        if e.get("kategori"):
            e["kategori"] = sorted(set(e["kategori"]))
        for g in s.get("info_kurang", []) or []:
            if g and g not in e["kelengkapan"]["kurang"]:
                e["kelengkapan"]["kurang"].append(g)
                diubah = True
        if diubah:
            # Hitung ulang skor kelengkapan agar konsisten dengan daftar `kurang`.
            e["kelengkapan"]["skor"] = round(max(0.0, 1.0 - 0.25 * len(e["kelengkapan"]["kurang"])), 2)
            e["sumber_kategori"] = "heuristik+ai"
            n += 1
    # Hitung ulang ringkas kategori.
    ringkas: dict[str, int] = {}
    for e in kandidat.get("per_endpoint", []):
        for k in e["kategori"]:
            ringkas[k] = ringkas.get(k, 0) + 1
    for g in kandidat.get("global", []):
        ringkas[g["kategori"]] = ringkas.get(g["kategori"], 0) + 1
    kandidat["ringkas_kategori"] = dict(sorted(ringkas.items()))
    return n
