"""Fase penemuan (mode eksploratif): crawl aplikasi dari satu URL, lalu
klasifikasikan titik uji & form yang ditemukan menjadi data persiapan
(`scan_targets`) secara otomatis.

Non-intrusif: hanya GET dalam cakupan host target, batas jumlah halaman, dan
tidak mengirim form apa pun (intersep aksi di browser membatalkan setiap request
non-GET sebelum keluar dari browser). Hasil klasifikasi diberi `sumber: "otomatis"` dan
tingkat `keyakinan`; backend menggabungkannya dengan data manual (manual menang).

Parser HTML memakai pustaka standar (`html.parser`) — tanpa dependensi baru.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx

from .http_client import USER_AGENT, _host
from .models import AkunUji, ScanContext
from . import peristiwa as pr

# Batas crawl agar aman & cepat (tanpa uji beban).
MAKS_HALAMAN = 40
MAKS_KEDALAMAN = 2

# Jalur dokumentasi API yang lazim (dicoba walau tak tertaut di HTML).
JALUR_API_DOC = (
    "/openapi.json",
    "/swagger.json",
    "/api-docs",
    "/v3/api-docs",
    "/swagger/v1/swagger.json",
    "/api/docs",
)

# Kata kunci (pada URL/teks tombol/field) untuk mengklasifikasi titik uji.
_KATA = {
    "login": ("login", "masuk", "signin", "sign-in", "log-in"),
    "registrasi": ("register", "registrasi", "daftar", "signup", "sign-up", "pendaftaran"),
    "reset_password": ("forgot", "lupa", "reset-password", "reset_password", "reset-sandi", "atur-ulang"),
    "ubah_password": ("change-password", "ubah-password", "ganti-password", "ubah-sandi", "ganti-sandi"),
    "logout": ("logout", "keluar", "signout", "sign-out"),
    "admin": ("/admin", "administrator", "backoffice"),
    "area_terautentikasi": ("dashboard", "beranda", "profil", "profile", "/me", "akun", "account"),
}

# Nama field yang menandai kata sandi / identitas.
_FIELD_SANDI = ("password", "passwd", "sandi", "kata_sandi", "pass")
_FIELD_IDENTITAS = ("email", "username", "user", "nrp", "nip", "identitas", "login")


# --------------------------------------------------------------------------- parser


@dataclass
class FormDitemukan:
    action: str = ""
    method: str = "POST"
    inputs: list[dict[str, str]] = field(default_factory=list)  # {name, type}

    @property
    def nama_input(self) -> list[str]:
        return [i.get("name", "") for i in self.inputs if i.get("name")]

    @property
    def tipe_input(self) -> list[str]:
        return [(i.get("type") or "text").lower() for i in self.inputs]


@dataclass
class HalamanDitemukan:
    url: str
    status: int = 0
    judul: str = ""
    tautan: list[str] = field(default_factory=list)
    form: list[FormDitemukan] = field(default_factory=list)
    skrip: list[str] = field(default_factory=list)  # <script src> (untuk analisis bundle JS)


class _ParserHtml(HTMLParser):
    """Kumpulkan <a href>, <form>, <input>, dan <title> dari satu halaman."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tautan: list[str] = []
        self.skrip: list[str] = []
        self.form: list[FormDitemukan] = []
        self.judul = ""
        self._di_judul = False
        self._form_aktif: Optional[FormDitemukan] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "a" and a.get("href"):
            self.tautan.append(a["href"])
        elif tag == "script" and a.get("src"):
            self.skrip.append(a["src"])
        elif tag == "title":
            self._di_judul = True
        elif tag == "form":
            self._form_aktif = FormDitemukan(
                action=a.get("action", ""),
                method=(a.get("method") or "GET").upper(),
            )
            self.form.append(self._form_aktif)
        elif tag in ("input", "select", "textarea") and self._form_aktif is not None:
            if a.get("name"):
                self._form_aktif.inputs.append({"name": a["name"], "type": a.get("type", "text")})
        elif tag in ("input", "select", "textarea") and a.get("type") == "file":
            # input file di luar form tetap menandai fitur unggah.
            self.tautan.append("#file")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._di_judul = False
        elif tag == "form":
            self._form_aktif = None

    def handle_data(self, data: str) -> None:
        if self._di_judul:
            self.judul += data.strip()


# --------------------------------------------------------------------------- klasifikasi


def _cocok(teks: str, kunci: tuple[str, ...]) -> bool:
    t = teks.lower()
    return any(k in t for k in kunci)


def klasifikasi_form(form: FormDitemukan, url_halaman: str) -> Optional[tuple[str, dict[str, Any]]]:
    """Petakan sebuah form ke (titik_uji, template_form) bila dikenali."""
    nama = [n.lower() for n in form.nama_input]
    punya_sandi = any(_cocok(n, _FIELD_SANDI) for n in nama) or "password" in form.tipe_input
    punya_file = "file" in form.tipe_input
    konteks = f"{url_halaman} {form.action} {' '.join(nama)}"

    field_sandi = next((n for n in form.nama_input if _cocok(n.lower(), _FIELD_SANDI)), "password")
    field_identitas = next((n for n in form.nama_input if _cocok(n.lower(), _FIELD_IDENTITAS)), "email")

    if punya_file:
        return "unggah_file", {"tipe_body": "form"}

    if punya_sandi:
        # Registrasi: banyak field (identitas + sandi + lainnya) atau konteks daftar.
        if _cocok(konteks, _KATA["registrasi"]) or len(form.nama_input) >= 3:
            dasar = {n: "" for n in form.nama_input if not _cocok(n.lower(), _FIELD_SANDI)}
            return "registrasi", {
                "field_dasar": dasar,
                "field_sandi": field_sandi,
                "field_unik": [n for n in form.nama_input if _cocok(n.lower(), ("email", "nrp", "nip"))],
                "tipe_body": "json",
            }
        # Ubah kata sandi: dua field sandi.
        jumlah_sandi = sum(1 for n in nama if _cocok(n, _FIELD_SANDI))
        if jumlah_sandi >= 2 or _cocok(konteks, _KATA["ubah_password"]):
            return "ubah_password", {"field_sandi": field_sandi}
        # Selain itu: login.
        return "login", {
            "field_username": field_identitas,
            "field_password": field_sandi,
            "tipe_body": "json",
        }

    # Form tanpa sandi: reset bila kontekstual, selain itu form input umum.
    if _cocok(konteks, _KATA["reset_password"]):
        return "reset_password", {"field_identitas": field_identitas}
    if form.nama_input:
        return "form_input", {"tipe_body": "form"}
    return None


_FIELD_UNIK = ("email", "surel", "nrp", "nip", "nik", "username", "user", "phone", "telp", "hp")
_FIELD_KONFIRMASI = ("confirm", "konfirm", "ulang", "repeat", "retype", "verify")


def templat_dari_field(titik: str, fields: list[Any], content_type: str = "") -> Optional[dict[str, Any]]:
    """Template form dari NAMA field body yang benar-benar dikirim aplikasi (intersep / lalu lintas
    jaringan / inventaris endpoint) — sumber terbaik untuk SPA yang tak punya form HTML statis.

    `fields`: [{nama, lokasi?, tipe?}] atau [str]. Nilai tak pernah dipakai (bisa memuat sandi).
    Bentuk keluaran sama dengan `klasifikasi_form`; None bila field tak cukup untuk titik itu.
    """
    nama: list[str] = []
    skema: dict[str, dict[str, Any]] = {}
    for f in fields or []:
        if isinstance(f, dict):
            if f.get("lokasi") not in (None, "", "body"):
                continue
            n = str(f.get("nama") or "")
            if n and f.get("tipe"):
                tipe = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}.get(str(f["tipe"]), str(f["tipe"]))
                skema[n] = {"type": tipe, "required": True}
        else:
            n = str(f or "")
        if n and n not in nama:
            nama.append(n)
    if not nama:
        return None
    ct = (content_type or "").lower()
    tipe_body = "form" if ("urlencoded" in ct or "multipart" in ct) else "json"
    sandi = [n for n in nama if _cocok(n.lower(), _FIELD_SANDI)]
    identitas = next((n for n in nama if _cocok(n.lower(), _FIELD_IDENTITAS)), None)

    if titik == "registrasi":
        if not sandi:
            return None
        konfirmasi = next((n for n in sandi[1:] if _cocok(n.lower(), _FIELD_KONFIRMASI)), "")
        dasar = {n: "" for n in nama if n not in sandi}
        out: dict[str, Any] = {
            "field_dasar": dasar,
            "field_sandi": next((n for n in sandi if n != konfirmasi), sandi[0]),
            "field_unik": [n for n in dasar if _cocok(n.lower(), _FIELD_UNIK)],
            "tipe_body": tipe_body,
            "skema_field": {k: v for k, v in skema.items() if k in dasar},
        }
        if identitas:
            out["field_identitas"] = identitas
        if konfirmasi:
            out["field_konfirmasi"] = konfirmasi
        return out
    if titik == "login":
        if not sandi:
            return None
        lain = [n for n in nama if n not in sandi]
        if not (identitas or lain):
            return None
        return {"field_username": identitas or lain[0], "field_password": sandi[0], "tipe_body": tipe_body}
    if titik == "reset_password":
        if sandi or not (identitas or len(nama) == 1):
            return None  # body bersandi = tahap konfirmasi (token + sandi baru), bukan permintaan reset
        return {"field_identitas": identitas or nama[0], "tipe_body": tipe_body}
    return None


def klasifikasi_tautan(href_abs: str) -> Optional[str]:
    """Tebak titik uji dari sebuah URL tautan (tanpa membuka halaman)."""
    for titik, kunci in _KATA.items():
        if _cocok(href_abs, kunci):
            return titik
    return None


# --------------------------------------------------------------------------- crawl


def _normalisasi(base: str, href: str) -> Optional[str]:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    absolut, _ = urldefrag(urljoin(base, href))
    if urlsplit(absolut).scheme not in ("http", "https"):
        return None
    return absolut


def crawl(base_url: str, *, timeout: float = 10.0, maks_halaman: int = MAKS_HALAMAN) -> list[HalamanDitemukan]:
    """BFS dalam-host dari base_url. Hanya GET; aman untuk dijalankan tanpa izin tulis."""
    host = _host(base_url)
    klien = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        verify=True,
    )
    antre: list[tuple[str, int]] = [(base_url, 0)]
    dikunjungi: set[str] = set()
    hasil: list[HalamanDitemukan] = []
    try:
        while antre and len(hasil) < maks_halaman:
            url, depth = antre.pop(0)
            if url in dikunjungi or _host(url) != host:
                continue
            dikunjungi.add(url)
            try:
                resp = klien.get(url)
            except httpx.HTTPError:
                continue
            hal = HalamanDitemukan(url=str(resp.url), status=resp.status_code)
            ctype = resp.headers.get("content-type", "")
            if "html" in ctype:
                p = _ParserHtml()
                try:
                    p.feed(resp.text)
                except Exception:
                    pass
                hal.judul = p.judul[:120]
                hal.form = p.form
                hal.skrip = [n for n in (_normalisasi(url, s) for s in p.skrip) if n]
                for href in p.tautan:
                    n = _normalisasi(url, href)
                    if n:
                        hal.tautan.append(n)
                        if depth < MAKS_KEDALAMAN and n not in dikunjungi:
                            antre.append((n, depth + 1))
            hasil.append(hal)
    finally:
        klien.close()
    return hasil


# Kandidat path halaman login frontend (untuk SPA yang endpoint API-nya saja terdeteksi).
_KANDIDAT_LOGIN = ("/login", "/masuk", "/signin", "/sign-in", "/auth/login", "/")


def _infer_login_page(base_url: str, timeout: float = 8.0) -> Optional[str]:
    """Tebak URL halaman login FRONTEND (HTML). None bila tak ada kandidat yang HTML.

    Hanya menerima respons text/html 200 → endpoint API (JSON) otomatis tersaring.
    """
    from urllib.parse import urljoin

    dasar = base_url.rstrip("/") + "/"
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}, verify=True) as klien:
        for path in _KANDIDAT_LOGIN:
            url = urljoin(dasar, path.lstrip("/"))
            try:
                r = klien.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", "").lower():
                return str(r.url)
    return None


def _probe_api(base_url: str, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Coba jalur dokumentasi API umum; kembalikan yang merespons 200 JSON."""
    host = _host(base_url)
    out: list[dict[str, Any]] = []
    klien = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}, verify=True)
    try:
        for jalur in JALUR_API_DOC:
            url = urljoin(base_url, jalur)
            if _host(url) != host:
                continue
            try:
                resp = klien.get(url)
            except httpx.HTTPError:
                continue
            ctype = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("json" in ctype or "yaml" in ctype):
                out.append({"url": str(resp.url), "tipe": "openapi"})
    finally:
        klien.close()
    return out


# --------------------------------------------------------------------------- orkestrasi


# Peringkat keyakinan: openapi/form terklasifikasi > tautan terklasifikasi.
_PERINGKAT = {"tinggi": 3, "sedang": 2, "rendah": 1}


def _gabung_titik(dst: dict[str, dict[str, Any]], src: dict[str, dict[str, Any]]) -> None:
    """Gabungkan test_points src ke dst; keyakinan lebih tinggi menang."""
    for titik, v in src.items():
        lama = dst.get(titik)
        if not lama or _PERINGKAT.get(lama.get("keyakinan", "rendah"), 1) < _PERINGKAT.get(v.get("keyakinan", "rendah"), 1):
            dst[titik] = v


# Tipe callback log bertahap: log(level, pesan). level ∈ info|peringatan|galat.
Logger = Optional[Any]


def _lognya(log: Logger, level: str, pesan: str) -> None:
    if log:
        try:
            log(level, pesan)
        except Exception:
            pass  # logging tak boleh menjatuhkan penemuan


def temukan(
    base_url: str,
    *,
    timeout: float = 10.0,
    openapi_url: Optional[str] = None,
    pakai_zap: bool = True,
    pakai_browser: bool = True,
    pakai_katana: bool = True,
    pakai_ai: bool = True,
    pakai_ffuf: bool = True,
    ctx: Optional[ScanContext] = None,
    log: Logger = None,
) -> dict[str, Any]:
    """Penemuan gabungan untuk `/internal/scans/:id/discovery`:
    (1) OpenAPI/Swagger bila spec ditemukan/diberikan — paling akurat untuk SPA+API;
    (2) crawl HTML untuk situs server-rendered;
    (3) browser (Playwright) render SPA + crawl TERAUTENTIKASI (bila `ctx` punya akun);
    (3b) ZAP spider/ajax (bila terkonfigurasi);
    (4) katana (bila terpasang) untuk enumerasi endpoint mendalam (JS parsing);
    (4b) analisis bundle JS — panggilan API (termasuk non-GET) di kode frontend;
    (5) inventaris endpoint + field terpadu berlapis (frontend/api), penajaman lapisan
        oleh AI, alur proses bisnis, dan enrichment AI.
    Tanpa OpenAPI, tahap browser juga menjalankan intersep aksi form (non-GET dibatalkan).

    `ctx` (opsional) membawa akun uji (+ totp_secret) untuk penemuan di balik login.
    `log(level, pesan)` dipanggil bertahap agar UI menampilkan apa yang ditemukan,
    dikerjakan, dan hasilnya."""
    from . import discovery_openapi as doa

    test_points: dict[str, dict[str, Any]] = {}
    forms: dict[str, dict[str, Any]] = {}
    sumber_form: dict[str, str] = {}  # titik → asal template (ditampilkan di ringkasan pemetaan)
    ringkasan_api: dict[str, Any] = {}
    spec_obj: Optional[dict[str, Any]] = None
    spec_url_simpan: Optional[str] = None

    def catat(titik: str, url: str, metode_http: str, keyakinan: str, catatan: str) -> None:
        # Tidak menimpa hasil dengan keyakinan lebih tinggi (mis. dari OpenAPI).
        lama = test_points.get(titik)
        if lama and _PERINGKAT[lama["keyakinan"]] >= _PERINGKAT[keyakinan]:
            return
        baru = lama is None
        test_points[titik] = {
            "tersedia": True, "url": url, "metode_http": metode_http,
            "sumber": "otomatis", "keyakinan": keyakinan, "catatan": catatan,
        }
        pr.pancar(
            log,
            f"  • titik '{titik}' {'ditemukan' if baru else 'diperkuat'} ({keyakinan}): {metode_http} {url}",
            {"jenis": "titik", "titik": titik, "url": pr.tanpa_query(url), "metode_http": metode_http, "keyakinan": keyakinan},
        )

    pr.tahap(log, "situs", f"Penemuan dimulai untuk {base_url}", url=base_url)

    # (1) OpenAPI.
    pr.tahap(
        log, "recon", "Mencari spesifikasi OpenAPI/Swagger…",
        jalur=[pre + suf for pre in doa._PREFIKS_API[:4] for suf in doa._SUFIKS_SPEC[:4]] + list(doa._SUFIKS_DOCS),
    )
    spec_url = openapi_url or doa.cari_spec(base_url, timeout=timeout)
    if spec_url:
        _lognya(log, "info", f"Spec OpenAPI ditemukan: {spec_url}")
        spec = doa.muat_spec(spec_url, timeout=timeout)
        if spec:
            spec_obj = spec
            spec_url_simpan = spec_url
            hasil_api = doa.dari_openapi(spec, spec_url)
            _gabung_titik(test_points, hasil_api["test_points"])
            forms.update(hasil_api["forms"])
            sumber_form.update({k: "OpenAPI" for k in hasil_api["forms"]})
            ringkasan_api = hasil_api["ringkasan"]
            rk = ringkasan_api
            pr.pancar(
                log,
                f"OpenAPI '{rk.get('judul','')}' v{rk.get('versi','')}: {rk.get('jumlah_endpoint',0)} endpoint, base API {rk.get('base_api','')}",
                {"jenis": "docs", "url": spec_url, "judul": rk.get("judul", ""), "versi": rk.get("versi", ""),
                 "jumlah_endpoint": rk.get("jumlah_endpoint", 0), "base_api": rk.get("base_api", "")},
            )
            _lognya(log, "info", f"OpenAPI → titik uji: {', '.join(rk.get('titik_ditemukan', [])) or '—'}")
        else:
            _lognya(log, "peringatan", "Spec OpenAPI ditemukan tetapi gagal diparse.")
    else:
        _lognya(log, "info", "Tidak ada OpenAPI; lanjut crawl HTML.")

    # (2) Crawl HTML.
    pr.tahap(log, "crawl", "Menjelajah (crawl) halaman HTML…")
    halaman = crawl(base_url, timeout=timeout)
    pr.pancar(
        log, f"Crawl HTML: {len(halaman)} halaman diperiksa.",
        {"jenis": "halaman", "items": [{"url": pr.tanpa_query(h.url), "status": h.status, "judul": (h.judul or "")[:120], "sumber": "html"}
                                for h in halaman[:60]]},
    )
    for hal in halaman:
        if hal.status in (401, 403):
            catat("area_terautentikasi", hal.url, "GET", "sedang", f"Merespons {hal.status} tanpa sesi.")
        for form in hal.form:
            hasil = klasifikasi_form(form, hal.url)
            if not hasil:
                continue
            titik, templat = hasil
            action_url = _normalisasi(hal.url, form.action) or hal.url
            catat(titik, action_url, form.method or "POST", "tinggi", f"Form pada {hal.url}")
            if titik not in forms:
                forms[titik] = templat
                sumber_form[titik] = "form HTML"
            # Form login ada di HALAMAN login (frontend) — rekam juga sebagai login_page (HTML).
            if titik == "login":
                catat("login_page", hal.url, "GET", "tinggi", "Halaman memuat form login (frontend).")
        for tautan in hal.tautan:
            titik = klasifikasi_tautan(tautan)
            if titik:
                # Tautan "login" menunjuk HALAMAN login (frontend), bukan endpoint aksi.
                if titik == "login":
                    titik = "login_page"
                catat(titik, tautan, "GET", "rendah", "Ditebak dari tautan.")

    endpoint_api = [] if ringkasan_api else _probe_api(base_url, timeout=timeout)
    if endpoint_api:
        catat("api", endpoint_api[0]["url"], "GET", "tinggi", "Dokumen OpenAPI/Swagger ditemukan.")

    # (3a) Penemuan berbasis browser (Playwright) — render SPA, baca form terender, sadap XHR/fetch.
    # Bila `ctx` punya akun uji & titik login telah terdeteksi → crawl TERAUTENTIKASI.
    # Tak bergantung OpenAPI; krusial untuk SPA (HTML awal kosong). Best-effort.
    ringkasan_browser: dict[str, Any] = {}
    akun = _akun_terpakai(ctx)
    # Inferensi halaman login frontend SEBELUM tahap browser: untuk SPA murni, `login`
    # kerap hanya berupa endpoint API (dari OpenAPI) sehingga tanpa ini login diarahkan
    # ke URL API, bukan halaman login. Dibutuhkan agar crawl terautentikasi tepat sasaran.
    if akun and "login" in test_points and "login_page" not in test_points:
        fe = _infer_login_page(base_url, timeout=timeout)
        if fe:
            catat("login_page", fe, "GET", "sedang", "Halaman login frontend (inferensi pra-browser).")
            _lognya(log, "info", f"  • 'login_page' diinferensi sebelum browser: {fe}")
    login_ctx = _bangun_login_ctx(ctx, base_url, test_points, forms, akun) if akun else None
    if pakai_browser:
        from . import discovery_browser as db
        if login_ctx is not None:
            pr.tahap(log, "browser", "Menjelajah via browser (SPA) + login terautentikasi…", login=True)
        else:
            pr.tahap(log, "browser", "Menjelajah via browser (SPA) — render rute & sadap endpoint API…", login=False)
        ringkasan_browser = db.jelajah_browser(
            base_url, catat, log, login_ctx=login_ctx, akun=akun,
            timeout=max(timeout, 15.0), pakai_ai_arbiter=pakai_ai,
            # Tanpa dokumentasi API, endpoint non-GET jarang terlihat → picu aksi form tanpa mengirim.
            intersep=spec_obj is None,
        )

    # Template form dari browser. Prioritas: OpenAPI > body request nyata (intersep/jaringan)
    # > form terender > form HTML statis. SPA tak punya form statis → tanpa ini `forms` kosong dan
    # uji registrasi/reset tak bisa menyusun payload walau endpoint-nya ditemukan.
    url_form = dict((ringkasan_browser or {}).get("url_form") or {})
    for titik, tpl in ((ringkasan_browser or {}).get("forms_bukti") or {}).items():
        if sumber_form.get(titik) != "OpenAPI":
            forms[titik] = tpl
            sumber_form[titik] = "body request nyata"
    for titik, tpl in ((ringkasan_browser or {}).get("forms_render") or {}).items():
        if titik not in forms:
            forms[titik] = tpl
            sumber_form[titik] = "form terender"

    # (3b) Pengayaan via ZAP (spider + ajax spider), terutama untuk SPA.
    ringkasan_zap: dict[str, Any] = {}
    if pakai_zap:
        ringkasan_zap = _enrich_zap(base_url, catat, log)

    # (4) Halaman login frontend. Bila hanya endpoint `login` (API — mis. dari OpenAPI) yang
    # terdeteksi, `login_page` kosong → check field-sandi/HTTPS keliru memakai endpoint API.
    # Inferensikan halaman login frontend agar pemeriksaan HTML mengarah ke frontend, bukan API.
    if "login" in test_points and "login_page" not in test_points:
        fe = _infer_login_page(base_url, timeout=timeout)
        if fe:
            catat("login_page", fe, "GET", "sedang", "Halaman login frontend (inferensi).")
        else:
            catat("login_page", base_url, "GET", "rendah", "Fallback: root aplikasi (SPA) untuk pemeriksaan frontend.")
        _lognya(log, "info", f"  • 'login' berupa endpoint API → 'login_page' diinferensi: {test_points['login_page']['url']}")

    # (4) katana — enumerasi endpoint mendalam (termasuk endpoint di dalam berkas JS).
    cookie_hdr = (ringkasan_browser or {}).get("cookie_header") or None
    ringkasan_katana, katana_hasil = _jalankan_katana(base_url, cookie_hdr, catat, log) if pakai_katana else ({}, [])

    # (4b) Analisis bundle JS — endpoint yang dipanggil kode frontend (termasuk non-GET).
    hasil_js = _analisis_bundle(base_url, halaman, ringkasan_browser, katana_hasil, ringkasan_zap, timeout, log)

    # (5) Inventaris endpoint + field terpadu dari semua sumber.
    endpoints_lengkap = _bangun_inventaris(
        base_url, spec_obj, spec_url_simpan, halaman, ringkasan_browser, katana_hasil, ringkasan_zap, doa,
        hasil_js=hasil_js,
    )
    if pakai_ffuf:
        _enrich_ffuf_parameter(endpoints_lengkap, cookie_hdr, log)
    if pakai_ai:
        _tajamkan_lapisan_ai(endpoints_lengkap, log)
    pr.tahap(log, "inventaris", f"Inventaris endpoint terpadu: {len(endpoints_lengkap)} endpoint unik.", jumlah=len(endpoints_lengkap))
    pr.pancar_endpoint(log, endpoints_lengkap)
    # Tuliskan daftar endpoint yang ditemukan agar pengguna melihat hasil konkret (dibatasi).
    MAKS_TAMPIL = 40
    for ep in endpoints_lengkap[:MAKS_TAMPIL]:
        auth = " 🔒" if ep.get("butuh_autentikasi") else ""
        sumber = "/".join(ep.get("sumber", []))
        _lognya(log, "info", f"    {ep['metode_http']:6} {ep['path_template']}{auth}  [{sumber}]")
    sisa = len(endpoints_lengkap) - MAKS_TAMPIL
    if sisa > 0:
        _lognya(log, "info", f"    … dan {sisa} endpoint lain (lihat inventaris lengkap di hasil penemuan).")

    # Area terautentikasi = endpoint API yang menolak/menyembunyikan data tanpa sesi (mis. /api/users/me),
    # bukan halaman frontend SPA (selalu 200 HTML sehingga proteksinya tak bisa dibuktikan dari luar).
    ep_auth = _endpoint_terproteksi(endpoints_lengkap) or _probe_area_api(base_url, endpoints_lengkap, timeout, log)
    if ep_auth:
        catat("area_terautentikasi", ep_auth["url"], "GET", "tinggi",
              "Endpoint API terproteksi (butuh sesi) dari inventaris endpoint.")
    _titik_inpv(endpoints_lengkap, catat)
    _ringkas_pemetaan(test_points, forms, sumber_form, url_form, log)

    # (6) Alur proses bisnis kandidat.
    from . import flow_map as fm

    flows = fm.bangun_flows(
        endpoints_lengkap,
        urutan_terpantau=(ringkasan_browser or {}).get("urutan"),
        test_points=test_points,
    )
    pr.pancar(
        log, f"Alur proses bisnis terpetakan: {len(flows)} alur.",
        {"jenis": "alur", "items": [
            {"nama": f.get("nama", ""), "sumber": f.get("sumber", ""),
             "langkah": [l.get("endpoint", "") for l in (f.get("langkah") or [])][:30]}
            for f in flows[:30]
        ]},
    )

    # (6b) Pemetaan KANDIDAT UJI: tiap endpoint → fungsi keamanan mana yang mengujinya.
    # Tool/check hilir tinggal membaca ini (tak perlu klasifikasi ulang).
    from . import kandidat as kd

    peta_kandidat = kd.petakan_kandidat(endpoints_lengkap, flows, test_points)
    pr.pancar(
        log,
        "Kandidat uji terpetakan: " + ", ".join(f"{k}×{v}" for k, v in peta_kandidat["ringkas_kategori"].items()),
        {"jenis": "kandidat", "ringkas": peta_kandidat["ringkas_kategori"],
         "per_endpoint": {e["endpoint"]: e["kategori"] for e in peta_kandidat["per_endpoint"][:300]}},
    )
    if pakai_ai:
        _sempurnakan_kandidat_ai(peta_kandidat, log)

    # (7) Enrichment AI (opsional).
    if pakai_ai:
        pr.tahap(log, "ai", "Analisis AI atas hasil penemuan…")
    ringkasan_ai = _enrich_ai(base_url, endpoints_lengkap, flows, test_points, halaman, log) if pakai_ai else {}

    ringkasan = {
        "halaman": [{"url": h.url, "status": h.status, "judul": h.judul} for h in halaman],
        "jumlah_halaman": len(halaman),
        "endpoint_api": endpoint_api,
        "titik_ditemukan": sorted(test_points.keys()),
        "endpoints_lengkap": endpoints_lengkap,
        "jumlah_endpoint_unik": len(endpoints_lengkap),
        "flows": flows,
        "terautentikasi": bool((ringkasan_browser or {}).get("terautentikasi")),
    }
    if ringkasan_api:
        ringkasan["openapi"] = ringkasan_api
    if ringkasan_browser:
        ringkasan["browser"] = {k: v for k, v in ringkasan_browser.items() if k != "request_detail"}
        if ringkasan_browser.get("endpoints"):
            # Inventaris endpoint API (dipakai uji fungsi lain, mis. validasi input).
            ringkasan["endpoints"] = ringkasan_browser["endpoints"]
    if ringkasan_zap:
        ringkasan["zap"] = ringkasan_zap
    if ringkasan_katana:
        ringkasan["katana"] = ringkasan_katana
    if peta_kandidat:
        ringkasan["kandidat_uji"] = peta_kandidat
    if ringkasan_ai:
        ringkasan["ai"] = ringkasan_ai
    pr.tahap(
        log, "selesai", f"Penemuan selesai. Titik uji terdeteksi: {', '.join(ringkasan['titik_ditemukan']) or '—'}",
        terautentikasi=ringkasan["terautentikasi"],
    )
    return {"test_points": test_points, "forms": forms, "ringkasan": ringkasan}


# --------------------------------------------------------------------------- pemetaan titik uji


_PRIORITAS_AREA = ("/me", "profil", "profile", "akun", "account", "dashboard", "user")


def _endpoint_terproteksi(endpoints: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """GET API yang butuh sesi: terlihat hanya saat terautentikasi atau membalas 401/403 tanpa sesi.
    Path tanpa parameter & bernuansa akun (/me, /profile) didahulukan."""
    kandidat = [
        e for e in endpoints
        if e.get("metode_http") == "GET" and (e.get("lapisan") or "api") == "api"
        and "{" not in (e.get("path_template") or "")
        and (e.get("butuh_autentikasi") or {401, 403} & set(e.get("status_terlihat") or []))
    ]
    if not kandidat:
        return None

    def skor(e: dict[str, Any]) -> tuple[int, int]:
        p = (e.get("path_template") or "").lower()
        return (next((i for i, k in enumerate(_PRIORITAS_AREA) if k in p), len(_PRIORITAS_AREA)), len(p))

    return min(kandidat, key=skor)


def _titik_inpv(endpoints: list[dict[str, Any]], catat: Any) -> None:
    """Titik uji fungsi Validasi Input: `api` (ada endpoint API) dan `form_input` (ada endpoint yang
    menerima field body/query). Check INPV menyapu SELURUH inventaris; URL titik hanya penanda
    ketersediaan agar metode INPV tidak dianggap tidak berlaku."""
    api = [e for e in endpoints if (e.get("lapisan") or "api") == "api"]
    berfield = [e for e in api if any(f.get("lokasi") in ("body", "query") for f in e.get("request_fields") or [])]
    if api:
        catat("api", api[0]["url"], api[0].get("metode_http", "GET"), "sedang", f"{len(api)} endpoint API terinventaris (uji INPV menyapu semuanya).")
    if berfield:
        e = next((x for x in berfield if str(x.get("metode_http", "GET")).upper() != "GET"), berfield[0])
        catat("form_input", e["url"], e.get("metode_http", "POST"), "sedang", f"{len(berfield)} endpoint menerima input body/query.")


_PATH_AKUN = ("/me", "profil", "profile", "akun", "account")


def _probe_area_api(base_url: str, endpoints: list[dict[str, Any]], timeout: float, log: Any) -> Optional[dict[str, Any]]:
    """Endpoint akun (/me, /profile) yang hanya dikenal dari bundle JS belum punya bukti proteksi.
    Satu GET anonim (baca saja, tanpa body) per kandidat: 401/403 → bukti endpoint butuh sesi."""
    dasar = (_host(base_url) or "").removeprefix("www.")
    kandidat = sorted(
        (e for e in endpoints
         if e.get("metode_http") == "GET" and (e.get("lapisan") or "api") == "api"
         and "{" not in (e.get("path_template") or "")
         and any(k in (e.get("path_template") or "").lower() for k in _PATH_AKUN)
         and ((_host(e.get("url", "")) or "") == dasar or (_host(e.get("url", "")) or "").endswith("." + dasar))),
        key=lambda e: len(e.get("path_template") or ""),
    )[:3]
    if not kandidat:
        return None
    with httpx.Client(timeout=min(timeout, 10.0), follow_redirects=False, headers={"User-Agent": USER_AGENT}) as klien:
        for e in kandidat:
            try:
                kode = klien.get(e["url"]).status_code
            except httpx.HTTPError:
                continue
            _lognya(log, "info", f"  • cek proteksi GET {e['path_template']} tanpa sesi → HTTP {kode}")
            if kode in (401, 403):
                e["status_terlihat"] = sorted(set(e.get("status_terlihat") or []) | {kode})
                return e
    return None


def _ringkas_pemetaan(
    test_points: dict[str, dict[str, Any]], forms: dict[str, dict[str, Any]], sumber_form: dict[str, str],
    url_form: dict[str, str], log: Any,
) -> None:
    """Ringkasan "titik uji → endpoint + template form" agar asesor melihat dasar setiap uji AUTH.

    Template browser yang endpoint-nya bukan titik terpilih (mis. titik diganti OpenAPI) dibuang.
    Hanya NAMA field yang ditampilkan."""
    for titik, asal in url_form.items():
        tp = test_points.get(titik) or {}
        if sumber_form.get(titik) == "body request nyata" and asal != f"{tp.get('metode_http', '')} {pr.tanpa_query(tp.get('url', ''))}":
            forms.pop(titik, None)
            sumber_form.pop(titik, None)
    _lognya(log, "info", "Pemetaan titik uji (dasar metode uji):")
    for titik in ("login", "registrasi", "reset_password", "ubah_password", "area_terautentikasi", "login_page", "logout"):
        tp = test_points.get(titik)
        f = forms.get(titik) or {}
        if not tp:
            if titik in ("login", "registrasi", "reset_password", "area_terautentikasi"):
                _lognya(log, "peringatan", f"  • {titik:20} → tidak ditemukan (uji terkait berstatus tidak berlaku/tidak dapat diverifikasi)")
            continue
        if titik == "registrasi":
            field = f"field: {', '.join(f.get('field_dasar') or {}) or '—'} | sandi: {f.get('field_sandi', '—')}" if f else "field: TIDAK DIKETAHUI"
        elif titik == "login":
            field = f"field: {f.get('field_username')} + {f.get('field_password')}" if f else "field: bawaan (email + password)"
        elif titik == "reset_password":
            field = f"field: {f.get('field_identitas')}" if f else "field: bawaan (email)"
        else:
            field = ""
        asal = f" · template: {sumber_form[titik]}" if titik in sumber_form else ""
        pr.pancar(
            log,
            f"  • {titik:20} → {tp.get('metode_http', 'GET')} {pr.tanpa_query(tp.get('url', ''))} [{tp.get('keyakinan', '')}]"
            + (f" {field}" if field else "") + asal,
            {"jenis": "pemetaan", "titik": titik, "url": pr.tanpa_query(tp.get("url", "")), "metode_http": tp.get("metode_http", "GET"),
             "keyakinan": tp.get("keyakinan", ""), "catatan": (tp.get("catatan") or "")[:200],
             "field": list((f.get("field_dasar") or {}).keys())[:20], "sumber_template": sumber_form.get(titik, "")},
            level="peringatan" if titik == "registrasi" and not f else "info",
        )


# --------------------------------------------------------------------------- pembantu autentikasi & inventaris


def _akun_terpakai(ctx: Optional[ScanContext]) -> Optional[AkunUji]:
    """Akun uji pertama yang siap dipakai (terisi + ada kata sandi)."""
    if ctx is None:
        return None
    for a in ctx.akun_uji:
        if a.terisi and a.password:
            return a
    return None


def _bangun_login_ctx(
    ctx: Optional[ScanContext],
    base_url: str,
    test_points: dict[str, dict[str, Any]],
    forms: dict[str, dict[str, Any]],
    akun: AkunUji,
) -> Optional[ScanContext]:
    """Susun ScanContext minimal (titik login + form + akun) untuk login via browser."""
    if "login" not in test_points and "login_page" not in test_points:
        return None
    tp: dict[str, Any] = {}
    for k in ("login", "login_page"):
        v = test_points.get(k)
        if v:
            tp[k] = {"tersedia": v.get("tersedia", True), "url": v.get("url", ""), "metode_http": v.get("metode_http", "POST")}
    data = {
        "scan_id": ctx.scan_id if ctx else "",
        "aplikasi_id": ctx.aplikasi_id if ctx else "",
        "base_url": base_url,
        "titik_uji": tp,
        "form": {"login": forms.get("login", {})} if forms.get("login") else {},
        "akun_uji": [{
            "kunci": akun.kunci, "username": akun.username, "password": akun.password,
            "terisi": True, "totp_secret": akun.totp_secret,
            "totp_digits": akun.totp_digits, "totp_period": akun.totp_period,
            "totp_algoritma": akun.totp_algoritma,
        }],
    }
    return ScanContext.from_dict(data)


def _jalankan_katana(base_url: str, cookie_hdr: Optional[str], catat: Any, log: Logger) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Jalankan katana (best-effort). Return (ringkasan, daftar_hasil); tiap hasil diberi `lapisan`."""
    from . import endpoint_map as em
    from . import katana_client as kc

    if not kc.tersedia():
        _lognya(log, "info", "Katana tak terpasang — lewati.")
        return {"tersedia": False}, []
    pr.tahap(log, "katana", "Menjalankan katana (crawl + JS parsing)…" + (" [terautentikasi]" if cookie_hdr else ""))
    hasil = kc.jalankan(base_url, cookie=cookie_hdr)
    for k in hasil:
        k["lapisan"] = em.klasifikasi_lapisan(k["method"], k["url"], base_url=base_url, content_type=k.get("content_type"))
    ringkas = {lp: sum(1 for k in hasil if k["lapisan"] == lp) for lp in em.LAPISAN}
    pr.pancar(
        log,
        f"Katana: {len(hasil)} URL/endpoint ditemukan (frontend {ringkas['frontend']}, API {ringkas['api']}, aset {ringkas['aset']}).",
        {"jenis": "katana", "jumlah": len(hasil), "ringkas": ringkas, "items": _item_lapisan(hasil)},
    )
    for k in hasil:
        titik = klasifikasi_tautan(k["url"])
        if titik:
            if titik == "login":
                titik = "login_page"
            catat(titik, k["url"], k.get("method", "GET"), "sedang", "Ditemukan katana.")
    return {"tersedia": True, "jumlah": len(hasil), "ringkas": ringkas, "terautentikasi": bool(cookie_hdr)}, hasil


# Batas item per peristiwa katana/ZAP agar data tetap < 64 KB.
MAKS_ITEM_PERISTIWA = 250
MAKS_ITEM_JS = 30


def _item_lapisan(hasil: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ringkas hasil crawl (berlapisan) untuk UI: URL tanpa query, non-aset + berkas JS saja."""
    items: list[dict[str, Any]] = []
    n_js = 0
    terlihat: set[str] = set()
    for k in hasil:
        url = pr.tanpa_query(k["url"])
        kunci = f"{k.get('method', 'GET')} {url}"
        if kunci in terlihat:
            continue
        if k["lapisan"] == "aset":
            if not url.lower().endswith((".js", ".mjs")) or n_js >= MAKS_ITEM_JS:
                continue
            n_js += 1
        elif len(items) - n_js >= MAKS_ITEM_PERISTIWA:
            continue
        terlihat.add(kunci)
        it: dict[str, Any] = {"url": url, "metode_http": k.get("method", "GET"), "lapisan": k["lapisan"]}
        if k.get("status"):
            it["status"] = k["status"]
        items.append(it)
    return items


def _analisis_bundle(
    base_url: str,
    halaman: list[HalamanDitemukan],
    ringkasan_browser: dict[str, Any],
    katana_hasil: list[dict[str, Any]],
    ringkasan_zap: dict[str, Any],
    timeout: float,
    log: Logger,
) -> dict[str, Any]:
    """Unduh berkas JS same-origin (dari HTML, browser, katana, ZAP) & ekstrak panggilan API."""
    from . import discovery_js as dj

    skrip: list[str] = [u for h in halaman for u in h.skrip]
    skrip += (ringkasan_browser or {}).get("skrip") or []
    skrip += [k["url"] for k in katana_hasil if k.get("lapisan") == "aset"]
    skrip += [u for u in (ringkasan_zap or {}).get("urls_aset", []) or []]
    skrip = [u for u in dict.fromkeys(pr.tanpa_query(u) for u in skrip) if u.lower().endswith((".js", ".mjs"))]
    if not skrip:
        _lognya(log, "info", "Analisis bundle JS: tidak ada berkas JS untuk dianalisis.")
        return {}
    pr.tahap(log, "bundle", f"Analisis bundle JS: membaca {min(len(skrip), dj.MAKS_BERKAS)} berkas skrip…")
    try:
        hasil = dj.analisis(base_url, skrip, timeout=timeout)
    except Exception as e:  # best-effort
        _lognya(log, "peringatan", f"Analisis bundle JS gagal: {type(e).__name__}: {e}")
        return {}
    eps = hasil.get("endpoints") or []
    non_get = sum(1 for e in eps if e["method"] != "GET")
    _lognya(log, "info", f"Analisis bundle JS: {len(hasil.get('berkas') or [])} berkas, {len(eps)} panggilan API ({non_get} non-GET)"
                         + (f"; base backend {', '.join(hasil['base'])}" if hasil.get("base") else "") + ".")
    for e in eps[:15]:
        _lognya(log, "info", f"  • {e['method']:6} {e['path']}  [{e['berkas']}]")
    return hasil


def _url_templat(url: str) -> bool:
    """URL masih memuat placeholder path (`{id}` / `%7Bid%7D`) → tak akan resolve; fuzz param sia-sia."""
    u = (url or "").lower()
    return "{" in u or "%7b" in u


def _enrich_ffuf_parameter(endpoints: list[dict[str, Any]], cookie: Optional[str], log: Logger) -> None:
    """Pengaya opsional: pakai ffuf untuk menemukan NAMA parameter query pada endpoint GET API yang
    belum punya parameter terdeteksi. No-op anggun bila biner ffuf tak terpasang/di-disable.

    Dibatasi agar tak memblokir pipeline: endpoint ber-placeholder `{id}` dilewati (fuzz sia-sia),
    jumlah endpoint dibatasi `FFUF_MAKS_ENDPOINT` (bawaan 5), dan ANGGARAN WAKTU TOTAL
    `FFUF_BUDGET_TOTAL` detik (bawaan 120) — bila habis, sisa endpoint dilewati."""
    import time

    from . import endpoint_map as em
    from . import ffuf_client as ff

    if not ff.tersedia():
        return
    try:
        maks_ep = int(os.environ.get("FFUF_MAKS_ENDPOINT", "5"))
    except ValueError:
        maks_ep = 5
    try:
        budget = float(os.environ.get("FFUF_BUDGET_TOTAL", "120"))
    except ValueError:
        budget = 120.0
    kandidat = [
        e for e in endpoints
        if str(e.get("metode_http") or "GET").upper() == "GET" and (e.get("lapisan") or "api") == "api"
        and not any(f.get("lokasi") == "query" for f in e.get("request_fields") or [])
        and not _url_templat(str(e.get("url") or ""))   # lewati /x/{id} yang belum terisi
    ][:maks_ep]
    if not kandidat:
        return
    pr.tahap(log, "ffuf", f"ffuf menemukan parameter query pada ≤{len(kandidat)} endpoint API (anggaran {budget:.0f}s)…")
    t0 = time.monotonic()
    total = diproses = 0
    for e in kandidat:
        if time.monotonic() - t0 > budget:
            _lognya(log, "info", f"ffuf: anggaran waktu {budget:.0f}s habis — {diproses}/{len(kandidat)} endpoint diproses, sisanya dilewati.")
            break
        diproses += 1
        try:
            nama = ff.temukan_parameter(str(e.get("url") or ""), cookie=cookie)
        except Exception:
            nama = []
        ada = {f.get("nama") for f in e.get("request_fields") or []}
        baru = [em.field(n, "query") for n in nama if n not in ada]
        if baru:
            e.setdefault("request_fields", []).extend(baru)
            e["sumber"] = list(dict.fromkeys((e.get("sumber") or []) + ["ffuf"]))
            e["catatan"] = (e.get("catatan") or "") + f" [ffuf: +{len(baru)} param]"
            total += len(baru)
    _lognya(log, "info", f"ffuf: {total} parameter query baru pada {diproses} endpoint ({time.monotonic() - t0:.0f}s).")


def _tajamkan_lapisan_ai(endpoints: list[dict[str, Any]], log: Logger) -> None:
    """Minta AI mengoreksi lapisan/metode endpoint yang ambigu (METADATA saja). Gagal → diam."""
    from . import ai as ai_mod

    ambigu = [
        e for e in endpoints
        if (e.get("lapisan") == "frontend" and e.get("request_fields"))
        or (e.get("sumber") == ["js"] and e.get("metode_http") == "GET")
        or (e.get("lapisan") == "frontend" and set(e.get("sumber") or []) <= {"katana", "zap"})
    ][:150]
    if not ambigu:
        return
    meta = [{
        "endpoint": f"{e['metode_http']} {e['path_template']}",
        "origin": pr.origin(e.get("url", "")),
        "sumber": e.get("sumber") or [],
        "content_type": e.get("content_type") or "",
        "lapisan_heuristik": e.get("lapisan"),
        "field": [f.get("nama") for f in e.get("request_fields") or []][:20],
    } for e in ambigu]
    pr.tahap(log, "ai", f"AI menajamkan klasifikasi {len(meta)} endpoint ambigu…")
    hasil = ai_mod.klasifikasi_endpoint(meta)
    if not hasil:
        _lognya(log, "info", "Penajaman AI dilewati (AI tak tersedia/gagal).")
        return
    per_id = {f"{e['metode_http']} {e['path_template']}": e for e in endpoints}
    n = 0
    for s in hasil["saran"]:
        if not isinstance(s, dict):
            continue
        ep = per_id.get(str(s.get("endpoint", "")))
        if ep is None:
            continue
        lp = s.get("lapisan")
        if lp in ("frontend", "api", "aset") and lp != ep.get("lapisan"):
            ep["lapisan"] = lp
            ep["catatan"] = (ep.get("catatan") or "") + f" [AI: {str(s.get('alasan', ''))[:120]}]"
            n += 1
        if s.get("upload") is True and not ep.get("titik_uji"):
            ep["titik_uji"] = "unggah_file"
            n += 1
    _lognya(log, "info", f"AI ({hasil.get('provider')}) menajamkan {n} endpoint.")


def _bangun_inventaris(
    base_url: str,
    spec_obj: Optional[dict[str, Any]],
    spec_url: Optional[str],
    halaman: list["HalamanDitemukan"],
    ringkasan_browser: dict[str, Any],
    katana_hasil: list[dict[str, Any]],
    ringkasan_zap: dict[str, Any],
    doa: Any,
    *,
    hasil_js: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Satukan endpoint + field dari OpenAPI, HTML, browser (+intersep), katana, ZAP, bundle JS.

    Tiap endpoint diberi `lapisan` (frontend/api). Aset statis (JS/CSS/gambar) tidak dimasukkan:
    mereka bukan permukaan uji dan hanya akan menghasilkan kandidat uji palsu."""
    from . import endpoint_map as em

    inv = em.InventarisEndpoint()

    def lapisan(method: str, url: str, sumber: str, ct: Optional[str] = None) -> str:
        return em.klasifikasi_lapisan(method, url, base_url=base_url, sumber=sumber, content_type=ct)

    # OpenAPI: field request/respons lengkap.
    if spec_obj is not None:
        for ep in doa.endpoint_fields(spec_obj, spec_url or base_url):
            inv.tambah(
                ep["method"], ep["url"], sumber="openapi",
                request_fields=ep["request_fields"], response_fields=ep["response_fields"],
                content_type=ep.get("content_type") or None, titik_uji=ep.get("titik"), lapisan="api",
            )

    # HTML: halaman (GET) + form (field input). Crawl HTML anonim.
    for hal in halaman:
        lp = lapisan("GET", hal.url, "html")
        if lp != "aset":
            inv.tambah("GET", hal.url, sumber="html", status=hal.status,
                       titik_uji=klasifikasi_tautan(hal.url),
                       terautentikasi=(hal.status not in (401, 403)), lapisan=lp)
        for form in hal.form:
            action_url = _normalisasi(hal.url, form.action) or hal.url
            kf = klasifikasi_form(form, hal.url)
            rf = [em.field(i.get("name", ""), "body", tipe=(i.get("type") or "")) for i in form.inputs if i.get("name")]
            inv.tambah(form.method or "POST", action_url, sumber="html", request_fields=rf,
                       titik_uji=(kf[0] if kf else None), terautentikasi=False,
                       lapisan=lapisan(form.method or "POST", action_url, "html"))

    # Browser: request XHR/fetch nyata (+ query/body fields + status + flag auth).
    for rec in (ringkasan_browser or {}).get("request_detail", []) or []:
        rf = em.field_dari_query(rec["url"]) + em.field_dari_body(rec.get("post_data"), rec.get("content_type", ""))
        inv.tambah(
            rec["method"], rec["url"], sumber="browser", request_fields=rf,
            content_type=rec.get("content_type") or None, status=rec.get("status"),
            titik_uji=klasifikasi_tautan(rec["url"]),
            terautentikasi=bool(rec.get("terautentikasi")), lapisan="api",
        )

    # Browser — intersep aksi (request non-GET yang dibatalkan sebelum terkirim).
    for rec in (ringkasan_browser or {}).get("intersep", []) or []:
        inv.tambah(
            rec["method"], rec["url"], sumber="browser-intersep",
            request_fields=em.field_dari_query(rec["url"]) + list(rec.get("fields") or []),
            content_type=("multipart/form-data" if rec.get("multipart") else rec.get("content_type")) or None,
            titik_uji=("unggah_file" if rec.get("multipart") else klasifikasi_tautan(rec["url"])),
            terautentikasi=bool((ringkasan_browser or {}).get("terautentikasi")), lapisan="api",
        )

    # Katana (lapisan sudah diklasifikasi di _jalankan_katana).
    auth_katana = bool((ringkasan_browser or {}).get("cookie_header"))
    for k in katana_hasil:
        lp = k.get("lapisan") or lapisan(k["method"], k["url"], "katana", k.get("content_type"))
        if lp == "aset":
            continue
        inv.tambah(k["method"], k["url"], sumber="katana",
                   request_fields=em.field_dari_query(k["url"]), content_type=k.get("content_type"),
                   status=k.get("status"), titik_uji=klasifikasi_tautan(k["url"]),
                   terautentikasi=auth_katana, lapisan=lp)

    # ZAP: seluruh URL non-aset hasil spider (versi lama hanya punya `contoh_url`).
    rz = ringkasan_zap if isinstance(ringkasan_zap, dict) else {}
    for u in rz.get("urls_inventaris") or rz.get("contoh_url") or []:
        lp = lapisan("GET", u, "zap")
        if lp != "aset":
            inv.tambah("GET", u, sumber="zap", request_fields=em.field_dari_query(u), terautentikasi=False, lapisan=lp)

    # Bundle JS: panggilan API yang tertanam di kode frontend.
    for e in (hasil_js or {}).get("endpoints", []) or []:
        url = _rebase_js(e["url"], base_url, ringkasan_browser)
        if _metode_js_terbantah(e["method"], url, ringkasan_browser) or lapisan(e["method"], url, "") == "aset":
            continue
        # Field query terlihat di bundle (nama parameter) + query pada URL (bila ada) → endpoint
        # berbasis query string tetap punya permukaan uji, bukan dianggap "tanpa input".
        rf = em.field_dari_query(url) + [em.field(q, "query") for q in (e.get("query") or [])
                                         if q not in {f.get("nama") for f in em.field_dari_query(url)}]
        inv.tambah(e["method"], url, sumber="js", titik_uji=klasifikasi_tautan(url),
                   request_fields=rf, catatan=f"Dari bundle {e.get('berkas', '')}", lapisan="api")

    return inv.sebagai_list()


def _lalu_lintas(ringkasan_browser: Optional[dict[str, Any]]) -> list[tuple[str, str]]:
    rb = ringkasan_browser or {}
    return [(str(r.get("method", "GET")).upper(), str(r.get("url", "")))
            for r in list(rb.get("request_detail") or []) + list(rb.get("intersep") or []) if r.get("url")]


def _segmen(path: str) -> str:
    bagian = path.strip("/").split("/")
    return "/" + bagian[0] if bagian and bagian[0] else ""


def _rebase_js(url: str, base_url: str, ringkasan_browser: Optional[dict[str, Any]]) -> str:
    """Path relatif dari bundle JS dirangkai ke origin frontend bila base backend tak terdeteksi
    (mis. baseURL dari variabel env). Bila lalu lintas nyata menunjukkan API di origin lain dengan
    segmen path pertama sama (rai-edu.com/api/x → api.rai-edu.com/api/x), pindahkan ke origin itu."""
    p = urlsplit(url)
    fe = urlsplit(base_url).netloc.lower()
    seg = _segmen(p.path)
    if p.netloc.lower() != fe or not seg:
        return url
    for _, u in _lalu_lintas(ringkasan_browser):
        q = urlsplit(u)
        if q.netloc.lower() != fe and _segmen(q.path) == seg:
            return f"{q.scheme}://{q.netloc}{p.path}" + (f"?{p.query}" if p.query else "")
    return url


def _metode_js_terbantah(metode: str, url: str, ringkasan_browser: Optional[dict[str, Any]]) -> bool:
    """Ekstraksi bundle kerap tak tahu metode (bawaan GET). Bila lalu lintas nyata memanggil path yang
    sama HANYA dengan metode lain (mis. POST /api/users/register), entri GET dari JS adalah palsu."""
    if metode.upper() != "GET":
        return False
    p = urlsplit(url)
    kunci = (p.netloc.lower(), p.path.rstrip("/"))
    terlihat = {m for m, u in _lalu_lintas(ringkasan_browser)
                if (urlsplit(u).netloc.lower(), urlsplit(u).path.rstrip("/")) == kunci}
    return bool(terlihat) and "GET" not in terlihat


def _enrich_ai(
    base_url: str,
    endpoints_lengkap: list[dict[str, Any]],
    flows: list[dict[str, Any]],
    test_points: dict[str, dict[str, Any]],
    halaman: list["HalamanDitemukan"],
    log: Logger,
) -> dict[str, Any]:
    """Enrichment AI (opsional, best-effort)."""
    from . import ai as ai_mod

    payload = {
        "base_url": base_url,
        "endpoints": endpoints_lengkap[:200],
        "flows": flows,
        "titik_uji": sorted(test_points.keys()),
        "halaman": [{"url": h.url, "judul": h.judul} for h in halaman][:50],
    }
    hasil = ai_mod.enrich_discovery(payload)
    if hasil.get("tersedia"):
        _lognya(log, "info", f"AI enrichment via {hasil.get('provider')} ({hasil.get('model')}).")
    elif hasil.get("provider"):
        _lognya(log, "peringatan", f"AI enrichment gagal: {hasil.get('galat')}")
    else:
        _lognya(log, "info", "AI tak dikonfigurasi — lewati enrichment.")
    return hasil


def _sempurnakan_kandidat_ai(peta_kandidat: dict[str, Any], log: Logger) -> None:
    """Minta AI menyempurnakan kategori kandidat & menandai info kurang (best-effort).

    Hanya METADATA non-sensitif (nama field, bukan nilai) yang dikirim. Gagal → diam."""
    from . import ai as ai_mod
    from . import kandidat as kd

    meta = kd.metadata_untuk_ai(peta_kandidat)
    hasil = ai_mod.lengkapi_kandidat(meta)
    if not hasil:
        _lognya(log, "info", "Kandidat: penyempurnaan AI dilewati (AI tak tersedia/gagal).")
        return
    n = kd.gabung_saran_ai(peta_kandidat, hasil.get("saran", []))
    peta_kandidat["sumber"] = "heuristik+ai"
    _lognya(log, "info", f"Kandidat disempurnakan AI ({hasil.get('provider')}): {n} endpoint diperbarui.")


_PERINGKAT_RISIKO = {"High": 3, "Medium": 2, "Low": 1, "Informational": 0}


def _enrich_zap(base_url: str, catat: Any, log: Logger) -> dict[str, Any]:
    """Jalankan ZAP spider/ajax untuk memperkaya URL & temuan (best-effort).
    Mengisi titik uji tambahan dari URL hasil crawl ZAP, dan menitipkan alert pasif
    ke cache engine zap agar check zap pasif tak mem-spider ulang."""
    from . import endpoint_map as em
    from . import zap_client as zc
    from .checks import zap_scan

    klien = zc.dari_env()
    if klien is None:
        _lognya(log, "info", "ZAP tidak dikonfigurasi — lewati pengayaan ZAP.")
        return {}
    try:
        with klien:
            versi = klien.version()
            pr.tahap(log, "zap", f"ZAP {versi}: menjalankan spider + ajax spider pada {base_url}…")
            spider_ok = klien.jalankan_spider(base_url, batas=zc.batas_spider())
            urls = klien.daftar_url(base_url)
            _lognya(log, "info", f"ZAP menemukan {len(urls)} URL di bawah target.")
            if not urls:
                _lognya(log, "peringatan", "ZAP tidak menjangkau target (0 URL) — pengayaan dilewati.")
                return {"jumlah_url": 0, "terjangkau": False}
            # Klasifikasi titik uji dari URL hasil ZAP (keyakinan sedang).
            for u in urls:
                titik = klasifikasi_tautan(u)
                if titik:
                    catat(titik, u, "GET", "sedang", "Ditemukan oleh spider ZAP.")
            # Temuan pasif awal (ringkasan untuk UI) + titipkan ke cache engine zap.
            alerts = klien.alerts(base_url)
            zap_scan.prime_cache(base_url, alerts, scan_ok=bool(spider_ok and urls))
            ringkas_temuan: dict[str, int] = {}
            for a in alerts:
                nama = a.get("alert") or a.get("name") or "?"
                ringkas_temuan[nama] = ringkas_temuan.get(nama, 0) + 1
            top = sorted(ringkas_temuan.items(), key=lambda x: -x[1])[:8]

            # Klasifikasi lapisan tiap URL → UI menempatkannya di klaster frontend/backend.
            berlapis = [{"url": u, "method": "GET", "lapisan": em.klasifikasi_lapisan("GET", u, base_url=base_url)} for u in urls]
            ringkas = {lp: sum(1 for b in berlapis if b["lapisan"] == lp) for lp in em.LAPISAN}
            # Alert per URL (nama + risiko), satu entri per (url, nama); risiko tertinggi diutamakan.
            alert_url: dict[tuple[str, str], dict[str, str]] = {}
            for a in sorted(alerts, key=lambda a: -_PERINGKAT_RISIKO.get(str(a.get("risk", "")), 0)):
                u = pr.tanpa_query(str(a.get("url") or ""))
                nama = str(a.get("alert") or a.get("name") or "?")
                if u and (u, nama) not in alert_url:
                    alert_url[(u, nama)] = {"url": u, "nama": nama[:120], "risk": str(a.get("risk") or "Informational")}
            pr.pancar(
                log,
                f"ZAP passive scan: {len(alerts)} alert ({len(ringkas_temuan)} jenis); URL: frontend {ringkas['frontend']}, "
                f"API {ringkas['api']}, aset {ringkas['aset']}.",
                {"jenis": "zap", "jumlah_url": len(urls), "ringkas": ringkas, "items": _item_lapisan(berlapis),
                 "alert_url": list(alert_url.values())[:150], "temuan": [{"nama": n, "n": c} for n, c in top]},
            )
            for nama, n in top:
                _lognya(log, "info", f"  • temuan awal: {nama} ×{n}")
            return {
                "jumlah_url": len(urls),
                "terjangkau": True,
                "jumlah_alert": len(alerts),
                "jenis_temuan": [{"nama": n, "jumlah": c} for n, c in top],
                "contoh_url": urls[:30],
                "ringkas": ringkas,
                "urls_inventaris": [b["url"] for b in berlapis if b["lapisan"] != "aset"][:300],
                "urls_aset": [b["url"] for b in berlapis if b["lapisan"] == "aset"][:100],
            }
    except Exception as e:
        _lognya(log, "peringatan", f"Pengayaan ZAP gagal: {type(e).__name__}: {e}")
        return {"gagal": f"{type(e).__name__}"}
