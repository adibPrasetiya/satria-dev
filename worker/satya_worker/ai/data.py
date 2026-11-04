"""AI penajam untuk fungsi Proteksi Data (DATA).

Dari METADATA non-sensitif (SUDAH diredaksi) — TIDAK PERNAH memutus lulus/gagal (lih. `ai/base.py`).
Dua kegunaan, kurangi positif palsu:

1. **Adjudikasi paparan berkas cadangan** (DATA-7.5-T01 `exposure.backup_files`): apakah temuan
   nuclei benar-benar berkas cadangan/dump basis data/arsip yang sensitif & ter-ekspos.
2. **Adjudikasi mass-assignment** (DATA-7.4-T01 `input.unexpected_parameters`): ketika respons
   ambigu, apakah parameter PRIVILESE tambahan benar-benar DITERIMA/direfleksikan server (bukan
   sekadar digaungkan tanpa efek).

Mode via env `AI_DATA`: hemat (bawaan) | minimal | off. Interpretasi runtime tak di-cache.
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
    m = os.environ.get("AI_DATA", "hemat").strip().lower()
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


# --------------------------------------------------------------------------- paparan backup

def _prompt_backup(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Pemindai menandai sebuah URL sebagai kemungkinan "
        "BERKAS CADANGAN / DUMP BASIS DATA / ARSIP yang ter-ekspos (mis. backup.zip, db.sql, "
        "dump.sql.gz, www.tar.gz, .bak). Dari metadata (template, nama, path, severity), tentukan "
        "apakah ini benar-benar berkas sensitif yang ter-ekspos & dapat diunduh, atau WAJAR/tak berisiko.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"sensitif": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_paparan_backup(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah temuan benar-benar berkas cadangan sensitif ter-ekspos? Return (`{sensitif,..}` | None, info)."""
    jawab, info = _tanya(_prompt_backup(redaksi(metadata)), "sensitif")
    if jawab is None:
        return None, info
    return {"sensitif": bool(jawab.get("sensitif")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


# --------------------------------------------------------------------------- mass assignment

def _prompt_mass(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Worker mengirim request berisi field tambahan "
        "berpotensi PRIVILESE (mis. role, is_admin, verified, balance) dengan nilai penanda. Dari "
        "metadata (field yang disuntik, status, cuplikan respons yang SUDAH diredaksi), tentukan apakah "
        "server MENERIMA/MEREFLEKSIKAN atribut privilese itu (mass assignment) atau MENGABAIKAN/menolaknya.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"diterima": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_mass_assignment(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah atribut privilese tambahan diterima server? Return (`{diterima,..}` | None, info)."""
    jawab, info = _tanya(_prompt_mass(redaksi(metadata)), "diterima")
    if jawab is None:
        return None, info
    return {"diterima": bool(jawab.get("diterima")), "keyakinan": jawab.get("keyakinan"),
            "alasan": str(jawab.get("alasan", ""))[:300]}, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
