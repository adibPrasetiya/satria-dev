"""AI tie-breaker hemat untuk uji Manajemen Sesi (SESS).

Dipanggil HANYA saat sebuah check SESS deterministik menghasilkan `tidak_dapat_diverifikasi`.
AI menjawab SATU sub-pertanyaan FAKTUAL per check (mis. "respons ini area terautentikasi
atau halaman publik?") dari METADATA non-sensitif — status, content-type, ciri bentuk token,
atribut cookie — TIDAK PERNAH nilai token/cookie. Kode check yang memetakan putusan faktual
ke lulus/gagal; **AI tak pernah memutus lulus/gagal sendiri** (lih. prinsip `ai/base.py`).

Mode via env `AI_SESS`: hemat (bawaan) | minimal | off. Karena runner men-dispatch SATU metode
per task, tiap check SESS memanggil AI paling banyak sekali. Putusan fingerprint pola token
(stabil) di-cache persisten di `worker/.cache/ai_sess.json` → scan ulang ≈ 0 token; putusan yang
bergantung isi respons runtime (logout/akses) tidak di-cache. Semua kegagalan ditangani anggun:
tanpa AI, hasil deterministik tetap utuh.
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
    "autentik", "tak_autentik", "publik",
    "cocok_kerangka", "tak_cocok",
    "ada_pembatasan", "tak_ada",
    "prediktabel", "acak_kuat",
    "tak_pasti",
}

# Sub-pertanyaan faktual per check (hanya check yang bisa ditajamkan AI).
_PERTANYAAN: dict[str, str] = {
    "session.logout_invalidates": (
        "Sebuah sesi dipakai mengakses area terautentikasi SETELAH logout. Dari metadata respons, "
        "apakah sesi lama itu MASIH diterima server. Putusan: 'autentik' (masih diterima), "
        "'tak_autentik' (ditolak/sudah tidak berlaku), atau 'tak_pasti'."
    ),
    "session.reject_unknown_id": (
        "Sebuah token sesi ASING (tak pernah diterbitkan server) dipakai mengakses sebuah endpoint. "
        "Dari metadata respons, apakah respons berasal dari AREA TERAUTENTIKASI (token asing diterima) "
        "atau HALAMAN PUBLIK/redirect login (token diabaikan). Putusan: 'autentik', 'publik', 'tak_pasti'."
    ),
    "session.framework_fingerprint": (
        "Dari ciri bentuk token sesi berikut, apakah pola ini cocok dengan pengendali sesi yang lazim "
        "disediakan kerangka kerja web (mis. JWT standar, cookie sesi kerangka umum). "
        "Putusan: 'cocok_kerangka', 'tak_cocok', 'tak_pasti'."
    ),
    "session.concurrent_sessions": (
        "Dua sesi untuk akun yang sama aktif bersamaan. Dari metadata respons, apakah aplikasi tampak "
        "MEMBATASI atau MEMBERI TAHU adanya sesi ganda. Putusan: 'ada_pembatasan', 'tak_ada', 'tak_pasti'."
    ),
    "session.concurrent_clone": (
        "Satu artefak sesi (token/cookie) yang SAMA dipakai dari DUA klien independen secara paralel, dan "
        "keduanya mengakses area terautentikasi. Dari metadata, apakah aplikasi tampak MEMBATASI/mengikat "
        "sesi ke satu klien (mis. menolak salah satu, memberi tahu), atau TIDAK ada pembatasan sama sekali. "
        "Putusan: 'ada_pembatasan', 'tak_ada', 'tak_pasti'."
    ),
    "session.token_structure": (
        "Berikut ciri STRUKTUR sebuah token sesi (format jwt/opaque, algoritma, daftar nama klaim, klaim "
        "pembawa identitas sesi dan BENTUK nilainya — uuid/int/timestamp/email/username/opaque, serta lapisan "
        "encode bila ada). TANPA melihat nilai mentah, apakah identitas sesi yang dibawa token ini tampak "
        "DAPAT DITEBAK/prediktabel (mis. angka berurutan, timestamp, username, email, alg 'none') atau ACAK "
        "kuat (uuid/opaque berentropi, tanda tangan memadai). Putusan: 'prediktabel', 'acak_kuat', 'tak_pasti'."
    ),
    "session.token_entropy": (
        "Berikut metadata dari beberapa sampel token sesi lintas-login (bentuk dominan, apakah semua unik, "
        "apakah identitas di dalamnya BERURUTAN/menaik, berapa yang angkanya terbaca). TANPA nilai mentah, "
        "apakah token sesi aplikasi ini tampak PREDIKTABEL (berpola/berurutan/ter-encode dari nilai tertebak) "
        "atau ACAK kuat. Putusan: 'prediktabel', 'acak_kuat', 'tak_pasti'."
    ),
}

# Fingerprint pola/struktur token yang layak di-cache (fitur stabil lintas scan).
_CACHE_UNTUK = {"session.framework_fingerprint", "session.token_structure"}

_kunci_cache = threading.Lock()


def _provider() -> Any:
    # Dibaca saat dipanggil (bukan saat impor) agar bisa di-monkeypatch pada tes.
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_SESS", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _berkas_cache() -> Path:
    return Path(os.environ.get("AI_SESS_CACHE", str(Path(__file__).resolve().parents[2] / ".cache" / "ai_sess.json")))


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


def arbitrase_sesi(
    check_id: str,
    metadata: dict[str, Any],
    *,
    kunci_cache: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Tie-breaker faktual untuk hasil SESS yang ambigu.

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
