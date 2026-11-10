"""Layer penemuan berbasis browser (Playwright) — SPA + crawl TERAUTENTIKASI.

Discovery statis (crawl HTML) & OpenAPI tak cukup untuk SPA: HTML awal kosong
(dirender JS) dan endpoint di balik login tak terlihat. Layer ini **merender**
aplikasi di browser nyata, opsional **login** (termasuk langkah MFA/TOTP), lalu
menjelajah rute frontend + tautan router internal, membaca **form/input terender**,
dan **menyadap lalu lintas XHR/fetch lengkap** (metode, URL, body, status) untuk
membangun inventaris endpoint API yang sebenarnya — anonim maupun terautentikasi.

Non-destruktif: navigasi GET + baca DOM + amati jaringan + login dengan akun uji.
Endpoint aksi ditemukan dari `action` form, XHR/fetch terpantau, dan (opsional)
`intersep_aksi`: form/tombol aksi dipicu tetapi setiap request non-GET dibatalkan
di browser sebelum terkirim, sehingga server tak pernah menerima mutasi.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit

from . import peristiwa as pr
from . import playwright_driver as pw
from .models import AkunUji, ScanContext

Logger = Optional[Callable[[str, str], None]]

# Rute frontend umum (anonim) untuk dirender (GET).
_RUTE_UMUM = (
    "/", "/login", "/masuk", "/signin", "/sign-in", "/auth/login",
    "/register", "/daftar", "/signup", "/sign-up", "/registrasi",
    "/forgot-password", "/lupa-password", "/reset-password",
    "/dashboard", "/beranda", "/admin",
)

# Rute yang umumnya hanya berguna SETELAH login (crawl terautentikasi).
_RUTE_AUTH = (
    "/dashboard", "/beranda", "/home", "/profile", "/profil", "/akun", "/account",
    "/settings", "/pengaturan", "/me", "/users", "/pengguna", "/admin", "/orders",
    "/transaksi", "/riwayat", "/notifications", "/notifikasi",
)

_ASET = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
         ".woff", ".woff2", ".ttf", ".map", ".webp", ".avif", ".mp4")


def _log(log: Logger, level: str, pesan: str) -> None:
    if log:
        try:
            log(level, pesan)
        except Exception:
            pass


def _host(u: str) -> str:
    return (urlsplit(u).hostname or "").lower()


def _baca_forms(page: Any) -> list[dict[str, Any]]:
    js = """() => [...document.querySelectorAll('form')].map(f => ({
        action: f.getAttribute('action') || '',
        method: (f.getAttribute('method') || 'POST'),
        inputs: [...f.querySelectorAll('input,select,textarea')].map(i => ({
            name: i.getAttribute('name') || i.getAttribute('id') || '',
            type: (i.getAttribute('type') || i.tagName.toLowerCase())
        }))
    }))"""
    try:
        return page.evaluate(js) or []
    except Exception:
        return []


def _baca_links(page: Any) -> list[str]:
    try:
        return page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))") or []
    except Exception:
        return []


def _login_di_konteks(
    page: Any,
    context: Any,
    login_ctx: ScanContext,
    akun: AkunUji,
    base_url: str,
    log: Logger,
    pakai_ai_arbiter: bool = True,
) -> bool:
    """Login di dalam `page`/context yang sedang berjalan (agar sesi dipakai crawl).

    Konfirmasi keberhasilan memakai `playwright_driver.konfirmasi_login` (deterministik,
    berbasis bentuk-nilai token + probe terproteksi). Bila sinyal tak meyakinkan dan
    arbiter AI diaktifkan, minta AI memutus dari METADATA non-sensitif (tanpa nilai token).
    Return True bila kemungkinan terautentikasi.
    """
    halaman = login_ctx.url_titik("login_page") or login_ctx.url_titik("login")
    if not halaman or not akun.password:
        return False
    f = login_ctx.form.get("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"
    if not pw._goto(page, halaman):  # noqa: SLF001
        return False
    storage_sebelum = pw._baca_storage(page)  # noqa: SLF001  (baseline diff)
    pw._isi(page, pw._SEL_USER, field_user, akun.username)  # noqa: SLF001
    pw._isi(page, pw._SEL_PASS, field_pass, akun.password or "")  # noqa: SLF001
    pw._klik_submit(page)  # noqa: SLF001
    try:
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
    except Exception:
        pass
    # Langkah MFA/TOTP.
    if akun.totp_secret and pw._ada_field_otp(page):  # noqa: SLF001
        from . import mfa

        kode = mfa.kode_untuk_akun(akun)
        if kode and pw._isi_otp(page, kode):  # noqa: SLF001
            pw._klik_submit(page)  # noqa: SLF001
            try:
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)
            except Exception:
                pass

    konf = pw.konfirmasi_login(page, context, halaman, base_url, storage_sebelum)
    _log(log, "info", f"  • sinyal login: {', '.join(konf.get('sinyal') or []) or 'tidak ada'}")
    if konf["ok"]:
        return True

    # Arbiter AI (opsional) — hanya saat deterministik inconclusive; kirim METADATA saja.
    if pakai_ai_arbiter:
        from . import ai, deteksi_sesi

        meta = {
            "url_login": _path_aman(halaman),
            "url_akhir": _path_aman(_url_page(page)),
            "masih_ada_field_sandi": _ada_field_sandi(page),
            "storage_sebelum": deteksi_sesi.metadata_storage(storage_sebelum),
            "storage_sesudah": deteksi_sesi.metadata_storage(konf.get("storage") or {}),
            "sinyal_terdeteksi": konf.get("sinyal") or [],
        }
        putusan = ai.arbitrase_login(meta)
        if putusan is not None:
            _log(log, "info", f"  • arbiter AI ({putusan.get('provider')}): "
                              f"{'terautentikasi' if putusan.get('ok') else 'belum'} — {putusan.get('alasan', '')[:120]}")
            return bool(putusan.get("ok"))
    return False


# --------------------------------------------------------------------------- intersep aksi (tanpa kirim)

# Teks tombol aksi yang layak dipicu (simpan/hapus/unggah …). Logout dikecualikan agar sesi tetap.
_TEKS_AKSI = re.compile(
    r"simpan|save|kirim|submit|hapus|delete|remove|unggah|upload|ubah|update|edit|tambah|create|add|buat|setuju|approve|tolak|reject|proses",
    re.IGNORECASE,
)
_TEKS_HINDARI = re.compile(r"keluar|logout|log out|sign ?out", re.IGNORECASE)
_METODE_AMAN = ("GET", "HEAD", "OPTIONS")
MAKS_RUTE_INTERSEP = 10
MAKS_AKSI_PER_RUTE = 8
BATAS_DETIK_INTERSEP = 90.0

# Nilai dummy per tipe input — sengaja jelas palsu; request tak pernah sampai ke server.
_DUMMY = {
    "email": "uji@contoh.test",
    "number": "1",
    "tel": "081200000000",
    "url": "https://contoh.test",
    "date": "2026-01-01",
    "password": "Uji#Satya2026",
}


def _isi_form(form: Any) -> None:
    """Isi input sebuah form (locator) dengan nilai dummy; input file diberi berkas teks kecil."""
    try:
        jumlah = form.locator("input, textarea, select").count()
    except Exception:
        return
    for i in range(min(jumlah, 25)):
        el = form.locator("input, textarea, select").nth(i)
        try:
            if not el.is_visible() and (el.get_attribute("type") or "") != "file":
                continue
            tag = (el.evaluate("e => e.tagName") or "").lower()
            tipe = (el.get_attribute("type") or "text").lower()
            if tag == "select":
                opsi = el.locator("option").all()
                nilai = [o.get_attribute("value") for o in opsi if o.get_attribute("value")]
                if nilai:
                    el.select_option(nilai[-1], timeout=800)
            elif tipe in ("checkbox", "radio"):
                el.check(timeout=800)
            elif tipe == "file":
                el.set_input_files({"name": "uji-satya.txt", "mimeType": "text/plain", "buffer": b"uji satya"}, timeout=800)
            elif tipe in ("hidden", "submit", "button", "reset", "image"):
                continue
            else:
                el.fill(_DUMMY.get(tipe, "uji satya"), timeout=800)
        except Exception:
            continue


def intersep_aksi(page: Any, rute: list[str], log: Logger = None) -> list[dict[str, Any]]:
    """Picu form & tombol aksi pada rute yang sudah dirender, sambil MENYADAP lalu MEMBATALKAN
    setiap request non-GET (`route.abort()`) — server tak pernah menerima mutasi.

    Mengungkap endpoint backend non-GET (simpan/hapus/unggah) beserta nama field body & jenis
    body (JSON/multipart). Return list {method, url, content_type, fields, multipart}.
    """
    import time

    from . import endpoint_map as em

    tertangkap: dict[str, dict[str, Any]] = {}
    halaman = {"url": ""}  # rute yang sedang dipicu → `asal` tiap request tertangkap

    def _rute(route: Any, request: Any) -> None:
        try:
            if request.method.upper() in _METODE_AMAN:
                route.continue_()
                return
            ct = (request.headers or {}).get("content-type", "")
            try:
                body = request.post_data
            except Exception:
                body = None  # body biner (multipart berkas) tak bisa didekode → cukup tandai multipart
            fields = [] if "multipart" in ct else em.field_dari_body(body, ct)
            kunci = f"{request.method.upper()} {pr.tanpa_query(request.url)}"
            rec = tertangkap.setdefault(kunci, {
                "method": request.method.upper(), "url": request.url, "content_type": ct.split(";", 1)[0],
                "fields": [], "multipart": "multipart" in ct, "asal": halaman["url"],
            })
            ada = {f["nama"] for f in rec["fields"]}
            rec["fields"] += [{"nama": f["nama"], "lokasi": "body", **({"tipe": f["tipe"]} if f.get("tipe") else {})}
                              for f in fields if f["nama"] not in ada]
        except Exception:
            pass
        try:
            route.abort()
        except Exception:
            pass

    def _dialog(d: Any) -> None:
        try:
            d.accept()  # konfirmasi "yakin hapus?" → request tetap dibatalkan di _rute
        except Exception:
            pass

    mulai = time.monotonic()
    page.route("**/*", _rute)
    page.on("dialog", _dialog)
    aksi = 0
    try:
        from . import koordinasi

        for url in rute[:MAKS_RUTE_INTERSEP]:
            koordinasi.periksa_batal()
            if time.monotonic() - mulai > BATAS_DETIK_INTERSEP:
                break
            if not pw._goto(page, url):  # noqa: SLF001
                continue
            halaman["url"] = pr.tanpa_query(url)
            n_form = 0
            try:
                n_form = page.locator("form").count()
            except Exception:
                pass
            for i in range(min(n_form, MAKS_AKSI_PER_RUTE)):
                form = page.locator("form").nth(i)
                _isi_form(form)
                try:
                    tombol = form.locator("button[type=submit], input[type=submit], button:not([type])").first
                    if tombol.count():
                        tombol.click(timeout=1500, no_wait_after=True)
                    else:
                        form.evaluate("f => f.requestSubmit ? f.requestSubmit() : f.submit()")
                    aksi += 1
                    page.wait_for_timeout(700)
                except Exception:
                    pass
                if page.url.split("#")[0] != url.split("#")[0]:
                    pw._goto(page, url)  # noqa: SLF001
            # Tombol aksi di luar form (mis. "Hapus" pada baris tabel).
            try:
                tombol_lepas = page.locator("button:visible, [role=button]:visible").all()[:40]
            except Exception:
                tombol_lepas = []
            n = 0
            for b in tombol_lepas:
                if n >= MAKS_AKSI_PER_RUTE:
                    break
                try:
                    if b.evaluate("e => !!e.closest('form')"):
                        continue
                    teks = (b.inner_text(timeout=500) or "") + " " + (b.get_attribute("aria-label") or "")
                    if not _TEKS_AKSI.search(teks) or _TEKS_HINDARI.search(teks):
                        continue
                    b.click(timeout=1500, no_wait_after=True)
                    n += 1
                    aksi += 1
                    page.wait_for_timeout(600)
                except Exception:
                    continue
                if page.url.split("#")[0] != url.split("#")[0]:
                    pw._goto(page, url)  # noqa: SLF001
    finally:
        try:
            page.unroute("**/*", _rute)
        except Exception:
            pass
        try:
            page.remove_listener("dialog", _dialog)
        except Exception:
            pass
    hasil = list(tertangkap.values())
    _log(log, "info", f"Intersep aksi: {aksi} aksi dipicu, {len(hasil)} endpoint non-GET terungkap, 0 request dikirim ke server.")
    for r in hasil[:15]:
        _log(log, "info", f"  • {r['method']} {pr.tanpa_query(r['url'])}{' [multipart]' if r['multipart'] else ''}")
    return hasil


def petakan_titik_intersep(
    hasil: list[dict[str, Any]], form_titik: dict[str, str], catat: Callable[..., None]
) -> dict[str, dict[str, Any]]:
    """Form SPA tanpa action → endpoint non-GET yang benar-benar dipanggil saat form dipicu (intersep).

    Kandidat dari halaman yang sama; yang URL-nya terklasifikasi titik yang sama (mis. /api/users/login
    untuk login) → keyakinan tinggi; satu-satunya kandidat lain → sedang.
    Return {titik: rekaman intersep terpilih} — field body-nya jadi template form titik itu.
    """
    from . import discovery as D  # lazy: hindari impor melingkar

    terpilih: dict[str, dict[str, Any]] = {}
    for asal, titik in form_titik.items():
        kandidat = [r for r in hasil if r.get("asal") == asal and r.get("method", "GET").upper() not in _METODE_AMAN]
        cocok = [r for r in kandidat if D.klasifikasi_tautan(r["url"]) == titik]
        if cocok:
            r, yakin = cocok[0], "tinggi"
        elif len(kandidat) == 1:
            r, yakin = kandidat[0], "sedang"
        else:
            continue
        catat(titik, pr.tanpa_query(r["url"]), r["method"].upper(), yakin,
              f"Aksi form di {asal} memanggil {r['method'].upper()} {pr.tanpa_query(r['url'])} (intersep, tidak dikirim)")
        terpilih.setdefault(titik, r)
    return terpilih


def templat_bukti(
    titik: str, rec: dict[str, Any], forms_bukti: dict[str, dict[str, Any]], url_form: dict[str, str], fields: list[Any]
) -> None:
    """Template form dari field body request nyata (intersep/jaringan) → `forms_bukti[titik]`."""
    from . import discovery as D

    if titik in forms_bukti:
        return
    t = D.templat_dari_field(titik, fields, rec.get("content_type") or "")
    if t:
        forms_bukti[titik] = t
        url_form[titik] = f"{rec['method'].upper()} {pr.tanpa_query(rec['url'])}"


def _tanda_tangan(page: Any) -> Optional[str]:
    """Ringkasan isi halaman terender (judul + awal teks) untuk membedakan rute nyata dari 404 SPA."""
    try:
        return page.evaluate("() => document.title + '|' + ((document.body && document.body.innerText) || '').slice(0, 400)")
    except Exception:
        return None


def _url_page(page: Any) -> str:
    try:
        return page.url
    except Exception:
        return ""


def _path_aman(url: str) -> str:
    return (urlsplit(url).path or "/") if url else ""


# Status HTTP navigasi yang menandakan rute tidak ada (host statis/SPA tanpa catch-all).
_STATUS_TIDAK_ADA = (404, 410)


def _goto_status(page: Any, url: str) -> tuple[bool, Optional[int]]:
    """Navigasi best-effort seperti `pw._goto`, tetapi juga mengembalikan status HTTP dokumen.

    Status `None` bila navigasi tak menghasilkan respons (mis. perubahan hash/same-document).
    """
    for tunggu in ("networkidle", "load"):
        try:
            resp = page.goto(url, wait_until=tunggu)
        except Exception:
            continue
        try:
            return True, (resp.status if resp is not None else None)
        except Exception:
            return True, None
    return False, None


def _ada_field_sandi(page: Any) -> bool:
    try:
        return page.query_selector("input[type=password]") is not None
    except Exception:
        return False


def jelajah_browser(
    base_url: str,
    catat: Callable[..., None],
    log: Logger = None,
    *,
    login_ctx: Optional[ScanContext] = None,
    akun: Optional[AkunUji] = None,
    timeout: float = 15.0,
    maks_rute: int = 30,
    pakai_ai_arbiter: bool = True,
    intersep: bool = False,
) -> dict[str, Any]:
    """Render SPA (opsional login), jelajah rute, sadap XHR/fetch → titik uji + inventaris endpoint.

    `catat(titik, url, metode_http, keyakinan, catatan)` sama seperti di `discovery.temukan`.
    Bila `login_ctx`+`akun` diberikan, worker login dulu lalu crawl terautentikasi.
    `intersep=True` menjalankan `intersep_aksi` pada rute terender (endpoint non-GET tanpa kirim).
    Rute yang benar-benar ada dipancarkan sebagai peristiwa `halaman` (sumber "browser").
    """
    if not pw.tersedia():
        _log(log, "info", "Playwright tak tersedia — lewati penemuan browser (SPA).")
        return {"tersedia": False}

    from . import discovery as D  # lazy: hindari impor melingkar
    from . import endpoint_map as em

    ctx = login_ctx or ScanContext.from_dict({"scan_id": "", "aplikasi_id": "", "base_url": base_url})
    host0 = _host(base_url)
    dasar = base_url.rstrip("/") + "/"

    endpoints: dict[str, str] = {}
    rute_terkunjungi: list[str] = []
    request_detail: list[dict[str, Any]] = []   # {method,url,post_data,content_type,status,terautentikasi}
    urutan: list[dict[str, str]] = []            # urutan XHR/fetch untuk pemetaan alur
    status_map: dict[str, int] = {}
    terautentikasi = False
    cookie_header = ""
    skrip: list[str] = []                        # URL berkas JS yang dimuat (untuk analisis bundle)
    rute_info: list[dict[str, Any]] = []         # {url, asal: tautan|tebakan, sig}
    hasil_intersep: list[dict[str, Any]] = []
    status_intersep = {"aktif": False}
    form_titik: dict[str, str] = {}              # halaman → titik uji form tanpa action (SPA)
    forms_render: dict[str, dict[str, Any]] = {}  # template dari form terender (nama input)
    forms_bukti: dict[str, dict[str, Any]] = {}   # template dari body request nyata (intersep/jaringan)
    url_form: dict[str, str] = {}                 # titik → "METODE url" asal template bukti

    def _norm_endpoint(method: str, url: str) -> str:
        s = urlsplit(url)
        return f"{method.upper()} {s.scheme}://{s.netloc}{s.path}"

    try:
        with pw.buka_konteks(ctx) as (context, page):
            def _on_req(req: Any) -> None:
                try:
                    if status_intersep["aktif"]:
                        return  # request saat intersep dicatat terpisah (dan dibatalkan)
                    if req.resource_type == "script":
                        skrip.append(req.url)
                        return
                    if req.resource_type not in ("xhr", "fetch"):
                        return
                    post = None
                    try:
                        post = req.post_data
                    except Exception:
                        post = None
                    ct = ""
                    try:
                        ct = req.headers.get("content-type", "")
                    except Exception:
                        ct = ""
                    rec = {
                        "method": req.method,
                        "url": req.url,
                        "post_data": post,
                        "content_type": ct,
                        "terautentikasi": terautentikasi,
                    }
                    request_detail.append(rec)
                    urutan.append({"method": req.method, "url": req.url})
                except Exception:
                    pass

            def _on_resp(resp: Any) -> None:
                try:
                    if resp.request.resource_type in ("xhr", "fetch"):
                        status_map[f"{resp.request.method} {resp.url}"] = resp.status
                except Exception:
                    pass

            page.on("request", _on_req)
            page.on("response", _on_resp)

            # (opsional) Login lebih dulu agar crawl berjalan terautentikasi.
            rute_awal = list(_RUTE_UMUM)
            if login_ctx is not None and akun is not None and akun.password:
                pr.tahap(log, "login", "Mencoba login untuk crawl terautentikasi…", akun=akun.kunci)
                terautentikasi = _login_di_konteks(
                    page, context, login_ctx, akun, base_url, log, pakai_ai_arbiter=pakai_ai_arbiter
                )
                if terautentikasi:
                    pr.pancar(
                        log, f"Login berhasil (akun '{akun.kunci}') — menjelajah area terautentikasi.",
                        {"jenis": "sesi", "berhasil": True, "akun": akun.kunci},
                    )
                    rute_awal = list(dict.fromkeys(list(_RUTE_AUTH) + list(_RUTE_UMUM)))
                else:
                    pr.pancar(
                        log, "Login tak terkonfirmasi — crawl lanjut sebagai anonim.",
                        {"jenis": "sesi", "berhasil": False, "akun": akun.kunci}, level="peringatan",
                    )

            antre: list[str] = [urljoin(dasar, p.lstrip("/")) for p in rute_awal]
            dikunjungi: set[str] = set()
            dari_tautan: set[str] = {dasar, base_url}
            ambil_link = True
            # Tanda tangan halaman "tidak ditemukan" SPA: rute tebakan yang merender halaman
            # identik dianggap tidak ada (SPA biasanya mengembalikan index.html untuk semua path).
            # Jeda render disamakan dgn rute biasa agar komponen "not found" SPA sempat tampil.
            sig404 = None
            ok404, _ = _goto_status(page, urljoin(dasar, "__satya_cek_404__"))
            if ok404:
                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    pass
                sig404 = _tanda_tangan(page)

            from . import koordinasi

            while antre and len(rute_terkunjungi) < maks_rute:
                koordinasi.periksa_batal()
                url = antre.pop(0)
                if url in dikunjungi:
                    continue
                dikunjungi.add(url)
                if _host(url) != host0:
                    continue
                ok, status_nav = _goto_status(page, url)
                if not ok:
                    continue
                if status_nav in _STATUS_TIDAK_ADA:
                    # Server menyatakan rute tak ada (mis. Netlify/host statis "Page not found") —
                    # bukan rute frontend; jangan dihitung, jangan diproses form/tautannya.
                    _log(log, "info", f"Browser: lewati {_path_aman(url)} (HTTP {status_nav}).")
                    continue
                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    pass
                rute_terkunjungi.append(url)
                rute_info.append({"url": pr.tanpa_query(_url_page(page) or url), "asal": "tautan" if url in dari_tautan else "tebakan",
                                  "sig": _tanda_tangan(page), "status": status_nav or 200})

                forms = _baca_forms(page)
                for frm in forms:
                    fd = D.FormDitemukan(action=frm.get("action", ""), method=(frm.get("method") or "POST"), inputs=frm.get("inputs", []))
                    hasil = D.klasifikasi_form(fd, url)
                    if not hasil:
                        continue
                    titik, templat = hasil
                    forms_render.setdefault(titik, templat)
                    action_url = D._normalisasi(url, frm.get("action", "")) or url
                    # Form tanpa action (khas SPA) dikirim lewat JS ke endpoint API lain; URL halaman
                    # hanya dugaan lemah — digantikan endpoint hasil intersep/lalu lintas jaringan.
                    spa = not (frm.get("action") or "").strip() or pr.tanpa_query(action_url) == pr.tanpa_query(url)
                    if spa:
                        form_titik.setdefault(pr.tanpa_query(url), titik)
                    catat(titik, action_url, (frm.get("method") or "POST").upper(), "rendah" if spa else "tinggi",
                          f"Form terender di {url}" + (" (tanpa action — endpoint API belum terkonfirmasi)" if spa else ""))
                    if titik == "login":
                        catat("login_page", url, "GET", "tinggi", "Halaman login terender (SPA).")

                if not forms:
                    try:
                        if page.query_selector("input[type=password]"):
                            catat("login_page", url, "GET", "sedang", "Input sandi terender tanpa <form> (SPA).")
                    except Exception:
                        pass

                # Antre-kan tautan internal relevan (pada render pertama & rute terautentikasi).
                if ambil_link or terautentikasi:
                    ambil_link = False
                    for href in _baca_links(page):
                        absu = D._normalisasi(url, href or "") or (href or "")
                        if not absu or _host(absu) != host0 or absu in dikunjungi:
                            continue
                        # Saat terautentikasi, ikuti semua tautan in-host; anonim → hanya yang terklasifikasi.
                        if terautentikasi or D.klasifikasi_tautan(absu):
                            if len(dikunjungi) + len(antre) < maks_rute * 3:
                                antre.append(absu)
                                dari_tautan.add(absu)

            # Rute nyata → peristiwa `halaman` (lapisan frontend).
            rute_nyata: dict[str, dict[str, Any]] = {}
            # Tanda tangan beranda: SPA dgn rewrite catch-all (`/* → /index.html 200`) tanpa
            # komponen "not found" merender beranda untuk path apa pun → bukan rute tersendiri.
            sig_beranda = next((r["sig"] for r in rute_info if _path_aman(r["url"]) == _path_aman(dasar)), None)
            for r in rute_info:
                if r["asal"] == "tebakan" and r["sig"] is not None:
                    if r["sig"] == sig404:
                        continue
                    if sig_beranda is not None and r["sig"] == sig_beranda and _path_aman(r["url"]) != _path_aman(dasar):
                        continue
                rute_nyata.setdefault(r["url"], r)
            if rute_nyata:
                pr.pancar(
                    log, f"Browser: {len(rute_nyata)} rute frontend terender.",
                    {"jenis": "halaman", "items": [{"url": u, "status": r.get("status") or 200, "judul": "", "sumber": "browser"}
                                                for u, r in list(rute_nyata.items())[:60]]},
                )

            # Intersep aksi form/tombol (request non-GET dibatalkan) — untuk backend tanpa dokumentasi.
            if intersep and rute_nyata:
                pr.tahap(log, "intersep", "Intersep aksi form & tombol (request mutasi dibatalkan, tidak dikirim)…")
                status_intersep["aktif"] = True
                try:
                    hasil_intersep = intersep_aksi(page, list(rute_nyata), log)
                finally:
                    status_intersep["aktif"] = False
                for t, rec in petakan_titik_intersep(hasil_intersep, form_titik, catat).items():
                    templat_bukti(t, rec, forms_bukti, url_form, list(rec.get("fields") or []))

            # Klasifikasi endpoint dari lalu lintas jaringan (XHR/fetch) = endpoint API sebenarnya.
            for rec in request_detail:
                method, u = rec["method"], rec["url"]
                endpoints[_norm_endpoint(method, u)] = u
                rec["status"] = status_map.get(f"{method} {u}")
                titik = D.klasifikasi_tautan(u)
                if titik in ("login", "registrasi", "reset_password", "logout", "area_terautentikasi"):
                    catat(titik, u, method.upper(), "sedang", "Terpantau dari lalu lintas SPA (jaringan).")
                    if method.upper() not in _METODE_AMAN and rec.get("post_data"):
                        # Hanya NAMA field yang dipakai (body login nyata memuat sandi akun uji).
                        templat_bukti(titik, rec, forms_bukti, url_form,
                                      em.field_dari_body(rec.get("post_data"), rec.get("content_type", "")))

            # Cookie sesi (untuk crawl katana terautentikasi) bila login berhasil.
            if terautentikasi:
                try:
                    ck = context.cookies()
                    cookie_header = "; ".join(f"{c.get('name')}={c.get('value')}" for c in ck if c.get("name"))
                except Exception:
                    cookie_header = ""
    except pw.PlaywrightTidakTersedia as e:
        _log(log, "peringatan", f"Browser tak bisa diluncurkan: {e}")
        return {"tersedia": False, "alasan": str(e)}
    except Exception as e:  # best-effort: jangan jatuhkan penemuan
        _log(log, "peringatan", f"Penemuan browser gagal sebagian: {type(e).__name__}: {e}")

    inv = sorted(endpoints.keys())
    _log(log, "info", f"Browser (SPA): {len(rute_terkunjungi)} rute dirender, {len(inv)} endpoint API terpantau"
                      f"{' (terautentikasi)' if terautentikasi else ''}.")
    for e in inv[:15]:
        _log(log, "info", f"  • endpoint API: {e}")
    return {
        "tersedia": True,
        "terautentikasi": terautentikasi,
        "rute": rute_terkunjungi,
        "endpoints": inv,
        "jumlah_endpoint": len(inv),
        "request_detail": request_detail,
        "urutan": urutan,
        "cookie_header": cookie_header,
        "skrip": list(dict.fromkeys(skrip)),
        "intersep": hasil_intersep,
        "forms_bukti": forms_bukti,
        "forms_render": forms_render,
        "url_form": url_form,
    }
