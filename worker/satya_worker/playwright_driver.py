"""Driver Playwright — fondasi engine `playwright` DAN fallback browser untuk check custom.

Berbeda dari ZAP (daemon REST) & nuclei (biner CLI): Playwright adalah **library Python**
yang dipakai worker **in-proses**. Modul ini meng-impor playwright secara **lazy** (di dalam
fungsi) agar paket `satya_worker` tetap bisa diimpor walau Playwright belum terpasang —
fallback lalu non-aktif dengan anggun (pola sama seperti `zap_client`).

Konfigurasi via env:
    PLAYWRIGHT_HEADLESS        '0'/'false' untuk tampak (default headless/true)
    PLAYWRIGHT_NAV_TIMEOUT_MS  batas navigasi/aksi (default 15000)
    PLAYWRIGHT_BROWSER         chromium|firefox|webkit (default chromium)

Ruang lingkup: navigasi hanya ke host aset (lihat `sesi.hosts_target`). Sub-sumber yang
dirujuk aplikasi (skrip/CDN pihak ketiga) sengaja dibiarkan termuat — itu memang data yang
diuji (mis. `deps.unknown_third_party_scripts`), bukan worker memindai host lain.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional
from urllib.parse import urlsplit

from . import deteksi_sesi
from .models import AkunUji, ScanContext
from .sesi import _COOKIE_SESI, hosts_target

# Kandidat endpoint "profil saya" untuk probe ground-truth pasca-login.
_KANDIDAT_ME = (
    "/api/v1/auth/me", "/api/auth/me", "/api/v1/users/me", "/api/users/me",
    "/api/me", "/auth/me", "/me", "/api/v1/profile", "/api/profile",
)


class PlaywrightTidakTersedia(Exception):
    """Playwright belum terpasang atau browser engine belum diunduh."""


def _headless() -> bool:
    return os.environ.get("PLAYWRIGHT_HEADLESS", "true").strip().lower() not in ("0", "false", "no")


def _nav_timeout() -> float:
    return float(os.environ.get("PLAYWRIGHT_NAV_TIMEOUT_MS", "15000"))


def _nama_browser() -> str:
    return os.environ.get("PLAYWRIGHT_BROWSER", "chromium").strip().lower() or "chromium"


def tersedia() -> bool:
    """True bila modul playwright bisa diimpor (ketersediaan browser dicek saat launch)."""
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        return False
    return True


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


# --------------------------------------------------------------------------- context

@contextmanager
def buka_konteks(ctx: ScanContext) -> Iterator[tuple[Any, Any]]:
    """Context manager → (browser_context, page). Lempar PlaywrightTidakTersedia bila gagal.

    Pemanggil bertanggung jawab hanya menavigasi ke host aset; `_jaga` tersedia untuk cek.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # modul belum terpasang
        raise PlaywrightTidakTersedia(f"Modul playwright tak tersedia: {e}") from e

    pw = None
    browser = None
    try:
        try:
            pw = sync_playwright().start()
            tipe = getattr(pw, _nama_browser(), pw.chromium)
            browser = tipe.launch(headless=_headless())
        except Exception as e:  # browser engine belum diunduh, dll.
            raise PlaywrightTidakTersedia(
                f"Gagal meluncurkan browser (coba `python -m playwright install {_nama_browser()}`): {e}"
            ) from e
        # Service worker diblokir: SW PWA (mis. Workbox `navigateFallback`) menyajikan index.html
        # dari cache untuk SEMUA path → rute tebakan (/admin, /beranda…) tampak 200 padahal server
        # membalas 404, dan respons XHR bisa berasal dari cache bukan server. Pemindai harus
        # melihat respons server yang sebenarnya.
        context = browser.new_context(ignore_https_errors=False, service_workers="block")
        context.set_default_navigation_timeout(_nav_timeout())
        context.set_default_timeout(_nav_timeout())
        page = context.new_page()
        yield context, page
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:
            pass


def dalam_lingkup(ctx: ScanContext, url: str) -> bool:
    izin = hosts_target(ctx)
    h = _host(url)
    return bool(h) and (not izin or h in izin)


def _goto(page: Any, url: str) -> bool:
    """Navigasi best-effort; True bila halaman termuat."""
    for tunggu in ("networkidle", "load"):
        try:
            page.goto(url, wait_until=tunggu)
            return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------- instrumentasi (skrip + izin)

# Init-script: bungkus API izin perangkat agar panggilan saat load terekam ke window.__satya_izin.
_INIT_IZIN = """
window.__satya_izin = [];
(function () {
  try {
    var rec = function (n) { try { window.__satya_izin.push(n); } catch (e) {} };
    try {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition = function () { rec('geolocation'); };
        navigator.geolocation.watchPosition = function () { rec('geolocation'); return 0; };
      }
    } catch (e) {}
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia = function () { rec('camera_microphone'); return new Promise(function () {}); };
      }
    } catch (e) {}
    try {
      if (window.Notification && Notification.requestPermission) {
        Notification.requestPermission = function () { rec('notifications'); return Promise.resolve('default'); };
      }
    } catch (e) {}
    try {
      if (navigator.permissions && navigator.permissions.query) {
        var orig = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function (d) { try { rec('permissions.query:' + (d && d.name)); } catch (e) {} return orig(d); };
      }
    } catch (e) {}
  } catch (e) {}
})();
"""


def muat_terinstrumentasi(page: Any, url: str) -> dict:
    """Muat `url` sekali sambil merekam: daftar URL skrip (DOM + jaringan) dan panggilan izin.

    Return { scripts: list[str], izin: list[str], ok: bool }.
    """
    skrip_net: list[str] = []
    try:
        page.add_init_script(_INIT_IZIN)
    except Exception:
        pass

    def _on_request(req: Any) -> None:
        try:
            if req.resource_type == "script":
                skrip_net.append(req.url)
        except Exception:
            pass

    try:
        page.on("request", _on_request)
    except Exception:
        pass

    ok = _goto(page, url)
    try:
        page.wait_for_timeout(1500)  # beri waktu SPA merender/menembak izin
    except Exception:
        pass

    skrip_dom: list[str] = []
    try:
        skrip_dom = page.eval_on_selector_all("script[src]", "els => els.map(e => e.src)") or []
    except Exception:
        pass

    izin: list[str] = []
    try:
        izin = page.evaluate("window.__satya_izin || []") or []
    except Exception:
        pass

    skrip = list(dict.fromkeys([s for s in (skrip_net + skrip_dom) if s]))
    return {"scripts": skrip, "izin": list(dict.fromkeys(izin)), "ok": ok}


# --------------------------------------------------------------------------- login browser (fallback + auth)

_SEL_USER = [
    'input[name="{n}"]',
    'input#{n}',
    'input[type="email"]',
    'input[type="text"]:not([type="hidden"])',
]
_SEL_PASS = ['input[name="{n}"]', 'input#{n}', 'input[type="password"]']
_SEL_SUBMIT = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Login")',
    'button:has-text("Masuk")',
    'button:has-text("Sign in")',
    'button:has-text("Sign In")',
    'button:has-text("Verify")',
    'button:has-text("Verifikasi")',
]

# Field OTP/MFA (kode satu kali) yang lazim pada langkah kedua login.
_SEL_OTP = [
    'input[autocomplete="one-time-code"]',
    'input[name*="otp" i]',
    'input[name*="code" i]',
    'input[name*="token" i]',
    'input[name*="mfa" i]',
    'input[name*="2fa" i]',
    'input[inputmode="numeric"]',
]


def _ada_field_otp(page: Any) -> bool:
    for sel in _SEL_OTP:
        try:
            if page.query_selector(sel) is not None:
                return True
        except Exception:
            continue
    return False


def _isi_otp(page: Any, kode: str) -> bool:
    """Isi field OTP. Dukungan pola 'satu kotak per digit' (isi berurutan)."""
    try:
        kotak = page.query_selector_all('input[inputmode="numeric"], input[autocomplete="one-time-code"]')
    except Exception:
        kotak = []
    if kotak and len(kotak) >= len(kode):
        ok = False
        for el, digit in zip(kotak, kode):
            try:
                el.fill(digit)
                ok = True
            except Exception:
                pass
        if ok:
            return True
    # Satu field tunggal.
    for sel in _SEL_OTP:
        try:
            el = page.query_selector(sel)
            if el is not None:
                el.fill(kode)
                return True
        except Exception:
            continue
    return False


def _isi(page: Any, selektor: list[str], nama: str, nilai: str) -> bool:
    for pola in selektor:
        sel = pola.format(n=nama)
        try:
            el = page.query_selector(sel)
            if el is not None:
                el.fill(nilai)
                return True
        except Exception:
            continue
    return False


def _klik_submit(page: Any) -> None:
    for sel in _SEL_SUBMIT:
        try:
            el = page.query_selector(sel)
            if el is not None:
                el.click()
                return
        except Exception:
            continue
    # fallback: tekan Enter pada field sandi
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass


def _baca_storage(page: Any) -> dict:
    out: dict[str, dict] = {"localStorage": {}, "sessionStorage": {}}
    for nama in ("localStorage", "sessionStorage"):
        try:
            out[nama] = page.evaluate(
                "(s) => { const o = {}; const st = window[s]; "
                "for (let i = 0; i < st.length; i++) { const k = st.key(i); o[k] = st.getItem(k); } return o; }",
                nama,
            ) or {}
        except Exception:
            out[nama] = {}
    return out


def _cari_token_storage(storage: dict) -> Optional[str]:
    """Token dari storage berdasarkan BENTUK-NILAI (JWT/UUID/opaque), lepas dari nama key.

    Menggantikan pencocokan substring nama key yang rapuh — mendeteksi token meski
    key-nya diberi prefiks aplikasi (mis. `cuti.session`)."""
    return deteksi_sesi.cari_token_nilai(storage)


def _path_login(url: str) -> str:
    return (urlsplit(url).path or "/").rstrip("/").lower()


def _masih_di_login(page: Any, login_url: str) -> bool:
    """True bila halaman masih menampilkan form login (URL rute login dan/atau field sandi)."""
    try:
        sekarang = _path_login(page.url)
    except Exception:
        sekarang = ""
    path_login = _path_login(login_url)
    di_rute_login = bool(path_login) and sekarang == path_login
    ada_sandi = False
    try:
        ada_sandi = page.query_selector("input[type=password]") is not None
    except Exception:
        ada_sandi = False
    return di_rute_login and ada_sandi


def _probe_terproteksi(page: Any, base_url: str, token: Optional[str]) -> Optional[int]:
    """Probe ground-truth: panggil endpoint 'me' dari dalam konteks terautentikasi.

    Cookie otomatis ikut; bila auth berbasis header & `token` terdeteksi, coba juga
    dengan Authorization: Bearer. Return status 2xx pertama yang ditemui, atau None.
    """
    js = """
    async ([bases, token]) => {
      const hdrs = token ? [{}, {Authorization: 'Bearer ' + token}, {'x-access-token': token}] : [{}];
      for (const path of bases) {
        for (const h of hdrs) {
          try {
            const r = await fetch(path, {headers: h, credentials: 'include'});
            if (r.status >= 200 && r.status < 300) return r.status;
          } catch (e) {}
        }
      }
      return 0;
    }
    """
    try:
        status = page.evaluate(js, [list(_KANDIDAT_ME), token or ""])
        return int(status) if status else None
    except Exception:
        return None


def konfirmasi_login(
    page: Any,
    context: Any,
    login_url: str,
    base_url: str,
    storage_sebelum: dict,
) -> dict:
    """Konfirmasi login berlapis & deterministik (tanpa bergantung nama key token).

    Sinyal:
      A. navigasi lepas dari halaman login (tak lagi menampilkan form sandi);
      B. token baru berbentuk JWT/UUID/opaque di storage (diff) → sekaligus Bearer;
      C. cookie sesi/HttpOnly baru;
      D. probe endpoint terproteksi ('me') balas 2xx (kebenaran-sejati).
    `ok = D or B or C or (A kuat)`.
    Return { ok, token, cookie, cookies, storage, sinyal: [...] }.
    """
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    storage = _baca_storage(page)

    sinyal: list[str] = []
    token = deteksi_sesi.token_baru(storage_sebelum, storage) or deteksi_sesi.cari_token_nilai(storage)
    if token:
        sinyal.append("token_storage")
    cookie = _artefak_cookie(cookies)
    if cookie:
        sinyal.append("cookie_sesi")
    lepas_login = not _masih_di_login(page, login_url)
    if lepas_login:
        sinyal.append("lepas_halaman_login")

    status_me = _probe_terproteksi(page, base_url, token)
    if status_me:
        sinyal.append(f"probe_me_{status_me}")

    ok = bool(status_me or token or cookie or lepas_login)
    return {
        "ok": ok, "token": token, "cookie": cookie, "cookies": cookies,
        "storage": storage, "sinyal": sinyal,
    }


def _artefak_cookie(cookies: list[dict]) -> Optional[dict]:
    """Pilih cookie sesi dari context.cookies() dan susun {name,value,flags} seperti sesi.ekstrak_sesi.

    Flag Secure/HttpOnly andal dari Playwright; SameSite = nilai efektif (Lax default aman).
    """
    kandidat = None
    for c in cookies:
        nama = c.get("name", "")
        is_sesi = bool(_COOKIE_SESI.match(nama))
        if not is_sesi and not c.get("httpOnly"):
            continue
        flags = []
        if c.get("secure"):
            flags.append("secure")
        if c.get("httpOnly"):
            flags.append("httponly")
        if str(c.get("sameSite", "")).lower() in ("strict", "lax", "none"):
            flags.append("samesite")
        entri = {"name": nama, "value": c.get("value", ""), "flags": " ".join(flags)}
        if is_sesi:
            return entri  # cocok pola sesi → prioritas
        if kandidat is None:
            kandidat = entri
    return kandidat


def login_browser(ctx: ScanContext, akun: AkunUji) -> dict:
    """Login lewat browser nyata (untuk form yang digerakkan JS/SPA).

    Return { ok, token, cookie, storage, cookies }:
      - cookie  : artefak {name,value,flags} seperti sesi.ekstrak_sesi (untuk cookie_flags)
      - cookies : daftar mentah context.cookies() (untuk disuntik ke klien httpx)
      - storage : {localStorage, sessionStorage}
    Lempar PlaywrightTidakTersedia bila browser tak bisa diluncurkan.
    """
    kosong = {"ok": False, "token": None, "cookie": None, "storage": {}, "cookies": []}
    halaman = ctx.url_titik("login_page") or ctx.url_titik("login")
    if halaman is None or not akun.password:
        return kosong
    if not dalam_lingkup(ctx, halaman):
        return kosong

    f = ctx.form_untuk("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"

    with buka_konteks(ctx) as (context, page):
        if not _goto(page, halaman):
            return kosong
        storage_sebelum = _baca_storage(page)  # baseline untuk diff token
        _isi(page, _SEL_USER, field_user, akun.username)
        _isi(page, _SEL_PASS, field_pass, akun.password)
        _klik_submit(page)
        try:
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass

        # Langkah MFA/TOTP: bila halaman meminta kode OTP dan akun punya totp_secret.
        if akun.totp_secret and _ada_field_otp(page):
            from . import mfa  # lazy

            kode = mfa.kode_untuk_akun(akun)
            if kode and _isi_otp(page, kode):
                _klik_submit(page)
                try:
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass
                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

        konf = konfirmasi_login(page, context, halaman, ctx.base_url, storage_sebelum)

    return {
        "ok": konf["ok"], "token": konf["token"], "cookie": konf["cookie"],
        "storage": konf["storage"], "cookies": konf["cookies"], "sinyal": konf["sinyal"],
    }


# --------------------------------------------------------------------------- logout (alur UI nyata)

def _is_logout_url(url: str) -> bool:
    u = (url or "").lower()
    return any(k in u for k in ("logout", "signout", "sign-out", "sign_out", "keluar"))


# Pemicu menu pengguna (avatar/dropdown pojok) agar item logout muncul sebelum diklik.
_MENU_TRIGGER = """
() => {
  const sel = '[aria-haspopup], header button, nav button, [class*=avatar i], [class*=dropdown i] button, [class*=profile i] button, button[id*=menu i]';
  const c = Array.from(document.querySelectorAll(sel)).slice(0, 10);
  let n = 0;
  for (const e of c) { try { e.click(); n++; } catch (_) {} }
  return n;
}
"""

_SEL_LOGOUT = [
    'a[href*="logout" i]', '[aria-label*="logout" i]', '[aria-label*="keluar" i]',
    'text=/log ?out/i', 'text=/sign ?out/i', 'text=/keluar/i', 'text=/logout/i',
]


def _picu_logout(page: Any) -> bool:
    """Temukan & klik kontrol logout (buka menu pengguna dulu bila perlu). True bila terklik."""
    def _klik() -> bool:
        for sel in _SEL_LOGOUT:
            try:
                el = page.query_selector(sel)
                if el is not None:
                    el.click()
                    return True
            except Exception:
                continue
        return False

    if _klik():
        return True
    # Tak terlihat → buka kandidat menu pengguna lalu coba lagi.
    try:
        page.evaluate(_MENU_TRIGGER)
        page.wait_for_timeout(900)
    except Exception:
        pass
    return _klik()


def logout_flow(ctx: ScanContext, akun: AkunUji) -> dict:
    """Jalankan alur LOGOUT seperti pengguna sungguhan di browser, lalu uji apakah token
    sesi LAMA masih berlaku — menangkap logout yang hanya membersihkan sisi-klien sementara
    sesi tetap hidup di server (yang tak terlihat oleh uji endpoint logout langsung).

    Return { login_ok, token_ada, logout_terpicu, logout_request, token_hapus_klien,
             status_token_lama }. Lempar PlaywrightTidakTersedia bila browser tak bisa diluncurkan.
    """
    hasil = {"login_ok": False, "token_ada": False, "logout_terpicu": False,
             "logout_request": False, "token_hapus_klien": None, "status_token_lama": None}
    halaman = ctx.url_titik("login_page") or ctx.url_titik("login")
    if halaman is None or not akun.password or not dalam_lingkup(ctx, halaman):
        return hasil

    f = ctx.form_untuk("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"
    reqs: list[str] = []

    with buka_konteks(ctx) as (context, page):
        try:
            page.on("request", lambda r: reqs.append(r.url) if _is_logout_url(r.url) else None)
        except Exception:
            pass
        if not _goto(page, halaman):
            return hasil
        storage0 = _baca_storage(page)
        _isi(page, _SEL_USER, field_user, akun.username)
        _isi(page, _SEL_PASS, field_pass, akun.password)
        _klik_submit(page)
        for _ in range(1):
            try:
                page.wait_for_load_state("networkidle")
            except Exception:
                pass
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
        if akun.totp_secret and _ada_field_otp(page):
            from . import mfa  # lazy
            kode = mfa.kode_untuk_akun(akun)
            if kode and _isi_otp(page, kode):
                _klik_submit(page)
                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

        storage1 = _baca_storage(page)
        token = deteksi_sesi.token_baru(storage0, storage1) or deteksi_sesi.cari_token_nilai(storage1)
        hasil["token_ada"] = bool(token)
        hasil["login_ok"] = bool(token) or bool(_probe_terproteksi(page, ctx.base_url, token))
        if not token:
            return hasil

        hasil["logout_terpicu"] = _picu_logout(page)
        try:
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
        try:
            page.wait_for_timeout(2000)
        except Exception:
            pass

        storage2 = _baca_storage(page)
        hasil["token_hapus_klien"] = deteksi_sesi.cari_token_nilai(storage2) is None
        hasil["logout_request"] = any(_is_logout_url(u) for u in reqs)

        # Uji ulang token LAMA beberapa kali (kurangi flaky; 2xx mana pun = masih berlaku).
        status = None
        for _ in range(3):
            status = _probe_terproteksi(page, ctx.base_url, token)
            if status:
                break
            try:
                page.wait_for_timeout(600)
            except Exception:
                pass
        hasil["status_token_lama"] = status
    return hasil


# --------------------------------------------------------------------------- form reset kata sandi

def _isi_semua_sandi(page: Any, nilai: str) -> int:
    """Isi SEMUA input[type=password] (kata sandi baru + konfirmasi) dengan `nilai`. Return jumlah."""
    try:
        els = page.query_selector_all("input[type=password]")
    except Exception:
        return 0
    n = 0
    for el in els:
        try:
            el.fill(nilai)
            n += 1
        except Exception:
            pass
    return n


def submit_reset(ctx: ScanContext, url: str, sandi_baru: str) -> dict:
    """Buka halaman reset di browser, isi semua field sandi dengan `sandi_baru`, submit.

    Return { ok, url_awal, url_akhir, teks, jumlah_field }. `ok` = halaman termuat & ada field sandi.
    Lempar PlaywrightTidakTersedia bila browser tak bisa diluncurkan.
    """
    kosong = {"ok": False, "url_awal": url, "url_akhir": "", "teks": "", "jumlah_field": 0}
    if not dalam_lingkup(ctx, url):
        return kosong
    with buka_konteks(ctx) as (context, page):
        if not _goto(page, url):
            return kosong
        n = _isi_semua_sandi(page, sandi_baru)
        if n == 0:
            # mungkin SPA butuh waktu merender form
            try:
                page.wait_for_timeout(1500)
            except Exception:
                pass
            n = _isi_semua_sandi(page, sandi_baru)
        _klik_submit(page)
        try:
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass
        teks = ""
        try:
            teks = page.inner_text("body")
        except Exception:
            try:
                teks = page.content()
            except Exception:
                teks = ""
        url_akhir = ""
        try:
            url_akhir = page.url
        except Exception:
            pass
    return {"ok": n > 0, "url_awal": url, "url_akhir": url_akhir, "teks": teks, "jumlah_field": n}
