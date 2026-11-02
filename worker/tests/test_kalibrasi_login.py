"""Kalibrasi titik uji: 'login_page' (halaman frontend HTML) vs 'login' (endpoint API aksi).

Memastikan check field-kata-sandi-tersamarkan memeriksa FRONTEND, bukan endpoint API, dan
discovery menginferensi halaman login frontend saat hanya endpoint API yang terpetakan.
"""

from __future__ import annotations

from satya_worker import discovery as D
from satya_worker.checks import field_sandi as FS
from satya_worker.checks.field_sandi import _tampak_api
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode
from tests.target_palsu import TargetPalsu


def test_tampak_api():
    assert _tampak_api("https://x.test/api/v1/auth/login")
    assert _tampak_api("https://x.test/v1/login")
    assert not _tampak_api("https://x.test/login")
    assert not _tampak_api("https://x.test/masuk")


def test_infer_login_page_mengembalikan_html():
    with TargetPalsu(mode="aman") as t:
        url = D._infer_login_page(t.base_url, timeout=5)
        assert url and url.rstrip("/").endswith("/login")


def _ctx_api_only(base: str) -> ScanContext:
    return ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": base,
        "titik_uji": {"login": {"tersedia": True, "url": f"{base}/api/v1/auth/login", "metode_http": "POST"}},
        "form": {"login": {"field_username": "email", "field_password": "password", "tipe_body": "json"}},
    })


def _metode_masked() -> MetodeSpec:
    return MetodeSpec.from_dict({"id": "AUTH-1.1-T02", "check_id": "auth.password_field_masked", "titik_uji": "login", "engine": "custom", "kriteria_lulus": "k"})


def test_titik_login_api_tanpa_playwright_tidak_get_api(monkeypatch):
    # Playwright tak tersedia (render None) + hanya endpoint API → tidak_dapat_diverifikasi, BUKAN GET API.
    monkeypatch.setattr(FS, "_render_dan_nilai", lambda *a, **k: None)
    ctx = _ctx_api_only("https://cuti.example.test")
    h = jalankan_metode(ctx, _metode_masked())
    assert h.status == "tidak_dapat_diverifikasi"
    assert "API" in h.ringkasan
    assert not h.bukti  # tidak ada request request/response ke endpoint API (tak menyesatkan)


def test_titik_login_api_dengan_render_frontend(monkeypatch):
    # Bila render frontend tersedia (Playwright) → hasilnya dipakai, bukan GET endpoint API.
    from satya_worker.models import HasilMetode
    monkeypatch.setattr(FS, "_render_dan_nilai", lambda ctx, url, nama, metode, bukti: HasilMetode(metode_id=metode.id, status="lulus", ringkasan="render frontend"))
    ctx = _ctx_api_only("https://cuti.example.test")
    h = jalankan_metode(ctx, _metode_masked())
    assert h.status == "lulus" and "render frontend" in h.ringkasan
