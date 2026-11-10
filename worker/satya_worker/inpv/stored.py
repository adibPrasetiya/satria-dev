"""Prober XSS tersimpan / kegagalan filter output (INPV-4.5 & INPV-4.7).

Sapuan INPV biasa hanya menilai REFLEKSI (penanda terpantul pada respons yang sama). XSS TERSIMPAN
berbeda: payload ditulis ke aplikasi (mis. form pengajuan), lalu MUNCUL lagi tanpa sanitasi saat
dibaca kembali di endpoint lain. Modul ini menulis penanda inert `<satya…>` ke endpoint create,
lalu membacanya kembali di endpoint GET sekerabat dan memeriksa apakah tersimpan MENTAH (tak
di-encode) — bukti data tak dipercaya tak difilter.

KEAMANAN: ini aksi MUTASI (menulis data), jadi HANYA dijalankan saat pemanggil mengizinkan
(`profil=='intrusif'` DAN `ctx.intrusif.izinkan_penguncian`). Penanda bersifat inert (tag palsu,
bukan skrip aktif), endpoint kritis (sandi/reset/sesi) tak pernah disentuh, dan hanya endpoint
create tanpa `{id}` yang ditulis. Hasil di-cache per scan agar tak menulis berulang.
"""

from __future__ import annotations

import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlsplit

from .. import atribusi_sandi as asd
from ..http_client import KlienScan, LuarRuangLingkup
from ..models import Bukti, ScanContext
from ..sesi import hosts_target, login
from . import cakupan as ck
from . import profil_field as pf

_cache: dict[str, "HasilStored"] = {}
_kunci = threading.Lock()


@dataclass
class TemuanStored:
    tulis: str              # "POST /api/pengajuan"
    baca: str               # "GET /api/pengajuan" tempat penanda muncul
    field_tulis: str
    mentah: bool            # True = muncul tanpa encoding (rentan); False = ter-encode (aman)
    content_type: str = ""

    @property
    def ringkas(self) -> str:
        return f"{self.tulis} → {self.baca} [field {self.field_tulis}]: " + ("MENTAH (tak difilter)" if self.mentah else "ter-encode")


@dataclass
class HasilStored:
    temuan: list[TemuanStored] = field(default_factory=list)
    ditulis: int = 0
    dibaca: int = 0
    login_ok: bool = False
    dijalankan: bool = False       # False bila dilewati (tanpa izin / tak ada endpoint)
    alasan: str = ""
    bukti: list[Bukti] = field(default_factory=list)

    @property
    def rentan(self) -> list[TemuanStored]:
        return [t for t in self.temuan if t.mentah]

    def teks(self) -> str:
        if not self.dijalankan:
            return f"Uji XSS tersimpan tidak dijalankan: {self.alasan}."
        n = len(self.rentan)
        return (f"Uji XSS tersimpan: {self.ditulis} penanda ditulis, dibaca ulang di {self.dibaca} endpoint — "
                + (f"{n} tersimpan MENTAH (tak difilter)." if n else "semua ter-encode / tak muncul."))


def _maks() -> int:
    try:
        return max(1, int(os.environ.get("INPV_STORED_MAKS", "8")))
    except ValueError:
        return 8


def _segmen_sumber(path: str) -> str:
    for s in (path or "").split("/"):
        if s and s != "api" and not s.startswith("{") and not re.fullmatch(r"v\d+", s):
            return s.lower()
    return ""


def _field_teks(ep: dict[str, Any]) -> list[str]:
    """Nama field body bertipe teks yang layak ditulisi penanda (bukan sandi/token/angka/enum)."""
    out = []
    for f in ep.get("request_fields") or []:
        nama = str(f.get("nama") or "")
        if f.get("lokasi") != "body" or not nama or re.search(r"pass|sandi|token|secret|otp", nama, re.I):
            continue
        p, _ = pf.profil(f)
        if p.get("tipe") in ("string", "", None) and not p.get("enum") and not p.get("format"):
            out.append(nama)
    return out


def probe(ctx: ScanContext) -> HasilStored:
    """Uji XSS tersimpan untuk scan ini (sekali; cache per scan). Pemanggil WAJIB sudah memeriksa izin."""
    kunci = ctx.scan_id or ctx.base_url
    with _kunci:
        if kunci not in _cache:
            _cache[kunci] = _jalankan(ctx)
        return _cache[kunci]


def reset_cache() -> None:
    with _kunci:
        _cache.clear()


def _jalankan(ctx: ScanContext) -> HasilStored:
    hasil = HasilStored()
    base_host = pf.host(ctx.base_url)
    izin = hosts_target(ctx)

    def dalam_lingkup(url: str) -> bool:
        return ck.host_dalam_lingkup(urlsplit(url).hostname or "", base_host, izin)

    eps = list(ctx.endpoints or [])
    # Endpoint tulis: POST non-kritis tanpa {id}, punya field teks, dalam lingkup.
    tulis = [e for e in eps
             if str(e.get("metode_http") or "").upper() == "POST"
             and "{id}" not in str(e.get("path_template") or "")
             and not ck.KRITIS.search(str(e.get("path_template") or ""))
             and (e.get("lapisan") or "api") == "api"
             and dalam_lingkup(str(e.get("url") or ""))
             and _field_teks(e)][:_maks()]
    if not tulis:
        hasil.alasan = "tidak ada endpoint create dengan field teks dalam lingkup"
        return hasil
    # Endpoint baca: GET dalam lingkup (list/detail), dikelompokkan per segmen sumber.
    baca_per_segmen: dict[str, list[dict[str, Any]]] = {}
    for e in eps:
        if str(e.get("metode_http") or "GET").upper() == "GET" and (e.get("lapisan") or "api") == "api" \
                and dalam_lingkup(str(e.get("url") or "")):
            baca_per_segmen.setdefault(_segmen_sumber(str(e.get("path_template") or "")), []).append(e)

    hasil.dijalankan = True
    host_klien = izin | {pf.host(str(e.get("url") or "")) for e in tulis}
    klien = KlienScan(ctx.base_url, timeout=10.0, host_izin=host_klien, saat_request=ctx.rekam_request)
    dibaca_url: set[str] = set()
    try:
        with klien:
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if akun and akun.password and ctx.url_titik("login"):
                try:
                    hasil.login_ok = login(klien, ctx, akun)
                except Exception:
                    hasil.login_ok = False
            ctx.catat("info", f"  Uji XSS tersimpan: {len(tulis)} endpoint create, sesi {'aktif' if hasil.login_ok else 'anonim'}.")
            for ep in tulis:
                _uji_satu(ctx, klien, ep, baca_per_segmen, hasil, dibaca_url)
            hasil.bukti = list(klien.bukti)[:20]
    except Exception as e:
        hasil.alasan = f"{type(e).__name__}: {e}"
    return hasil


def _uji_satu(ctx: ScanContext, klien: KlienScan, ep: dict[str, Any],
              baca_per_segmen: dict[str, list[dict[str, Any]]], hasil: HasilStored, dibaca_url: set[str]) -> None:
    fields = _field_teks(ep)
    if not fields:
        return
    tok = secrets.token_hex(3)
    penanda = f"<satya{tok}>"                         # tag inert unik — dicari mentah vs ter-encode
    ter_encode = f"&lt;satya{tok}&gt;"
    field_tulis = max(fields, key=len)                # field teks terpanjang → paling mungkin bebas-teks
    payload = asd.payload_endpoint(ep, "body")
    payload[field_tulis] = f"Satya uji {penanda}"
    label_tulis = f"{ep.get('metode_http')} {ep.get('path_template')}"
    form = "x-www-form-urlencoded" in str(ep.get("content_type") or "")
    try:
        resp = klien.kirim("POST", str(ep.get("url")), json=None if form else payload,
                           data=payload if form else None, judul_bukti=f"XSS tersimpan — tulis {label_tulis}")
    except (LuarRuangLingkup, Exception):
        return
    if resp.status_code not in (200, 201, 202, 204):
        ctx.catat("info", f"    • {label_tulis}: penanda tak tersimpan (HTTP {resp.status_code}).")
        return
    hasil.ditulis += 1
    # Baca ulang di endpoint GET sekerabat (segmen sumber sama) + endpoint list umum.
    seg = _segmen_sumber(str(ep.get("path_template") or ""))
    kandidat = list(baca_per_segmen.get(seg, []))
    for e in kandidat[:6]:
        url = str(e.get("url") or "")
        if not url or url in dibaca_url:
            continue
        dibaca_url.add(url)
        try:
            r = klien.kirim("GET", url, judul_bukti=f"XSS tersimpan — baca {e.get('metode_http')} {e.get('path_template')}")
        except Exception:
            continue
        hasil.dibaca += 1
        teks = r.text[:500_000]
        if penanda in teks:
            hasil.temuan.append(TemuanStored(label_tulis, f"GET {e.get('path_template')}", field_tulis, True,
                                             r.headers.get("content-type", "")))
            ctx.catat("peringatan", f"    • XSS TERSIMPAN: penanda dari {label_tulis} muncul MENTAH di GET {e.get('path_template')}.")
            return
        if ter_encode in teks:
            hasil.temuan.append(TemuanStored(label_tulis, f"GET {e.get('path_template')}", field_tulis, False,
                                             r.headers.get("content-type", "")))
            return
