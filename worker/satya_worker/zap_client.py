"""Klien REST OWASP ZAP (engine `zap`).

Memanggil API ZAP langsung via HTTP(S) — cocok untuk ZAP di belakang reverse proxy
(mis. https://zap.satria.pro) maupun lokal (http://127.0.0.1:8080). API key dikirim
lewat header `X-ZAP-API-Key`. Konfigurasi via env:

    ZAP_BASE_URL   contoh https://zap.satria.pro  (atau http://127.0.0.1:8080)
    ZAP_API_KEY    kunci API ZAP (wajib; ZAP menolak/menutup koneksi tanpa key yang benar)
    ZAP_TIMEOUT_SPIDER   detik maksimum menunggu spider (default 120)
    ZAP_TIMEOUT_ASCAN    detik maksimum menunggu active scan (default 300)

Klien ini hanya mengakses ZAP; ZAP yang mengakses target. Semua operasi bersifat
best-effort dengan batas waktu agar satu scan tidak menggantung worker.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

from . import koordinasi


class ZapTidakTersedia(Exception):
    """ZAP belum dikonfigurasi atau tidak dapat dihubungi."""


class ZapClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 30.0) -> None:
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self._klien = httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={"X-ZAP-API-Key": api_key, "Accept": "application/json"},
            verify=True,
        )

    def __enter__(self) -> "ZapClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self._klien.close()

    # ---- primitif API ----
    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        r = self._klien.get(f"{self.base}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def version(self) -> str:
        return str(self._get("/JSON/core/view/version/").get("version", ""))

    def access_url(self, url: str) -> None:
        try:
            self._get("/JSON/core/action/accessUrl/", url=url, followRedirects="true")
        except httpx.HTTPError:
            pass

    # ---- spider tradisional ----
    def spider_start(self, url: str) -> str:
        return str(self._get("/JSON/spider/action/scan/", url=url, recurse="true", subtreeOnly="true").get("scan", ""))

    def spider_status(self, sid: str) -> int:
        return int(self._get("/JSON/spider/view/status/", scanId=sid).get("status", 0))

    # ---- ajax spider (untuk SPA) ----
    def ajax_start(self, url: str) -> None:
        self._get("/JSON/ajaxSpider/action/scan/", url=url, inScope="false")

    def ajax_status(self) -> str:
        return str(self._get("/JSON/ajaxSpider/view/status/").get("status", "stopped"))

    # ---- passive scan ----
    def pscan_records_to_scan(self) -> int:
        return int(self._get("/JSON/pscan/view/recordsToScan/").get("recordsToScan", 0))

    def send_request(self, raw: str) -> bool:
        """Kirim request mentah lewat ZAP (menyemai endpoint API — termasuk POST JSON — ke situs ZAP)."""
        try:
            self._get("/JSON/core/action/sendRequest/", request=raw, followRedirects="false")
            return True
        except httpx.HTTPError:
            return False

    # ---- active scan ----
    def ascan_start(self, url: str) -> str:
        return str(self._get("/JSON/ascan/action/scan/", url=url, recurse="true", inScopeOnly="false").get("scan", ""))

    def ascan_status(self, sid: str) -> int:
        return int(self._get("/JSON/ascan/view/status/", scanId=sid).get("status", 0))

    # ---- alerts & cakupan ----
    def alerts(self, baseurl: str, *, count: int = 2000) -> list[dict[str, Any]]:
        data = self._get("/JSON/core/view/alerts/", baseurl=baseurl, start=0, count=count)
        return list(data.get("alerts", []))

    def daftar_url(self, baseurl: str) -> list[str]:
        """Daftar URL di bawah baseurl yang sudah dilihat ZAP."""
        try:
            data = self._get("/JSON/core/view/urls/", baseurl=baseurl)
            return list(data.get("urls", []))
        except httpx.HTTPError:
            return []

    def jumlah_url(self, baseurl: str) -> int:
        """Berapa URL di bawah baseurl yang sudah dilihat ZAP (0 = target tak terjangkau)."""
        return len(self.daftar_url(baseurl))

    # ---- orkestrasi dgn batas waktu ----
    def jalankan_spider(self, url: str, *, batas: float) -> bool:
        """Spider + ajax spider + tunggu passive scan. True bila selesai dalam batas."""
        self.access_url(url)
        t0 = time.monotonic()
        sid = self.spider_start(url)
        while self.spider_status(sid) < 100:
            if time.monotonic() - t0 > batas:
                return False
            koordinasi.tunggu(2)
        # Ajax spider untuk aplikasi SPA (best-effort).
        try:
            self.ajax_start(url)
            while self.ajax_status() == "running":
                if time.monotonic() - t0 > batas:
                    break
                koordinasi.tunggu(2)
        except httpx.HTTPError:
            pass
        # Tunggu antrean passive scan kosong.
        while self.pscan_records_to_scan() > 0:
            if time.monotonic() - t0 > batas:
                break
            koordinasi.tunggu(1)
        return True

    def jalankan_ascan(self, url: str, *, batas: float) -> bool:
        t0 = time.monotonic()
        try:
            sid = self.ascan_start(url)
        except httpx.HTTPError:
            return False
        while self.ascan_status(sid) < 100:
            if time.monotonic() - t0 > batas:
                return False
            koordinasi.tunggu(3)
        return True


def dari_env() -> Optional[ZapClient]:
    """Buat klien dari env; None bila ZAP belum dikonfigurasi."""
    base = os.environ.get("ZAP_BASE_URL", "").strip()
    key = os.environ.get("ZAP_API_KEY", "").strip()
    if not base or not key:
        return None
    return ZapClient(base, key)


def batas_spider() -> float:
    return float(os.environ.get("ZAP_TIMEOUT_SPIDER", "120"))


def batas_ascan() -> float:
    return float(os.environ.get("ZAP_TIMEOUT_ASCAN", "300"))
