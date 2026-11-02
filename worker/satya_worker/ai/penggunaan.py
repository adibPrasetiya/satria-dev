"""Penghitung pemakaian AI (panggilan & token) per proses — agar biaya AI berbayar terlihat di log.

Provider mencatat `usage` dari respons bila tersedia; bila tidak, token diperkirakan dari panjang
teks (±4 karakter per token). `potret()` → {panggilan, token_masuk, token_keluar, perkiraan}.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

_kunci = threading.Lock()
_data: dict[str, Any] = {"panggilan": 0, "token_masuk": 0, "token_keluar": 0, "perkiraan": False}


def catat(prompt: str, teks: str, masuk: Optional[int] = None, keluar: Optional[int] = None) -> None:
    with _kunci:
        _data["panggilan"] += 1
        if masuk is None or keluar is None:
            _data["perkiraan"] = True
        _data["token_masuk"] += int(masuk if masuk is not None else len(prompt) // 4)
        _data["token_keluar"] += int(keluar if keluar is not None else len(teks or "") // 4)


def potret() -> dict[str, Any]:
    with _kunci:
        return dict(_data)


def selisih(awal: dict[str, Any]) -> dict[str, Any]:
    """Pemakaian sejak `awal` (hasil `potret()` sebelumnya)."""
    kini = potret()
    return {
        "panggilan": kini["panggilan"] - awal.get("panggilan", 0),
        "token": (kini["token_masuk"] - awal.get("token_masuk", 0)) + (kini["token_keluar"] - awal.get("token_keluar", 0)),
        "perkiraan": kini["perkiraan"],
    }


def usage_gemini(resp: Any) -> tuple[Optional[int], Optional[int]]:
    u = getattr(resp, "usage_metadata", None)
    if u is None:
        return None, None
    return getattr(u, "prompt_token_count", None), (getattr(u, "candidates_token_count", None) or 0) + (getattr(u, "thoughts_token_count", None) or 0)


def usage_anthropic(resp: Any) -> tuple[Optional[int], Optional[int]]:
    u = getattr(resp, "usage", None)
    if u is None:
        return None, None
    return getattr(u, "input_tokens", None), getattr(u, "output_tokens", None)
