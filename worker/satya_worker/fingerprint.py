"""Fingerprint teknologi target (non-intrusif, hanya GET) → komponen untuk pencocokan CVE di backend.

Sumber:
  - **banner**    header `Server`/`X-Powered-By`/`X-Generator`, meta `generator`, footer halaman galat
                  bawaan (Apache `<address>`, nginx `<center>`), nama cookie sesi khas kerangka kerja.
  - **bundle_js** banner/versi library di berkas JS same-origin & versi di URL CDN (`jquery-3.4.1.min.js`,
                  `bootstrap@5.1.3`).
  - **nuclei**    template `-tags tech` (tech-detect & *-version) beserta hasil ekstraksinya.

Worker hanya mengirim teks mentah (mis. "Apache/2.4.41 (Ubuntu)"); backend mengurainya dengan parser yang
sama dengan isian formulir aset, sehingga normalisasi nama/versi cukup di satu tempat.
"""

from __future__ import annotations

import json
import re
import secrets
import subprocess
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import httpx

from .http_client import USER_AGENT
from . import koordinasi
from . import nuclei_client as nc

MAKS_BERKAS_JS = 15
MAKS_BYTE_JS = 3 * 1024 * 1024
MAKS_ITEM = 100

Logger = Optional[Callable[..., None]]

# --- Banner HTML halaman galat bawaan server.
_ALAMAT_APACHE = re.compile(r"<address>\s*([^<]{3,120}?)\s+Server at", re.I)
_PUSAT_NGINX = re.compile(r"<center>\s*((?:nginx|openresty)(?:/[\w.\-]+)?)\s*</center>", re.I)

# --- Cookie sesi khas kerangka kerja (tanpa versi → keyakinan rendah).
_COOKIE = {
    "phpsessid": ("PHP", "backend"),
    "laravel_session": ("Laravel", "backend"),
    "ci_session": ("CodeIgniter", "backend"),
    "jsessionid": ("Java", "backend"),
    "asp.net_sessionid": (".NET Framework", "backend"),
    "connect.sid": ("Express", "backend"),
}

# --- Banner/versi library di isi berkas JS.
_POLA_JS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("", re.compile(r"/\*!?\s*(jQuery|Bootstrap|Vue\.js|AngularJS|Lodash|Moment\.js|Popper\.js)\s+v?(\d+\.\d+(?:\.\d+)?)", re.I)),
    ("jQuery", re.compile(r"""jquery\s*:\s*["'](\d+\.\d+\.\d+)["']""")),
    ("React", re.compile(r"""version\s*:\s*["'](\d+\.\d+\.\d+)[^"']*["']\s*,\s*rendererPackageName\s*:\s*["']react-dom["']""")),
    ("Vue.js", re.compile(r"""/\*\*?\s*\*?\s*vue v(\d+\.\d+\.\d+)""", re.I)),
    ("Svelte", re.compile(r"""__svelte\s*=\s*\{\s*v\s*:\s*new Set\s*\}\s*\)\s*\)\s*\.v\.add\(\s*["'](\d+)["']""")),
)

# --- Versi di URL skrip/stylesheet (CDN maupun lokal).
_POLA_URL = re.compile(
    r"(jquery|bootstrap|vue|react-dom|react|angular|lodash|moment|svelte)(?:[@/\-]|\.js/)v?(\d+\.\d+\.\d+)", re.I
)
_NAMA_LIB = {"react-dom": "React", "vue": "Vue.js", "jquery": "jQuery", "bootstrap": "Bootstrap", "react": "React",
             "angular": "AngularJS", "svelte": "Svelte", "lodash": "Lodash", "moment": "Moment.js"}


class _Halaman(HTMLParser):
    """Ambil src skrip, href stylesheet, dan meta generator."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skrip: list[str] = []
        self.gaya: list[str] = []
        self.generator: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("src"):
            self.skrip.append(a["src"])
        elif tag == "link" and "stylesheet" in a.get("rel", "").lower() and a.get("href"):
            self.gaya.append(a["href"])
        elif tag == "meta" and a.get("name", "").lower() == "generator" and a.get("content"):
            self.generator.append(a["content"])


def _item(sumber: str, kategori: str, teks: str, keyakinan: str, bukti: str = "") -> dict[str, Any]:
    teks = re.sub(r"\s+", " ", teks).strip()[:200]
    return {"sumber": sumber, "kategori": kategori, "teks": teks, "keyakinan": keyakinan, "bukti": (bukti or teks)[:255]}


def _berversi(teks: str) -> bool:
    return bool(re.search(r"\d+\.\d+", teks))


def dari_respons(headers: dict[str, str], html: str, cookies: Iterable[str]) -> list[dict[str, Any]]:
    """Komponen dari satu respons (header, isi HTML, nama cookie). Murni — mudah diuji."""
    h = {k.lower(): v for k, v in headers.items()}
    out: list[dict[str, Any]] = []
    if h.get("server"):
        out.append(_item("banner", "server", h["server"], "tinggi" if _berversi(h["server"]) else "sedang", f"Server: {h['server']}"))
    for kunci in ("x-powered-by", "x-generator"):
        if h.get(kunci):
            nilai = h[kunci]
            out.append(_item("banner", "backend", nilai, "tinggi" if _berversi(nilai) else "sedang", f"{kunci}: {nilai}"))
    if h.get("x-aspnet-version"):
        out.append(_item("banner", "backend", f".NET Framework {h['x-aspnet-version']}", "sedang", f"X-AspNet-Version: {h['x-aspnet-version']}"))

    hal = _Halaman()
    try:
        hal.feed(html or "")
    except Exception:  # HTML rusak — tetap pakai yang sudah terbaca
        pass
    for g in hal.generator[:3]:
        out.append(_item("banner", "backend", g, "tinggi" if _berversi(g) else "sedang", f'meta generator="{g}"'))
    for pola in (_ALAMAT_APACHE, _PUSAT_NGINX):
        for m in pola.finditer(html or ""):
            out.append(_item("banner", "server", m.group(1), "tinggi", m.group(0)))

    for nama in cookies:
        k = nama.lower()
        if k in _COOKIE:
            produk, kategori = _COOKIE[k]
            out.append(_item("banner", kategori, produk, "rendah", f"cookie {nama}"))

    for u in hal.skrip + hal.gaya:
        out.extend(dari_url_aset(u))
    return out


def dari_url_aset(url: str) -> list[dict[str, Any]]:
    """Versi library dari URL skrip/stylesheet ("…/jquery-3.4.1.min.js", "…/bootstrap@5.1.3/…")."""
    out = []
    for m in _POLA_URL.finditer(url):
        nama = _NAMA_LIB.get(m.group(1).lower(), m.group(1))
        out.append(_item("bundle_js", "library", f"{nama} {m.group(2)}", "tinggi", url))
    return out


def dari_js(isi: str, berkas: str = "") -> list[dict[str, Any]]:
    """Banner/versi library dari isi berkas JS."""
    out = []
    for nama, pola in _POLA_JS:
        for m in pola.finditer(isi):
            if nama:
                teks = f"{nama} {m.group(1)}"
            else:
                teks = f"{m.group(1)} {m.group(2)}"
            out.append(_item("bundle_js", "library", teks, "tinggi", f"{berkas}: {m.group(0)[:120]}" if berkas else m.group(0)[:120]))
    return out


def dari_nuclei(baris_jsonl: str) -> list[dict[str, Any]]:
    """Komponen dari keluaran `nuclei -tags tech -jsonl` (matcher-name + extracted-results)."""
    out = []
    for baris in baris_jsonl.splitlines():
        try:
            obj = json.loads(baris)
        except ValueError:
            continue
        tid = str(obj.get("template-id") or "")
        matcher = str(obj.get("matcher-name") or "")
        ekstrak = [str(x) for x in (obj.get("extracted-results") or []) if str(x).strip()]
        nama = matcher or re.sub(r"-(detect|version|panel|fingerprint|tech)$", "", tid)
        if not nama or nama in ("tech-detect", "waf-detect"):
            continue
        if ekstrak:
            e = ekstrak[0]
            teks = e if re.search(r"[a-z]", e, re.I) and _berversi(e) else f"{nama} {e}"
            keyakinan = "tinggi" if _berversi(teks) else "sedang"
        else:
            teks, keyakinan = nama.replace("-", " "), "sedang"
        out.append(_item("nuclei", "lainnya", teks, keyakinan, f"nuclei {tid}{':' + matcher if matcher else ''}"))
    return out


def _jalankan_nuclei(base_url: str, timeout: float) -> str:
    if not nc.tersedia():
        return ""
    perintah = [nc._bin(), "-u", base_url, "-jsonl", "-silent", "-no-color", "-disable-update-check",
                "-no-interactsh", "-tags", "tech", "-severity", "info", "-rate-limit", nc._rate(),
                "-concurrency", nc._concurrency(), "-timeout", "8", "-retries", "1"]
    try:
        proc = koordinasi.jalankan_proses(perintah, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return proc.stdout or ""


def _unik(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terlihat: set[tuple[str, str]] = set()
    out = []
    for it in items:
        k = (it["sumber"], it["teks"].lower())
        if k not in terlihat:
            terlihat.add(k)
            out.append(it)
    return out[:MAKS_ITEM]


def kumpulkan(base_url: str, *, timeout: float = 10.0, nuclei: bool = True, nuclei_timeout: float = 60.0,
              log: Logger = None) -> list[dict[str, Any]]:
    """Fingerprint `base_url` → daftar item {sumber, kategori, teks, keyakinan, bukti}. Best-effort."""
    host = (urlsplit(base_url).hostname or "").lower()
    items: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as klien:
        skrip: list[str] = []
        # Halaman utama + halaman tak ada (halaman galat bawaan sering memuat banner server berversi).
        for path in ("", f"/satria-{secrets.token_hex(4)}"):
            try:
                r = klien.get(urljoin(base_url.rstrip("/") + "/", path.lstrip("/")))
            except httpx.HTTPError:
                continue
            if (urlsplit(str(r.url)).hostname or "").lower() != host:
                continue
            html = r.text if "html" in r.headers.get("content-type", "") else ""
            items.extend(dari_respons(dict(r.headers), html, r.cookies.keys()))
            if not path:
                hal = _Halaman()
                try:
                    hal.feed(html)
                except Exception:
                    pass
                skrip = [urljoin(str(r.url), s) for s in hal.skrip]

        for u in [s for s in dict.fromkeys(skrip) if (urlsplit(s).hostname or "").lower() == host][:MAKS_BERKAS_JS]:
            koordinasi.periksa_batal()
            try:
                with klien.stream("GET", u) as r:
                    if r.status_code != 200:
                        continue
                    isi = b""
                    for potong in r.iter_bytes():
                        isi += potong
                        if len(isi) > MAKS_BYTE_JS:
                            break
            except httpx.HTTPError:
                continue
            items.extend(dari_js(isi.decode("utf-8", "replace"), urlsplit(u).path.rsplit("/", 1)[-1]))

    if nuclei:
        items.extend(dari_nuclei(_jalankan_nuclei(base_url, nuclei_timeout)))
    hasil = _unik(items)
    if log:
        contoh = ", ".join(i["teks"] for i in hasil[:6]) or "tidak ada"
        log("info", f"Fingerprint teknologi: {len(hasil)} komponen terdeteksi ({contoh}).")
    return hasil
