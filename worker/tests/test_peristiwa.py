"""Peristiwa penemuan terstruktur (visualisasi UI)."""

from satya_worker import peristiwa as pr


def test_ringkas_endpoint_membuang_contoh_dan_query():
    ep = {
        "metode_http": "POST",
        "path_template": "/api/v1/auth/login",
        "url": "https://api.contoh.id/api/v1/auth/login?token=rahasia",
        "sumber": ["browser"],
        "butuh_autentikasi": False,
        "request_fields": [{"nama": "password", "lokasi": "body", "contoh": "Sandi123!"}],
        "response_fields": [{"nama": "token"}],
        "status_terlihat": [200],
        "titik_uji": "login",
    }
    r = pr.ringkas_endpoint(ep)
    assert r["id"] == "POST /api/v1/auth/login"
    assert r["origin"] == "https://api.contoh.id"
    assert r["url"] == "https://api.contoh.id/api/v1/auth/login"
    assert r["request_fields"] == [{"nama": "password", "lokasi": "body"}]
    assert "Sandi123!" not in repr(r) and "rahasia" not in repr(r)
    assert r["response_fields"] == ["token"]


def test_pancar_dengan_data_dan_callback_lama():
    terima = []
    pr.tahap(lambda lv, p, d: terima.append((lv, p, d)), "recon", "Mencari docs…", jalur=["/openapi.json"])
    assert terima == [("info", "Mencari docs…", {"v": 1, "jenis": "tahap", "tahap": "recon", "jalur": ["/openapi.json"]})]

    lama = []
    pr.tahap(lambda lv, p: lama.append((lv, p)), "situs", "Mulai")
    assert lama == [("info", "Mulai")]


def test_pancar_endpoint_per_batch():
    batch = []
    eps = [{"metode_http": "GET", "path_template": f"/x/{i}", "url": f"http://a/x/{i}"} for i in range(45)]
    pr.pancar_endpoint(lambda lv, p, d: batch.append(d), eps)
    assert [len(b["items"]) for b in batch] == [20, 20, 5]
    assert all(b["jenis"] == "endpoint" for b in batch)


def test_ringkas_endpoint_membawa_lapisan():
    ep = {"metode_http": "GET", "path_template": "/beranda", "url": "https://a.test/beranda", "lapisan": "frontend"}
    assert pr.ringkas_endpoint(ep)["lapisan"] == "frontend"
    # Inventaris lama tanpa lapisan → dianggap API (perilaku sebelumnya).
    assert pr.ringkas_endpoint({"metode_http": "GET", "path_template": "/x", "url": "https://a.test/x"})["lapisan"] == "api"
