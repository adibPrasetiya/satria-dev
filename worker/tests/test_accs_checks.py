"""Uji check Kontrol Akses (ACCS) terhadap target palsu."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import satya_worker.ai as ai_pkg
from satya_worker.ai import akses as ai_akses
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode
from tests.target_palsu import AKUN_KUNCI, AKUN_UTAMA, TargetPalsu


def ctx_for(base: str, *, dua_akun: bool = True, admin: bool = True, form_input: bool = True,
            orders: bool = True, intrusif: bool = False) -> ScanContext:
    titik = {
        "login": {"tersedia": True, "url": f"{base}/auth/login", "metode_http": "POST"},
        "area_terautentikasi": {"tersedia": True, "url": f"{base}/auth/me", "metode_http": "GET"},
    }
    if admin:
        titik["admin"] = {"tersedia": True, "url": f"{base}/admin", "metode_http": "GET"}
    if form_input:
        titik["form_input"] = {"tersedia": True, "url": f"{base}/api/cari", "metode_http": "GET"}
    akun = [{"kunci": "akun_uji_1", "username": AKUN_UTAMA[0], "password": AKUN_UTAMA[1], "terisi": True}]
    if dua_akun:
        akun.append({"kunci": "akun_uji_2", "username": AKUN_KUNCI[0], "password": AKUN_KUNCI[1], "terisi": True})
    endpoints = []
    if orders:
        endpoints.append({"metode_http": "GET", "path_template": "/orders/{id}", "url": f"{base}/orders/1001"})
    return ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": base,
        "titik_uji": titik,
        "form": {"login": {"field_username": "email", "field_password": "password", "tipe_body": "json"}},
        "akun_uji": akun,
        "endpoints": endpoints,
        "intrusif": {"izinkan_penguncian": intrusif},
    })


def metode(mid: str, cid: str, titik: str, **extra) -> MetodeSpec:
    return MetodeSpec.from_dict(
        {"id": mid, "check_id": cid, "titik_uji": titik, "kriteria_lulus": "k",
         "parameter": {"jumlah_request": 8}, **extra}
    )


class ProviderPalsu:
    """Provider AI palsu: merekam prompt, mengembalikan jawaban tetap."""

    nama = "palsu"
    model = "uji"

    def __init__(self, jawab):
        self._jawab = jawab
        self.prompt_terakhir = None

    def tanya_json(self, prompt, max_tokens=2000):
        self.prompt_terakhir = prompt
        return self._jawab


# =========================================================== access.horizontal (ACCS-3.1-T01)

def test_horizontal_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /orders/{id} bisa dibaca siapa pun (IDOR)
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.1-T01", "access.horizontal", "area_terautentikasi"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_horizontal_aman_lulus():
    with TargetPalsu("aman") as t:  # objek akun B ditolak (403) untuk akun A
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.1-T01", "access.horizontal", "area_terautentikasi"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_horizontal_satu_akun_tdv():
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url, dua_akun=False), metode("ACCS-3.1-T01", "access.horizontal", "area_terautentikasi"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


# =========================================================== access.vertical (ACCS-3.1-T02)

def test_vertical_aman_lulus():
    with TargetPalsu("aman") as t:  # akun biasa → /admin 403
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.1-T02", "access.vertical", "admin"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_vertical_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /admin 200 untuk siapa pun
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.1-T02", "access.vertical", "admin"))
    assert hasil.status == "gagal", hasil.ringkasan


def test_vertical_tanpa_titik_admin_tidak_berlaku():
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url, admin=False), metode("ACCS-3.1-T02", "access.vertical", "admin"))
    assert hasil.status == "tidak_berlaku", hasil.ringkasan


# =========================================================== access.token_validation (ACCS-3.4-T01)

def test_token_validation_aman_lulus():
    with TargetPalsu("aman") as t:  # token dimodifikasi tak ada di 'diterbitkan' → 401
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.4-T01", "access.token_validation", "area_terautentikasi"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_token_validation_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /auth/me 200 untuk token apa pun
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.4-T01", "access.token_validation", "area_terautentikasi"))
    assert hasil.status == "gagal", hasil.ringkasan


# =========================================================== access.rate_limit (ACCS-3.2-T01)

def test_rate_limit_tanpa_izin_tdv():
    with TargetPalsu("aman", rate_limit=True) as t:  # intrusif=False → butuh persetujuan
        hasil = jalankan_metode(ctx_for(t.base_url, intrusif=False), metode("ACCS-3.2-T01", "access.rate_limit", "form_input", profil="intrusif"))
    assert hasil.status == "tidak_dapat_diverifikasi", hasil.ringkasan


def test_rate_limit_ada_429_lulus():
    with TargetPalsu("aman", rate_limit=True, rate_batas=5) as t:
        hasil = jalankan_metode(ctx_for(t.base_url, intrusif=True), metode("ACCS-3.2-T01", "access.rate_limit", "form_input", profil="intrusif"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_rate_limit_tanpa_pembatasan_gagal():
    with TargetPalsu("aman", rate_limit=False) as t:  # tak pernah 429
        hasil = jalankan_metode(ctx_for(t.base_url, intrusif=True), metode("ACCS-3.2-T01", "access.rate_limit", "form_input", profil="intrusif"))
    assert hasil.status == "gagal", hasil.ringkasan


# =========================================================== access.admin_panel_exposure (ACCS-3.3-T01)

def test_admin_exposure_aman_lulus():
    with TargetPalsu("aman") as t:  # /admin tanpa auth → 401
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.3-T01", "access.admin_panel_exposure", "admin"))
    assert hasil.status == "lulus", hasil.ringkasan


def test_admin_exposure_rentan_gagal():
    with TargetPalsu("rentan") as t:  # /admin 200 tanpa auth
        hasil = jalankan_metode(ctx_for(t.base_url), metode("ACCS-3.3-T01", "access.admin_panel_exposure", "admin"))
    assert hasil.status == "gagal", hasil.ringkasan


# =========================================================== lapisan AI tie-breaker

def test_ai_off_mengembalikan_none(monkeypatch):
    monkeypatch.setenv("AI_ACCS", "off")
    putusan, info = ai_akses.arbitrase_akses("access.vertical", {"status": 200})
    assert putusan is None and info["mode"] == "off"


def test_ai_tanpa_provider_graceful(monkeypatch):
    monkeypatch.setenv("AI_ACCS", "hemat")
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: None)
    putusan, _ = ai_akses.arbitrase_akses("access.vertical", {"status": 200})
    assert putusan is None


def test_ai_putusan_tak_sah_ditolak(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_ACCS", "hemat")
    monkeypatch.setenv("AI_ACCS_CACHE", str(tmp_path / "c.json"))
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: ProviderPalsu({"putusan": "gagal"}))
    putusan, info = ai_akses.arbitrase_akses("access.vertical", {"status": 200})
    assert putusan is None and "galat" in info  # "gagal" bukan putusan faktual yang sah


def test_ai_redaksi_tak_bocor_rahasia(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_ACCS", "hemat")
    monkeypatch.setenv("AI_ACCS_CACHE", str(tmp_path / "c.json"))
    prov = ProviderPalsu({"putusan": "tak_pasti", "keyakinan": 0.1, "alasan": "x"})
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env", lambda: prov)
    ai_akses.arbitrase_akses("access.token_validation", {"authorization": "sup3r-s3cret-token", "status": 200})
    assert "sup3r-s3cret-token" not in (prov.prompt_terakhir or "")


def test_ai_admin_exposure_html_ambigu_gagal(monkeypatch, tmp_path):
    # /admin membalas HTML 200 (ambigu) → AI 'panel_terbuka' → gagal.
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            b = b"<html><body>Admin Dashboard: kelola pengguna</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("AI_ACCS", "hemat")
    monkeypatch.setenv("AI_ACCS_CACHE", str(tmp_path / "c.json"))
    monkeypatch.setattr(ai_pkg, "muat_provider_dari_env",
                        lambda: ProviderPalsu({"putusan": "panel_terbuka", "keyakinan": 0.9, "alasan": "dashboard admin tampil"}))
    try:
        hasil = jalankan_metode(ctx_for(base), metode("ACCS-3.3-T01", "access.admin_panel_exposure", "admin"))
    finally:
        srv.shutdown()
    assert hasil.status == "gagal", hasil.ringkasan
    assert hasil.menunggu_tinjauan is True
