"""Uji pembungkus katana — skip anggun bila biner tak terpasang."""

from __future__ import annotations

import os

import pytest

from satya_worker import katana_client as kc


def test_disable_via_env(monkeypatch):
    monkeypatch.setenv("KATANA_ENABLE", "0")
    assert kc.tersedia() is False


def test_jalankan_tanpa_biner_kembali_kosong(monkeypatch):
    # Paksa biner tak ditemukan.
    monkeypatch.setenv("KATANA_BIN", "katana-tidak-ada-xyz")
    monkeypatch.delenv("KATANA_ENABLE", raising=False)
    assert kc.tersedia() is False
    assert kc.jalankan("https://contoh.test") == []


@pytest.mark.skipif(not kc.tersedia(), reason="biner katana tak terpasang")
def test_jalankan_nyata_bentuk_hasil():
    # Hanya berjalan bila katana benar-benar ada di PATH; verifikasi bentuk keluaran.
    hasil = kc.jalankan("https://example.com", timeout=30)
    assert isinstance(hasil, list)
    for h in hasil[:5]:
        assert "url" in h and "method" in h


def test_info_respons_dari_jsonl():
    assert kc._info_respons({"status_code": 200, "headers": {"content_type": "text/html; charset=utf-8"}}) == {
        "status": 200, "content_type": "text/html; charset=utf-8"}
    assert kc._info_respons({"headers": {"Content-Type": ["application/json"]}}) == {"content_type": "application/json"}
    assert kc._info_respons({}) == {}


def test_keluaran_dibaca_utf8(monkeypatch):
    # Windows bawaan cp1252 → karakter UTF-8 (mis. “ ” → byte 0x9d) dulu membuat thread pembaca crash.
    import subprocess

    dipanggil = {}

    def palsu(cmd, **kw):
        dipanggil.update(kw)
        baris = '{"request":{"endpoint":"https://contoh.test/berita/“judul”","method":"GET"}}'
        return subprocess.CompletedProcess(cmd, 0, stdout=baris, stderr="")

    monkeypatch.setattr(kc, "tersedia", lambda: True)
    monkeypatch.setattr(kc.subprocess, "run", palsu)
    hasil = kc.jalankan("https://contoh.test")
    assert dipanggil["encoding"] == "utf-8" and dipanggil["errors"] == "replace"
    assert hasil and "“judul”" in hasil[0]["url"]
