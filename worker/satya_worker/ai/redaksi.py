"""Redaksi payload sebelum dikirim ke provider AI eksternal.

Selaras dengan `http_client._KUNCI_SENSITIF`: nilai field yang namanya menandakan
kredensial/token/cookie/PII diganti `[disamarkan]` secara rekursif. Nama field
tetap dipertahankan (berguna untuk pemetaan); hanya NILAI contoh yang disensor.
"""

from __future__ import annotations

import re
from typing import Any

_KUNCI_SENSITIF = re.compile(
    r"(pass|sandi|password|passwd|token|secret|authorization|auth|api[-_]?key|"
    r"cookie|session|otp|totp|mfa|credential|kredensial|bearer|jwt|"
    r"ssn|nik|nip|nrp|kartu|card|cvv|pin)",
    re.IGNORECASE,
)

_DISAMARKAN = "[disamarkan]"


def _sensitif(nama: str) -> bool:
    return bool(_KUNCI_SENSITIF.search(nama or ""))


def redaksi(obj: Any) -> Any:
    """Salin `obj` secara rekursif dengan nilai field sensitif disensor."""
    if isinstance(obj, dict):
        keluar: dict[str, Any] = {}
        for k, v in obj.items():
            if _sensitif(str(k)) and not isinstance(v, (dict, list)):
                keluar[k] = _DISAMARKAN
            else:
                keluar[k] = redaksi(v)
        return keluar
    if isinstance(obj, list):
        return [redaksi(x) for x in obj]
    return obj
