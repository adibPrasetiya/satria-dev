"""Uji check Pengendalian Kode Berbahaya (MALC) — hanya headers.permissions_policy yang baru."""

from __future__ import annotations

import pytest

from satya_worker.checks import kode_berbahaya as M
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx() -> ScanContext:
    return ScanContext.from_dict({"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": []})


def metode():
    return MetodeSpec.from_dict({"id": "MALC-9.3-T01", "check_id": "headers.permissions_policy",
                                 "titik_uji": "global", "engine": "custom", "kriteria_lulus": "kriteria"})


class _Resp:
    def __init__(self, headers=None):
        self.status_code = 200
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = ""


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
    def pasang(resp):
        monkeypatch.setattr(M, "buat_klien", lambda c, **kw: _Klien(resp))

    return pasang


def jalankan(c):
    return cari_check("headers.permissions_policy", "custom").run(c, metode())


def test_tanpa_header_gagal(fake):
    fake(_Resp(headers={}))
    assert jalankan(ctx()).status == "gagal"


def test_membatasi_lulus(fake):
    fake(_Resp(headers={"Permissions-Policy": "camera=(), microphone=(), geolocation=(self)"}))
    assert jalankan(ctx()).status == "lulus"


def test_fitur_terbuka_gagal(fake):
    fake(_Resp(headers={"Permissions-Policy": "camera=*, microphone=()"}))
    assert jalankan(ctx()).status == "gagal"


def test_feature_policy_legasi_lulus(fake):
    fake(_Resp(headers={"Feature-Policy": "camera 'none'; microphone 'none'"}))
    assert jalankan(ctx()).status == "lulus"
