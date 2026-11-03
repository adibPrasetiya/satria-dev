"""Peristiwa uji terstruktur (fase pengujian) untuk animasi graf di UI.

Menumpang pada log task yang sama dengan peristiwa penemuan (`peristiwa.pancar`):
`data = {"v": 1, "jenis": "uji", "fase": ..., "metode_id": ...}`. Fase:
  mulai    {check_id, fungsi, judul, skenario}       — dipancarkan runner sebelum check
  langkah  {langkah, label, detail}                  — dipancarkan check (`ctx.langkah`)
  request  {no, metode_http, url, skema, host, lapisan, field, status, alasan, lokasi, durasi_ms}
                                                     — otomatis dari `KlienScan.kirim`
  hasil    {status, ringkasan}                       — dipancarkan runner sesudah check
Tidak ada nilai kata sandi/token yang dipancarkan: payload diringkas lewat `payload_aman`.
Lihat frontend `lib/pengujian/uji.ts`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from . import peristiwa as pr

# Jenis adegan animasi per check (frontend memilih tata letak graf dari sini).
SKENARIO = {
    "auth.login_required": "akses_terproteksi",
    "auth.password_field_masked": "field_sandi",
    "auth.server_side_validation": "payload_server",
    "auth.password_policy.server_side": "kebijakan_sandi",
    "auth.password_policy.min_length": "kebijakan_sandi",
    "auth.password_policy.complexity": "kebijakan_sandi",
    "auth.password_policy.min_length+complexity": "kebijakan_sandi",
    "auth.lockout_threshold": "lockout",
    "auth.reset.no_user_enumeration": "enumerasi_reset",
    "auth.password_not_echoed": "echo_sandi",
    "auth.login_over_https": "kanal_https",
    "tls.http_redirect": "redirect_http",
    # Keamanan Komunikasi (COMM) — kanal TLS & sertifikat (pakai skenario generik/kanal yang ada).
    "tls.https_enforced": "kanal_https",
    "headers.hsts": "header_keamanan",
    "tls.protocol_versions": "kanal_https",
    "tls.weak_ciphers": "kanal_https",
    "tls.certificate_validity": "kanal_https",
    "tls.certificate_browser_trust": "kanal_https",
    "tls.certificate_issuer_psre": "kanal_https",
    # Validasi Input (INPV) — sapuan seluruh endpoint (lihat satya_worker/inpv).
    "input.server_side_validation": "validasi_input",
    "input.reject_on_error": "validasi_input",
    "input.allowlist_validation": "validasi_input",
    "input.runtime_known_cves": "versi_runtime",
    "headers.csp": "header_keamanan",
    "zap.active.injection_policy": "pemindaian_aktif",
    "zap.active.code_injection_policy": "pemindaian_aktif",
    "zap.active.xss_policy": "pemindaian_aktif",
    "zap.active.sqli_policy": "pemindaian_aktif",
}

_SENSITIF = re.compile(r"(password|passwd|sandi|token|secret|authorization|api[_-]?key|cookie|otp)", re.IGNORECASE)


def pancar(log: Any, metode_id: str, fase: str, pesan: str, level: str = "info", **isi: Any) -> None:
    pr.pancar(log, pesan, {"jenis": "uji", "fase": fase, "metode_id": metode_id, **isi}, level=level)


def mulai(log: Any, metode: Any) -> None:
    pancar(
        log, metode.id, "mulai",
        f"▶ {metode.id} — {metode.nama or metode.check_id} (titik: {metode.titik_uji})",
        check_id=metode.check_id,
        fungsi=metode.id.split("-", 1)[0],
        judul=(metode.nama or metode.check_id)[:160],
        titik_uji=metode.titik_uji,
        skenario=SKENARIO.get(metode.check_id, "generik"),
    )


def hasil(log: Any, metode: Any, h: Any) -> None:
    # Pesan kosong: backend sudah menulis baris ringkasan hasil ke log saat menerima hasil task;
    # peristiwa ini hanya membawa data verdict untuk animasi (UI menyembunyikan baris kosong).
    pancar(log, metode.id, "hasil", "", status=h.status, ringkasan=(h.ringkasan or "")[:300])


def payload_aman(body: Optional[dict[str, Any]], tampilkan: Iterable[str] = ()) -> dict[str, str]:
    """Ringkas payload untuk UI: nilai field sensitif disamarkan, kecuali kunci di `tampilkan`
    (mis. kata sandi LEMAH buatan uji yang memang bukan rahasia)."""
    boleh = set(tampilkan)
    out: dict[str, str] = {}
    for k, v in list((body or {}).items())[:20]:
        k = str(k)[:60]
        if _SENSITIF.search(k) and k not in boleh:
            out[k] = "[disamarkan]"
        else:
            out[k] = str(v)[:60]
    return out


def ringkas_request(no: int, metode_http: str, url: str, body: Optional[dict[str, Any]], resp: Any,
                    durasi_ms: int, galat: Optional[str] = None) -> dict[str, Any]:
    """Metadata satu request untuk animasi (tanpa nilai body/respons)."""
    from urllib.parse import urlsplit

    from .endpoint_map import klasifikasi_lapisan

    p = urlsplit(url)
    info: dict[str, Any] = {
        "no": no,
        "metode_http": metode_http.upper(),
        "url": pr.tanpa_query(url),
        "skema": p.scheme.lower(),
        "host": p.hostname or "",
        "lapisan": klasifikasi_lapisan(metode_http, url),
        "field": [str(k)[:60] for k in list((body or {}).keys())[:20]],
        "durasi_ms": durasi_ms,
        "status": None,
    }
    if resp is not None:
        info["status"] = resp.status_code
        info["alasan"] = resp.reason_phrase
        lokasi = resp.headers.get("location", "")
        if lokasi:
            info["lokasi"] = pr.tanpa_query(lokasi)
        info["content_type"] = resp.headers.get("content-type", "").split(";", 1)[0][:60]
    if galat:
        info["galat"] = galat
    return info
