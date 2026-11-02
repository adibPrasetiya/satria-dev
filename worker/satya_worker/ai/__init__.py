"""Enrichment discovery berbasis AI (opsional).

Pemilihan provider via env `AI_PROVIDER`:
    gemini     → GeminiProvider (utama)
    anthropic  → AnthropicProvider (fallback)
    none/''    → nonaktif
Default: coba gemini dulu, lalu anthropic, bila kuncinya ada.

Redaksi (AI_REDAKSI, default aktif) menyensor nilai field sensitif sebelum payload
dikirim ke provider eksternal. Semua kegagalan ditangani anggun: discovery tetap
berjalan dengan hasil deterministik bila AI tak tersedia/gagal.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .anthropic_provider import AnthropicProvider
from .base import AIProvider
from .gemini import GeminiProvider
from .redaksi import redaksi


def _redaksi_aktif() -> bool:
    return os.environ.get("AI_REDAKSI", "true").strip().lower() not in ("0", "false", "no")


def muat_provider_dari_env() -> Optional[AIProvider]:
    """Pilih provider AI sesuai env. None bila dinonaktifkan atau tak ada kunci."""
    pilih = os.environ.get("AI_PROVIDER", "").strip().lower()
    if pilih in ("none", "off", "disabled"):
        return None

    if pilih == "gemini":
        return GeminiProvider.dari_env()
    if pilih == "anthropic":
        return AnthropicProvider.dari_env()

    # Auto (tak diset): gemini dulu, lalu anthropic.
    return GeminiProvider.dari_env() or AnthropicProvider.dari_env()


def enrich_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    """Jalankan enrichment AI atas `payload` discovery.

    Kembalikan { tersedia, provider, model, disamarkan, isi|galat }.
    """
    provider = muat_provider_dari_env()
    if provider is None:
        return {"tersedia": False, "provider": None}

    disamarkan = _redaksi_aktif()
    kirim = redaksi(payload) if disamarkan else payload
    hasil = provider.enrich(kirim)

    if isinstance(hasil, dict) and hasil.get("_galat"):
        return {
            "tersedia": False,
            "provider": provider.nama,
            "model": provider.model,
            "disamarkan": disamarkan,
            "galat": hasil["_galat"],
        }
    return {
        "tersedia": True,
        "provider": provider.nama,
        "model": provider.model,
        "disamarkan": disamarkan,
        "isi": hasil,
    }


def arbitrase_login(metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Minta AI memutus status login dari METADATA non-sensitif (tanpa nilai token/sandi).

    Dipakai HANYA sebagai tie-breaker saat sinyal deterministik tak meyakinkan.
    Return { ok: bool, keyakinan: float, alasan: str, provider: str } atau None
    (provider tak ada / gagal / respons tak valid). Tidak pernah melempar.
    """
    provider = muat_provider_dari_env()
    if provider is None or not hasattr(provider, "putuskan_login"):
        return None
    try:
        hasil = provider.putuskan_login(metadata)
    except Exception:
        return None
    if not isinstance(hasil, dict) or hasil.get("_galat") or "ok" not in hasil:
        return None
    return {
        "ok": bool(hasil.get("ok")),
        "keyakinan": hasil.get("keyakinan"),
        "alasan": hasil.get("alasan", ""),
        "provider": provider.nama,
    }


def lengkapi_kandidat(metadata: list[Any]) -> Optional[dict[str, Any]]:
    """Minta AI menyempurnakan kandidat uji dari METADATA non-sensitif (nama field, bukan nilai).

    Return { saran: [ {endpoint, tambah_kategori?, info_kurang?, catatan?} ], provider, model }
    atau None (provider tak ada / gagal / respons tak valid). Tidak pernah melempar.
    """
    provider = muat_provider_dari_env()
    if provider is None or not hasattr(provider, "lengkapi_kandidat"):
        return None
    try:
        hasil = provider.lengkapi_kandidat(metadata)
    except Exception:
        return None
    if not isinstance(hasil, dict) or hasil.get("_galat") or not isinstance(hasil.get("saran"), list):
        return None
    return {"saran": hasil["saran"], "provider": provider.nama, "model": provider.model}


def klasifikasi_endpoint(metadata: list[Any]) -> Optional[dict[str, Any]]:
    """Minta AI menajamkan lapisan (frontend/api/aset) endpoint ambigu dari METADATA non-sensitif.

    Return { saran: [ {endpoint, lapisan, upload?, alasan?} ], provider, model } atau None
    (provider tak ada / gagal / respons tak valid). Tidak pernah melempar.
    """
    provider = muat_provider_dari_env()
    if provider is None or not hasattr(provider, "klasifikasi_endpoint"):
        return None
    try:
        hasil = provider.klasifikasi_endpoint(metadata)
    except Exception:
        return None
    if not isinstance(hasil, dict) or hasil.get("_galat") or not isinstance(hasil.get("saran"), list):
        return None
    return {"saran": hasil["saran"], "provider": provider.nama, "model": provider.model}


def atribusi_penolakan(metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Minta AI menafsirkan penyebab penolakan uji kebijakan sandi (metadata SUDAH tersamar).

    Return { penyebab, field, alasan, provider, model } atau None. Tidak pernah melempar.
    """
    provider = muat_provider_dari_env()
    if provider is None or not hasattr(provider, "atribusi_penolakan"):
        return None
    try:
        hasil = provider.atribusi_penolakan(metadata)
    except Exception:
        return None
    if not isinstance(hasil, dict) or hasil.get("_galat") or not isinstance(hasil.get("penyebab"), str):
        return None
    return {**hasil, "provider": provider.nama, "model": provider.model}


def isi_payload(metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Minta AI mengusulkan nilai dummy valid untuk field form. Return { nilai, provider } atau None."""
    provider = muat_provider_dari_env()
    if provider is None or not hasattr(provider, "isi_payload"):
        return None
    try:
        hasil = provider.isi_payload(redaksi(metadata) if _redaksi_aktif() else metadata)
    except Exception:
        return None
    if not isinstance(hasil, dict) or hasil.get("_galat") or not isinstance(hasil.get("nilai"), dict):
        return None
    return {"nilai": hasil["nilai"], "provider": provider.nama}
