"""Uji engine playwright + fallback browser.

Fungsi penilaian bersifat murni (tanpa browser). Jalur yang butuh browser diuji lewat
monkeypatch (driver.tersedia / login_browser) sehingga tidak memerlukan Chromium saat CI.
"""

from __future__ import annotations

import pytest

from satya_worker import playwright_driver as pw
from satya_worker import sesi
from satya_worker.checks import playwright_scan as P
from satya_worker.models import AkunUji, MetodeSpec, ScanContext
from satya_worker.registry import cari_check
from satya_worker.sesi import buat_klien


def metode(check_id: str, **extra) -> MetodeSpec:
    return MetodeSpec.from_dict(
        {"id": check_id, "check_id": check_id, "titik_uji": extra.pop("titik", "global"),
         "engine": "playwright", "kriteria_lulus": "k", **extra}
    )


def ctx_dasar(**extra) -> ScanContext:
    d = {"scan_id": "s", "aplikasi_id": "a", "base_url": "https://app.satria.pro", **extra}
    return ScanContext.from_dict(d)


# --------------------------------------------------------------------------- registry

def test_semua_check_playwright_terdaftar():
    for cid in P.PETA:
        assert cari_check(cid, "playwright") is not None, cid


# --------------------------------------------------------------------------- klasifikasi_skrip

def test_skrip_host_sendiri_dan_subdomain_lolos():
    s = ["https://app.satria.pro/a.js", "https://cdn.app.satria.pro/b.js", "/rel.js"]
    tak, flag = P.klasifikasi_skrip(s, "app.satria.pro", P._DEFAULT_DIIZINKAN, P._DEFAULT_DITANDAI)
    assert tak == [] and flag == []


def test_skrip_diizinkan_vs_ditandai_vs_takdikenal():
    s = [
        "https://cdn.jsdelivr.net/x.js",            # diizinkan
        "https://www.google-analytics.com/ga.js",   # ditandai
        "https://evil.example.com/track.js",         # tak dikenal
    ]
    tak, flag = P.klasifikasi_skrip(s, "app.satria.pro", P._DEFAULT_DIIZINKAN, P._DEFAULT_DITANDAI)
    assert any("evil.example.com" in u for u in tak)
    assert any("google-analytics" in u for u in flag)
    assert all("jsdelivr" not in u for u in tak + flag)


# --------------------------------------------------------------------------- pindai_storage

def test_storage_tandai_sandi_dan_key_sensitif_tapi_bukan_token():
    storage = {
        "localStorage": {"access_token": "eyJhbG.sig.part", "user_password": "x", "nama": "Budi"},
        "sessionStorage": {"bocor": "RahasiaKu123!"},
    }
    temuan = P.pindai_storage(storage, rahasia=["RahasiaKu123!"])
    # nilai rahasia terdeteksi + key 'user_password' terdeteksi; token sesi TIDAK ditandai
    assert any("bocor" in t for t in temuan)
    assert any("user_password" in t for t in temuan)
    assert not any("access_token" in t for t in temuan)


# --------------------------------------------------------------------------- evaluasi_*

def test_evaluasi_skrip_lulus_dan_gagal():
    m = metode("deps.unknown_third_party_scripts")
    lulus = P.evaluasi_skrip(m, ["https://app.satria.pro/a.js"], "app.satria.pro", P._DEFAULT_DIIZINKAN, P._DEFAULT_DITANDAI, muat_ok=True)
    assert lulus.status == "lulus"
    gagal = P.evaluasi_skrip(m, ["https://evil.example.com/a.js"], "app.satria.pro", P._DEFAULT_DIIZINKAN, P._DEFAULT_DITANDAI, muat_ok=True)
    assert gagal.status == "gagal" and gagal.bukti


def test_evaluasi_izin():
    m = metode("privacy.permission_prompts")
    assert P.evaluasi_izin(m, [], muat_ok=True).status == "lulus"
    assert P.evaluasi_izin(m, ["permissions.query:geolocation"], muat_ok=True).status == "lulus"  # query ≠ prompt
    assert P.evaluasi_izin(m, ["geolocation"], muat_ok=True).status == "gagal"


def test_evaluasi_storage():
    m = metode("data.browser_storage", titik="area_terautentikasi")
    assert P.evaluasi_storage(m, {"localStorage": {}}, [], login_ok=True).status == "lulus"
    assert P.evaluasi_storage(m, {}, [], login_ok=False).status == "tidak_dapat_diverifikasi"
    bocor = {"localStorage": {"pw": "secret"}}
    assert P.evaluasi_storage(m, bocor, ["secret"], login_ok=True).status == "gagal"


def test_nilai_reset():
    assert P._nilai_reset("Kata sandi minimal 8 karakter", "u/r", "u/r") == "tolak"
    assert P._nilai_reset("Berhasil, silakan login", "u/reset", "u/login") == "terima"
    assert P._nilai_reset("", "u/reset", "u/reset") == "tolak"  # tetap di halaman reset
    assert P._nilai_reset("halaman netral", "u/reset", "u/lain") == "ambigu"


# --------------------------------------------------------------------------- Playwright tak terpasang

def test_check_global_tanpa_playwright(monkeypatch):
    monkeypatch.setattr(P.pw, "tersedia", lambda: False)
    h = P._jalankan(ctx_dasar(), metode("privacy.permission_prompts"))
    assert h.status == "tidak_dapat_diverifikasi"


def test_check_reset_tanpa_playwright_minta_tinjauan(monkeypatch):
    monkeypatch.setattr(P.pw, "tersedia", lambda: False)
    m = metode("auth.reset.token_single_use_expiry", titik="reset_password")
    h = P._jalankan(ctx_dasar(), m)
    assert h.status == "tidak_dapat_diverifikasi" and h.menunggu_tinjauan


# --------------------------------------------------------------------------- fallback browser di sesi

def test_sesi_fallback_browser_suntik_token(monkeypatch):
    monkeypatch.setattr(pw, "tersedia", lambda: True)
    monkeypatch.setattr(
        pw, "login_browser",
        lambda ctx, akun: {"ok": True, "token": "TKN123", "cookie": {"name": "sid", "value": "v", "flags": "secure httponly samesite"}, "cookies": [{"name": "sid", "value": "v", "domain": "app.satria.pro"}], "storage": {}},
    )
    ctx = ctx_dasar(titik_uji={"login": {"tersedia": True, "url": "https://app.satria.pro/login"}})
    akun = AkunUji(kunci="utama", username="u@x.go.id", password="p", terisi=True)
    with buat_klien(ctx) as klien:
        art = sesi._coba_browser(klien, ctx, akun)
        assert art is not None and art["ok"] and art["token"] == "TKN123"
        assert klien._klien.headers.get("Authorization") == "Bearer TKN123"


def test_sesi_fallback_nonaktif_tanpa_playwright(monkeypatch):
    monkeypatch.setattr(pw, "tersedia", lambda: False)
    ctx = ctx_dasar()
    akun = AkunUji(kunci="utama", username="u", password="p", terisi=True)
    with buat_klien(ctx) as klien:
        assert sesi._coba_browser(klien, ctx, akun) is None
