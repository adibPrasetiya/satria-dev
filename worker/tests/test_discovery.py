"""Uji fase penemuan (mode eksploratif) terhadap target palsu."""

from __future__ import annotations

import pytest

from satya_worker.discovery import FormDitemukan, klasifikasi_form, temukan
from tests.target_palsu import TargetPalsu


@pytest.fixture
def target():
    with TargetPalsu("aman") as t:
        yield t


def test_temukan_klasifikasi_titik_uji(target):
    hasil = temukan(target.base_url, pakai_browser=False)
    tp = hasil["test_points"]
    # Dari landing page → login, registrasi, reset_password, area_terautentikasi.
    assert "login" in tp and tp["login"]["sumber"] == "otomatis"
    assert "registrasi" in tp
    assert "reset_password" in tp
    assert "area_terautentikasi" in tp
    # Form login & registrasi terdeteksi dengan keyakinan tinggi.
    assert tp["login"]["keyakinan"] == "tinggi"
    assert tp["registrasi"]["keyakinan"] == "tinggi"


def test_temukan_template_form(target):
    hasil = temukan(target.base_url, pakai_browser=False)
    forms = hasil["forms"]
    assert forms["login"]["field_username"] == "email"
    assert forms["login"]["field_password"] == "password"
    # Registrasi mengenali field dasar + field unik.
    assert "email" in forms["registrasi"]["field_dasar"]
    assert "email" in forms["registrasi"]["field_unik"] or "nrp" in forms["registrasi"]["field_unik"]


def test_temukan_url_action_absolut(target):
    hasil = temukan(target.base_url, pakai_browser=False)
    assert hasil["test_points"]["login"]["url"].endswith("/auth/login")
    assert hasil["test_points"]["login"]["metode_http"] == "POST"


def test_klasifikasi_form_ubah_sandi():
    form = FormDitemukan(
        action="/auth/change-password",
        method="POST",
        inputs=[{"name": "current_password", "type": "password"}, {"name": "new_password", "type": "password"}],
    )
    titik, templat = klasifikasi_form(form, "http://x/akun/ubah-sandi")
    assert titik == "ubah_password"


def test_klasifikasi_form_unggah_file():
    form = FormDitemukan(action="/upload", method="POST", inputs=[{"name": "berkas", "type": "file"}])
    titik, _ = klasifikasi_form(form, "http://x/unggah")
    assert titik == "unggah_file"


def test_ringkasan_halaman(target):
    hasil = temukan(target.base_url, pakai_browser=False)
    r = hasil["ringkasan"]
    assert r["jumlah_halaman"] >= 1
    assert "login" in r["titik_ditemukan"]


def test_ringkasan_inventaris_dan_flows(target):
    """Output baru: inventaris endpoint terpadu + alur bisnis (tanpa browser/katana/AI)."""
    hasil = temukan(target.base_url, pakai_browser=False)
    r = hasil["ringkasan"]
    assert isinstance(r.get("endpoints_lengkap"), list)
    assert r["jumlah_endpoint_unik"] == len(r["endpoints_lengkap"])
    assert isinstance(r.get("flows"), list)
    # Tanpa ctx/akun → tidak terautentikasi.
    assert r["terautentikasi"] is False
    # Endpoint login (POST) masuk inventaris lewat form HTML.
    login_eps = [
        e for e in r["endpoints_lengkap"]
        if e["metode_http"] == "POST" and e["path_template"].endswith("/auth/login")
    ]
    assert login_eps, "endpoint login harus ada di inventaris endpoint"
