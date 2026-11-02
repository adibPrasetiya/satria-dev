"""Uji pembangkitan kode TOTP (MFA) — tanpa jaringan."""

from __future__ import annotations

import pytest

from satya_worker import mfa

# Secret uji tetap (base32). Lihat RFC 6238.
SECRET = "JBSWY3DPEHPK3PXP"


def test_secret_valid():
    assert mfa.secret_valid(SECRET)
    assert mfa.secret_valid("jbswy3dpehpk3pxp")  # case-insensitive
    assert mfa.secret_valid("JBSW Y3DP EHPK 3PXP")  # spasi diabaikan
    assert not mfa.secret_valid("")
    assert not mfa.secret_valid(None)
    assert not mfa.secret_valid("bukan-base32!!!")


def test_kode_totp_bentuk():
    if not mfa.tersedia():
        pytest.skip("pyotp tak terpasang")
    kode = mfa.kode_totp(SECRET)
    assert kode is not None and kode.isdigit() and len(kode) == 6


def test_kode_totp_cocok_pyotp():
    pyotp = pytest.importorskip("pyotp")
    assert mfa.kode_totp(SECRET) == pyotp.TOTP(SECRET).now()


def test_kode_totp_secret_invalid_none():
    assert mfa.kode_totp(None) is None
    # Mengandung karakter di luar alfabet base32 (!,1) → invalid.
    assert mfa.kode_totp("invalid!1") is None


def test_kode_totp_parameter_non_standar_cocok_pyotp():
    """Parameter dari URI otpauth (QR): 8 digit, 60 dtk, SHA256."""
    import hashlib

    pyotp = pytest.importorskip("pyotp")
    kode = mfa.kode_totp(SECRET, digits=8, interval=60, algoritma="SHA256")
    assert kode == pyotp.TOTP(SECRET, digits=8, interval=60, digest=hashlib.sha256).now()
    assert len(kode) == 8


def test_kode_totp_algoritma_tak_dikenal_none():
    assert mfa.kode_totp(SECRET, algoritma="MD5") is None


def test_kode_untuk_akun_memakai_parameter_akun():
    import hashlib

    pyotp = pytest.importorskip("pyotp")
    from satya_worker.models import ScanContext

    ctx = ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": "https://x",
        "akun_uji": [{
            "kunci": "akun_uji_1", "username": "u", "password": "p", "terisi": True,
            "totp_secret": SECRET, "totp_digits": 8, "totp_period": 60, "totp_algoritma": "sha512",
        }],
    })
    akun = ctx.akun_uji[0]
    assert (akun.totp_digits, akun.totp_period, akun.totp_algoritma) == (8, 60, "SHA512")
    assert mfa.kode_untuk_akun(akun) == pyotp.TOTP(SECRET, digits=8, interval=60, digest=hashlib.sha512).now()


def test_from_dict_default_parameter_bila_null():
    from satya_worker.models import ScanContext

    ctx = ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": "https://x",
        "akun_uji": [{"kunci": "akun_uji_1", "username": "u", "password": "p", "terisi": True,
                      "totp_secret": SECRET, "totp_digits": None, "totp_period": None, "totp_algoritma": None}],
    })
    akun = ctx.akun_uji[0]
    assert (akun.totp_digits, akun.totp_period, akun.totp_algoritma) == (6, 30, "SHA1")
