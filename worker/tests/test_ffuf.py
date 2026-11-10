"""Klien ffuf (opsional): parsing output & fallback anggun saat biner absen."""

from __future__ import annotations

from satya_worker import ffuf_client as ff

HASIL_JSON = """
{"commandline":"ffuf ...","time":"...","results":[
  {"input":{"FUZZ":"status"},"position":1,"status":200,"length":120,"url":"https://x/api/cuti?status=satya"},
  {"input":{"FUZZ":"page"},"position":1,"status":200,"length":118,"url":"https://x/api/cuti?page=satya"},
  {"input":{"FUZZ":"page"},"position":1,"status":200,"length":118,"url":"https://x/api/cuti?page=satya"}
],"config":{}}
"""


def test_parse_hasil_json():
    r = ff.parse_hasil_json(HASIL_JSON)
    nama = [x["input"]["FUZZ"] for x in r]
    assert nama == ["status", "page", "page"]


def test_parse_output_kotor_dan_kosong():
    assert ff.parse_hasil_json("WARN: kalibrasi\n" + HASIL_JSON)  # prefiks non-JSON diabaikan
    assert ff.parse_hasil_json("bukan json") == []
    assert ff.parse_hasil_json("") == []


def test_tersedia_hormati_disable(monkeypatch):
    monkeypatch.setenv("FFUF_ENABLE", "0")
    assert ff.tersedia() is False


def test_temukan_parameter_tanpa_biner_kosong(monkeypatch):
    # Biner absen → fungsi tak melempar & mengembalikan daftar kosong (recon tetap jalan).
    monkeypatch.setattr(ff, "tersedia", lambda: False)
    assert ff.temukan_parameter("https://x.test/api/cuti") == []
    assert ff.temukan_path("https://x.test") == []


def test_temukan_parameter_mem_parse_input_fuzz(monkeypatch):
    monkeypatch.setattr(ff, "tersedia", lambda: True)
    monkeypatch.setattr(ff, "_wordlist", lambda *a, **k: "wl.txt")
    monkeypatch.setattr(ff, "_jalankan_ffuf", lambda *a, **k: ff.parse_hasil_json(HASIL_JSON))
    nama = ff.temukan_parameter("https://x.test/api/cuti")
    assert nama == ["status", "page"]  # unik, urut kemunculan


def test_wordlist_dipangkas_agar_ffuf_tuntas(monkeypatch, tmp_path):
    # Wordlist besar dipangkas ke FFUF_WORDLIST_MAXLINES agar ffuf selesai dalam timeout (hasil tak kosong).
    besar = tmp_path / "besar.txt"
    besar.write_text("\n".join(f"p{i}" for i in range(5000)), encoding="utf-8")
    monkeypatch.setenv("FFUF_W", str(besar))
    monkeypatch.setenv("FFUF_WORDLIST_MAXLINES", "100")
    path = ff._wordlist("FFUF_W", None)
    assert path != str(besar), "wordlist besar dipangkas ke berkas sementara"
    assert sum(1 for _ in open(path, encoding="utf-8")) == 100
    # Tanpa pangkas (0) → berkas asli dipakai.
    monkeypatch.setenv("FFUF_WORDLIST_MAXLINES", "0")
    assert ff._wordlist("FFUF_W", None) == str(besar)


def test_enrich_lewati_templated_dan_hormati_maks(monkeypatch):
    from satya_worker import discovery, endpoint_map as em, ffuf_client as ffc

    dicoba: list[str] = []
    monkeypatch.setattr(ffc, "tersedia", lambda: True)
    monkeypatch.setattr(ffc, "temukan_parameter", lambda url, cookie=None: (dicoba.append(url) or ["status"]))
    monkeypatch.setenv("FFUF_MAKS_ENDPOINT", "5")
    monkeypatch.setenv("FFUF_BUDGET_TOTAL", "999")
    eps = [
        {"metode_http": "GET", "url": "https://x/api/cuti", "path_template": "/api/cuti", "lapisan": "api", "request_fields": []},
        {"metode_http": "GET", "url": "https://x/api/cuti/%7Bid%7D", "path_template": "/api/cuti/{id}", "lapisan": "api", "request_fields": []},
        {"metode_http": "POST", "url": "https://x/api/cuti", "path_template": "/api/cuti", "lapisan": "api", "request_fields": []},
    ]
    discovery._enrich_ffuf_parameter(eps, None, None)
    # Hanya GET non-templated yang difuzz; {id} & POST dilewati.
    assert dicoba == ["https://x/api/cuti"]
    assert any(f.get("nama") == "status" and f.get("lokasi") == "query" for f in eps[0]["request_fields"])
