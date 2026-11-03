"""AI penajam untuk uji Keamanan Komunikasi (COMM).

Dua kegunaan — keduanya dari METADATA non-sensitif (nama organisasi penerbit, status boolean),
TIDAK PERNAH memutus lulus/gagal (lih. prinsip `ai/base.py`):

1. **Klasifikasi penerbit → PSrE** (COMM-8.4-T03, info): mencocokkan nama organisasi penerbit
   sertifikat ke daftar PSrE resmi Komdigi secara fuzzy (varian nama/anak usaha/singkatan) ketika
   pencocokan string eksak gagal. Hasil hanya informasi bagi asesor — tak memengaruhi status kontrol.
2. **Adjudikasi ambigu** (COMM-8.4-T01): saat check sertifikat deterministik tak dapat memastikan
   kecocokan nama host (mis. wildcard SAN kompleks), AI menjawab SATU pertanyaan faktual; pemetaan
   ke status tetap di kode check.

Mode via env `AI_COMM`: hemat (bawaan) | minimal | off. Karena runner men-dispatch SATU metode per
task, tiap check COMM memanggil AI paling banyak sekali (total ≤2 untuk kedua check di atas per scan).
Klasifikasi penerbit (stabil per host) di-cache persisten di `worker/.cache/ai_comm.json`.
Semua kegagalan ditangani anggun: tanpa AI, hasil deterministik tetap utuh.
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
    # Dibaca saat dipanggil (bukan saat impor) agar bisa di-monkeypatch pada tes.
    from . import muat_provider_dari_env

    return muat_provider_dari_env()


def mode() -> str:
    m = os.environ.get("AI_COMM", "hemat").strip().lower()
    return m if m in ("hemat", "minimal", "off") else "hemat"


def _berkas_cache() -> Path:
    return Path(os.environ.get("AI_COMM_CACHE", str(Path(__file__).resolve().parents[2] / ".cache" / "ai_comm.json")))


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


# --------------------------------------------------------------------------- klasifikasi PSrE

def _prompt_psre(penerbit: dict[str, Any], daftar_psre: list[dict[str, Any]]) -> str:
    nama_psre = [str(p.get("nama", "")) for p in daftar_psre if p.get("nama")]
    return (
        "Asesmen keamanan web yang SAH/berizin. Di bawah ada nama ORGANISASI penerbit sebuah "
        "sertifikat TLS dan DAFTAR Penyelenggara Sertifikat Elektronik (PSrE) yang diakui Komdigi "
        "Indonesia. Tentukan apakah penerbit tersebut termasuk salah satu PSrE pada daftar "
        "(pertimbangkan varian nama resmi, singkatan, nama dagang, atau badan induk; mis. 'BSrE' = "
        "'Balai Besar Sertifikasi Elektronik - BSSN').\n"
        "Nilai HANYA dari nama di bawah; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"psre_cocok": true|false, "nama_psre": "<nama dari daftar atau kosong>", '
        '"keyakinan": 0.0, "alasan": "<ringkas>"}\n\n'
        "Penerbit:\n```json\n" + json.dumps(penerbit, ensure_ascii=False, indent=2) + "\n```\n"
        "Daftar PSrE:\n```json\n" + json.dumps(nama_psre, ensure_ascii=False, indent=2) + "\n```"
    )


def klasifikasi_psre(
    penerbit: dict[str, Any],
    daftar_psre: list[dict[str, Any]],
    *,
    kunci_cache: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Fuzzy-match penerbit sertifikat ke daftar PSrE. Info-only; tak pernah melempar.

    Return (`{psre_cocok, nama_psre, keyakinan, alasan}` | None, info). None bila mode off,
    provider tak ada, atau respons AI tak valid.
    """
    info: dict[str, Any] = {"mode": mode(), "dari_cache": False, "dikirim": 0}
    if mode() == "off" or not (penerbit.get("penerbit_o") or penerbit.get("penerbit_cn")):
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

    kirim = redaksi(penerbit)
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt_psre(kirim, daftar_psre), max_tokens=300)
    except Exception as e:  # provider tak boleh menjatuhkan check
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info

    if not isinstance(jawab, dict) or jawab.get("_galat") or "psre_cocok" not in jawab:
        info["galat"] = (jawab or {}).get("_galat", "respons AI tak valid") if isinstance(jawab, dict) else "respons AI tak valid"
        return None, info

    hasil = {
        "psre_cocok": bool(jawab.get("psre_cocok")),
        "nama_psre": str(jawab.get("nama_psre", ""))[:160],
        "keyakinan": jawab.get("keyakinan"),
        "alasan": str(jawab.get("alasan", ""))[:300],
    }
    if kunci_cache:
        with _kunci_cache:
            cache = _muat_cache()
            cache[kunci_cache] = hasil
            _simpan_cache(cache)
    return hasil, info


# --------------------------------------------------------------------------- adjudikasi kecocokan host

_PUTUSAN_HOST = {"cocok", "tidak_cocok", "tak_pasti"}


def _prompt_host(metadata: dict[str, Any]) -> str:
    return (
        "Asesmen keamanan web yang SAH/berizin. Sebuah sertifikat TLS disajikan untuk sebuah host. "
        "Dari metadata (nama host yang diminta, Subject CN, dan daftar SAN), tentukan apakah "
        "sertifikat SAH untuk host tersebut (termasuk kecocokan wildcard yang benar, mis. "
        "'*.contoh.go.id' cocok untuk 'api.contoh.go.id' tetapi TIDAK untuk 'a.b.contoh.go.id').\n"
        "Nilai HANYA dari metadata; jangan mengarang. Jawab HANYA satu objek JSON ringkas:\n"
        '  {"putusan":"cocok|tidak_cocok|tak_pasti","keyakinan":0.0,"alasan":"<ringkas>"}\n\n'
        "Metadata:\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```"
    )


def arbitrase_host(metadata: dict[str, Any]) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Tie-breaker faktual kecocokan nama host sertifikat yang ambigu. Tak pernah melempar.

    Return (`{putusan, keyakinan, alasan}` | None, info). None bila mode off / provider tak ada /
    respons tak valid. `putusan` ∈ {cocok, tidak_cocok, tak_pasti}.
    """
    info: dict[str, Any] = {"mode": mode(), "dikirim": 0}
    if mode() == "off":
        return None, info
    provider = _provider()
    if provider is None or not hasattr(provider, "tanya_json"):
        return None, info
    info["dikirim"] = 1
    try:
        jawab = provider.tanya_json(_prompt_host(redaksi(metadata)), max_tokens=300)
    except Exception as e:
        info["galat"] = f"{type(e).__name__}: {e}"
        return None, info
    putusan = str(jawab.get("putusan")) if isinstance(jawab, dict) else None
    if putusan not in _PUTUSAN_HOST:
        info["galat"] = "respons AI tak valid"
        return None, info
    return {
        "putusan": putusan,
        "keyakinan": jawab.get("keyakinan"),
        "alasan": str(jawab.get("alasan", ""))[:300],
    }, info


def provider_aktif() -> Optional[str]:
    p = _provider()
    return f"{p.nama} ({p.model})" if p is not None else None
