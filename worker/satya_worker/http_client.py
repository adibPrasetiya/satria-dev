"""Klien HTTP worker: timeout, user-agent SATYA, penjaga ruang lingkup
(hanya host aset), perekam bukti request/response, dan penyamaran kredensial.

Penyamaran dilakukan DI SINI sebelum bukti meninggalkan worker, sesuai
aturan di backend/README.md dan API_CONTRACT.md (kata sandi/token/cookie
tidak boleh keluar sebagai teks asli).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx

from .models import Bukti

USER_AGENT = "SATYA-Worker/0.1 (+asesmen-kelaikan-keamanan)"
_DISAMARKAN = "[disamarkan]"

# Kunci sensitif yang nilainya disamarkan pada bukti.
_KUNCI_SENSITIF = re.compile(
    r"(password|passwd|sandi|token|secret|authorization|api[_-]?key|cookie)",
    re.IGNORECASE,
)


def _sekarang() -> str:
    return datetime.now(timezone.utc).isoformat()


class LuarRuangLingkup(Exception):
    """Dilempar bila sebuah URL keluar dari host aset yang diizinkan."""


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def samarkan_nilai(data: Any) -> Any:
    """Salin struktur data dengan nilai pada kunci sensitif diganti."""
    if isinstance(data, dict):
        return {
            k: (_DISAMARKAN if _KUNCI_SENSITIF.search(str(k)) else samarkan_nilai(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [samarkan_nilai(v) for v in data]
    return data


def samarkan_header(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: (_DISAMARKAN if _KUNCI_SENSITIF.search(k) else v) for k, v in headers.items()
    }


class KlienScan:
    """Pembungkus httpx.Client dengan penjaga ruang lingkup + perekam bukti."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        *,
        host_izin: Optional[set[str]] = None,
        follow_redirects: bool = False,
        saat_request: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        # Host yang boleh dihubungi: host aset + host endpoint yang operator konfigurasikan
        # (mis. api.* di subdomain berbeda). Semua berasal dari target tepercaya.
        self._host_izin = {_host(base_url)} | {h for h in (host_izin or set()) if h}
        self._bukti: list[Bukti] = []
        # Hook peristiwa uji (animasi UI): dipanggil sekali per request dengan metadata aman.
        self._saat_request = saat_request
        self._no = 0
        self._klien = httpx.Client(
            timeout=timeout,
            follow_redirects=follow_redirects,
            headers={"User-Agent": USER_AGENT},
            verify=True,
        )

    def __enter__(self) -> "KlienScan":
        return self

    def __exit__(self, *exc: object) -> None:
        self._klien.close()

    @property
    def bukti(self) -> list[Bukti]:
        return self._bukti

    def pakai_token(self, token: str) -> None:
        """Pasang Authorization: Bearer untuk request berikutnya (sesi token)."""
        self._klien.headers["Authorization"] = f"Bearer {token}"

    def _jaga_ruang_lingkup(self, url: str) -> None:
        h = _host(url)
        if h and self._host_izin and h not in self._host_izin:
            raise LuarRuangLingkup(f"URL {url} di luar host yang diizinkan ({', '.join(sorted(self._host_izin))})")

    def kirim(
        self,
        metode: str,
        url: str,
        *,
        json: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        content: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        judul_bukti: str,
        sandi_disamarkan: Optional[str] = None,
    ) -> httpx.Response:
        """Kirim request dan rekam bukti request/response (tersamarkan).

        `content` = badan mentah (str/bytes) untuk menguji penanganan body non-JSON (mis. uji
        Content-Type/skema API). `headers` = header tambahan per-request (mis. Origin untuk uji CORS);
        nilai berkunci sensitif otomatis disamarkan pada bukti.
        """
        self._jaga_ruang_lingkup(url)
        # Badan untuk bukti selalu dict agar perekam & animasi aman (content mentah diringkas).
        body_rekam: dict[str, Any] = (
            json if isinstance(json, dict)
            else data if isinstance(data, dict)
            else {"_body": str(content)[:500]} if content is not None
            else {}
        )
        t0 = time.perf_counter()
        try:
            resp = self._klien.request(metode, url, json=json, data=data, content=content, headers=headers)
        except Exception as e:
            self._lapor(metode, url, body_rekam, None, t0, type(e).__name__)
            raise
        self._rekam(resp, judul_bukti, body_rekam, sandi_disamarkan)
        self._lapor(metode, url, body_rekam, resp, t0)
        return resp

    def _lapor(self, metode: str, url: str, body: Optional[dict[str, Any]], resp: Optional[httpx.Response],
               t0: float, galat: Optional[str] = None) -> None:
        if self._saat_request is None:
            return
        from .peristiwa_uji import ringkas_request

        self._no += 1
        try:
            self._saat_request(ringkas_request(self._no, metode, url, body, resp, int((time.perf_counter() - t0) * 1000), galat))
        except Exception:
            pass  # animasi tak boleh menjatuhkan check

    def _rekam(
        self,
        resp: httpx.Response,
        judul: str,
        body_dikirim: dict[str, Any],
        sandi_disamarkan: Optional[str],
    ) -> None:
        req = resp.request
        body_aman = samarkan_nilai(body_dikirim)
        cuplik = resp.text[:1000]
        if sandi_disamarkan:
            cuplik = cuplik.replace(sandi_disamarkan, _DISAMARKAN)
        isi = (
            f"> {req.method} {req.url}\n"
            f"> body: {body_aman}\n"
            f"< {resp.status_code} {resp.reason_phrase}\n"
            f"< {dict(list(samarkan_header(dict(resp.headers)).items())[:8])}\n"
            f"< {cuplik}"
        )
        self._bukti.append(
            Bukti(
                jenis="request_response",
                judul=judul,
                isi=isi,
                waktu=_sekarang(),
            )
        )
