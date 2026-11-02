"""MFA/TOTP untuk discovery & check terautentikasi.

Bila akun uji menyertakan `totp_secret` (base32), worker membangkitkan kode OTP
enam digit sendiri (RFC 6238) agar login dua langkah bisa dilalui tanpa interaksi.

Impor `pyotp` secara LAZY + fallback anggun: tanpa paket/secret, `kode_totp`
mengembalikan None dan alur login melewati langkah MFA (pola sama seperti
`playwright_driver`/`zap_client`).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

# Base32 valid (huruf A-Z, digit 2-7, opsional padding '='), spasi/garis diabaikan.
_BASE32 = re.compile(r"^[A-Z2-7]+=*$", re.IGNORECASE)


def _bersihkan(secret: str) -> str:
    """Normalisasi secret: buang spasi/strip, huruf besar (format QR sering berspasi)."""
    return re.sub(r"[\s-]", "", secret or "").upper()


def secret_valid(secret: Optional[str]) -> bool:
    if not secret:
        return False
    s = _bersihkan(secret)
    return bool(s) and bool(_BASE32.match(s))


def tersedia() -> bool:
    """True bila modul pyotp bisa diimpor."""
    try:
        import pyotp  # noqa: F401
    except Exception:
        return False
    return True


_DIGEST = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


def kode_totp(
    secret: Optional[str], *, digits: int = 6, interval: int = 30, algoritma: str = "SHA1"
) -> Optional[str]:
    """Kode TOTP saat ini untuk `secret`. None bila secret/pyotp tak tersedia atau secret invalid.

    Parameter non-standar (digits/interval/algoritma) mengikuti URI otpauth dari QR aplikasi target.
    Best-effort: tak pernah melempar; kegagalan apa pun → None.
    """
    if not secret_valid(secret):
        return None
    digest = _DIGEST.get((algoritma or "SHA1").upper())
    if digest is None:
        return None
    try:
        import pyotp  # lazy
    except Exception:
        return None
    try:
        return pyotp.TOTP(_bersihkan(secret), digits=digits or 6, interval=interval or 30, digest=digest).now()
    except Exception:
        return None


def kode_untuk_akun(akun: Any) -> Optional[str]:
    """Kode TOTP untuk sebuah AkunUji, memakai parameter TOTP yang tersimpan pada akun."""
    return kode_totp(
        getattr(akun, "totp_secret", None),
        digits=getattr(akun, "totp_digits", 6) or 6,
        interval=getattr(akun, "totp_period", 30) or 30,
        algoritma=getattr(akun, "totp_algoritma", "SHA1") or "SHA1",
    )
