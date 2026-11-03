"""AI penajam untuk fungsi Keamanan API & Web Service (APIS).

Dari METADATA non-sensitif (metode+path, nama field, status) — TIDAK PERNAH memutus lulus/gagal
(lih. `ai/base.py`). Dua kegunaan, kurangi positif palsu:

1. **Klasifikasi endpoint publik** (APIS-12.3-T01 `api.auth_required`): ketika sebuah endpoint
   membalas tanpa token, AI menilai apakah endpoint itu MEMANG dirancang publik (login, registrasi,
   health, dokumentasi, aset) atau SEHARUSNYA terlindungi. Hasil dipakai pemanggil untuk tak salah
   menuduh endpoint publik sebagai "autentikasi hilang".
2. **Adjudikasi paparan** (APIS-12.2-T02 `exposure.api_docs_debug`): apakah temuan nuclei benar-benar
   paparan sensitif (dok API/endpoint debug nyata) atau wajar/tak berisiko.

Mode via env `AI_APIS`: hemat (bawaan) | minimal | off. Klasifikasi endpoint stabil per (metode,path)
→ di-cache persisten di `worker/.cache/ai_apis.json`. Semua kegagalan ditangani anggun.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from .redaksi import redaksi

_kunci_cache = threading.Lock()


def _provider() -> Any:
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_APIS", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _berkas_cache() -> Path:
    return Path(os.environ.get("AI_APIS_CACHE", str(Path(__file__).resolve().parents[2] / ".cache" / "ai_apis.json")))


def _muat_cache() -> dict[str, Any]:
    try:
        return json.loads(_berkas_cache().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _simpan_cache(data: dict[str, Any]) -> None:
    try:
        p = _berkas_cache()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- klasifikasi publik

def _prompt_publik(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan API yang SAH/berizin. Sebuah endpoint API membalas data TANPA autentikasi. "
        "Dari metadata (metode HTTP, path, nama field; tanpa nilai), tentukan apakah endpoint ini WAJAR "
        "dirancang PUBLIK (mis. login, registrasi, lupa-sandi, health/ping, dokumentasi, aset statis, "
        "daftar publik) atau SEHARUSNYA TERLINDUNGI (mis. data pengguna, admin, pengaturan, objek ber-ID).\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"publik": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def klasifikasi_publik(
    metadata: dict[str, Any],
    *,
    kunci_cache: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah endpoint wajar publik? Return (`{publik, keyakinan, alasan}` | None, info). Tak melempar."""
    info: dict[str, Any] = {"mode": mode(), "dari_cache": False, "dikirim": 0}
    if mode() == "off":
        return None, info
    if kunci_cache:
        with _kunci_cache:
            cache = _muat_cache()
        if kunci_cache in cache:
            info["dari_cache"] = True
            return cache[kunci_cache], info

    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt_publik(redaksi(metadata)), max_tokens=250)
    except Exception as e:
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info
    if not isinstance(jawab, dict) or jawab.get("_galat") or "publik" not in jawab:
        info["galat"] = "respons AI tak valid"
        return None, info
    hasil = {"publik": bool(jawab.get("publik")), "keyakinan": jawab.get("keyakinan"),
             "alasan": str(jawab.get("alasan", ""))[:300]}
    if kunci_cache:
        with _kunci_cache:
            cache = _muat_cache()
            cache[kunci_cache] = hasil
            _simpan_cache(cache)
    return hasil, info


# --------------------------------------------------------------------------- adjudikasi paparan

def _prompt_exposure(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan API yang SAH/berizin. Pemindai menandai sebuah URL sebagai kemungkinan "
        "paparan dokumentasi API atau endpoint debug. Dari metadata (template, nama, path, severity), "
        "tentukan apakah ini PAPARAN SENSITIF yang nyata (Swagger/OpenAPI/GraphQL introspeksi/actuator/"
        "debug/phpinfo yang terbuka tanpa otorisasi) atau WAJAR/tak berisiko.\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"sensitif": true|false, "keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_exposure(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Apakah temuan paparan benar-benar sensitif? Return (`{sensitif, keyakinan, alasan}` | None, info)."""
    info: dict[str, Any] = {"mode": mode(), "dikirim": 0}
    if mode() == "off":
        return None, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt_exposure(redaksi(metadata)), max_tokens=250)
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
