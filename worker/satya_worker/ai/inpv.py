"""AI hemat token untuk uji Validasi Input (INPV). Maksimal DUA panggilan per scan, keduanya opsional:

1. `profil_validasi(items)` — SATU panggilan berkelompok untuk field yang profilnya ambigu.
   Dedup per signature (`nama|tipe|segmen`), hanya metadata (nama, tipe, BENTUK contoh — bukan nilai).
   Hasil di-cache persisten (`worker/.cache/ai_inpv_profil.json`) → scan ulang ≈ 0 token.
2. `nilai_ambigu(kasus)` — SATU panggilan setelah sapuan untuk input tak valid yang DITERIMA (2xx):
   fitur ringkas (status, selisih panjang, content-type) → diproses | disanitasi | diabaikan | tak_pasti.

Mode via env `AI_INPV`: hemat (bawaan: 1+2) | minimal (hanya 1) | off. AI tak pernah memutus
lulus/gagal sendiri — hanya menajamkan payload & menafsirkan kasus ambigu.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional

from .redaksi import redaksi

MAKS_FIELD = 60
MAKS_KASUS = 25
_KUNCI_SENSITIF = re.compile(r"(pass|sandi|token|secret|otp|pin|cvv|card|kartu|nik|nip|nrp)", re.IGNORECASE)
_kunci_cache = threading.Lock()


def _provider() -> Any:
    # Dibaca saat dipanggil (bukan saat impor) agar bisa diganti tes (monkeypatch ai.muat_provider_dari_env).
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_INPV", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _berkas_cache() -> Path:
    return Path(os.environ.get("AI_INPV_CACHE", str(Path(__file__).resolve().parents[2] / ".cache" / "ai_inpv_profil.json")))


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


def _prompt_profil(items: list[dict[str, Any]]) -> str:
    return (
        "Asesmen keamanan web berizin. Untuk tiap field input API berikut (k = nama|tipe|sumber), "
        "tebak aturan validasi yang SEHARUSNYA ditegakkan server dan beri ≤3 nilai TIDAK VALID spesifik "
        "domain (bukan data orang nyata, bukan payload eksploit). Jawab HANYA JSON ringkas tanpa penjelasan:\n"
        '{"p":{"<k>":{"tipe":"string|integer|number|boolean","format":"email|date|uuid|url|digits|slug|kata|",'
        '"min":0,"max":0,"enum":[],"invalid":["..."]}}}  (hilangkan kunci yang tak diketahui)\n'
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )


def _prompt_ambigu(kasus: list[dict[str, Any]]) -> str:
    return (
        "Asesmen keamanan web berizin. Server membalas 2xx atas input TIDAK VALID berikut. Dari fitur ringkas "
        "(m=metode, j=jenis varian, s=status varian/baseline, d=selisih panjang relatif vs baseline, ct=content-type), "
        "nilai apakah input itu: diproses (disimpan/dipakai apa adanya), disanitasi, diabaikan (mis. parameter filter "
        "dibuang), atau tak_pasti. Jawab HANYA JSON ringkas: {\"v\":{\"<id>\":\"diproses|disanitasi|diabaikan|tak_pasti\"}}\n"
        + json.dumps(kasus, ensure_ascii=False, separators=(",", ":"))
    )


def profil_validasi(items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """`items`: [{k, nama, tipe, path, bentuk?}] (field ambigu, sudah unik per k).
    Return (profil_per_k, info) dengan info = {dari_cache, dikirim, galat?}."""
    info: dict[str, Any] = {"dari_cache": 0, "dikirim": 0}
    if mode() == "off" or not items:
        return {}, info
    with _kunci_cache:
        cache = _muat_cache()
    hasil = {it["k"]: cache[it["k"]] for it in items if it["k"] in cache}
    info["dari_cache"] = len(hasil)
    sisa = [it for it in items if it["k"] not in cache][:MAKS_FIELD]
    if not sisa:
        return hasil, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return hasil, info
    kirim = [
        {k: v for k, v in {"k": it["k"], "p": it.get("path", ""), "b": None if _KUNCI_SENSITIF.search(it["nama"]) else it.get("bentuk")}.items() if v}
        for it in sisa
    ]
    info["dikirim"] = len(kirim)
    jawab = provider.tanya_json(_prompt_profil(redaksi(kirim)), max_tokens=60 * len(kirim) + 200)
    peta = jawab.get("p") if isinstance(jawab, dict) else None
    if not isinstance(peta, dict):
        info["galat"] = (jawab or {}).get("_galat", "respons AI tak valid") if isinstance(jawab, dict) else "respons AI tak valid"
        return hasil, info
    baru = {k: v for k, v in peta.items() if isinstance(v, dict) and k in {it["k"] for it in sisa}}
    hasil.update(baru)
    with _kunci_cache:
        cache = _muat_cache()
        cache.update(baru)
        _simpan_cache(cache)
    return hasil, info


def nilai_ambigu(kasus: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
    """`kasus`: [{id, m, j, s, d, ct}] → ({id: penilaian}, info)."""
    info: dict[str, Any] = {"dikirim": 0}
    if mode() != "hemat" or not kasus:
        return {}, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return {}, info
    kirim = kasus[:MAKS_KASUS]
    info["dikirim"] = len(kirim)
    jawab = provider.tanya_json(_prompt_ambigu(kirim), max_tokens=20 * len(kirim) + 100)
    v = jawab.get("v") if isinstance(jawab, dict) else None
    if not isinstance(v, dict):
        info["galat"] = (jawab or {}).get("_galat", "respons AI tak valid") if isinstance(jawab, dict) else "respons AI tak valid"
        return {}, info
    sah = {"diproses", "disanitasi", "diabaikan", "tak_pasti"}
    return {str(k): str(x) for k, x in v.items() if str(x) in sah}, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
