"""AI penajam untuk fungsi Penanganan Error dan Pencatatan Log (ERRL).

Dari METADATA non-sensitif (status, cuplikan error yang SUDAH diredaksi, path) — TIDAK PERNAH
memutus lulus/gagal (lih. `ai/base.py`). Dua kegunaan, kurangi positif palsu:

1. **Adjudikasi kebocoran error** (ERRL-6.1-T01 `error.verbose_messages`, ERRL-6.2-T01
   `error.unhandled_exception`): ketika deteksi regel ragu, AI menilai apakah respons error
   benar-benar membocorkan DETAIL TEKNIS (stack trace, query SQL, path sistem, versi/komponen,
   halaman debug) atau sekadar halaman error generik.
2. **Adjudikasi paparan file log** (ERRL-6.5-T01 `exposure.log_files`): apakah temuan nuclei
   benar-benar file log yang ter-ekspos & sensitif.

Mode via env `AI_ERRL`: hemat (bawaan) | minimal | off. Interpretasi respons runtime tak di-cache.
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
    m = os.environ.get("AI_ERRL", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _tanya(prompt: str, kunci_wajib: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
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
    if not isinstance(jawab, dict) or jawab.get("_galat") or kunci_wajib not in jawab:
        info["galat"] = "respons AI tak valid"
        return None, info
    return jawab, info


# --------------------------------------------------------------------------- kebocoran error

def _prompt_kebocoran(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Sebuah respons error dikirim server. Dari metadata "
        "(status HTTP, cuplikan badan respons yang SUDAH diredaksi), tentukan apakah respons "
        "MEMBOCORKAN DETAIL TEKNIS internal — stack trace, query/galat SQL, path berkas/direktori "
        "sistem, nama & versi komponen (framework/bahasa/server), atau halaman debug — yang bisa "
        "membantu penyerang; ATAU hanya halaman error GENERIK yang wajar.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"bocor": true|false, "jenis": "<stack_trace|sql|path|versi|debug|tidak_ada>", '
        '"keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_kebocoran(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah respons error membocorkan detail teknis? Return (`{bocor, jenis, keyakinan, alasan}` | None, info)."""
    jawab, info = _tanya(_prompt_kebocoran(redaksi(metadata)), "bocor")
    if jawab is None:
        return None, info
    return {
        "bocor": bool(jawab.get("bocor")),
        "jenis": str(jawab.get("jenis", ""))[:40],
        "keyakinan": jawab.get("keyakinan"),
        "alasan": str(jawab.get("alasan", ""))[:300],
    }, info


# --------------------------------------------------------------------------- paparan file log

def _prompt_log(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Pemindai menandai sebuah URL sebagai kemungkinan "
        "FILE LOG yang ter-ekspos (mis. access.log, error.log, debug.log, laravel.log). Dari metadata "
        "(template, nama, path, severity), tentukan apakah ini benar-benar file log aplikasi yang "
        "ter-ekspos & berpotensi sensitif, atau WAJAR/tak berisiko.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"sensitif": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_paparan_log(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah temuan benar-benar file log sensitif ter-ekspos? Return (`{sensitif, keyakinan, alasan}` | None, info)."""
    jawab, info = _tanya(_prompt_log(redaksi(metadata)), "sensitif")
    if jawab is None:
        return None, info
    return {"sensitif": bool(jawab.get("sensitif")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
