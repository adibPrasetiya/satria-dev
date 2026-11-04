"""AI penajam untuk fungsi File (FILE).

Dari METADATA non-sensitif (SUDAH diredaksi) — TIDAK PERNAH memutus lulus/gagal (lih. `ai/base.py`).
Dua kegunaan, kurangi positif palsu:

1. **Adjudikasi hasil unggahan** (FILE-11.2/11.3/11.4): ketika respons ambigu, apakah file uji
   (tipe tak sesuai / nama berbahaya / EICAR) benar-benar DITERIMA & disimpan server, atau DITOLAK.
2. **Adjudikasi paparan ekstensi** (FILE-11.5-T02 `file.extension_allowlist`): apakah temuan nuclei
   benar-benar berkas konfigurasi/sumber sensitif yang disajikan.

Mode via env `AI_FILE`: hemat (bawaan) | minimal | off. Interpretasi runtime tak di-cache.
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
    m = os.environ.get("AI_FILE", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _tanya(prompt: str, kunci: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    info: dict[str, Any] = {"mode": mode(), "dikirim": 0}
    if mode() == "off":
        return None, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(prompt, max_tokens=250)
    except Exception as e:
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info
    if not isinstance(jawab, dict) or jawab.get("_galat") or kunci not in jawab:
        info["galat"] = "respons AI tak valid"
        return None, info
    return jawab, info


# --------------------------------------------------------------------------- hasil unggahan

def _prompt_unggahan(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Worker mengunggah sebuah file UJI (mis. tipe konten "
        "tidak sesuai ekstensi, nama berbahaya, atau file uji antivirus EICAR) ke endpoint unggah. "
        "Dari metadata (jenis uji, status HTTP, cuplikan respons yang SUDAH diredaksi), tentukan apakah "
        "file tersebut DITERIMA/disimpan server (mis. mengembalikan URL/id file, 2xx sukses) atau "
        "DITOLAK/divalidasi (mis. 400/415/422, pesan penolakan).\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"diterima": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_unggahan(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah file uji diterima/disimpan server? Return (`{diterima, keyakinan, alasan}` | None, info)."""
    jawab, info = _tanya(_prompt_unggahan(redaksi(metadata)), "diterima")
    if jawab is None:
        return None, info
    return {"diterima": bool(jawab.get("diterima")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


# --------------------------------------------------------------------------- paparan ekstensi

def _prompt_ekstensi(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Pemindai menandai sebuah URL sebagai kemungkinan "
        "BERKAS KONFIGURASI/SUMBER yang disajikan (mis. .bak, .config, .sql, .env, .inc, kode sumber). "
        "Dari metadata (template, nama, path, severity), tentukan apakah ini benar-benar berkas "
        "konfigurasi/sumber sensitif yang disajikan server, atau WAJAR/tak berisiko.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"sensitif": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_paparan_ekstensi(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah temuan benar-benar berkas konfig/sumber sensitif disajikan? Return (`{sensitif,..}` | None, info)."""
    jawab, info = _tanya(_prompt_ekstensi(redaksi(metadata)), "sensitif")
    if jawab is None:
        return None, info
    return {"sensitif": bool(jawab.get("sensitif")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
