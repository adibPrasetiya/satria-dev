"""Uji check Manajemen Sesi (SESS) terhadap target palsu."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode
from tests.target_palsu import AKUN_UTAMA, TargetPalsu


def ctx_for(base: str) -> ScanContext:
    return ScanContext.from_dict(
        {
            "scan_id": "s", "aplikasi_id": "a", "base_url": base,
            "titik_uji": {
                "login": {"tersedia": True, "url": f"{base}/auth/login", "metode_http": "POST"},
                "area_terautentikasi": {"tersedia": True, "url": f"{base}/auth/me", "metode_http": "GET"},
                "logout": {"tersedia": True, "url": f"{base}/auth/logout", "metode_http": "POST"},
            },
            "form": {"login": {"field_username": "email", "field_password": "password", "tipe_body": "json"}},
            "akun_uji": [{"kunci": "akun_uji_1", "username": AKUN_UTAMA[0], "password": AKUN_UTAMA[1], "terisi": True}],
        }
    )


def metode(mid: str, check_id: str, titik: str, **extra) -> MetodeSpec:
    return MetodeSpec.from_dict(
        {"id": mid, "check_id": check_id, "titik_uji": titik, "kriteria_lulus": "k",
         "parameter": {"jumlah_sampel": 12, "entropi_minimum_bit": 64, "batas_idle_menit": 30}, **extra}
    )


AMAN_LULUS = [
    ("SESS-2.1-T01", "session.token_issued", "login", {"butuh_autentikasi": True}),
    ("SESS-2.3-T01", "session.token_entropy", "login", {}),  # token opaque acak → entropi lulus
    ("SESS-2.5-T01", "session.rotation_on_login", "login", {}),
    ("SESS-2.5-T02", "session.reject_unknown_id", "area_terautentikasi", {}),
]


@pytest.mark.parametrize("mid,cid,titik,extra", AMAN_LULUS)
def test_aman_lulus(mid, cid, titik, extra):
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode(mid, cid, titik, **extra))
    assert hasil.status == "lulus", f"{mid}: {hasil.status} — {hasil.ringkasan}"


def test_framework_fingerprint_jwt_lulus():
    with TargetPalsu("aman", jwt=True) as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.2-T01", "session.framework_fingerprint", "global"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_entropi_jwt_tdv():
    with TargetPalsu("aman", jwt=True) as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.3-T01", "session.token_entropy", "login"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_entropi_rentan_gagal():
    with TargetPalsu("rentan") as t:  # token berurutan sess-1, sess-2, ...
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.3-T01", "session.token_entropy", "login"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_rotasi_token_tetap_gagal():
    with TargetPalsu("aman", token_tetap=True) as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.5-T01", "session.rotation_on_login", "login"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_reject_unknown_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /auth/me menerima token apa pun
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.5-T02", "session.reject_unknown_id", "area_terautentikasi"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_framework_rentan_tdv(monkeypatch):
    monkeypatch.setenv("AI_SESS", "off")  # tanpa tie-breaker AI → tetap tdv
    with TargetPalsu("rentan") as t:  # token "sess-1" bukan JWT, tanpa cookie
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.2-T01", "session.framework_fingerprint", "global"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_cookie_flags_aman_lulus():
    with TargetPalsu("aman", cookie=True) as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.6-T01", "session.cookie_flags", "login"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_cookie_flags_rentan_gagal():
    with TargetPalsu("rentan", cookie=True) as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.6-T01", "session.cookie_flags", "login"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_cookie_flags_token_based_tdv():
    with TargetPalsu("aman") as t:  # tanpa cookie → sesi token
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.6-T01", "session.cookie_flags", "login"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_token_issued_tanpa_token_gagal():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
            b = b'{"success":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        hasil = jalankan_metode(ctx_for(base), metode("SESS-2.1-T01", "session.token_issued", "login", butuh_autentikasi=True))
    finally:
        srv.shutdown()
    assert hasil.status == "gagal", hasil.ringkasan


# =========================================================== logout invalidates (SESS-2.4-T01)

def test_logout_invalidates_lulus():
    with TargetPalsu("aman") as t:  # logout menghapus token di server → akses ulang 401
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.4-T01", "session.logout_invalidates", "logout"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_logout_invalidates_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /auth/me menerima token apa pun → sesi lama tetap autentik
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.4-T01", "session.logout_invalidates", "logout"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_logout_tidak_berlaku_tanpa_titik():
    ctx = ctx_for("http://127.0.0.1:1")
    del ctx.titik_uji["logout"]  # titik logout tak tersedia
    hasil = jalankan_metode(ctx, metode("SESS-2.4-T01", "session.logout_invalidates", "logout"))
    assert hasil.status == "tidak_berlaku", hasil.ringkasan


# =========================================================== idle timeout (SESS-2.4-T02)

def test_idle_opaque_tdv(monkeypatch):
    monkeypatch.setenv("AI_SESS", "off")
    with TargetPalsu("aman") as t:  # token opaque tanpa Max-Age → TTL tak terbaca
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.4-T02", "session.idle_timeout", "area_terautentikasi"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_idle_jwt_exp_pendek_lulus():
    with TargetPalsu("aman", jwt=True, jwt_exp=600) as t:  # exp 10 mnt ≤ batas 30 mnt
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.4-T02", "session.idle_timeout", "area_terautentikasi"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_idle_jwt_exp_panjang_gagal():
    with TargetPalsu("aman", jwt=True, jwt_exp=86400) as t:  # exp 24 jam ≫ batas 30 mnt
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.4-T02", "session.idle_timeout", "area_terautentikasi"))
    assert hasil.status == "gagal", hasil.ringkasan


# =========================================================== concurrent sessions (SESS-2.7-T01)

def test_concurrent_sesi_tunggal_lulus():
    with TargetPalsu("aman", sesi_tunggal=True) as t:  # login B meng-invalidasi sesi A
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.7-T01", "session.concurrent_sessions", "login"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_concurrent_kedua_aktif_tdv(monkeypatch):
    monkeypatch.setenv("AI_SESS", "off")
    with TargetPalsu("aman") as t:  # kedua sesi tetap valid → kebijakan, AI off → tdv
        hasil = jalankan_metode(ctx_for(t.base_url), metode("SESS-2.7-T01", "session.concurrent_sessions", "login"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


# =========================================================== lapisan AI tie-breaker

import satya_worker.ai as ai_pkg
from satya_worker.ai import sesi as ai_sesi


class ProviderPalsu:
    """Provider AI palsu: merekam prompt yang diterima, mengembalikan jawaban tetap."""

    nama = "palsu"
    model = "uji"

    def __init__(self, jawab):
        self._jawab = jawab
        self.prompt_terakhir = None

    def tanya_json(self, prompt, max_tokens=2000):
        self.prompt_terakhir = prompt
        return self._jawab


def test_ai_off_mengembalikan_none(monkeypatch):
    monkeypatch.setenv("AI_SESS", "off")
    putusan, info = ai_sesi.arbitrase_sesi("session.logout_invalidates", {"status_pakai_ulang": 200})
    assert putusan is None and info["mode"] == "off"


def test_ai_tanpa_provider_graceful(monkeypatch):
    monkeypatch.setenv("AI_SESS", "hemat")
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: None)
    putusan, _ = ai_sesi.arbitrase_sesi("session.logout_invalidates", {"status_pakai_ulang": 200})
    assert putusan is None  # degradasi anggun


def test_ai_putusan_tak_sah_ditolak(monkeypatch):
    monkeypatch.setenv("AI_SESS", "hemat")
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: ProviderPalsu({"putusan": "lulus"}))
    putusan, info = ai_sesi.arbitrase_sesi("session.logout_invalidates", {"status_pakai_ulang": 200})
    assert putusan is None and "galat" in info  # "lulus" bukan putusan faktual yang sah


def test_ai_redaksi_tak_bocor_rahasia(monkeypatch):
    monkeypatch.setenv("AI_SESS", "hemat")
    prov = ProviderPalsu({"putusan": "tak_pasti", "keyakinan": 0.1, "alasan": "x"})
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: prov)
    ai_sesi.arbitrase_sesi("session.logout_invalidates", {"authorization": "sup3r-s3cret-token", "status": 200})
    assert "sup3r-s3cret-token" not in (prov.prompt_terakhir or "")  # nilai berkunci sensitif disensor


def test_ai_tie_break_logout_memetakan_gagal(monkeypatch):
    # Target "aman" tapi /auth/me mengembalikan HTML 200 setelah logout → branch ambigu.
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
            if self.path == "/auth/login":
                self._send(200, '{"success":true,"accessToken":"tok-abc"}')
            else:  # logout
                self._send(200, '{"success":true}')

        def do_GET(self):  # area terautentikasi selalu balas HTML 200 (ambigu)
            self._send(200, "<html><body>dashboard pengguna</body></html>", "text/html")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("AI_SESS", "hemat")
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env",
                        lambda: ProviderPalsu({"putusan": "autentik", "keyakinan": 0.9, "alasan": "masih dashboard"}))
    try:
        hasil = jalankan_metode(ctx_for(base), metode("SESS-2.4-T01", "session.logout_invalidates", "logout"))
    finally:
        srv.shutdown()
    assert hasil.status == "gagal", hasil.ringkasan  # AI: sesi lama masih autentik → gagal
    assert hasil.menunggu_tinjauan is True
