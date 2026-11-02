"""Uji penemuan dari spesifikasi OpenAPI (tanpa jaringan)."""

from __future__ import annotations

from satya_worker.discovery_openapi import dari_openapi

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Contoh API", "version": "1.0.0"},
    "servers": [{"url": "/api/v1"}],
    "components": {
        "schemas": {
            "LoginInput": {"type": "object", "properties": {"username": {}, "password": {}}},
            "RegisterInput": {
                "type": "object",
                "properties": {"username": {}, "nama": {}, "nip": {}, "password": {}},
            },
            "PasswordInput": {"type": "object", "properties": {"password": {}}},
        }
    },
    "paths": {
        "/auth/register": {"post": {"requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/RegisterInput"}}}}}},
        "/auth/login": {"post": {"requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginInput"}}}}}},
        "/auth/me": {"get": {}},
        "/auth/logout": {"post": {}},
        "/auth/password": {"post": {"requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/PasswordInput"}}}}}},
        "/users": {"get": {}, "post": {}},
        "/uploads/{filename}": {"get": {}},
        "/health": {"get": {}},
    },
}

URL = "https://contoh.test/api/v1/docs/openapi.yaml"


def test_base_api_absolut():
    res = dari_openapi(SPEC, URL)
    assert res["ringkasan"]["base_api"] == "https://contoh.test/api/v1"


def test_klasifikasi_titik_auth():
    tp = dari_openapi(SPEC, URL)["test_points"]
    assert tp["login"]["url"] == "https://contoh.test/api/v1/auth/login"
    assert tp["login"]["metode_http"] == "POST"
    assert tp["login"]["keyakinan"] == "tinggi"
    assert tp["registrasi"]["url"].endswith("/auth/register")
    assert tp["area_terautentikasi"]["url"].endswith("/auth/me")
    assert tp["logout"]["url"].endswith("/auth/logout")
    assert tp["ubah_password"]["url"].endswith("/auth/password")
    assert tp["admin"]["url"].endswith("/users")


def test_path_berparameter_tidak_tersedia():
    tp = dari_openapi(SPEC, URL)["test_points"]
    # /uploads/{filename} punya placeholder → tandai belum siap dipakai worker.
    assert tp.get("unduh_file", {}).get("tersedia") is False or tp.get("unggah_file", {}).get("tersedia") is False


def test_form_resolve_ref():
    forms = dari_openapi(SPEC, URL)["forms"]
    assert forms["login"]["field_username"] == "username"
    assert forms["login"]["field_password"] == "password"
    assert set(forms["registrasi"]["field_dasar"]) == {"username", "nama", "nip"}
    assert "username" in forms["registrasi"]["field_unik"] or "nip" in forms["registrasi"]["field_unik"]
    assert forms["ubah_password"]["field_baru"] == "password"
