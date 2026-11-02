"""Uji inventaris endpoint terpadu + pemetaan field — tanpa jaringan."""

from __future__ import annotations

from satya_worker import endpoint_map as em
from satya_worker.discovery_openapi import endpoint_fields

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Contoh", "version": "1.0.0"},
    "servers": [{"url": "/api/v1"}],
    "components": {
        "schemas": {
            "LoginInput": {
                "type": "object",
                "required": ["username", "password"],
                "properties": {"username": {"type": "string"}, "password": {"type": "string"}},
            }
        }
    },
    "paths": {
        "/auth/login": {
            "post": {"requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginInput"}}}}}
        },
        "/users/{id}": {
            "get": {
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "expand", "in": "query", "schema": {"type": "string"}},
                ]
            }
        },
    },
}
URL = "https://contoh.test/api/v1/openapi.json"


def test_normalisasi_path_template():
    assert em.path_template("https://x.test/api/users/42") == "/api/users/{id}"
    assert em.path_template("https://x.test/api/users/550e8400-e29b-41d4-a716-446655440000/edit") == "/api/users/{id}/edit"
    assert em.path_template("https://x.test/api/users?q=1") == "/api/users"


def test_field_dari_query_dan_body():
    q = em.field_dari_query("https://x.test/s?q=hai&page=2")
    assert {f["nama"] for f in q} == {"q", "page"}
    assert all(f["lokasi"] == "query" for f in q)
    b = em.field_dari_body('{"email":"a@b.c","umur":9}', "application/json")
    assert {f["nama"] for f in b} == {"email", "umur"}
    assert all(f["lokasi"] == "body" for f in b)


def test_openapi_endpoint_fields():
    eps = {f"{e['method']} {e['path']}": e for e in endpoint_fields(SPEC, URL)}
    login = eps["POST /auth/login"]
    nama = {f["nama"]: f for f in login["request_fields"]}
    assert "password" in nama and nama["password"]["lokasi"] == "body"
    assert nama["username"].get("wajib") is True
    user = eps["GET /users/{id}"]
    lok = {f["nama"]: f["lokasi"] for f in user["request_fields"]}
    assert lok["id"] == "path" and lok["expand"] == "query"


def test_inventaris_merge_dan_auth_inference():
    inv = em.InventarisEndpoint()
    # Sama endpoint (id berbeda) dari dua sumber → 1 entri, sumber tergabung.
    inv.tambah("GET", "https://x.test/api/users/1", sumber="browser", terautentikasi=True)
    inv.tambah("GET", "https://x.test/api/users/2", sumber="katana", terautentikasi=True)
    # Endpoint publik terlihat anonim.
    inv.tambah("GET", "https://x.test/api/health", sumber="html", terautentikasi=False)
    lst = {e["metode_http"] + " " + e["path_template"]: e for e in inv.sebagai_list()}
    users = lst["GET /api/users/{id}"]
    assert set(users["sumber"]) == {"browser", "katana"}
    assert users["butuh_autentikasi"] is True
    assert lst["GET /api/health"]["butuh_autentikasi"] is False


def test_inventaris_anonim_menang_atas_auth():
    # Endpoint terlihat anonim DAN terautentikasi → tidak butuh auth (publik).
    inv = em.InventarisEndpoint()
    inv.tambah("GET", "https://x.test/api/items", sumber="html", terautentikasi=False)
    inv.tambah("GET", "https://x.test/api/items", sumber="browser", terautentikasi=True)
    assert inv.sebagai_list()[0]["butuh_autentikasi"] is False


def test_klasifikasi_lapisan():
    base = "https://app.contoh.test"
    k = em.klasifikasi_lapisan
    assert k("GET", f"{base}/static/main.3f2a.js", base_url=base) == "aset"
    assert k("GET", f"{base}/logo", base_url=base, content_type="image/png") == "aset"
    assert k("GET", f"{base}/api/users", base_url=base) == "api"
    assert k("GET", f"{base}/v1/cuti", base_url=base) == "api"
    assert k("POST", f"{base}/login", base_url=base) == "api"
    assert k("GET", f"{base}/data", base_url=base, content_type="application/json; charset=utf-8") == "api"
    assert k("GET", "https://api.contoh.test/cuti", base_url=base) == "api"
    assert k("GET", f"{base}/dashboard", base_url=base, sumber="browser") == "api"
    assert k("GET", f"{base}/login", base_url=base) == "frontend"
    assert k("GET", f"{base}/profil/edit", base_url=base, content_type="text/html") == "frontend"


def test_inventaris_lapisan_api_menang():
    inv = em.InventarisEndpoint()
    inv.tambah("GET", "https://a.test/profil", sumber="html", lapisan="frontend")
    inv.tambah("GET", "https://a.test/profil", sumber="browser", lapisan="api")
    inv.tambah("GET", "https://a.test/beranda", sumber="html", lapisan="frontend")
    lp = {e["path_template"]: e["lapisan"] for e in inv.sebagai_list()}
    assert lp == {"/profil": "api", "/beranda": "frontend"}


def test_contoh_nilai_body_hanya_field_aman():
    b = {f["nama"]: f for f in em.field_dari_body('{"alasan":"cuti tahunan","password":"Rahasia1!","nip":"199001012020121001","jumlah":3}', "application/json")}
    assert b["alasan"]["contoh"] == "cuti tahunan" and b["jumlah"]["contoh"] == 3
    assert "contoh" not in b["password"] and "contoh" not in b["nip"]


def test_inventaris_menggabungkan_skema_dan_contoh():
    inv = em.InventarisEndpoint()
    inv.tambah("POST", "https://a.test/api/cuti", sumber="openapi",
               request_fields=[{"nama": "jenis", "lokasi": "body", "skema": {"enum": ["tahunan", "sakit"]}}])
    inv.tambah("POST", "https://a.test/api/cuti", sumber="browser", request_fields=[{"nama": "jenis", "lokasi": "body", "contoh": "sakit"}])
    f = inv.sebagai_list()[0]["request_fields"][0]
    assert f["skema"]["enum"] == ["tahunan", "sakit"] and f["contoh"] == "sakit"


def test_openapi_field_membawa_skema():
    spec = {"openapi": "3.0.0", "paths": {"/cuti": {"post": {"requestBody": {"content": {"application/json": {"schema": {
        "type": "object", "required": ["nip"], "properties": {"nip": {"type": "string", "pattern": r"^\d{18}$"}}}}}}}}}}
    f = endpoint_fields(spec, "https://a.test/openapi.json")[0]["request_fields"][0]
    assert f["wajib"] is True and f["skema"]["pattern"] == r"^\d{18}$"


def test_payload_endpoint_prioritas_contoh_skema_nama():
    from satya_worker.atribusi_sandi import payload_endpoint

    ep = {"request_fields": [
        {"nama": "jenis", "lokasi": "body", "contoh": "sakit", "skema": {"enum": ["tahunan"]}},
        {"nama": "nip", "lokasi": "body", "skema": {"pattern": r"^\d{18}$"}},
        {"nama": "email", "lokasi": "body", "contoh": "lama@contoh.id"},
        {"nama": "password", "lokasi": "body"},
        {"nama": "q", "lokasi": "query"},
    ]}
    p = payload_endpoint(ep)
    assert p["jenis"] == "sakit"                      # contoh nyata didahulukan
    assert len(p["nip"]) == 18                        # dari pola skema
    assert p["email"] != "lama@contoh.id"             # field unik selalu baru
    assert "password" not in p and "q" not in p
