"""Engine crawl katana (projectdiscovery) — penemuan endpoint mendalam.

Berbeda dari ZAP (daemon REST) & Playwright (library in-proses): katana adalah
**biner Go eksternal** yang dijalankan via subprocess. Modul ini membungkusnya
dengan fallback anggun — bila biner tak terpasang/di-disable, `jalankan()`
mengembalikan daftar kosong dan discovery tetap berjalan tanpa katana.

Katana melakukan crawl standar + headless + JS-parsing (opsi `-jc`/`-kf`) sehingga
menemukan endpoint yang tertanam di berkas JavaScript, tidak hanya tautan HTML.
Scope dikunci ke host target (`-fs fqdn`). Crawl terautentikasi didukung lewat
header/cookie opsional (`-H`).

Konfigurasi env:
    KATANA_BIN       path biner katana (default 'katana' di PATH)
    KATANA_ENABLE    '1'/'true' untuk memaksa aktif; default: aktif bila biner ada
    KATANA_TIMEOUT   batas waktu proses (detik, default 120)
    KATANA_DEPTH     kedalaman crawl (-d, default 3)
    KATANA_MAX       batas jumlah URL yang dikembalikan (default 500)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Optional
from urllib.parse import urlsplit

from . import koordinasi


def _bin() -> str:
    return os.environ.get("KATANA_BIN", "katana").strip() or "katana"


def tersedia() -> bool:
    """True bila biner katana ditemukan dan tidak di-disable via env."""
    flag = os.environ.get("KATANA_ENABLE", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    return shutil.which(_bin()) is not None


def _timeout() -> float:
    try:
        return float(os.environ.get("KATANA_TIMEOUT", "120"))
    except ValueError:
        return 120.0


def _depth() -> int:
    try:
        return int(os.environ.get("KATANA_DEPTH", "3"))
    except ValueError:
        return 3


def _maks() -> int:
    try:
        return int(os.environ.get("KATANA_MAX", "500"))
    except ValueError:
        return 500


def _host(u: str) -> str:
    return (urlsplit(u).hostname or "").lower()


def _info_respons(resp: dict[str, Any]) -> dict[str, Any]:
    """Status & content-type dari blok `response` JSONL katana (kunci header dinormalisasi
    katana jadi snake_case, mis. `content_type`; bentuk asli `Content-Type` juga diterima)."""
    out: dict[str, Any] = {}
    status = resp.get("status_code")
    if isinstance(status, int) and status:
        out["status"] = status
    hdr = resp.get("headers") or {}
    if isinstance(hdr, dict):
        for k, v in hdr.items():
            if str(k).lower().replace("-", "_") == "content_type" and v:
                out["content_type"] = str(v[0] if isinstance(v, list) and v else v)
                break
    return out


def jalankan(
    base_url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    cookie: Optional[str] = None,
    timeout: Optional[float] = None,
    depth: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Crawl `base_url` dengan katana. Kembalikan list {url, method, tag, source, status?, content_type?} in-scope.

    `headers`/`cookie` dipakai untuk crawl terautentikasi (mis. Authorization/Cookie sesi).
    Best-effort: biner absen, timeout, atau output tak terparse → [].
    """
    if not tersedia():
        return []
    host = _host(base_url)
    perintah = [
        _bin(),
        "-u", base_url,
        "-jc",            # crawl endpoint di dalam berkas JS
        "-kf", "all",     # ikuti known-files (robots, sitemap)
        "-silent",
        "-jsonl",         # satu objek JSON per baris
        "-d", str(depth if depth is not None else _depth()),
        "-fs", "fqdn",    # batasi scope ke FQDN target
        "-timeout", "10",
    ]
    for k, v in (headers or {}).items():
        perintah += ["-H", f"{k}: {v}"]
    if cookie:
        perintah += ["-H", f"Cookie: {cookie}"]

    try:
        # Bisa disela: proses dimatikan bila scan dibatalkan / target dinyatakan tak terjangkau.
        proc = koordinasi.jalankan_proses(
            perintah,
            text=True,
            # Keluaran katana UTF-8; tanpa ini Windows memakai cp1252 → thread pembaca crash pada
            # karakter non-Latin dan seluruh hasil hilang. Byte rusak diganti, bukan menggagalkan.
            encoding="utf-8",
            errors="replace",
            timeout=timeout if timeout is not None else _timeout(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    hasil: list[dict[str, Any]] = []
    terlihat: set[str] = set()
    maks = _maks()
    for baris in (proc.stdout or "").splitlines():
        baris = baris.strip()
        if not baris:
            continue
        try:
            obj = json.loads(baris)
        except ValueError:
            continue
        # Skema JSONL katana: {"timestamp":..,"request":{"endpoint","method"},"response":{..}}
        req = obj.get("request") or {}
        url = req.get("endpoint") or obj.get("endpoint") or obj.get("url") or ""
        if not url or _host(url) != host:
            continue
        kunci = f"{(req.get('method') or 'GET').upper()} {url}"
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        hasil.append({
            "url": url,
            "method": (req.get("method") or "GET").upper(),
            "tag": req.get("tag") or obj.get("tag") or "",
            "source": req.get("source") or obj.get("source") or "katana",
            **_info_respons(obj.get("response") or {}),
        })
        if len(hasil) >= maks:
            break
    return hasil
