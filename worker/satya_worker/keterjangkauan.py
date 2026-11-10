"""Keterjangkauan target dari worker: preflight sebelum task & pemutus sirkuit selama task.

Kasus nyata: firewall/WAF target memblokir IP worker (paket di-drop → SYN tak dibalas). Tanpa
penjaga, setiap alat (crawler, ZAP, katana, ffuf, nuclei, Playwright) menunggu timeout-nya
sendiri-sendiri sehingga recon tampak "hang" belasan menit tanpa penjelasan.

- `preflight(base_url)`: DNS → TCP connect → satu request HTTP. Gagal → task langsung diakhiri
  dengan alasan jelas. Hasil di-cache singkat per host:port agar task metode beruntun pada scan
  yang sama tak masing-masing menunggu timeout.
- `Pengawas` (thread per task): probe TCP berkala; setelah `TARGET_GAGAL_MAKS` kegagalan
  beruntun, `koordinasi.STATUS` ditandai sehingga `periksa_batal()` melempar
  `TargetTakTerjangkau` dan alat eksternal yang sedang berjalan dimatikan. Pengawas juga
  mendeteksi blokir tingkat HTTP (WAF/rate-limit: 403/429/503 + halaman blokir yang tadinya
  tidak ada) dan melaporkannya sebagai peringatan — task tetap jalan, hasil ditandai mungkin tak lengkap.
- `peristiwa_terblokir()` membentuk peristiwa `terblokir` (v=1) untuk keterangan di UI.

Konfigurasi (env): `TARGET_PREFLIGHT_TIMEOUT` (dtk, default 8), `TARGET_CEK_INTERVAL` (dtk,
default 15), `TARGET_GAGAL_MAKS` (default 4), `TARGET_CEK_AKTIF` (0 = nonaktif),
`WORKER_IP_PUBLIK` (opsional — disebut di saran whitelist).
"""

from __future__ import annotations

import os
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx

from . import koordinasi

_UA = "SATYA-Worker/0.1 (+preflight)"


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
    status: Optional[int] = None   # status HTTP request preflight (bila ada)
    waf: Optional[str] = None      # tanda blokir WAF/rate-limit pada respons preflight (bila ada)
    lapisan: str = ""              # dns | tcp | http — lapisan kegagalan (bila gagal)


# --------------------------------------------------------------------------- deteksi blokir HTTP

# Status HTTP yang lazim dipakai WAF/rate-limiter untuk menolak klien.
_STATUS_BLOKIR = (403, 406, 429, 503)
# Tanda halaman/header blokir WAF umum (huruf kecil). Dicocokkan hanya bila status ∈ _STATUS_BLOKIR.
_TANDA_WAF: tuple[tuple[str, str], ...] = (
    ("cf-mitigated", "Cloudflare"),
    ("attention required! | cloudflare", "Cloudflare"),
    ("cloudflare ray id", "Cloudflare"),
    ("sucuri website firewall", "Sucuri"),
    ("the requested url was rejected", "F5 BIG-IP ASM"),
    ("request rejected", "WAF"),
    ("modsecurity", "ModSecurity"),
    ("mod_security", "ModSecurity"),
    ("not acceptable!", "ModSecurity"),
    ("incapsula", "Imperva Incapsula"),
    ("fortiweb", "FortiWeb"),
    ("akamai", "Akamai"),
    ("web application firewall", "WAF"),
    ("access denied", "WAF"),
    ("too many requests", "rate-limit"),
)


def tanda_blokir_http(status: int, headers: dict[str, str], cuplik: str) -> Optional[str]:
    """Deskripsi singkat bila respons tampak penolakan WAF/rate-limit; None bila tidak."""
    if status not in _STATUS_BLOKIR:
        return None
    teks = (" ".join(f"{k}: {v}" for k, v in headers.items()) + " " + cuplik[:4000]).lower()
    for tanda, nama in _TANDA_WAF:
        if tanda in teks:
            return f"HTTP {status} — halaman blokir {nama}"
    if status == 429:
        return "HTTP 429 Too Many Requests (rate-limit)"
    return None


def _probe_http(url: str, timeout: float) -> tuple[Optional[int], Optional[str]]:
    """(status, tanda_waf). (None, None) bila request gagal di tingkat jaringan."""
    try:
        with httpx.Client(timeout=timeout, verify=False, follow_redirects=False) as k:
            r = k.get(url, headers={"User-Agent": _UA})
        return r.status_code, tanda_blokir_http(r.status_code, dict(r.headers), r.text[:4000])
    except Exception:
        return None, None


# --------------------------------------------------------------------------- keterangan untuk UI


def saran_whitelist() -> str:
    ip = os.environ.get("WORKER_IP_PUBLIK", "").strip()
    awal = f"Minta pengelola target me-whitelist IP worker {ip}" if ip else \
        "Minta pengelola target me-whitelist IP publik server worker"
    return awal + " pada firewall/WAF/rate-limit, lalu jalankan ulang pengujian."


def peristiwa_terblokir(*, fase: str, lapisan: str, alasan: str, fatal: bool, awal: bool = False,
                        host: str = "", status: Optional[int] = None) -> dict[str, Any]:
    """Peristiwa `terblokir` (v=1) — keterangan blokir untuk visualisasi penemuan/pengujian.

    fase: recon | pengujian · lapisan: dns | tcp | http · awal: terdeteksi saat preflight (sebelum
    task berjalan) · fatal: task dihentikan (bukan sekadar peringatan).
    """
    saran = ("Periksa nama host target (DNS) dan konektivitas jaringan worker." if lapisan == "dns"
             else saran_whitelist())
    d: dict[str, Any] = {"v": 1, "jenis": "terblokir", "fase": fase, "lapisan": lapisan,
                         "alasan": alasan, "fatal": fatal, "awal": awal, "saran": saran}
    if host:
        d["host"] = host
    if status is not None:
        d["status"] = status
    ip = os.environ.get("WORKER_IP_PUBLIK", "").strip()
    if ip:
        d["ip_worker"] = ip
    return d


# --------------------------------------------------------------------------- preflight


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
        return Hasil(False, f"URL target tidak valid: {base_url}", lapisan="dns")
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
        hasil = Hasil(False, galat, lapisan="dns" if "DNS" in galat else "tcp")
    else:
        # TCP tersambung; pastikan server benar-benar menjawab HTTP (WAF "tarpit" menerima TCP
        # tetapi tak pernah membalas). Status apa pun (termasuk 4xx/5xx) = terjangkau.
        try:
            with httpx.Client(timeout=t, verify=False, follow_redirects=False) as k:
                r = k.get(base_url, headers={"User-Agent": _UA})
            hasil = Hasil(True, status=r.status_code,
                          waf=tanda_blokir_http(r.status_code, dict(r.headers), r.text[:4000]))
        except httpx.TimeoutException:
            hasil = Hasil(False, f"TCP ke {host}:{port} tersambung tetapi tak ada respons HTTP dalam {t:g} dtk "
                                 "(kemungkinan diblokir/ditahan WAF)", lapisan="http")
        except (httpx.ConnectError, ssl.SSLError) as e:
            # Galat TLS/handshake berarti server menjawab — biarkan pengujian (COMM/CRYP) menilainya.
            pesan = str(e).lower()
            if "ssl" in pesan or "tls" in pesan or "certificate" in pesan or "handshake" in pesan:
                hasil = Hasil(True)
            else:
                hasil = Hasil(False, f"koneksi HTTP ke {host}:{port} gagal: {type(e).__name__}: {e}", lapisan="tcp")
        except httpx.HTTPError as e:
            hasil = Hasil(False, f"request HTTP ke {base_url} gagal: {type(e).__name__}: {e}", lapisan="http")
    with _CACHE_KUNCI:
        _CACHE[kunci] = (time.monotonic(), hasil)
    return hasil


def hapus_cache() -> None:
    with _CACHE_KUNCI:
        _CACHE.clear()


# --------------------------------------------------------------------------- pengawas (pemutus sirkuit)


class Pengawas(threading.Thread):
    """Pemutus sirkuit: probe TCP berkala ke target selama task berjalan.

    Setelah `maks_gagal` kegagalan TCP beruntun (default 4 × 15 dtk ≈ 1 menit), task ditandai
    `tak_terjangkau` sehingga berhenti di titik periksa berikutnya. Satu keberhasilan mereset hitungan.

    Bila TCP tersambung dan `lapor` diberikan, satu GET ringan ke `base_url` mendeteksi blokir
    tingkat HTTP (WAF / rate-limit) yang muncul SETELAH awal task (dibanding `status_dasar` dari
    preflight): dua probe beruntun tampak diblokir → `lapor("peringatan", pesan, peristiwa)` sekali.
    `lapor` dipanggil dari thread pengawas — pemanggil wajib memberi callback yang thread-safe.
    """

    def __init__(self, base_url: str, *, interval: Optional[float] = None, maks_gagal: Optional[int] = None,
                 timeout: Optional[float] = None, fase: str = "recon", status_dasar: Optional[int] = None,
                 lapor: Optional[Callable[[str, str, dict[str, Any]], None]] = None) -> None:
        super().__init__(name="satya-pengawas-target", daemon=True)
        self.base_url = base_url
        self.host, self.port = host_port(base_url)
        self.interval = interval if interval is not None else _env_num("TARGET_CEK_INTERVAL", 15)
        self.maks_gagal = int(maks_gagal if maks_gagal is not None else _env_num("TARGET_GAGAL_MAKS", 4))
        self.timeout = timeout if timeout is not None else _env_num("TARGET_PREFLIGHT_TIMEOUT", 8)
        self.fase = fase
        self.status_dasar = status_dasar
        self.lapor = lapor
        self.gagal_beruntun = 0
        self.blokir_http_beruntun = 0
        self.blokir_http_dilaporkan = False
        self._henti = threading.Event()

    def hentikan(self) -> None:
        self._henti.set()

    def cek_sekali(self) -> bool:
        """Satu probe. True bila pemutus sirkuit terpicu pada probe ini."""
        galat = cek_tcp(self.host, self.port, self.timeout)
        if galat is None:
            self.gagal_beruntun = 0
            if self.lapor is not None and not self.blokir_http_dilaporkan:
                self._cek_http()
            return False
        self.gagal_beruntun += 1
        if self.gagal_beruntun >= self.maks_gagal:
            koordinasi.STATUS.tandai_tak_terjangkau(
                f"{self.gagal_beruntun}× probe berturut-turut gagal — {galat}."
            )
            return True
        return False

    def _cek_http(self) -> None:
        status, waf = _probe_http(self.base_url, self.timeout)
        # Blokir = tanda WAF/rate-limit yang TIDAK sudah ada sejak awal task (status dasar berbeda).
        if status is None or not waf or status == self.status_dasar:
            self.blokir_http_beruntun = 0
            return
        self.blokir_http_beruntun += 1
        if self.blokir_http_beruntun < 2:
            return
        self.blokir_http_dilaporkan = True
        awal = f" (awalnya HTTP {self.status_dasar})" if self.status_dasar else ""
        alasan = (f"Target mulai menolak worker di tengah {self.fase}: {waf}{awal}. "
                  "Kemungkinan worker dibatasi/diblokir WAF — hasil bisa tidak lengkap.")
        try:
            self.lapor("peringatan", alasan, peristiwa_terblokir(  # type: ignore[misc]
                fase=self.fase, lapisan="http", alasan=alasan, fatal=False, host=self.host, status=status))
        except Exception:
            pass

    def run(self) -> None:
        if not self.host or not aktif():
            return
        while not self._henti.wait(self.interval):
            if self.cek_sekali():
                return
