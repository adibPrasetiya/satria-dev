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
