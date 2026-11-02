"""Peristiwa uji terstruktur (animasi fase pengujian) — urutan fase & tanpa kebocoran sandi."""

from __future__ import annotations

import json

import pytest

from satya_worker.checks.https import _probe_payload_http
from satya_worker.runner import jalankan_metode
from tests.target_palsu import AKUN_UTAMA, TargetPalsu
from tests.test_auth_checks import ctx_for, metode


def _rekam():
    terima: list[dict] = []

    def log(level, pesan, data=None):
        if data is not None:
            terima.append(data)

    return terima, log


@pytest.mark.parametrize(
    "mid,check_id,titik",
    [
        ("AUTH-1.2-T01", "auth.server_side_validation", "login"),
        ("AUTH-1.2-T02", "auth.password_policy.server_side", "registrasi"),
        ("AUTH-1.6-T01", "auth.password_not_echoed", "area_terautentikasi"),
        ("AUTH-1.4-T01", "auth.lockout_threshold", "login"),
    ],
)
def test_urutan_fase_dan_tanpa_kebocoran_sandi(mid, check_id, titik):
    terima, log = _rekam()
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode(mid, check_id, titik), log=log)
    fase = [d["fase"] for d in terima]
    assert all(d["jenis"] == "uji" and d["metode_id"] == mid for d in terima)
    assert fase[0] == "mulai" and fase[-1] == "hasil"
    assert "langkah" in fase and "request" in fase
    assert terima[-1]["status"] == hasil.status
    req = next(d for d in terima if d["fase"] == "request")
    assert req["skema"] == "http" and isinstance(req["status"], int) and req["metode_http"] in ("GET", "POST")
    # Kata sandi akun uji tak pernah muncul di data peristiwa.
    assert AKUN_UTAMA[1] not in json.dumps(terima)


def test_skenario_mulai():
    terima, log = _rekam()
    with TargetPalsu("aman") as t:
        jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.7-T02", "tls.http_redirect", "login_page"), log=log)
    mulai = terima[0]
    assert mulai["fase"] == "mulai" and mulai["skenario"] == "redirect_http" and mulai["fungsi"] == "AUTH"
    assert any(d["fase"] == "langkah" and d["langkah"] == "ubah_skema" for d in terima)


def test_login_http_gagal_dengan_periksa_skema():
    terima, log = _rekam()
    with TargetPalsu("aman") as t:
        hasil = jalankan_metode(ctx_for(t.base_url), metode("AUTH-1.7-T01", "auth.login_over_https", "login"), log=log)
    assert hasil.status == "gagal"
    skema = [d["detail"]["skema"] for d in terima if d["fase"] == "langkah" and d["langkah"] == "periksa_skema"]
    assert skema == ["http", "http"]


def test_probe_payload_http_diproses_aplikasi_gagal():
    # Target palsu melayani HTTP dan memproses login (401) → payload lewat HTTP diterima aplikasi.
    terima, log = _rekam()
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx._log, ctx._metode_aktif = log, "AUTH-1.7-T01"
        hasil = _probe_payload_http(ctx, metode("AUTH-1.7-T01", "auth.login_over_https", "login"), f"{t.base_url}/auth/login")
        diterima = list(t.post_masuk)
    assert hasil.status == "gagal"
    assert diterima == ["/auth/login"]
    req = next(d for d in terima if d["fase"] == "request")
    assert req["skema"] == "http" and req["status"] == 401
    # Payload memakai kredensial acak — tak ada akun uji.
    assert AKUN_UTAMA[0] not in json.dumps(terima)
