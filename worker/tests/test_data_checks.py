"""Uji check Proteksi Data (DATA).

Check custom diuji dengan memalsukan `buat_klien` (+ `login_ambil` untuk check terautentikasi);
check nuclei dengan memalsukan `nuclei_client`. AI dinonaktifkan (AI_DATA=off).
"""

from __future__ import annotations

import json as _json

import pytest

from satya_worker import nuclei_client
from satya_worker.checks import proteksi_data as D
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx(*, endpoints=None, area=False, akun=False) -> ScanContext:
    d = {"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": endpoints or []}
    if area:
        d["titik_uji"] = {
            "area_terautentikasi": {"tersedia": True, "url": f"{BASE}/api/me", "metode_http": "GET"},
            "login": {"tersedia": True, "url": f"{BASE}/api/login", "metode_http": "POST"},
        }
    if akun:
        d["akun_uji"] = [{"kunci": "akun_uji_1", "username": "uji@contoh.go.id", "password": "X", "terisi": True}]
    return ScanContext.from_dict(d)


def metode(mid, check_id, engine="custom", **param):
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "global",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


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
        return self._h(metode_http, url, {"json": json, "headers": headers or {}, "content": content})


@pytest.fixture
def fake_klien(monkeypatch):
    monkeypatch.setenv("AI_DATA", "off")

    def pasang(handler):
        monkeypatch.setattr(D, "buat_klien", lambda c, **kw: _Klien(handler))

    return pasang


# --------------------------------------------------------------------------- 7.2-T01 cache-control

@pytest.fixture
def fake_login(monkeypatch):
    monkeypatch.setattr(D, "login_ambil", lambda klien, ctx, akun, judul="": {"ok": True, "token": "t", "cookie": None, "resp": None})


def test_cache_no_store_lulus(fake_klien, fake_login):
    fake_klien(lambda mh, url, i: _Resp(200, headers={"Cache-Control": "no-store, private"}))
    h = jalankan("headers.cache_control_sensitive", "custom",
                 metode("DATA-7.2-T01", "headers.cache_control_sensitive"), ctx(area=True, akun=True))
    assert h.status == "lulus"


def test_cache_tanpa_no_store_gagal(fake_klien, fake_login):
    fake_klien(lambda mh, url, i: _Resp(200, headers={"Cache-Control": "max-age=3600"}))
    h = jalankan("headers.cache_control_sensitive", "custom",
                 metode("DATA-7.2-T01", "headers.cache_control_sensitive"), ctx(area=True, akun=True))
    assert h.status == "gagal"


def test_cache_tanpa_akun_tdv(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(200))
    h = jalankan("headers.cache_control_sensitive", "custom",
                 metode("DATA-7.2-T01", "headers.cache_control_sensitive"), ctx(area=True, akun=False))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 7.4-T01 mass assignment

_EP_BODY = [{"url": f"{BASE}/api/users", "metode_http": "POST", "lapisan": "api",
             "request_fields": [{"nama": "nama", "lokasi": "body"}]}]


def test_mass_assignment_refleksi_gagal(fake_klien):
    # Server menggaungkan body (termasuk role=sentinel) → mass assignment.
    fake_klien(lambda mh, url, i: _Resp(201, text=_json.dumps(i["json"] or {})))
    h = jalankan("input.unexpected_parameters", "custom",
                 metode("DATA-7.4-T01", "input.unexpected_parameters"), ctx(endpoints=_EP_BODY))
    assert h.status == "gagal"


def test_mass_assignment_diabaikan_lulus(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(201, text='{"id":1,"ok":true}'))
    h = jalankan("input.unexpected_parameters", "custom",
                 metode("DATA-7.4-T01", "input.unexpected_parameters"), ctx(endpoints=_EP_BODY))
    assert h.status == "lulus"


def test_mass_assignment_ditolak_tdv(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(400, text='{"error":"field wajib kurang"}'))
    h = jalankan("input.unexpected_parameters", "custom",
                 metode("DATA-7.4-T01", "input.unexpected_parameters"), ctx(endpoints=_EP_BODY))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 7.4-T02 duplicate params

_EP_GET = [{"url": f"{BASE}/api/search?q=a", "metode_http": "GET", "lapisan": "api"}]


def test_duplicate_crash_gagal(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(500, text="error"))
    h = jalankan("input.duplicate_parameters", "custom",
                 metode("DATA-7.4-T02", "input.duplicate_parameters"), ctx(endpoints=_EP_GET))
    assert h.status == "gagal"


def test_duplicate_konsisten_lulus(fake_klien):
    fake_klien(lambda mh, url, i: _Resp(200, text="[]"))
    h = jalankan("input.duplicate_parameters", "custom",
                 metode("DATA-7.4-T02", "input.duplicate_parameters"), ctx(endpoints=_EP_GET))
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 7.5-T01 backup (nuclei)

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_DATA", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


def test_backup_terbuka_gagal(nuclei_fake):
    nuclei_fake([{"template_id": "backup-zip", "nama": "Exposed Backup", "severity": "high",
                  "tags": ["backup", "exposure"], "url": f"{BASE}/backup.zip"}])
    h = jalankan("exposure.backup_files", "nuclei", metode("DATA-7.5-T01", "exposure.backup_files", "nuclei"), ctx())
    assert h.status == "gagal"


def test_backup_bersih_lulus(nuclei_fake):
    nuclei_fake([])
    h = jalankan("exposure.backup_files", "nuclei", metode("DATA-7.5-T01", "exposure.backup_files", "nuclei"), ctx())
    assert h.status == "lulus"


def test_backup_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("exposure.backup_files", "nuclei", metode("DATA-7.5-T01", "exposure.backup_files", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
