"""Pemetaan endpoint → titik uji & template form untuk SPA tanpa OpenAPI (kasus rai-edu.com):
template dari body request nyata, cadangan dari inventaris endpoint, area terautentikasi = API."""

from __future__ import annotations

import pytest

import satya_worker.ai as ai_mod
from satya_worker.discovery import _endpoint_terproteksi, templat_dari_field
from satya_worker.discovery_browser import petakan_titik_intersep, templat_bukti
from satya_worker.runner import jalankan_metode
from tests.target_palsu import TargetPalsu
from tests.test_auth_checks import ctx_for, metode


@pytest.fixture(autouse=True)
def _tanpa_ai(monkeypatch):
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)


BODY_REG = [{"nama": "name", "lokasi": "body", "tipe": "str"}, {"nama": "email", "lokasi": "body", "tipe": "str"},
            {"nama": "password", "lokasi": "body", "tipe": "str"}]


def test_templat_registrasi_dari_field_body():
    t = templat_dari_field("registrasi", BODY_REG, "application/json")
    assert t["field_sandi"] == "password"
    assert set(t["field_dasar"]) == {"name", "email"}
    assert t["field_unik"] == ["email"]
    assert t["tipe_body"] == "json"
    assert t["skema_field"]["name"]["type"] == "string"


def test_templat_registrasi_dengan_konfirmasi_dan_form_urlencoded():
    t = templat_dari_field("registrasi", ["nip", "password", "password_confirmation"], "application/x-www-form-urlencoded")
    assert t["field_sandi"] == "password"
    assert t["field_konfirmasi"] == "password_confirmation"
    assert t["field_unik"] == ["nip"]
    assert t["tipe_body"] == "form"


def test_templat_login_dan_reset():
    assert templat_dari_field("login", ["email", "password"]) == {"field_username": "email", "field_password": "password", "tipe_body": "json"}
    assert templat_dari_field("reset_password", ["email"])["field_identitas"] == "email"
    # Body bersandi = konfirmasi reset (token + sandi baru), bukan permintaan reset.
    assert templat_dari_field("reset_password", ["token", "password"]) is None
    assert templat_dari_field("registrasi", ["name", "email"]) is None  # tanpa sandi bukan registrasi


def test_intersep_menghasilkan_template_registrasi():
    catatan: dict = {}
    hasil = [{"method": "POST", "url": "https://api.x.test/api/users/register", "asal": "https://x.test/register",
              "content_type": "application/json", "fields": BODY_REG}]
    terpilih = petakan_titik_intersep(hasil, {"https://x.test/register": "registrasi"},
                                      lambda titik, url, m, k, c: catatan.setdefault(titik, (m, url, k)))
    assert catatan["registrasi"] == ("POST", "https://api.x.test/api/users/register", "tinggi")
    forms, url_form = {}, {}
    for titik, rec in terpilih.items():
        templat_bukti(titik, rec, forms, url_form, rec["fields"])
    assert forms["registrasi"]["field_sandi"] == "password"
    assert url_form["registrasi"] == "POST https://api.x.test/api/users/register"


def test_form_untuk_disusun_dari_inventaris_endpoint():
    ctx = ctx_for("https://x.test")
    ctx.form.pop("registrasi")
    ctx.endpoints = [{"metode_http": "POST", "url": "https://x.test/auth/register", "content_type": "application/json",
                      "request_fields": BODY_REG}]
    f = ctx.form_untuk("registrasi")
    assert f is not None and f.field_sandi == "password" and set(f.field_dasar) == {"name", "email"}
    # Template yang sudah dikonfigurasi tetap diutamakan.
    assert ctx.form_untuk("login") is ctx.form["login"]


def test_area_terautentikasi_memilih_api_terproteksi():
    eps = [
        {"metode_http": "GET", "path_template": "/api/packages", "url": "https://api.x.test/api/packages", "lapisan": "api", "status_terlihat": [200]},
        {"metode_http": "GET", "path_template": "/api/orders/{id}", "url": "https://api.x.test/api/orders/7", "lapisan": "api", "butuh_autentikasi": True},
        {"metode_http": "GET", "path_template": "/api/users/history", "url": "https://api.x.test/api/users/history", "lapisan": "api", "status_terlihat": [401]},
        {"metode_http": "GET", "path_template": "/api/users/me", "url": "https://api.x.test/api/users/me", "lapisan": "api", "butuh_autentikasi": True},
        {"metode_http": "GET", "path_template": "/dashboard", "url": "https://x.test/dashboard", "lapisan": "frontend", "butuh_autentikasi": True},
    ]
    assert _endpoint_terproteksi(eps)["path_template"] == "/api/users/me"
    assert _endpoint_terproteksi(eps[:1]) is None


def test_kebijakan_sandi_berjalan_tanpa_template_dari_inventaris():
    # Hasil penemuan lama: `forms` kosong, tetapi inventaris punya field body endpoint registrasi.
    with TargetPalsu("rentan") as t:
        ctx = ctx_for(t.base_url)
        ctx.form.pop("registrasi")
        ctx.endpoints = [{"metode_http": "POST", "url": f"{t.base_url}/auth/register", "content_type": "application/json",
                          "request_fields": [{"nama": "email", "lokasi": "body"}, {"nama": "password", "lokasi": "body"}]}]
        h = jalankan_metode(ctx, metode("AUTH-1.3-T01", "auth.password_policy.min_length", "registrasi"))
    assert h.status == "gagal", h.ringkasan


def test_tanpa_field_pesan_menyebut_endpoint():
    with TargetPalsu("aman") as t:
        ctx = ctx_for(t.base_url)
        ctx.form.pop("registrasi")
        h = jalankan_metode(ctx, metode("AUTH-1.3-T01", "auth.password_policy.min_length", "registrasi"))
    assert h.status == "tidak_dapat_diverifikasi"
    assert "/auth/register" in h.ringkasan and "field body" in h.ringkasan


def test_endpoint_js_dipindah_ke_origin_api_dan_get_palsu_dibuang():
    from satya_worker.discovery import _metode_js_terbantah, _rebase_js

    rb = {"request_detail": [{"method": "GET", "url": "https://api.x.test/api/packages?page=1"}],
          "intersep": [{"method": "POST", "url": "https://api.x.test/api/users/register"}]}
    assert _rebase_js("https://x.test/api/users/me", "https://x.test", rb) == "https://api.x.test/api/users/me"
    assert _rebase_js("https://x.test/assets/a.json", "https://x.test", rb) == "https://x.test/assets/a.json"
    assert _rebase_js("https://x.test/api/users/me", "https://x.test", {}) == "https://x.test/api/users/me"
    assert _metode_js_terbantah("GET", "https://api.x.test/api/users/register", rb) is True
    assert _metode_js_terbantah("GET", "https://api.x.test/api/users/me", rb) is False
    assert _metode_js_terbantah("POST", "https://api.x.test/api/users/register", rb) is False


def test_berkas_build_framework_bukan_backend():
    from satya_worker.endpoint_map import klasifikasi_lapisan

    for u in ("https://x.test/_app/version.json", "https://x.test/_next/data/b/i.json", "https://x.test/manifest.json"):
        assert klasifikasi_lapisan("GET", u, base_url="https://x.test", sumber="js") == "aset", u
    assert klasifikasi_lapisan("GET", "https://x.test/api/config.json", base_url="https://x.test", sumber="js") == "api"
