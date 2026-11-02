"""Uji layer penemuan berbasis browser (Playwright) terhadap target palsu.

Target palsu server-rendered (punya /login berform sandi); layer browser harus merender rute,
mengklasifikasi form login, dan merekam login_page. Butuh Chromium (di-skip bila Playwright
tak tersedia)."""

from __future__ import annotations

import pytest

from satya_worker import discovery_browser as DB
from satya_worker import playwright_driver as pw
from tests.target_palsu import TargetPalsu

pytestmark = pytest.mark.skipif(not pw.tersedia(), reason="Playwright/Chromium tak tersedia")


def test_jelajah_browser_menemukan_login():
    found: dict[str, tuple] = {}

    def catat(titik, url, metode, keyakinan, catatan):
        found.setdefault(titik, (url, metode, keyakinan))

    with TargetPalsu(mode="aman") as t:
        hasil = DB.jelajah_browser(t.base_url, catat, timeout=8, maks_rute=6)

    assert hasil.get("tersedia") is True
    assert "login" in found and found["login"][0].endswith("/auth/login")
    assert "login_page" in found and found["login_page"][0].rstrip("/").endswith("/login")
    assert isinstance(hasil.get("endpoints"), list)


def test_intersep_mengungkap_post_tanpa_mengirim():
    found: dict[str, tuple] = {}

    def catat(titik, url, metode, keyakinan, catatan):
        found.setdefault(titik, (url, metode, keyakinan))

    with TargetPalsu(mode="aman") as t:
        hasil = DB.jelajah_browser(t.base_url, catat, timeout=8, maks_rute=8, intersep=True)
        diterima = list(t.post_masuk)

    tertangkap = {(r["method"], r["url"].split("?")[0].rsplit("/", 2)[-2] + "/" + r["url"].rsplit("/", 1)[-1]) for r in hasil["intersep"]}
    assert ("POST", "auth/register") in tertangkap
    # Request mutasi dibatalkan di browser → server tak pernah menerima POST apa pun.
    assert diterima == []
