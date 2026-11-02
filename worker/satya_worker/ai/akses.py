"""AI tie-breaker hemat untuk uji Kontrol Akses (ACCS).

Dipanggil HANYA saat sebuah check ACCS deterministik menghasilkan `tidak_dapat_diverifikasi`.
AI menjawab SATU sub-pertanyaan FAKTUAL per check (mis. "respons ini memuat data milik pengguna
lain?" atau "panel admin tersaji tanpa autentikasi?") dari METADATA non-sensitif — status,
content-type, sinyal boolean — TIDAK PERNAH nilai token/cookie/ID mentah. Kode check yang memetakan
putusan faktual ke lulus/gagal; **AI tak pernah memutus lulus/gagal sendiri** (lih. prinsip `ai/base.py`).

Mode via env `AI_ACCS`: hemat (bawaan) | minimal | off. Karena runner men-dispatch SATU metode per task,
tiap check ACCS memanggil AI paling banyak sekali. Klasifikasi antarmuka admin (fitur stabil per endpoint)
boleh di-cache persisten di `worker/.cache/ai_accs.json`; interpretasi respons runtime tidak di-cache.
Semua kegagalan ditangani anggun: tanpa AI, hasil deterministik tetap utuh.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from .redaksi import redaksi

# Putusan faktual yang sah (bukan "lulus/gagal"); pemetaan ke status dilakukan pemanggil.
_PUTUSAN_SAH = {
    "milik_lain", "milik_sendiri", "publik_atau_kosong",
    "admin_tersaji", "panel_terbuka", "ditolak", "ditolak_atau_login",
    "autentik", "tak_autentik",
    "tak_pasti",
}

# Sub-pertanyaan faktual per check (hanya check yang bisa ditajamkan AI).
_PERTANYAAN: dict[str, str] = {
    "access.horizontal": (
        "Akun A mengakses sebuah objek yang identitasnya milik akun B. Dari metadata respons, apakah "
        "respons memuat DATA MILIK PENGGUNA LAIN (akun B), data MILIK PEMOHON sendiri, atau halaman "
        "publik/kosong/error. Putusan: 'milik_lain', 'milik_sendiri', 'publik_atau_kosong', 'tak_pasti'."
    ),
    "access.vertical": (
        "Seorang pengguna BIASA mengakses URL fungsi administrator. Dari metadata respons, apakah "
        "antarmuka/fungsi ADMIN benar-benar TERSAJI untuk pengguna biasa, atau akses DITOLAK/dialihkan. "
        "Putusan: 'admin_tersaji', 'ditolak', 'tak_pasti'."
    ),
    "access.admin_panel_exposure": (
        "Sebuah URL panel administrator diakses TANPA autentikasi. Dari metadata respons, apakah PANEL "
        "ADMIN terbuka/tersaji, atau respons berupa halaman login/publik/ditolak. "
        "Putusan: 'panel_terbuka', 'ditolak_atau_login', 'tak_pasti'."
    ),
    "access.token_validation": (
        "Sebuah token sesi yang DIMODIFIKASI/dirusak dipakai mengakses area terbatas. Dari metadata "
        "respons, apakah sesi masih diterima (TERAUTENTIKASI) atau DITOLAK. "
        "Putusan: 'autentik', 'tak_autentik', 'tak_pasti'."
    ),
}

# Hanya klasifikasi antarmuka admin (stabil per endpoint) yang layak di-cache.
_CACHE_UNTUK = {"access.vertical", "access.admin_panel_exposure"}

_kunci_cache = threading.Lock()


def _provider() -> Any:
    # Dibaca saat dipanggil (bukan saat impor) agar bisa di-monkeypatch pada tes.
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_ACCS", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _berkas_cache() -> Path:
    return Path(os.environ.get("AI_ACCS_CACHE", str(Path(__file__).resolve().parents[2] / ".cache" / "ai_accs.json")))


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


def _prompt(check_id: str, metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. " + _PERTANYAAN[check_id] + "\n"
        "Nilai hanya dari metadata di bawah (tanpa nilai rahasia); jangan mengarang. "
        "Jawab HANYA satu objek JSON ringkas tanpa penjelasan panjang:\n"
        '  {"putusan":"<salah satu pilihan>","keyakinan":0.0,"alasan":"<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def layak(check_id: str) -> bool:
    """True bila check ini punya pertanyaan faktual yang bisa ditajamkan AI."""
    return check_id in _PERTANYAAN


def arbitrase_akses(
    check_id: str,
    metadata: dict[str, Any],
    *,
    kunci_cache: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Tie-breaker faktual untuk hasil ACCS yang ambigu.

    Return (`{putusan, keyakinan, alasan}` | None, info). Mengembalikan None bila mode off,
    check tak didukung, provider tak ada, atau respons AI tak valid. **Tidak pernah melempar.**
    """
    info: dict[str, Any] = {"mode": mode(), "dari_cache": False, "dikirim": 0}
    if mode() == "off" or not layak(check_id):
        return None, info

    boleh_cache = check_id in _CACHE_UNTUK and bool(kunci_cache)
    if boleh_cache:
        with _kunci_cache:
            cache = _muat_cache()
        if kunci_cache in cache:
            info["dari_cache"] = True
            return cache[kunci_cache], info

    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info

    kirim = redaksi(metadata)  # pertahanan berlapis: nilai berkunci sensitif tetap disensor
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt(check_id, kirim), max_tokens=300)
    except Exception as e:  # provider tak boleh menjatuhkan check
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info

    putusan = str(jawab.get("putusan")) if isinstance(jawab, dict) else None
    if putusan not in _PUTUSAN_SAH:
        info["galat"] = (jawab or {}).get("_galat", "respons AI tak valid") if isinstance(jawab, dict) else "respons AI tak valid"
        return None, info

    hasil = {
        "putusan": putusan,
        "keyakinan": jawab.get("keyakinan"),
        "alasan": str(jawab.get("alasan", ""))[:300],
    }
    if boleh_cache:
        with _kunci_cache:
            cache = _muat_cache()
            cache[kunci_cache] = hasil
            _simpan_cache(cache)
    return hasil, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
