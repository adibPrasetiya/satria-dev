"""Uji check Penanganan Error & Pencatatan Log (ERRL).

Check custom diuji dengan memalsukan `buat_klien`; check nuclei dengan memalsukan `nuclei_client`.
AI dinonaktifkan (AI_ERRL=off) agar verdict deterministik.
"""

from __future__ import annotations

from email.utils import formatdate

import pytest

from satya_worker import nuclei_client
from satya_worker.checks import penanganan_error as E
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx(*, endpoints=None, login=False, akun=False) -> ScanContext:
    d = {"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": endpoints or []}
    if login:
        d["titik_uji"] = {"login": {"tersedia": True, "url": f"{BASE}/api/login", "metode_http": "POST"}}
        d["form"] = {"login": {"field_username": "email", "field_password": "password", "tipe_body": "json"}}
    if akun:
        d["akun_uji"] = [{"kunci": "akun_uji_1", "username": "uji@contoh.go.id", "password": "X", "terisi": True}]
    return ScanContext.from_dict(d)


def metode(mid, check_id, engine="custom", **param):
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "global",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


class _Resp:
    def __init__(self, status, headers=None, text="", json_body=None):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = text
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class _Klien:
    def __init__(self, handler):
        self._h = handler
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def kirim(self, metode_http, url, *, json=None, data=None, content=None, headers=None, judul_bukti="", sandi_disamarkan=None):
        return self._h(metode_http, url, {"headers": headers or {}, "content": content, "json": json, "data": data})


@pytest.fixture
def fake_klien(monkeypatch):
    monkeypatch.setenv("AI_ERRL", "off")

    def pasang(handler):
        monkeypatch.setattr(E, "buat_klien", lambda c, **kw: _Klien(handler))

    return pasang


# --------------------------------------------------------------------------- 6.1-T01 verbose

_STACK = "Traceback (most recent call last):\n  File \"/app/main.py\", line 42, in handler\nValueError"


def test_verbose_bocor_gagal(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(500, text=_STACK))
    h = jalankan("error.verbose_messages", "custom", metode("ERRL-6.1-T01", "error.verbose_messages"), ctx())
    assert h.status == "gagal"


def test_verbose_bersih_lulus(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(404, text="<html><body>404 Not Found</body></html>"))
    h = jalankan("error.verbose_messages", "custom", metode("ERRL-6.1-T01", "error.verbose_messages"), ctx())
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 6.1-T02 login generik

def _login_handler(beda: bool):
    def h(mh, url, i):
        body = i["json"] or {}
        user = str(body.get("email", ""))
        tak_ada = "satya-uji-" in user
        if beda:
            return _Resp(404, json_body={"message": "user tidak ditemukan"}) if tak_ada \
                else _Resp(401, json_body={"message": "kata sandi salah"})
        return _Resp(401, json_body={"message": "kredensial tidak valid"})
    return h


def test_login_message_beda_gagal(fake_klien):
    fake_klien(_login_handler(beda=True))
    h = jalankan("error.generic_login_message", "custom",
                 metode("ERRL-6.1-T02", "error.generic_login_message"), ctx(login=True, akun=True))
    assert h.status == "gagal"


def test_login_message_generik_lulus(fake_klien):
    fake_klien(_login_handler(beda=False))
    h = jalankan("error.generic_login_message", "custom",
                 metode("ERRL-6.1-T02", "error.generic_login_message"), ctx(login=True, akun=True))
    assert h.status == "lulus"


def test_login_message_tanpa_akun_tdv(fake_klien):
    fake_klien(_login_handler(beda=False))
    h = jalankan("error.generic_login_message", "custom",
                 metode("ERRL-6.1-T02", "error.generic_login_message"), ctx(login=True, akun=False))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 6.2-T01 unhandled

_EP_BODY = [{"url": f"{BASE}/api/items", "metode_http": "POST", "lapisan": "api",
             "request_fields": [{"nama": "nama", "lokasi": "body"}]}]


def test_unhandled_crash_gagal(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(500, text="Internal Server Error"))
    h = jalankan("error.unhandled_exception", "custom",
                 metode("ERRL-6.2-T01", "error.unhandled_exception"), ctx(endpoints=_EP_BODY))
    assert h.status == "gagal"


def test_unhandled_terkendali_lulus(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(400, json_body={"message": "bad request"}))
    h = jalankan("error.unhandled_exception", "custom",
                 metode("ERRL-6.2-T01", "error.unhandled_exception"), ctx(endpoints=_EP_BODY))
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 6.7-T01 clock drift

def test_clock_drift_gagal(fake_klien):
    old = formatdate(0, usegmt=True)  # 1970 → drift raksasa
    fake_klien(lambda mh, url, i: _Resp(200, headers={"Date": old}))
    h = jalankan("time.server_clock_drift", "custom",
                 metode("ERRL-6.7-T01", "time.server_clock_drift", toleransi_detik=60), ctx())
    assert h.status == "gagal"


def test_clock_drift_lulus(fake_klien):
    import time
    now = formatdate(time.time(), usegmt=True)
    fake_klien(lambda mh, url, i: _Resp(200, headers={"Date": now}))
    h = jalankan("time.server_clock_drift", "custom",
                 metode("ERRL-6.7-T01", "time.server_clock_drift", toleransi_detik=60), ctx())
    assert h.status == "lulus"


def test_clock_drift_tanpa_date_tdv(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(200, headers={}))
    h = jalankan("time.server_clock_drift", "custom",
                 metode("ERRL-6.7-T01", "time.server_clock_drift", toleransi_detik=60), ctx())
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 6.5-T01 log files (nuclei)

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_ERRL", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


def test_log_terbuka_gagal(nuclei_fake):
    nuclei_fake([{"template_id": "exposed-log", "nama": "Exposed Laravel Log", "severity": "high",
                  "tags": ["exposure", "logs"], "url": f"{BASE}/storage/logs/laravel.log"}])
    h = jalankan("exposure.log_files", "nuclei", metode("ERRL-6.5-T01", "exposure.log_files", "nuclei"), ctx())
    assert h.status == "gagal"


def test_log_bersih_lulus(nuclei_fake):
    nuclei_fake([])
    h = jalankan("exposure.log_files", "nuclei", metode("ERRL-6.5-T01", "exposure.log_files", "nuclei"), ctx())
    assert h.status == "lulus"


def test_log_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("exposure.log_files", "nuclei", metode("ERRL-6.5-T01", "exposure.log_files", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
