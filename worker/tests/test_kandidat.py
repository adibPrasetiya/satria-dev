"""Uji pemetaan kandidat uji dari inventaris discovery + helper ScanContext."""

from __future__ import annotations

from satya_worker import kandidat as kd
from satya_worker.models import ScanContext

_INV = [
    {
        "metode_http": "POST", "path_template": "/api/v1/auth/login",
        "url": "https://x/api/v1/auth/login", "titik_uji": "login",
        "content_type": "application/json", "status_terlihat": [200],
        "request_fields": [
            {"nama": "username", "lokasi": "body"}, {"nama": "password", "lokasi": "body"},
        ],
    },
    {
        "metode_http": "GET", "path_template": "/api/v1/users/{id}",
        "url": "https://x/api/v1/users/1", "butuh_autentikasi": True,
        "status_terlihat": [200], "request_fields": [],
    },
    {
        "metode_http": "POST", "path_template": "/api/v1/upload",
        "url": "https://x/api/v1/upload", "titik_uji": "unggah_file",
        "content_type": "multipart/form-data", "request_fields": [{"nama": "berkas", "lokasi": "body"}],
    },
]


def test_kategori_per_endpoint():
    peta = kd.petakan_kandidat(_INV)
    byep = {e["endpoint"]: e for e in peta["per_endpoint"]}

    login = byep["POST /api/v1/auth/login"]
    assert {"AUTH", "SESS", "INPV", "ERRL", "APIS", "DATA"}.issubset(set(login["kategori"]))

    users = byep["GET /api/v1/users/{id}"]
    assert "ACCS" in users["kategori"]  # butuh auth + {id} (IDOR)
    assert "butuh_akun_uji_untuk_verifikasi_akses" in users["kelengkapan"]["kurang"]

    upload = byep["POST /api/v1/upload"]
    assert "FILE" in upload["kategori"]


def test_kandidat_global_dan_ringkas():
    peta = kd.petakan_kandidat(_INV)
    kategori_global = {g["kategori"] for g in peta["global"]}
    assert {"CONF", "COMM"}.issubset(kategori_global)
    assert peta["ringkas_kategori"].get("INPV", 0) >= 1


def test_metadata_ai_tanpa_nilai():
    peta = kd.petakan_kandidat(_INV)
    meta = kd.metadata_untuk_ai(peta)
    # Hanya nama field, tak ada nilai/contoh.
    assert meta[0]["field"] == ["username", "password"]
    assert "contoh" not in str(meta)


def test_gabung_saran_ai():
    peta = kd.petakan_kandidat(_INV)
    n = kd.gabung_saran_ai(peta, [
        {"endpoint": "GET /api/v1/users/{id}", "tambah_kategori": ["DATA"],
         "info_kurang": ["skema_respons_tak_diketahui"], "catatan": "mengembalikan data pengguna"},
    ])
    assert n == 1
    users = next(e for e in peta["per_endpoint"] if e["endpoint"] == "GET /api/v1/users/{id}")
    assert "DATA" in users["kategori"] and users["sumber_kategori"] == "heuristik+ai"
    assert "skema_respons_tak_diketahui" in users["kelengkapan"]["kurang"]
    # Skor dihitung ulang: 2 gap (butuh_akun_uji… + skema_respons…) → 1.0 - 0.25*2 = 0.5.
    assert users["kelengkapan"]["skor"] == 0.5


def test_scancontext_kandidat_untuk():
    peta = kd.petakan_kandidat(_INV)
    ctx = ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": "https://x",
        "kandidat_uji": peta, "endpoints": _INV,
    })
    inpv = ctx.kandidat_untuk("INPV")
    assert any(e["endpoint"] == "POST /api/v1/auth/login" for e in inpv)
    assert ctx.kandidat_untuk("TIDAKADA") == []
    assert len(ctx.endpoints) == 3
