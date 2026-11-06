"""Uji lapisan analisis struktur token (analisis_token)."""

from __future__ import annotations

import base64
import json
import uuid

from satya_worker import analisis_token as at


def _b64(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).decode().rstrip("=")


def _jwt(klaim: dict, alg: str = "HS256", sig_bytes: int = 32) -> str:
    h = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    p = _b64(json.dumps(klaim).encode())
    s = _b64(b"\x00" * sig_bytes) if sig_bytes else ""
    return f"{h}.{p}.{s}"


# --------------------------------------------------------------- klasifikasi_nilai

def test_klasifikasi_bentuk_dasar():
    assert at.klasifikasi_nilai(str(uuid.uuid4())) == "uuid"
    assert at.klasifikasi_nilai("42") == "int"
    assert at.klasifikasi_nilai("1700000000") == "timestamp"
    assert at.klasifikasi_nilai("budi@contoh.id") == "email"
    assert at.klasifikasi_nilai("budi_pegawai") == "username"
    assert at.klasifikasi_nilai("a" * 32) == "username" or at.klasifikasi_nilai("abcdef0123456789abcdef0123456789") == "hex"
    assert at.klasifikasi_nilai("") == "kosong"


# --------------------------------------------------------------- bongkar_jwt / identitas

def test_bongkar_jwt_dan_identitas():
    tok = _jwt({"jti": str(uuid.uuid4()), "sub": "7", "iat": 1700000000})
    j = at.bongkar_jwt(tok)
    assert j is not None
    assert j["header"]["alg"] == "HS256"
    nama, _nilai, bentuk = at.identitas_sesi(j["klaim"])
    assert nama == "jti" and bentuk == "uuid"  # jti diprioritaskan atas sub


def test_bongkar_jwt_bukan_jwt():
    assert at.bongkar_jwt("bukan.jwt") is None
    assert at.bongkar_jwt("abcdef") is None


# --------------------------------------------------------------- dekode_lapis

def test_dekode_lapis_base64_prediktabel():
    lap = at.dekode_lapis(_b64(b"user-123"))
    assert lap is not None and lap["skema"] == "base64" and lap["bentuk_isi"] == "int"


def test_dekode_lapis_base64_uuid():
    lap = at.dekode_lapis(_b64(str(uuid.uuid4()).encode()))
    assert lap is not None and lap["bentuk_isi"] == "uuid"


def test_dekode_lapis_acak_tak_terbaca():
    import secrets
    assert at.dekode_lapis(secrets.token_urlsafe(32)) is None  # byte acak bukan teks bermakna


# --------------------------------------------------------------- analisis

def test_analisis_jwt_acak_kuat():
    a = at.analisis(token=_jwt({"jti": str(uuid.uuid4()), "iat": 1700000000}))
    assert a["kualitas"] == "acak_kuat"
    assert a["metadata_ai"]["format"] == "jwt"
    assert a["nilai_entropi"]  # segmen tanda tangan


def test_analisis_jwt_alg_none_prediktabel():
    a = at.analisis(token=_jwt({"sub": "1"}, alg="none", sig_bytes=0))
    assert a["kualitas"] == "prediktabel"


def test_analisis_uuid_acak_kuat():
    a = at.analisis(token=str(uuid.uuid4()))
    assert a["kualitas"] == "acak_kuat" and a["metadata_ai"]["format"] == "uuid"


def test_analisis_int_prediktabel():
    a = at.analisis(token="12345")
    assert a["kualitas"] == "prediktabel"


def test_analisis_encoded_prediktabel():
    a = at.analisis(token=_b64(b"user-5"))
    assert a["kualitas"] == "prediktabel"
    assert a["metadata_ai"]["bentuk_setelah_dekode"] == "int"


def test_analisis_opaque_acak_tak_pasti_atau_kuat():
    import secrets
    a = at.analisis(token=secrets.token_urlsafe(32))
    assert a["kualitas"] in ("acak_kuat", "tak_pasti")
    assert a["nilai_entropi"]


def test_analisis_cookie_metadata():
    a = at.analisis(cookie={"name": "JSESSIONID", "value": str(uuid.uuid4()), "flags": "httponly"})
    assert a["metadata_ai"]["wadah"] == "cookie"
    assert a["metadata_ai"]["nama_cookie"] == "JSESSIONID"


# --------------------------------------------------------------- metadata_sampel (lintas login)

def test_metadata_sampel_berurutan():
    sampel = [_b64(f"user-{n}".encode()) for n in range(1, 6)]
    md = at.metadata_sampel(sampel)
    assert md["identitas_berurutan"] is True


def test_metadata_sampel_acak_tidak_berurutan():
    import secrets
    sampel = [secrets.token_urlsafe(32) for _ in range(6)]
    md = at.metadata_sampel(sampel)
    assert md["identitas_berurutan"] is False
    assert md["semua_unik"] is True
