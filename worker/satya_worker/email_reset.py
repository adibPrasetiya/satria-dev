"""Klien Resend Inbound — menerima email reset kata sandi untuk otomasi AUTH-1.3-T03 / AUTH-1.5-T02.

Alur otomasi reset menuntut worker mendaftarkan pengguna baru dengan alamat email yang
BISA DIBACA, lalu mengambil email reset yang dikirim aplikasi target. Resend menyediakan
inbound email: email ke `*@<RESEND_INBOUND_DOMAIN>` masuk ke akun Resend dan dapat diambil
lewat REST API (webhook-first, tetapi daftar/isi bisa di-*poll*):

    GET https://api.resend.com/emails/receiving            → daftar email diterima
    GET https://api.resend.com/emails/receiving/{id}       → isi (html/text)

Konfigurasi via env (RESEND_API_KEY sebaiknya lewat vault/secret, bukan berkas commit):
    RESEND_API_KEY         kunci API Resend (wajib)
    RESEND_INBOUND_DOMAIN  domain inbound terverifikasi di Resend (wajib), mis. reset.satria.pro
    RESEND_BASE_URL        default https://api.resend.com
    RESEND_POLL_TIMEOUT    detik menunggu email reset (default 60)
    RESEND_POLL_INTERVAL   jeda poll (default 3)

Bila RESEND_API_KEY / RESEND_INBOUND_DOMAIN kosong → `dari_env()` mengembalikan None, dan
check reset melapor menunggu_tinjauan (tidak menghakimi tanpa bukti).
"""

from __future__ import annotations

import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx


class ResendTidakTersedia(Exception):
    """Resend belum dikonfigurasi atau tidak dapat dihubungi."""


# URL http(s) di dalam teks email.
_URL = re.compile(r"https?://[^\s\"'<>)\]}]+", re.IGNORECASE)
# Petunjuk bahwa URL/parameter adalah tautan reset.
_PETUNJUK_RESET = ("reset", "lupa", "forgot", "token", "recover", "set-password", "ubah-sandi")


def _sekarang() -> datetime:
    return datetime.now(timezone.utc)


def _parse_waktu(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class KlienResend:
    def __init__(self, api_key: str, domain: str, *, base_url: str = "https://api.resend.com", timeout: float = 15.0) -> None:
        self.domain = domain.strip().lstrip("@")
        self.base = base_url.rstrip("/")
        self._klien = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            verify=True,
        )

    def __enter__(self) -> "KlienResend":
        return self

    def __exit__(self, *exc: object) -> None:
        self._klien.close()

    # ---- alamat ----
    def alamat_baru(self, prefiks: str = "satya") -> str:
        """Alamat unik di domain inbound Resend untuk satu pendaftaran uji."""
        return f"{prefiks}-{secrets.token_hex(6)}@{self.domain}"

    # ---- API inbound ----
    def _daftar(self, limit: int = 100) -> list[dict[str, Any]]:
        r = self._klien.get(f"{self.base}/emails/receiving", params={"limit": limit})
        r.raise_for_status()
        return list(r.json().get("data", []))

    def _isi(self, email_id: str) -> str:
        r = self._klien.get(f"{self.base}/emails/receiving/{email_id}")
        r.raise_for_status()
        d = r.json()
        # Gabungkan field teks yang mungkin ada (html/text) agar ekstraksi tautan andal.
        bagian = [str(d.get(k, "")) for k in ("html", "text", "body") if d.get(k)]
        return "\n".join(bagian)

    def tunggu_email(self, alamat: str, sejak: datetime, *, batas_dtk: Optional[float] = None, jeda: Optional[float] = None) -> Optional[str]:
        """Poll inbound sampai ada email ke `alamat` yang tiba setelah `sejak`. Return isi teks atau None."""
        batas = batas_dtk if batas_dtk is not None else float(os.environ.get("RESEND_POLL_TIMEOUT", "60"))
        tidur = jeda if jeda is not None else float(os.environ.get("RESEND_POLL_INTERVAL", "3"))
        alamat_l = alamat.lower()
        t0 = time.monotonic()
        while time.monotonic() - t0 <= batas:
            try:
                for e in self._daftar():
                    tujuan = [str(x).lower() for x in (e.get("to") or [])]
                    if alamat_l not in tujuan:
                        continue
                    waktu = _parse_waktu(str(e.get("created_at", "")))
                    if waktu is not None and waktu < sejak:
                        continue
                    return self._isi(str(e.get("id", "")))
            except httpx.HTTPError:
                pass  # best-effort: coba lagi sampai batas waktu
            time.sleep(tidur)
        return None


def dari_env() -> Optional[KlienResend]:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    domain = os.environ.get("RESEND_INBOUND_DOMAIN", "").strip()
    if not key or not domain:
        return None
    base = os.environ.get("RESEND_BASE_URL", "https://api.resend.com").strip() or "https://api.resend.com"
    return KlienResend(key, domain, base_url=base)


# --------------------------------------------------------------------------- ekstraksi tautan/token

def _relevan(url: str) -> bool:
    low = url.lower()
    return any(k in low for k in _PETUNJUK_RESET)


def ekstrak_link_reset(teks: str, *, host_izin: Optional[set[str]] = None) -> Optional[str]:
    """Tautan reset dari isi email. Prioritas: host diizinkan + petunjuk reset."""
    urls = _URL.findall(teks or "")
    if not urls:
        return None

    def _ok_host(u: str) -> bool:
        if not host_izin:
            return True
        return (urlsplit(u).hostname or "").lower() in host_izin

    for u in urls:
        if _ok_host(u) and _relevan(u):
            return u
    for u in urls:  # longgar: host cocok walau tanpa kata kunci
        if _ok_host(u):
            return u
    return urls[0]


def ekstrak_token(teks: str) -> Optional[str]:
    """Token reset longgar: dari query `token=`/`code=` atau segmen hex/base64url panjang."""
    m = re.search(r"[?&](?:token|code|t)=([^\s&\"'<>)\]}]+)", teks or "", re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Za-z0-9_-]{24,})\b", teks or "")
    return m.group(1) if m else None
