"""Uji seluruh check AUTH (engine custom) terhadap target palsu aman vs rentan."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode
from tests.target_palsu import AKUN_KUNCI, AKUN_UTAMA, TargetPalsu


def ctx_for(base: str) -> ScanContext:
    return ScanContext.from_dict(
        {
            "scan_id": "s",
            "aplikasi_id": "a",
            "base_url": base,
            "titik_uji": {
                "registrasi": {"tersedia": True, "url": f"{base}/auth/register", "metode_http": "POST"},
                "login": {"tersedia": True, "url": f"{base}/auth/login", "metode_http": "POST"},
                "login_page": {"tersedia": True, "url": f"{base}/login", "metode_http": "GET"},
                "area_terautentikasi": {"tersedia": True, "url": f"{base}/auth/me", "metode_http": "GET"},
                "reset_password": {"tersedia": True, "url": f"{base}/auth/forgot-password", "metode_http": "POST"},
                "ubah_password": {"tersedia": True, "url": f"{base}/auth/change-password", "metode_http": "POST"},
            },
            "form": {
                "registrasi": {"field_dasar": {"email": "uji@contoh.go.id"}, "field_sandi": "password", "field_unik": ["email"], "status_sukses": [200, 201, 202]},
                "login": {"field_username": "email", "field_password": "password", "tipe_body": "json"},
                "ubah_password": {"field_lama": "current_password", "field_baru": "new_password", "tipe_body": "json"},
                "reset_password": {"field_identitas": "email", "email": AKUN_UTAMA[0], "tipe_body": "json"},
            },
            "akun_uji": [
                {"kunci": "akun_uji_1", "username": AKUN_UTAMA[0], "password": AKUN_UTAMA[1], "terisi": True},
                {"kunci": "akun_uji_2", "username": AKUN_KUNCI[0], "password": AKUN_KUNCI[1], "terisi": True},
            ],
            "intrusif": {"izinkan_penguncian": True},
        }
    )


def metode(mid: str, check_id: str, titik: str, **extra) -> MetodeSpec:
    return MetodeSpec.from_dict(
        {
            "id": mid,
            "check_id": check_id,
            "titik_uji": titik,
            "kriteria_lulus": "kriteria",
            "parameter": {"panjang_minimum": 8, "wajib": ["huruf_besar", "huruf_kecil", "angka", "simbol"], "batas_percobaan": 5},
            **extra,
        }
    )


# (mid, check_id, titik, extra) — diuji aman→lulus, rentan→gagal.
KASUS = [
    ("AUTH-1.1-T01", "auth.login_required", "area_terautentikasi", {}),
    ("AUTH-1.1-T02", "auth.password_field_masked", "login_page", {}),
    ("AUTH-1.2-T02", "auth.password_policy.server_side", "registrasi", {}),
    ("AUTH-1.3-T01", "auth.password_policy.min_length", "registrasi", {}),
    ("AUTH-1.3-T02", "auth.password_policy.complexity", "registrasi", {}),
    ("AUTH-1.3-T04", "auth.password_policy.min_length+complexity", "ubah_password", {"butuh_autentikasi": True}),
    ("AUTH-1.4-T01", "auth.lockout_threshold", "login", {"profil": "intrusif"}),
    ("AUTH-1.5-T01", "auth.reset.no_user_enumeration", "reset_password", {}),
    ("AUTH-1.6-T01", "auth.password_not_echoed", "area_terautentikasi", {"butuh_autentikasi": True}),
]


import pytest


@pytest.mark.parametrize("mid,check_id,titik,extra", KASUS)
def test_aman_lulus(mid, check_id, titik, extra):
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode(mid, check_id, titik, **extra))
    assert hasil.status == "lulus", f"{mid}: {hasil.status} — {hasil.ringkasan}"


@pytest.mark.parametrize("mid,check_id,titik,extra", KASUS)
def test_rentan_gagal(mid, check_id, titik, extra):
    with TargetPalsu("rentan") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode(mid, check_id, titik, **extra))
    assert hasil.status == "gagal", f"{mid}: {hasil.status} — {hasil.ringkasan}"


def test_server_side_validation_aman_lulus():
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.2-T01", "auth.server_side_validation", "login"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_server_side_validation_gagal_pada_server_terima_semua():
    # Server rusak: menerima login apa pun (tanpa validasi server).
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
            body = b'{"accessToken":"x"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        hasil = jalankan_metode(ctx_for(base), metode("AUTH-1.2-T01", "auth.server_side_validation", "login"))
    finally:
        srv.shutdown()
    assert hasil.status == "gagal", hasil.ringkasan


def test_https_localhost_gagal():
    # Target http (localhost) → login_over_https & tls.http_redirect harus gagal.
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        h1 = jalankan_metode(ctx, metode("AUTH-1.7-T01", "auth.login_over_https", "login"))
        h2 = jalankan_metode(ctx, metode("AUTH-1.7-T02", "tls.http_redirect", "login"))
    assert h1.status == "gagal", h1.ringkasan
    assert h2.status == "gagal", h2.ringkasan


def test_login_over_https_lulus_bila_https():
    ctx = ScanContext.from_dict(
        {
            "scan_id": "s", "aplikasi_id": "a", "base_url": "https://app.contoh.mil.id",
            "titik_uji": {
                "login_page": {"tersedia": True, "url": "https://app.contoh.mil.id/login", "metode_http": "GET"},
                "login": {"tersedia": True, "url": "https://api.contoh.mil.id/auth/login", "metode_http": "POST"},
            },
        }
    )
    hasil = jalankan_metode(ctx, metode("AUTH-1.7-T01", "auth.login_over_https", "login"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_ubah_tanpa_akun_tidak_dapat_diverifikasi():
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx.akun_uji = []  # kosongkan
        hasil = jalankan_metode(ctx, metode("AUTH-1.3-T04", "auth.password_policy.min_length+complexity", "ubah_password", butuh_autentikasi=True))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_ubah_tanpa_izin_berisiko_tidak_mengganti_sandi():
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx.intrusif.izinkan_penguncian = False
        hasil = jalankan_metode(ctx, metode("AUTH-1.3-T04", "auth.password_policy.min_length+complexity", "ubah_password", butuh_autentikasi=True))
        diterima = list(t.post_masuk)
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan
    assert "/auth/change-password" not in diterima


def test_lockout_tanpa_izin_tidak_dapat_diverifikasi():
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx.intrusif.izinkan_penguncian = False
        hasil = jalankan_metode(ctx, metode("AUTH-1.4-T01", "auth.lockout_threshold", "login", profil="intrusif"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_check_tak_dikenal():
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("X-1", "auth.belum_ada", "login"))
    assert hasil.status == "tidak_dapat_diverifikasi"
