"""Sesi login untuk check yang butuh autentikasi (1.3-T04, 1.4-T01, 1.6-T01).

login() memakai form 'login' + akun uji: menyimpan cookie (httpx.Client) dan, bila respons
JSON memuat token (accessToken/token/access_token), memasang header Authorization: Bearer.
Mendukung aplikasi berbasis cookie maupun token (mis. SATYA).
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlsplit

from .http_client import KlienScan
from .models import AkunUji, ScanContext

_KUNCI_TOKEN = ("accessToken", "token", "access_token", "jwt", "idToken")

# Sinyal bahwa langkah MFA/OTP diperlukan sebelum sesi penuh terbit.
_MFA_SINYAL = re.compile(
    r"(mfa|otp|two[\s_-]?factor|2fa|one[\s_-]?time|verifikasi|verification|challenge)",
    re.IGNORECASE,
)


def _butuh_otp(resp) -> bool:
    """Deteksi (best-effort) bahwa respons login meminta kode OTP/MFA.

    Memeriksa body JSON (kunci/nilai) atau teks respons untuk sinyal MFA tanpa
    adanya token sesi. Dipakai untuk memutuskan fallback login via browser (yang
    menyelesaikan langkah TOTP secara visual).
    """
    try:
        data = resp.json()
    except Exception:
        data = None
    if isinstance(data, dict):
        # Token sudah terbit → tak perlu OTP.
        if _cari_token(data):
            return False
        gabung = " ".join(f"{k} {v}" for k, v in data.items() if isinstance(v, (str, bool, int)))
        if _MFA_SINYAL.search(gabung):
            return True
    try:
        if resp.status_code in (401, 428) and _MFA_SINYAL.search(resp.text or ""):
            return True
    except Exception:
        pass
    return False

# Nama cookie sesi yang dikenal (pola pengendali sesi kerangka kerja).
_COOKIE_SESI = re.compile(
    r"^(jsessionid|phpsessid|asp\.net_sessionid|connect\.sid|laravel_session|"
    r"sessionid|_session_id|session|sid|express:sess|ci_session|symfony|rack\.session)$",
    re.IGNORECASE,
)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def hosts_target(ctx: ScanContext) -> set[str]:
    """Semua host yang boleh dihubungi worker: base_url + setiap URL titik uji terkonfigurasi."""
    hosts = {_host(ctx.base_url)}
    for t in ctx.titik_uji.values():
        if t.url:
            hosts.add(_host(t.url))
    return {h for h in hosts if h}


def buat_klien(ctx: ScanContext, *, follow_redirects: bool = False, timeout: float = 15.0) -> KlienScan:
    return KlienScan(ctx.base_url, timeout=timeout, host_izin=hosts_target(ctx), follow_redirects=follow_redirects,
                     saat_request=ctx.rekam_request)


def _cari_token(obj: Any) -> Optional[str]:
    """Cari token di JSON respons (top-level atau di dalam 'data')."""
    if not isinstance(obj, dict):
        return None
    for k in _KUNCI_TOKEN:
        v = obj.get(k)
        if isinstance(v, str) and v:
            return v
    data = obj.get("data")
    if isinstance(data, dict):
        return _cari_token(data)
    return None


def ekstrak_sesi(resp) -> dict:
    """Ambil artefak sesi dari respons login: token (body) & cookie sesi (Set-Cookie).

    Mengembalikan { token: str|None, cookie: {name,value,flags}|None }.
    """
    token = None
    try:
        token = _cari_token(resp.json())
    except Exception:
        token = None

    cookie = None
    try:
        raw_list = resp.headers.get_list("set-cookie")
    except Exception:
        sc = resp.headers.get("set-cookie")
        raw_list = [sc] if sc else []
    # Pilih cookie yang namanya pola sesi, atau yang ber-HttpOnly.
    kandidat = None
    for raw in raw_list:
        nama_nilai = raw.split(";", 1)[0]
        if "=" not in nama_nilai:
            continue
        nama, nilai = nama_nilai.split("=", 1)
        nama = nama.strip()
        flags = raw.split(";", 1)[1].lower() if ";" in raw else ""
        if _COOKIE_SESI.match(nama):
            kandidat = {"name": nama, "value": nilai.strip(), "flags": flags, "raw": raw}
            break
        if "httponly" in flags and kandidat is None:
            kandidat = {"name": nama, "value": nilai.strip(), "flags": flags, "raw": raw}
    cookie = kandidat
    return {"token": token, "cookie": cookie}


def artefak_sesi(r: dict) -> Optional[dict]:
    """Rangkum artefak sesi dari hasil login agar bisa DIPAKAI ULANG di klien lain / setelah logout.

    Return {"jenis": "token"|"cookie", "nilai": str, "nama": str} atau None.
    """
    if r.get("token"):
        return {"jenis": "token", "nilai": r["token"], "nama": "Authorization"}
    c = r.get("cookie")
    if c and c.get("value"):
        return {"jenis": "cookie", "nilai": c["value"], "nama": c.get("name") or "session"}
    return None


def header_artefak(art: Optional[dict]) -> dict:
    """Header untuk melampirkan artefak sesi secara EKSPLISIT pada klien bersih.

    Dipakai menguji pemakaian-ulang sesi (mis. setelah logout) TANPA bergantung pada cookie-jar
    klien — yang bisa ikut terhapus oleh `Set-Cookie` logout (Max-Age=0) dan menutupi apakah
    server benar-benar menginvalidasi sesi. Nilai disamarkan otomatis pada bukti (kunci sensitif).
    """
    if not art:
        return {}
    if art["jenis"] == "token":
        return {"Authorization": f"Bearer {art['nilai']}"}
    return {"Cookie": f"{art['nama']}={art['nilai']}"}


def _coba_browser(klien: KlienScan, ctx: ScanContext, akun: AkunUji) -> Optional[dict]:
    """Fallback login via Playwright (form digerakkan JS/SPA). Suntik sesi ke `klien` httpx.

    Import playwright_driver secara LAZY (hindari impor melingkar; driver mengimpor sesi).
    Return { ok, token, cookie } bila berhasil; None bila Playwright tak tersedia/gagal.
    """
    try:
        from . import playwright_driver as pw  # lazy
    except Exception:
        return None
    if not pw.tersedia():
        return None
    try:
        r = pw.login_browser(ctx, akun)
    except Exception:
        return None
    if not r.get("ok"):
        return None
    if r.get("token"):
        klien.pakai_token(r["token"])
    for c in r.get("cookies", []):
        try:
            dom = str(c.get("domain", "")).lstrip(".") or None
            klien._klien.cookies.set(c.get("name", ""), c.get("value", ""), domain=dom)  # noqa: SLF001
        except Exception:
            pass
    return {"ok": True, "token": r.get("token"), "cookie": r.get("cookie")}


def login_ambil(klien: KlienScan, ctx: ScanContext, akun: AkunUji, *, judul: str = "Login (ambil sesi)") -> dict:
    """Login dan kembalikan artefak sesi + respons. { ok, token, cookie, resp }."""
    url = ctx.url_titik("login")
    if url is None or not akun.password:
        return {"ok": False, "token": None, "cookie": None, "resp": None}
    f = ctx.form_untuk("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"
    tipe = f.tipe_body if f else "json"
    body = {field_user: akun.username, field_pass: akun.password}
    resp = klien.kirim(
        ctx.titik_uji["login"].metode_http,
        url,
        json=body if tipe == "json" else None,
        data=body if tipe == "form" else None,
        judul_bukti=judul,
        sandi_disamarkan=akun.password,
    )
    ok = resp.status_code < 400
    sesi = ekstrak_sesi(resp) if ok else {"token": None, "cookie": None}
    if ok and sesi["token"]:
        klien.pakai_token(sesi["token"])
    hasil = {"ok": ok, "token": sesi["token"], "cookie": sesi["cookie"], "resp": resp}
    # Login httpx gagal / tak membuahkan artefak sesi (form SPA/JS) → coba fallback browser.
    if not (hasil["ok"] and (hasil["token"] or hasil["cookie"])):
        fb = _coba_browser(klien, ctx, akun)
        if fb is not None:
            hasil.update(ok=True, token=fb["token"], cookie=fb["cookie"])
    return hasil


def login(klien: KlienScan, ctx: ScanContext, akun: AkunUji) -> bool:
    """Login dengan akun uji. Return True bila kemungkinan berhasil.

    Keberhasilan dinilai dari: status 2xx DAN (ada token / penanda_berhasil cocok / tak ada penanda_gagal).
    Cookie & token sesi menempel pada `klien` untuk request berikutnya.
    """
    url = ctx.url_titik("login")
    if url is None or not akun.password:
        return False
    f = ctx.form_untuk("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"
    tipe = f.tipe_body if f else "json"
    body = {field_user: akun.username, field_pass: akun.password}

    resp = klien.kirim(
        ctx.titik_uji["login"].metode_http,
        url,
        json=body if tipe == "json" else None,
        data=body if tipe == "form" else None,
        judul_bukti="Login akun uji",
        sandi_disamarkan=akun.password,
    )
    if resp.status_code >= 400:
        return _coba_browser(klien, ctx, akun) is not None  # fallback: form SPA/JS

    # Langkah MFA/OTP diminta → selesaikan via browser (mengisi TOTP otomatis).
    if akun.totp_secret and _butuh_otp(resp):
        return _coba_browser(klien, ctx, akun) is not None

    # Token-based: pasang Authorization bila ada token di body.
    try:
        token = _cari_token(resp.json())
    except Exception:
        token = None
    if token:
        klien.pakai_token(token)
        return True

    # Cookie-based / penanda.
    body_bawah = resp.text.lower()
    if f and f.penanda_gagal and f.penanda_gagal.lower() in body_bawah:
        return _coba_browser(klien, ctx, akun) is not None  # httpx login ditolak → coba browser
    if f and f.penanda_berhasil and f.penanda_berhasil.lower() in body_bawah:
        return True
    # Ada cookie sesi? anggap berhasil.
    if resp.cookies or klien._klien.cookies:  # noqa: SLF001 (akses internal disengaja)
        return True
    # 2xx tanpa sinyal lain — anggap berhasil secara longgar, atau coba browser.
    return resp.status_code < 300 or (_coba_browser(klien, ctx, akun) is not None)
