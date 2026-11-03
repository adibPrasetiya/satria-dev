"""Uji check Keamanan API & Web Service (APIS).

Check custom diuji dengan memalsukan `buat_klien` (tanpa socket) + endpoint sintetis di
`ctx.endpoints`. Check nuclei diuji dengan memalsukan `nuclei_client`. AI dinonaktifkan
(AI_APIS=off) agar verdict murni deterministik.
"""

from __future__ import annotations

import pytest

from satya_worker import nuclei_client
from satya_worker.checks import api_web as A
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx(endpoints=None) -> ScanContext:
    return ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": BASE,
        "endpoints": endpoints if endpoints is not None else _eps_default(),
    })


def _eps_default():
    return [
        {"url": f"{BASE}/api/v1/users/5", "metode_http": "GET", "path_template": "/api/v1/users/{id}",
         "butuh_autentikasi": True, "lapisan": "api", "request_fields": []},
        {"url": f"{BASE}/api/v1/items", "metode_http": "POST", "path_template": "/api/v1/items",
         "butuh_autentikasi": False, "lapisan": "api",
         "request_fields": [{"nama": "nama", "lokasi": "body"}]},
    ]


def metode(mid, check_id, engine="custom", **param) -> MetodeSpec:
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "api",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


# --------------------------------------------------------------------------- fake klien

class _Resp:
    def __init__(self, status, headers=None, text=""):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = text


class _Klien:
    def __init__(self, handler):
        self._h = handler
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def kirim(self, metode_http, url, *, json=None, data=None, content=None, headers=None, judul_bukti="", sandi_disamarkan=None):
        return self._h(metode_http, url, headers or {}, content)


@pytest.fixture
def fake_klien(monkeypatch):
    monkeypatch.setenv("AI_APIS", "off")

    def pasang(handler):
        monkeypatch.setattr(A, "buat_klien", lambda c, **kw: _Klien(handler))

    return pasang


# --------------------------------------------------------------------------- APIS-12.1-T01 CORS

def test_cors_pantul_origin_gagal(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200, {"Access-Control-Allow-Origin": A._ORIGIN_UJI,
                                                 "Access-Control-Allow-Credentials": "true"}))
    h = jalankan("api.cors_policy", "custom", metode("APIS-12.1-T01", "api.cors_policy"), ctx())
    assert h.status == "gagal"


def test_cors_aman_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200, {}))  # tanpa ACAO
    h = jalankan("api.cors_policy", "custom", metode("APIS-12.1-T01", "api.cors_policy"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.1-T02 TRACE

def test_trace_aktif_gagal(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200, {"content-type": "message/http"}, "TRACE / HTTP/1.1"))
    h = jalankan("api.http_methods", "custom", metode("APIS-12.1-T02", "api.http_methods"), ctx())
    assert h.status == "gagal"


def test_trace_nonaktif_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(405))
    h = jalankan("api.http_methods", "custom", metode("APIS-12.1-T02", "api.http_methods"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.3-T01 auth

def test_auth_bocor_gagal(fake_klien):
    # Endpoint butuh_autentikasi membalas 200 tanpa token → gagal (AI off → tak disaring).
    fake_klien(lambda mh, url, h, c: _Resp(200, {}, '{"id":5}'))
    h = jalankan("api.auth_required", "custom", metode("APIS-12.3-T01", "api.auth_required"), ctx())
    assert h.status == "gagal"


def test_auth_terlindungi_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(401))
    h = jalankan("api.auth_required", "custom", metode("APIS-12.3-T01", "api.auth_required"), ctx())
    assert h.status == "lulus"


def test_auth_tanpa_endpoint_tdv(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200))
    # endpoints tanpa butuh_autentikasi
    eps = [{"url": f"{BASE}/api/v1/public", "metode_http": "GET", "lapisan": "api", "butuh_autentikasi": False}]
    h = jalankan("api.auth_required", "custom", metode("APIS-12.3-T01", "api.auth_required"), ctx(eps))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- APIS-12.4-T01 metode

def test_method_enforcement_diproses_gagal(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200))  # metode palsu diproses
    h = jalankan("api.method_enforcement", "custom", metode("APIS-12.4-T01", "api.method_enforcement"), ctx())
    assert h.status == "gagal"


def test_method_enforcement_ditolak_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(405))
    h = jalankan("api.method_enforcement", "custom", metode("APIS-12.4-T01", "api.method_enforcement"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.5-T01 skema

def test_schema_diterima_gagal(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(201))  # JSON rusak diterima
    h = jalankan("api.schema_validation", "custom", metode("APIS-12.5-T01", "api.schema_validation"), ctx())
    assert h.status == "gagal"


def test_schema_ditolak_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(400))
    h = jalankan("api.schema_validation", "custom", metode("APIS-12.5-T01", "api.schema_validation"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.5-T02 content-type

def test_content_type_diterima_gagal(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200))
    h = jalankan("api.content_type_enforcement", "custom", metode("APIS-12.5-T02", "api.content_type_enforcement"), ctx())
    assert h.status == "gagal"


def test_content_type_ditolak_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(415))
    h = jalankan("api.content_type_enforcement", "custom", metode("APIS-12.5-T02", "api.content_type_enforcement"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.6-T01 header

def test_header_api_kurang_gagal(fake_klien):
    # respons JSON tetapi tanpa nosniff
    fake_klien(lambda mh, url, h, c: _Resp(200, {"content-type": "application/json"}, '{"a":1}'))
    h = jalankan("headers.api_security_headers", "custom", metode("APIS-12.6-T01", "headers.api_security_headers"), ctx())
    assert h.status == "gagal"


def test_header_api_lengkap_lulus(fake_klien):
    fake_klien(lambda mh, url, h, c: _Resp(200, {
        "content-type": "application/json", "x-content-type-options": "nosniff",
        "cache-control": "no-store",
    }, '{"a":1}'))
    h = jalankan("headers.api_security_headers", "custom", metode("APIS-12.6-T01", "headers.api_security_headers"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- APIS-12.2-T02 nuclei

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_APIS", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


def test_exposure_terbuka_gagal(nuclei_fake):
    nuclei_fake([{"template_id": "swagger-api", "nama": "Swagger UI", "severity": "medium",
                  "tags": ["exposure", "swagger"], "url": f"{BASE}/swagger-ui.html"}])
    h = jalankan("exposure.api_docs_debug", "nuclei", metode("APIS-12.2-T02", "exposure.api_docs_debug", "nuclei"), ctx())
    assert h.status == "gagal"


def test_exposure_bersih_lulus(nuclei_fake):
    nuclei_fake([])
    h = jalankan("exposure.api_docs_debug", "nuclei", metode("APIS-12.2-T02", "exposure.api_docs_debug", "nuclei"), ctx())
    assert h.status == "lulus"


def test_exposure_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("exposure.api_docs_debug", "nuclei", metode("APIS-12.2-T02", "exposure.api_docs_debug", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
