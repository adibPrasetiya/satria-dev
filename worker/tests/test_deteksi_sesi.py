"""Uji deteksi token berbasis bentuk-nilai (lepas dari nama key)."""

from __future__ import annotations

from satya_worker import deteksi_sesi as d

_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123DEF-_x"
_UUID = "3ce417ee-410c-416b-9c35-b49bb9be929d"


def test_bentuk_token():
    assert d.bentuk_token(_JWT) == "jwt"
    assert d.bentuk_token(_UUID) == "uuid"
    assert d.bentuk_token("A1b2C3d4E5f6G7h8J9k0") == "opaque"  # 20 char, entropi campur
    assert d.bentuk_token("dark") is None
    assert d.bentuk_token("beranda-pengguna-aktif") is None  # kata biasa, tanpa entropi token
    assert d.bentuk_token("") is None


def test_token_app_named_terdeteksi():
    """Kasus nyata: key diberi prefiks aplikasi (`cuti.session`) tetap terdeteksi."""
    st = {"localStorage": {"cuti.session": _UUID, "cuti.user": '{"id":1,"username":"admin"}'}}
    assert d.cari_token_nilai(st) == _UUID


def test_prioritas_jwt_di_atas_uuid():
    st = {"localStorage": {"x.sid": _UUID, "y.auth": _JWT}}
    assert d.cari_token_nilai(st) == _JWT


def test_token_dalam_nilai_json():
    st = {"localStorage": {"auth": '{"token":"%s","exp":123}' % _JWT}}
    assert d.cari_token_nilai(st) == _JWT


def test_tanpa_token():
    st = {"localStorage": {"theme": "dark", "lang": "id", "count": "3"}}
    assert d.cari_token_nilai(st) is None


def test_token_baru_diff():
    sebelum = {"localStorage": {"theme": "dark"}}
    sesudah = {"localStorage": {"theme": "dark", "cuti.session": _UUID}}
    assert d.token_baru(sebelum, sesudah) == _UUID
    # Tak ada perubahan → None.
    assert d.token_baru(sesudah, sesudah) is None


def test_metadata_tanpa_nilai():
    """Metadata untuk arbiter AI TIDAK boleh memuat nilai token."""
    st = {"localStorage": {"cuti.session": _UUID}}
    meta = d.metadata_storage(st)
    assert meta == [{"key": "cuti.session", "panjang": len(_UUID), "bentuk": "uuid"}]
    # Pastikan nilai token tidak bocor ke metadata.
    assert all(_UUID not in str(v) for m in meta for v in m.values())
