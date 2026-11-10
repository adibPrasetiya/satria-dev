"""Fuzzing recon dengan ffuf (biner Go eksternal) — pengaya penemuan parameter & path.

Dipakai saat lebih efisien daripada menebak sendiri: menemukan NAMA parameter query yang
diterima endpoint (`?FUZZ=…`) dan path/berkas tersembunyi (`/FUZZ`). Seperti katana, ini biner
eksternal yang dibungkus dengan fallback anggun — bila ffuf tak terpasang / di-disable, setiap
fungsi mengembalikan daftar kosong dan recon tetap berjalan tanpanya.

Deteksi "diterima" memakai auto-kalibrasi ffuf (`-ac`) + penyaringan status, sehingga respons
generik (404/halaman seragam) tak dianggap temuan. Non-destruktif: hanya GET.

Konfigurasi env:
    FFUF_BIN             path biner ffuf (default 'ffuf' di PATH)
    FFUF_ENABLE          '1'/'true' memaksa aktif; default: aktif bila biner ada
    FFUF_TIMEOUT         batas waktu proses (detik, default 60)
    FFUF_MAX             batas jumlah temuan yang dikembalikan (default 40)
    FFUF_WORDLIST_PARAM  wordlist nama parameter (opsional; bawaan: daftar internal ringkas)
    FFUF_WORDLIST_PATH   wordlist path/berkas (opsional; tanpa ini, penemuan path dilewati)
    FFUF_RATE            batas laju request/detik (default 40) — jaga target tak kebanjiran
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from . import koordinasi

# Nama parameter umum pada API pemerintahan/berbahasa Indonesia + konvensi REST (untuk FUZZ ?param).
_PARAM_BAWAAN = [
    "id", "page", "halaman", "limit", "offset", "per_page", "size", "q", "query", "cari", "keyword", "kata",
    "sort", "order", "sort_by", "order_by", "urut", "filter", "status", "tipe", "jenis", "kategori", "tahun",
    "bulan", "tanggal", "start", "end", "mulai", "selesai", "unit", "satuan", "nip", "nik", "user_id", "unit_id",
    "search", "fields", "include", "expand", "format", "lang", "export", "download", "preview", "debug",
]


def _bin() -> str:
    return os.environ.get("FFUF_BIN", "ffuf").strip() or "ffuf"


def tersedia() -> bool:
    """True bila biner ffuf ditemukan dan tidak di-disable via env."""
    flag = os.environ.get("FFUF_ENABLE", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    return shutil.which(_bin()) is not None


def _env_num(nama: str, bawaan: float) -> float:
    try:
        return float(os.environ.get(nama, str(bawaan)))
    except ValueError:
        return bawaan


def _maks() -> int:
    return int(_env_num("FFUF_MAX", 40))


def _maks_baris() -> int:
    """Batas jumlah entri wordlist agar ffuf TUNTAS dalam FFUF_TIMEOUT (ffuf hanya menulis hasil saat
    selesai — bila di-kill timeout, keluaran kosong). 0 = tanpa batas. Bawaan 1500 (~38 dtk @ rate 40)."""
    return int(_env_num("FFUF_WORDLIST_MAXLINES", 1500))


def _tulis_temp(baris: list[str]) -> str:
    fd, path = tempfile.mkstemp(prefix="satya_ffuf_", suffix=".txt", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(baris))
    return path


def _wordlist(env: str, bawaan: Optional[list[str]]) -> Optional[str]:
    """Path wordlist dari env (dipangkas ke `FFUF_WORDLIST_MAXLINES` agar ffuf tuntas dalam timeout),
    atau tulis `bawaan` ke berkas sementara. None bila tak ada sumber."""
    cap = _maks_baris()
    p = os.environ.get(env, "").strip()
    if p and os.path.isfile(p):
        if cap <= 0:
            return p
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                baris = [b.rstrip("\n") for _, b in zip(range(cap + 1), f)]
        except OSError:
            return p
        if len(baris) <= cap:
            return p                      # sudah cukup kecil → pakai apa adanya
        return _tulis_temp(baris[:cap])   # dipangkas → berkas sementara
    if not bawaan:
        return None
    return _tulis_temp(bawaan if cap <= 0 else bawaan[:cap])


def _jalankan_ffuf(url: str, wordlist: str, *, cookie: Optional[str] = None) -> list[dict[str, Any]]:
    """Jalankan ffuf dengan output JSON ke stdout; return list hasil mentah (`results`). [] bila gagal."""
    perintah = [
        _bin(),
        "-u", url,
        "-w", f"{wordlist}:FUZZ",
        "-ac",                     # auto-kalibrasi: buang respons generik/seragam
        "-mc", "200,201,204,301,302,307,400,401,403,405,422,429,500",  # status menarik; 404 dibuang
        "-fc", "404",
        "-t", "20",
        "-rate", str(int(_env_num("FFUF_RATE", 40))),
        "-timeout", "10",
        "-s",                      # senyap (tanpa banner/progress)
        "-of", "json",
        "-o", "/dev/stdout" if os.name != "nt" else "CON",
    ]
    if cookie:
        perintah += ["-b", cookie]
    try:
        proc = koordinasi.jalankan_proses(perintah, text=True, encoding="utf-8", errors="replace",
                                          timeout=_env_num("FFUF_TIMEOUT", 60))
    except (subprocess.TimeoutExpired, OSError):
        return []
    out = proc.stdout or ""
    i = out.find("{")
    if i < 0:
        return []
    try:
        data = json.loads(out[i:])
    except ValueError:
        return []
    hasil = data.get("results") if isinstance(data, dict) else None
    return hasil if isinstance(hasil, list) else []


def temukan_parameter(url: str, *, cookie: Optional[str] = None) -> list[str]:
    """Temukan NAMA parameter query yang berpengaruh pada `url` (mis. `/api/cuti?FUZZ=1`).

    Return daftar nama parameter unik (≤FFUF_MAX). Best-effort: biner absen → []."""
    if not tersedia():
        return []
    wl = _wordlist("FFUF_WORDLIST_PARAM", _PARAM_BAWAAN)
    if not wl:
        return []
    s = urlsplit(url)
    sep = "&" if s.query else ""
    fuzz_url = urlunsplit((s.scheme, s.netloc, s.path, f"{s.query}{sep}FUZZ=satya", ""))
    hasil = _jalankan_ffuf(fuzz_url, wl, cookie=cookie)
    nama: list[str] = []
    for r in hasil:
        inp = r.get("input") if isinstance(r, dict) else None
        v = (inp or {}).get("FUZZ") if isinstance(inp, dict) else None
        if isinstance(v, str) and v and v not in nama:
            nama.append(v)
    return nama[:_maks()]


def temukan_path(base_url: str, *, cookie: Optional[str] = None) -> list[dict[str, Any]]:
    """Temukan path/berkas tersembunyi di bawah `base_url` (`/FUZZ`). Hanya aktif bila FFUF_WORDLIST_PATH
    diset (wordlist path bisa besar; tak disertakan bawaan). Return [{path, status}]. [] bila tak ada."""
    if not tersedia():
        return []
    wl = _wordlist("FFUF_WORDLIST_PATH", None)
    if not wl:
        return []
    s = urlsplit(base_url)
    fuzz_url = urlunsplit((s.scheme, s.netloc, (s.path.rstrip("/") + "/FUZZ"), "", ""))
    out: list[dict[str, Any]] = []
    terlihat: set[str] = set()
    for r in _jalankan_ffuf(fuzz_url, wl, cookie=cookie):
        inp = (r.get("input") or {}) if isinstance(r, dict) else {}
        v = inp.get("FUZZ")
        if isinstance(v, str) and v and v not in terlihat:
            terlihat.add(v)
            out.append({"path": s.path.rstrip("/") + "/" + v, "status": r.get("status")})
        if len(out) >= _maks():
            break
    return out


def parse_hasil_json(teks: str) -> list[dict[str, Any]]:
    """Parse output JSON ffuf (dipakai tes & pemanggil yang menjalankan ffuf sendiri)."""
    i = teks.find("{")
    if i < 0:
        return []
    try:
        data = json.loads(teks[i:])
    except ValueError:
        return []
    r = data.get("results") if isinstance(data, dict) else None
    return r if isinstance(r, list) else []
