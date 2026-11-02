"""Uji enrichment AI discovery: redaksi, orkestrasi, fallback — tanpa jaringan."""

from __future__ import annotations

import satya_worker.ai as ai_mod
from satya_worker.ai.base import parse_json
from satya_worker.ai.redaksi import redaksi

_ENV_AI = ("AI_PROVIDER", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "AI_API_KEY", "AI_REDAKSI")


def _bersihkan_env(monkeypatch):
    for k in _ENV_AI:
        monkeypatch.delenv(k, raising=False)


def test_redaksi_menyensor_nilai_sensitif():
    payload = {
        "username": "budi",
        "password": "rahasia",
        "akun": {"token": "abc", "biasa": "ok"},
        "list": [{"api_key": "xx", "nama": "y"}],
    }
    r = redaksi(payload)
    assert r["username"] == "budi"
    assert r["password"] == "[disamarkan]"
    assert r["akun"]["token"] == "[disamarkan]"
    assert r["akun"]["biasa"] == "ok"
    assert r["list"][0]["api_key"] == "[disamarkan]"
    assert r["list"][0]["nama"] == "y"
    # Input asli tak berubah.
    assert payload["password"] == "rahasia"


def test_parse_json_toleran_code_fence():
    assert parse_json('```json\n{"a":1}\n```') == {"a": 1}
    assert parse_json('teks… {"b":2} ekor') == {"b": 2}
    assert parse_json("bukan json") is None


def test_enrich_tanpa_provider(monkeypatch):
    _bersihkan_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "none")
    hasil = ai_mod.enrich_discovery({"endpoints": []})
    assert hasil == {"tersedia": False, "provider": None}


def test_enrich_dengan_provider_tiruan(monkeypatch):
    _bersihkan_env(monkeypatch)

    class _Palsu:
        nama = "palsu"
        model = "uji-1"

        def __init__(self):
            self.terima = None

        def enrich(self, payload):
            self.terima = payload
            return {"ringkasan_risiko": "ok"}

    palsu = _Palsu()
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: palsu)

    hasil = ai_mod.enrich_discovery({"password": "rahasia", "endpoints": [1]})
    assert hasil["tersedia"] is True
    assert hasil["provider"] == "palsu" and hasil["model"] == "uji-1"
    assert hasil["isi"] == {"ringkasan_risiko": "ok"}
    # Redaksi aktif secara default → provider menerima nilai tersensor.
    assert palsu.terima["password"] == "[disamarkan]"


def test_enrich_provider_galat_anggun(monkeypatch):
    _bersihkan_env(monkeypatch)

    class _Galat:
        nama = "galat"
        model = "m"

        def enrich(self, payload):
            return {"_galat": "boom"}

    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: _Galat())
    hasil = ai_mod.enrich_discovery({"endpoints": []})
    assert hasil["tersedia"] is False
    assert hasil["galat"] == "boom"


def test_klasifikasi_endpoint_provider_tiruan(monkeypatch):
    _bersihkan_env(monkeypatch)

    class _Palsu:
        nama = "palsu"
        model = "m"

        def klasifikasi_endpoint(self, meta):
            return {"saran": [{"endpoint": "GET /x", "lapisan": "api"}]}

    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: _Palsu())
    hasil = ai_mod.klasifikasi_endpoint([{"endpoint": "GET /x"}])
    assert hasil == {"saran": [{"endpoint": "GET /x", "lapisan": "api"}], "provider": "palsu", "model": "m"}


def test_klasifikasi_endpoint_respons_rusak_diabaikan(monkeypatch):
    _bersihkan_env(monkeypatch)

    class _Rusak:
        nama = "rusak"
        model = "m"

        def klasifikasi_endpoint(self, meta):
            return {"saran": "bukan list"}

    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: _Rusak())
    assert ai_mod.klasifikasi_endpoint([]) is None


def test_gemini_teks_respons_abaikan_bagian_pemikiran():
    from types import SimpleNamespace as NS

    from satya_worker.ai.gemini import _teks_respons

    resp = NS(candidates=[NS(content=NS(parts=[NS(text="rencana…", thought=True), NS(text='{"ok": true}', thought=None), NS(text=None, thought_signature=b"x")]))])
    assert _teks_respons(resp) == '{"ok": true}'
