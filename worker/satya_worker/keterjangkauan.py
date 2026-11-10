"""Keterjangkauan target dari worker: preflight sebelum task & pemutus sirkuit selama task.

Kasus nyata: firewall/WAF target memblokir IP worker (paket di-drop → SYN tak dibalas). Tanpa
penjaga, setiap alat (crawler, ZAP, katana, ffuf, nuclei, Playwright) menunggu timeout-nya
sendiri-sendiri sehingga recon tampak "hang" belasan menit tanpa penjelasan.

- `preflight(base_url)`: DNS → TCP connect → satu request HTTP. Gagal → task langsung diakhiri
  dengan alasan jelas. Hasil di-cache singkat per host:port agar task metode beruntun pada scan
  yang sama tak masing-masing menunggu timeout.
- `Pengawas` (thread per task): probe TCP berkala; setelah `TARGET_GAGAL_MAKS` kegagalan
  beruntun, `koordinasi.STATUS` ditandai sehingga `periksa_batal()` melempar
  `TargetTakTerjangkau` dan alat eksternal yang sedang berjalan dimatikan.

Konfigurasi (env): `TARGET_PREFLIGHT_TIMEOUT` (dtk, default 8), `TARGET_CEK_INTERVAL` (dtk,
default 15), `TARGET_GAGAL_MAKS` (default 4), `TARGET_CEK_AKTIF` (0 = nonaktif).
"""

from __future__ import annotations

import os
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

import httpx

from . import koordinasi


def _env_num(nama: str, bawaan: float) -> float:
    try:
        return float(os.environ.get(nama, "") or bawaan)
    except ValueError:
        return bawaan


def aktif() -> bool:
    return os.environ.get("TARGET_CEK_AKTIF", "1").strip().lower() not in ("0", "false", "tidak", "no")


def host_port(url: str) -> tuple[str, int]:
    s = urlsplit(url)
    host = (s.hostname or "").lower()
    port = s.port or (443 if s.scheme == "https" else 80)
    return host, port


@dataclass
class Hasil:
    ok: bool
    alasan: str = ""


def cek_tcp(host: str, port: int, timeout: float) -> Optional[str]:
    """None bila TCP tersambung; selain itu deskripsi singkat kegagalan."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except socket.gaierror:
        return f"nama host '{host}' tidak dapat di-resolve (DNS)"
    except (socket.timeout, TimeoutError):
        return f"koneksi TCP ke {host}:{port} timeout {timeout:g} dtk (paket tak dibalas — kemungkinan IP worker diblokir firewall/WAF)"
    except ConnectionRefusedError:
        return f"koneksi TCP ke {host}:{port} ditolak (port tertutup / layanan mati)"
    except OSError as e:
        return f"koneksi TCP ke {host}:{port} gagal: {e.strerror or type(e).__name__}"


_CACHE: dict[tuple[str, int], tuple[float, Hasil]] = {}
_CACHE_KUNCI = threading.Lock()
_CACHE_TTL_OK = 30.0
_CACHE_TTL_GAGAL = 60.0


def preflight(base_url: str, *, timeout: Optional[float] = None, percobaan: int = 2, pakai_cache: bool = True) -> Hasil:
    """Pastikan target terjangkau: DNS + TCP (≤`percobaan` kali) + satu respons HTTP apa pun."""
    if not aktif():
        return Hasil(True)
    host, port = host_port(base_url)
    if not host:
        return Hasil(False, f"URL target tidak valid: {base_url}")
    kunci = (host, port)
    if pakai_cache:
        with _CACHE_KUNCI:
            c = _CACHE.get(kunci)
        if c and time.monotonic() - c[0] < (_CACHE_TTL_OK if c[1].ok else _CACHE_TTL_GAGAL):
            return c[1]

    t = timeout if timeout is not None else _env_num("TARGET_PREFLIGHT_TIMEOUT", 8)
    galat: Optional[str] = None
    for _ in range(max(1, percobaan)):
        galat = cek_tcp(host, port, t)
        if galat is None or "DNS" in galat:
            break
    hasil: Hasil
    if galat is not None:
        hasil = Hasil(False, galat)
    else:
        # TCP tersambung; pastikan server benar-benar menjawab HTTP (WAF "tarpit" menerima TCP
        # tetapi tak pernah membalas). Status apa pun (termasuk 4xx/5xx) = terjangkau.
        try:
            with httpx.Client(timeout=t, verify=False, follow_redirects=False) as k:
                k.get(base_url, headers={"User-Agent": "SATYA-Worker/0.1 (+preflight)"})
            hasil = Hasil(True)
        except httpx.TimeoutException:
            hasil = Hasil(False, f"TCP ke {host}:{port} tersambung tetapi tak ada respons HTTP dalam {t:g} dtk (kemungkinan diblokir/ditahan WAF)")
        except (httpx.ConnectError, ssl.SSLError) as e:
            # Galat TLS/handshake berarti server menjawab — biarkan pengujian (COMM/CRYP) menilainya.
            pesan = str(e).lower()
            if "ssl" in pesan or "tls" in pesan or "certificate" in pesan or "handshake" in pesan:
                hasil = Hasil(True)
            else:
                hasil = Hasil(False, f"koneksi HTTP ke {host}:{port} gagal: {type(e).__name__}: {e}")
        except httpx.HTTPError as e:
            hasil = Hasil(False, f"request HTTP ke {base_url} gagal: {type(e).__name__}: {e}")
    with _CACHE_KUNCI:
        _CACHE[kunci] = (time.monotonic(), hasil)
    return hasil


def hapus_cache() -> None:
    with _CACHE_KUNCI:
        _CACHE.clear()


class Pengawas(threading.Thread):
    """Pemutus sirkuit: probe TCP berkala ke target selama task berjalan.

    Setelah `maks_gagal` kegagalan TCP beruntun (default 4 × 15 dtk ≈ 1 menit), task ditandai
    `tak_terjangkau` sehingga berhenti di titik periksa berikutnya. Satu keberhasilan mereset hitungan.
    Probe TCP saja (tanpa request HTTP) agar tak menambah beban/jejak berarti di target.
    """

    def __init__(self, base_url: str, *, interval: Optional[float] = None, maks_gagal: Optional[int] = None,
                 timeout: Optional[float] = None) -> None:
        super().__init__(name="satya-pengawas-target", daemon=True)
        self.host, self.port = host_port(base_url)
        self.interval = interval if interval is not None else _env_num("TARGET_CEK_INTERVAL", 15)
        self.maks_gagal = int(maks_gagal if maks_gagal is not None else _env_num("TARGET_GAGAL_MAKS", 4))
        self.timeout = timeout if timeout is not None else _env_num("TARGET_PREFLIGHT_TIMEOUT", 8)
        self.gagal_beruntun = 0
        self._henti = threading.Event()

    def hentikan(self) -> None:
        self._henti.set()

    def cek_sekali(self) -> bool:
        """Satu probe. True bila pemutus sirkuit terpicu pada probe ini."""
        galat = cek_tcp(self.host, self.port, self.timeout)
        if galat is None:
            self.gagal_beruntun = 0
            return False
        self.gagal_beruntun += 1
        if self.gagal_beruntun >= self.maks_gagal:
            koordinasi.STATUS.tandai_tak_terjangkau(
                f"Target tak terjangkau selama pengujian: {self.gagal_beruntun}× berturut-turut {galat}."
            )
            return True
        return False

    def run(self) -> None:
        if not self.host or not aktif():
            return
        while not self._henti.wait(self.interval):
            if self.cek_sekali():
                return
