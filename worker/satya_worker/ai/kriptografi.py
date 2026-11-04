"""AI penajam untuk fungsi Kriptografi (CRYP).

Dari METADATA non-sensitif (SUDAH diredaksi) — TIDAK PERNAH memutus lulus/gagal (lih. `ai/base.py`).
Adjudikasi paparan rahasia (CRYP-5.3-T01 `crypto.exposed_secrets`): apakah temuan nuclei benar-benar
kunci privat / API key / rahasia yang ter-ekspos di aset publik, atau positif palsu (mis. contoh,
placeholder, kunci publik).

Mode via env `AI_CRYP`: hemat (bawaan) | minimal | off. Interpretasi runtime tak di-cache.
Semua kegagalan ditangani anggun: tanpa AI, hasil deterministik tetap utuh.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .redaksi import redaksi


def _provider() -> Any:
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_CRYP", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _prompt(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Pemindai menandai sebuah lokasi sebagai kemungkinan "
        "RAHASIA yang ter-ekspos (kunci privat, API key, token, kredensial) di aset publik (JavaScript, "
        "berkas). Dari metadata (template, nama, path, severity), tentukan apakah ini benar-benar rahasia "
        "SENSITIF yang nyata ter-ekspos, atau positif palsu (placeholder, contoh, kunci PUBLIK, nilai dummy).\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"sensitif": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_rahasia(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah temuan benar-benar rahasia sensitif ter-ekspos? Return (`{sensitif, keyakinan, alasan}` | None, info)."""
    info: dict[str, Any] = {"mode": mode(), "dikirim": 0}
    if mode() == "off":
        return None, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt(redaksi(metadata)), max_tokens=250)
    except Exception as e:
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info
    if not isinstance(jawab, dict) or jawab.get("_galat") or "sensitif" not in jawab:
        info["galat"] = "respons AI tak valid"
        return None, info
    return {"sensitif": bool(jawab.get("sensitif")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
