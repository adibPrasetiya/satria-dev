"""Uji check Konfigurasi (CONF)."""

from __future__ import annotations

import pytest

from satya_worker import nuclei_client
from satya_worker.checks import konfigurasi as K
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx() -> ScanContext:
    return ScanContext.from_dict({"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": []})


def metode(mid, check_id, engine="custom", **param):
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "global",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


class _Resp:
    def __init__(self, status=200, headers=None, text=""):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = text


class _Klien:
    def __init__(self, resp):
        self._r = resp
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def kirim(self, metode_http, url, **kw):
        return self._r


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("AI_CONF", "off")

    def pasang(resp):
        monkeypatch.setattr(K, "buat_klien", lambda c, **kw: _Klien(resp))

    return pasang


# --------------------------------------------------------------------------- 13.1-T01 banner

def test_banner_versi_gagal(fake):
    fake(_Resp(headers={"Server": "nginx/1.18.0", "X-Powered-By": "PHP/7.4"}))
    h = jalankan("headers.server_banner", "custom", metode("CONF-13.1-T01", "headers.server_banner"), ctx())
    assert h.status == "gagal"


def test_banner_bersih_lulus(fake):
    fake(_Resp(headers={"Server": "cloudflare"}))
    h = jalankan("headers.server_banner", "custom", metode("CONF-13.1-T01", "headers.server_banner"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 13.5-T01 baseline

def test_baseline_lengkap_lulus(fake):
    fake(_Resp(headers={"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                        "Referrer-Policy": "no-referrer"}))
    h = jalankan("headers.security_baseline", "custom", metode("CONF-13.5-T01", "headers.security_baseline"), ctx())
    assert h.status == "lulus"


def test_baseline_kurang_gagal(fake):
    fake(_Resp(headers={"X-Content-Type-Options": "nosniff"}))  # tanpa framing & referrer
    h = jalankan("headers.security_baseline", "custom", metode("CONF-13.5-T01", "headers.security_baseline"), ctx())
    assert h.status == "gagal"


def test_baseline_csp_framing_lulus(fake):
    fake(_Resp(headers={"X-Content-Type-Options": "nosniff",
                        "Content-Security-Policy": "frame-ancestors 'none'", "Referrer-Policy": "same-origin"}))
    h = jalankan("headers.security_baseline", "custom", metode("CONF-13.5-T01", "headers.security_baseline"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 13.5-T02 content-type charset

def test_charset_ada_lulus(fake):
    fake(_Resp(headers={"Content-Type": "text/html; charset=utf-8"}))
    h = jalankan("headers.content_type_charset", "custom", metode("CONF-13.5-T02", "headers.content_type_charset"), ctx())
    assert h.status == "lulus"


def test_charset_hilang_gagal(fake):
    fake(_Resp(headers={"Content-Type": "text/html"}))
    h = jalankan("headers.content_type_charset", "custom", metode("CONF-13.5-T02", "headers.content_type_charset"), ctx())
    assert h.status == "gagal"


def test_charset_tanpa_ct_gagal(fake):
    fake(_Resp(headers={}))
    h = jalankan("headers.content_type_charset", "custom", metode("CONF-13.5-T02", "headers.content_type_charset"), ctx())
    assert h.status == "gagal"


# --------------------------------------------------------------------------- 13.4-T01 SRI

def test_sri_tanpa_integrity_gagal(fake):
    html = '<html><head><script src="https://cdn.other.test/lib.js"></script></head></html>'
    fake(_Resp(headers={"Content-Type": "text/html"}, text=html))
    h = jalankan("integrity.sri", "custom", metode("CONF-13.4-T01", "integrity.sri"), ctx())
    assert h.status == "gagal"


def test_sri_dengan_integrity_lulus(fake):
    html = '<script src="https://cdn.other.test/lib.js" integrity="sha384-abc" crossorigin="anonymous"></script>'
    fake(_Resp(headers={"Content-Type": "text/html"}, text=html))
    h = jalankan("integrity.sri", "custom", metode("CONF-13.4-T01", "integrity.sri"), ctx())
    assert h.status == "lulus"


def test_sri_tanpa_aset_eksternal_lulus(fake):
    html = '<script src="/local/app.js"></script><link rel="stylesheet" href="/css/app.css">'
    fake(_Resp(headers={"Content-Type": "text/html"}, text=html))
    h = jalankan("integrity.sri", "custom", metode("CONF-13.4-T01", "integrity.sri"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- nuclei (13.1-T03, 13.3)

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_CONF", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


@pytest.mark.parametrize("cid", ["conf.debug_mode", "exposure.default_sample_pages", "exposure.config_vcs_files"])
def test_nuclei_temuan_gagal(nuclei_fake, cid):
    nuclei_fake([{"template_id": "x", "nama": "Exposed", "severity": "high", "tags": ["exposure"], "url": f"{BASE}/x"}])
    h = jalankan(cid, "nuclei", metode("CONF-x", cid, "nuclei"), ctx())
    assert h.status == "gagal"


@pytest.mark.parametrize("cid", ["conf.debug_mode", "exposure.default_sample_pages", "exposure.config_vcs_files"])
def test_nuclei_bersih_lulus(nuclei_fake, cid):
    nuclei_fake([])
    h = jalankan(cid, "nuclei", metode("CONF-x", cid, "nuclei"), ctx())
    assert h.status == "lulus"


def test_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("conf.debug_mode", "nuclei", metode("CONF-13.1-T03", "conf.debug_mode", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
