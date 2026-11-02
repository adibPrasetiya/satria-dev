"""Analisis statis bundle JS — ekstraksi panggilan API tanpa jaringan."""

from __future__ import annotations

from satya_worker import discovery_js as dj

BUNDLE = """
const c=axios.create({baseURL:"https://api.contoh.test/api/v1"});
c.post("/cuti",d);axios.delete(`${API}/cuti/${id}`);
fetch("/api/v1/lampiran",{method:"POST",body:f});x.open("PUT","/api/v1/profil");
request({url:"/api/v1/unit",method:"patch"});const u="/api/v1/laporan/ekspor";
document.querySelector(".btn");m.get("kunci");fetch("/assets/app.js");
"""


def test_ekstrak_metode_dan_path():
    r = dj.ekstrak(BUNDLE)
    eps = {(e["method"], e["path"]) for e in r["endpoints"]}
    assert ("POST", "/cuti") in eps
    assert ("DELETE", "/cuti/{id}") in eps
    assert ("POST", "/api/v1/lampiran") in eps
    assert ("PUT", "/api/v1/profil") in eps
    assert ("PATCH", "/api/v1/unit") in eps
    assert ("GET", "/api/v1/laporan/ekspor") in eps
    # Bukan path API: selector CSS, kunci map, berkas aset.
    assert not any(p in ("kunci", ".btn", "/assets/app.js") for _m, p in eps)
    assert r["base"] == ["https://api.contoh.test/api/v1"]


def test_rangkai_url_tanpa_menggandakan_basis():
    basis = ["https://api.contoh.test/api/v1"]
    assert dj.rangkai_url("https://app.contoh.test", basis, "/cuti") == "https://api.contoh.test/api/v1/cuti"
    assert dj.rangkai_url("https://app.contoh.test", basis, "/api/v1/unit") == "https://api.contoh.test/api/v1/unit"
    assert dj.rangkai_url("https://app.contoh.test", [], "/api/x") == "https://app.contoh.test/api/x"
