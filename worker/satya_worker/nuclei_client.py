"""Engine `nuclei` (projectdiscovery) — pemindai berbasis template untuk paparan API/debug.

Seperti katana: **biner Go eksternal** via subprocess dengan fallback anggun — bila biner tak
terpasang / di-disable / template belum terunduh, `jalankan()` mengembalikan daftar kosong dan
check yang memanggilnya melapor `tidak_dapat_diverifikasi` (tak menghakimi tanpa bukti).

Dipakai fungsi Keamanan API (APIS-12.2-T02): mendeteksi dokumentasi API / endpoint debug yang
terbuka publik (Swagger/OpenAPI/GraphQL/actuator/debug-vars). Dijalankan dengan TAG terfokus agar
hemat & minim derau; hasil mentah masih dapat ditajamkan AI (`ai/api.py`) untuk kurangi positif palsu.

Konfigurasi env:
    NUCLEI_BIN       path biner nuclei (default 'nuclei' di PATH)
    NUCLEI_ENABLE    '0'/'false' menonaktifkan; selain itu aktif bila biner ada
    NUCLEI_TIMEOUT   batas waktu proses (detik, default 180)
    NUCLEI_TAGS      tag template (default 'exposure,swagger,api,config,misconfig,debug')
    NUCLEI_SEVERITY  ambang severity (default 'low,medium,high,critical')
    NUCLEI_RATE      batas laju request/detik (default 50)

Pasang: `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` lalu
`nuclei -update-templates` sekali. Tanpa itu, check APIS-12.2-T02 = tidak_dapat_diverifikasi.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Optional
from urllib.parse import urlsplit

# Kata kunci template yang relevan dengan "dokumentasi API / endpoint debug terbuka".
_RELEVAN = (
    "swagger", "openapi", "api-doc", "api_doc", "apidoc", "graphql", "redoc",
    "actuator", "debug", "phpinfo", "env", "config", "wadl", "wsdl", "soap",
)


def _bin() -> str:
    return os.environ.get("NUCLEI_BIN", "nuclei").strip() or "nuclei"


def tersedia() -> bool:
    flag = os.environ.get("NUCLEI_ENABLE", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    return shutil.which(_bin()) is not None


def _timeout() -> float:
    try:
        return float(os.environ.get("NUCLEI_TIMEOUT", "180"))
    except ValueError:
        return 180.0


def _tags() -> str:
    return os.environ.get("NUCLEI_TAGS", "exposure,swagger,api,config,misconfig,debug").strip()


def _severity() -> str:
    return os.environ.get("NUCLEI_SEVERITY", "low,medium,high,critical").strip()


def _rate() -> str:
    return os.environ.get("NUCLEI_RATE", "50").strip() or "50"


def _host(u: str) -> str:
    return (urlsplit(u).hostname or "").lower()


def _relevan(f: dict[str, Any]) -> bool:
    """True bila temuan terkait paparan dokumentasi/debug API."""
    tid = str(f.get("template_id") or "").lower()
    nama = str(f.get("nama") or "").lower()
    tags = " ".join(str(t).lower() for t in (f.get("tags") or []))
    blob = f"{tid} {nama} {tags}"
    return any(k in blob for k in _RELEVAN)


def jalankan(
    base_url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    hanya_relevan: bool = True,
    timeout: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Pindai `base_url` dengan nuclei (tag terfokus). Kembalikan list temuan in-scope:
    {template_id, nama, severity, tags, matched_at, url}. Best-effort → [] bila biner absen/gagal.
    """
    if not tersedia():
        return []
    host = _host(base_url)
    perintah = [
        _bin(),
        "-u", base_url,
        "-jsonl",
        "-silent",
        "-no-color",
        "-disable-update-check",
        "-tags", _tags(),
        "-severity", _severity(),
        "-rate-limit", _rate(),
        "-timeout", "10",
    ]
    for k, v in (headers or {}).items():
        perintah += ["-H", f"{k}: {v}"]

    try:
        proc = subprocess.run(
            perintah,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout if timeout is not None else _timeout(),
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    hasil: list[dict[str, Any]] = []
    terlihat: set[str] = set()
    for baris in (proc.stdout or "").splitlines():
        baris = baris.strip()
        if not baris:
            continue
        try:
            obj = json.loads(baris)
        except ValueError:
            continue
        info = obj.get("info") or {}
        url = obj.get("matched-at") or obj.get("matched_at") or obj.get("host") or ""
        if url and _host(url) and _host(url) != host:
            continue
        f = {
            "template_id": obj.get("template-id") or obj.get("templateID") or "",
            "nama": info.get("name") or "",
            "severity": str(info.get("severity") or "").lower(),
            "tags": info.get("tags") or [],
            "matched_at": url,
            "url": url,
        }
        if hanya_relevan and not _relevan(f):
            continue
        kunci = f"{f['template_id']}@{url}"
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        hasil.append(f)
    return hasil
