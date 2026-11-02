"""Uji pemetaan alur proses bisnis — tanpa jaringan."""

from __future__ import annotations

from satya_worker import flow_map as fm


def _ep(method, path, *, titik="api", auth=False):
    return {"metode_http": method, "path_template": path, "butuh_autentikasi": auth, "titik_uji": titik}


ENDPOINTS = [
    _ep("POST", "/api/auth/login", titik="login"),
    _ep("POST", "/api/orders", auth=True),
    _ep("GET", "/api/orders", auth=True),
    _ep("GET", "/api/orders/{id}", auth=True),
    _ep("PUT", "/api/orders/{id}", auth=True),
    _ep("DELETE", "/api/orders/{id}", auth=True),
]


def test_alur_autentikasi_ada():
    flows = fm.bangun_flows(ENDPOINTS, test_points={"login": {}})
    nama = [f["nama"] for f in flows]
    assert "Autentikasi" in nama


def test_alur_crud_terurut():
    flows = fm.bangun_flows(ENDPOINTS)
    crud = next(f for f in flows if f["nama"].startswith("Kelola"))
    ep_urut = [l["endpoint"] for l in crud["langkah"]]
    # Buat → Daftar → Detail → Ubah → Hapus.
    assert ep_urut[0] == "POST /api/orders"
    assert ep_urut.index("GET /api/orders") < ep_urut.index("GET /api/orders/{id}")
    assert ep_urut[-1] == "DELETE /api/orders/{id}"
    # Prasyarat sesi login untuk endpoint terproteksi.
    assert any(l["prasyarat"] == "sesi login" for l in crud["langkah"])


def test_alur_teramati_dari_browser():
    urutan = [
        {"method": "POST", "url": "https://x.test/api/auth/login"},
        {"method": "GET", "url": "https://x.test/api/orders"},
        {"method": "GET", "url": "https://x.test/api/orders/9"},
    ]
    flows = fm.bangun_flows(ENDPOINTS, urutan_terpantau=urutan)
    teramati = next((f for f in flows if f["sumber"] == "terpantau"), None)
    assert teramati is not None
    assert len(teramati["langkah"]) == 3


def test_tanpa_endpoint_tak_jatuh():
    assert fm.bangun_flows([]) == []
