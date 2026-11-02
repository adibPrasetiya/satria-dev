"""Engine `playwright` — check berbasis browser nyata (Playwright, library in-proses).

Menangani 5 metode katalog ber-`engine: playwright`:
  deps.unknown_third_party_scripts (MALC-9.2-T02, global)  — skrip dari domain tak dikenal
  privacy.permission_prompts       (MALC-9.3-T02, global)  — izin perangkat diminta saat load
  data.browser_storage             (DATA-7.2-T02, auth)    — kredensial/data di localStorage
  auth.password_policy.min_length+complexity (AUTH-1.3-T03, reset_password) — kebijakan saat reset
  auth.reset.token_single_use_expiry         (AUTH-1.5-T02, reset_password) — token sekali pakai

Navigasi global (skrip + izin) di-*cache* per base_url (satu muat dipakai dua check), meniru
pola cache engine `zap`. Metode reset butuh Resend inbound (lihat `email_reset`) untuk menerima
email reset; bila belum dikonfigurasi → `menunggu_tinjauan` (tidak menghakimi tanpa bukti).
"""

from __future__ import annotations

import secrets
import threading
from typing import Any, Optional
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, hosts_target
from .. import playwright_driver as pw
from .. import atribusi_sandi as asd
from .. import email_reset

# Allowlist default MALC-9.2-T02 (ratakan grup katalog) + domain ditandai.
_DEFAULT_DIIZINKAN = {
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "code.jquery.com",
    "ajax.googleapis.com", "cdn.datatables.net", "cdn.ckeditor.com",
    "stackpath.bootstrapcdn.com", "maxcdn.bootstrapcdn.com", "use.fontawesome.com",
    "kit.fontawesome.com", "ka-f.fontawesome.com", "fonts.googleapis.com", "fonts.gstatic.com",
    "www.google.com", "www.gstatic.com", "www.recaptcha.net", "challenges.cloudflare.com",
    "hcaptcha.com", "js.hcaptcha.com",
}
_DEFAULT_DITANDAI = {
    "www.googletagmanager.com", "www.google-analytics.com", "connect.facebook.net",
    "static.hotjar.com", "script.hotjar.com", "cdn.tailwindcss.com",
}

# Kata kunci nama key storage yang menandakan kredensial/data dikecualikan (bukan sekadar token sesi).
_KEY_SENSITIF = ("password", "passwd", "sandi", "secret", "cvv", "ktp", "nik", "kartu", "credit", "pin")

PETA: dict[str, dict[str, Any]] = {
    "deps.unknown_third_party_scripts": {"jenis": "global"},
    "privacy.permission_prompts": {"jenis": "global"},
    "data.browser_storage": {"jenis": "auth"},
    "auth.password_policy.min_length+complexity": {"jenis": "reset"},
    "auth.reset.token_single_use_expiry": {"jenis": "reset"},
}


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "", *, tinjau: bool = False, bukti=None) -> HasilMetode:
    return HasilMetode(
        metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=ringkasan,
        detail=detail, menunggu_tinjauan=tinjau, bukti=bukti or [],
    )


# =========================================================================== fungsi murni (diuji tanpa browser)

def _cocok_domain(host: str, daftar: set[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in daftar)


def klasifikasi_skrip(scripts: list[str], own_host: str, diizinkan: set[str], ditandai: set[str]) -> tuple[list[str], list[str]]:
    """Pisahkan skrip jadi (tak_dikenal, ditandai). Host sendiri/subdomain & diizinkan → aman."""
    own_host = (own_host or "").lower()
    tak_dikenal: list[str] = []
    ditandai_hit: list[str] = []
    for s in scripts:
        h = (urlsplit(s).hostname or "").lower()
        if not h:
            continue  # inline/relatif → milik aplikasi
        if own_host and (h == own_host or h.endswith("." + own_host)):
            continue
        if _cocok_domain(h, ditandai):
            ditandai_hit.append(s)
        elif _cocok_domain(h, diizinkan):
            continue
        else:
            tak_dikenal.append(s)
    return tak_dikenal, ditandai_hit


def pindai_storage(storage: dict, rahasia: list[str]) -> list[str]:
    """Temuan penyimpanan browser: nilai memuat rahasia (sandi/email akun) atau key bernama sensitif.

    Token sesi di localStorage (pola SPA umum) TIDAK ditandai — fokus pada kredensial/data dikecualikan.
    """
    rahasia = [r for r in rahasia if r]
    temuan: list[str] = []
    for area, bag in (storage or {}).items():
        if not isinstance(bag, dict):
            continue
        for k, v in bag.items():
            vs = v if isinstance(v, str) else str(v)
            kl = str(k).lower()
            if any(r in vs for r in rahasia):
                temuan.append(f"{area}['{k}'] memuat nilai kredensial/data uji (disamarkan)")
            elif any(w in kl for w in _KEY_SENSITIF):
                temuan.append(f"{area}['{k}'] — nama kunci menandakan data sensitif")
    return temuan


def evaluasi_skrip(metode: MetodeSpec, scripts: list[str], own_host: str, diizinkan: set[str], ditandai: set[str], *, muat_ok: bool, bukti=None) -> HasilMetode:
    if not muat_ok:
        return _tdv(metode, "Halaman tidak termuat di browser untuk analisis skrip.", bukti=bukti)
    tak_dikenal, ditandai_hit = klasifikasi_skrip(scripts, own_host, diizinkan, ditandai)
    if ditandai_hit or tak_dikenal:
        rinci = []
        if ditandai_hit:
            rinci.append("ditandai: " + ", ".join(sorted({urlsplit(u).hostname or u for u in ditandai_hit})))
        if tak_dikenal:
            rinci.append("tak dikenal: " + ", ".join(sorted({urlsplit(u).hostname or u for u in tak_dikenal})))
        b = (bukti or []) + [Bukti(jenis="dokumen", judul="Skrip pihak ketiga", isi="\n".join((ditandai_hit + tak_dikenal)[:20]))]
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Skrip dari domain luar allowlist terdeteksi (" + "; ".join(rinci) + ").", detail=metode.kriteria_lulus, bukti=b)
    return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Semua skrip dari domain aplikasi atau allowlist tepercaya.", detail=metode.kriteria_lulus, bukti=bukti or [])


def evaluasi_izin(metode: MetodeSpec, izin: list[str], *, muat_ok: bool, bukti=None) -> HasilMetode:
    if not muat_ok:
        return _tdv(metode, "Halaman tidak termuat di browser untuk memeriksa permintaan izin.", bukti=bukti)
    diminta = [i for i in izin if not str(i).startswith("permissions.query:")]  # query ≠ prompt aktif
    if diminta:
        b = (bukti or []) + [Bukti(jenis="dokumen", judul="Izin perangkat diminta saat load", isi=", ".join(sorted(set(diminta))))]
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Aplikasi meminta izin perangkat saat dimuat: {', '.join(sorted(set(diminta)))}.", detail=metode.kriteria_lulus, bukti=b)
    return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Tidak ada permintaan izin perangkat (kamera/mikrofon/geolokasi/notifikasi) saat load.", detail=metode.kriteria_lulus, bukti=bukti or [])


def evaluasi_storage(metode: MetodeSpec, storage: dict, rahasia: list[str], *, login_ok: bool, bukti=None) -> HasilMetode:
    if not login_ok:
        return _tdv(metode, "Gagal login di browser; tidak bisa memeriksa penyimpanan terautentikasi.", bukti=bukti)
    temuan = pindai_storage(storage, rahasia)
    if temuan:
        b = (bukti or []) + [Bukti(jenis="dokumen", judul="Temuan penyimpanan browser", isi="\n".join(temuan[:20]))]
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Penyimpanan browser memuat kredensial/data dikecualikan ({len(temuan)} temuan).", detail=metode.kriteria_lulus, bukti=b)
    return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="localStorage/sessionStorage tak memuat kata sandi/data dikecualikan.", detail=metode.kriteria_lulus, bukti=bukti or [])


def _nilai_reset(teks: str, url_awal: str, url_akhir: str) -> str:
    """Tafsir hasil submit form reset → 'tolak' | 'terima' | 'ambigu'."""
    low = (teks or "").lower()
    tanda_tolak = ("minimal", "min ", "karakter", "lemah", "weak", "tidak valid", "invalid", "harus", "kombinasi", "syarat", "gagal", "error")
    tanda_terima = ("berhasil", "success", "updated", "diperbarui", "silakan login", "please log in", "login", "sign in")
    masih_di_reset = bool(url_akhir) and bool(url_awal) and url_akhir.split("?")[0] == url_awal.split("?")[0]
    if any(k in low for k in tanda_tolak):
        return "tolak"
    if any(k in low for k in tanda_terima) and not masih_di_reset:
        return "terima"
    if masih_di_reset:
        return "tolak"  # tetap di halaman reset tanpa sukses → kemungkinan ditolak
    return "ambigu"


# =========================================================================== orkestrasi navigasi global (cache)

_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}  # base_url -> {scripts, izin, ok}


def _muat_global(ctx: ScanContext) -> dict[str, Any]:
    base = ctx.base_url
    with _lock:
        entri = _cache.get(base)
        if entri is not None:
            return entri
    with pw.buka_konteks(ctx) as (context, page):
        hasil = pw.muat_terinstrumentasi(page, base)
    with _lock:
        _cache[base] = hasil
    return hasil


def _param_domain(metode: MetodeSpec) -> tuple[set[str], set[str]]:
    """Allowlist & daftar-ditandai dari parameter metode (ratakan grup) atau default katalog."""
    p = metode.parameter or {}
    diz = p.get("domain_diizinkan")
    izin: set[str] = set()
    if isinstance(diz, dict):
        for grup in diz.values():
            if isinstance(grup, list):
                izin.update(str(d).lower() for d in grup)
    elif isinstance(diz, list):
        izin.update(str(d).lower() for d in diz)
    ditandai = {str(d).lower() for d in p.get("domain_ditandai", [])} if isinstance(p.get("domain_ditandai"), list) else set()
    return (izin or set(_DEFAULT_DIIZINKAN)), (ditandai or set(_DEFAULT_DITANDAI))


# =========================================================================== reset (Resend + browser)

def _registrasi_pengguna(ctx: ScanContext, reg_url: str, email: str, sandi: str) -> tuple[bool, list[Bukti]]:
    """Daftar pengguna baru beremail Resend (pola sama password_policy._jalankan_registrasi)."""
    form = ctx.form_untuk("registrasi")
    if form is None or not (form.field_dasar or form.skema_field):
        return False, []
    # Payload VALID (field lain lolos validasi), email = alamat Resend agar email reset bisa diterima.
    payload, _ = asd.payload_valid(form)
    for fk in {form.field_identitas, "email", "surel"}:
        if fk and (fk in payload or fk == "email"):
            payload[fk] = email
    payload = asd.pasang_sandi(payload, form, sandi)
    try:
        with buat_klien(ctx) as klien:
            resp = klien.kirim(
                ctx.titik_uji["registrasi"].metode_http, reg_url,
                json=payload if form.tipe_body == "json" else None,
                data=payload if form.tipe_body == "form" else None,
                judul_bukti="Reset — daftar pengguna uji (email Resend)", sandi_disamarkan=sandi,
            )
            return resp.status_code in form.status_sukses, list(klien.bukti)
    except (LuarRuangLingkup, Exception):
        return False, []


def _picu_lupa_sandi(ctx: ScanContext, reset_url: str, email: str) -> list[Bukti]:
    f = ctx.form_untuk("reset_password")
    field_id = f.field_identitas if f else "email"
    tipe = f.tipe_body if f else "json"
    try:
        with buat_klien(ctx) as klien:
            klien.kirim(
                ctx.titik_uji["reset_password"].metode_http, reset_url,
                json={field_id: email} if tipe == "json" else None,
                data={field_id: email} if tipe == "form" else None,
                judul_bukti="Reset — picu permintaan lupa sandi",
            )
            return list(klien.bukti)
    except (LuarRuangLingkup, Exception):
        return []


def _jalankan_reset(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
    if not pw.tersedia():
        return _tdv(metode, "Playwright belum terpasang; uji reset berbasis browser tak dapat dijalankan.", tinjau=True)
    reset_url = ctx.url_titik("reset_password")
    if reset_url is None:
        return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "reset_password" tidak tersedia pada aplikasi.')
    resend = email_reset.dari_env()
    if resend is None:
        return _tdv(metode, "Resend inbound belum dikonfigurasi (RESEND_API_KEY/RESEND_INBOUND_DOMAIN); otomasi reset butuh email masuk.", tinjau=True)
    reg_url = ctx.url_titik("registrasi")
    if reg_url is None:
        return _tdv(metode, "Perlu titik uji 'registrasi' untuk mendaftar pengguna baru beremail Resend.", tinjau=True)

    izin_host = hosts_target(ctx)
    try:
        with resend:
            alamat = resend.alamat_baru()
            sandi_kuat = "Satya9!" + secrets.token_urlsafe(10)
            ok_reg, bukti_reg = _registrasi_pengguna(ctx, reg_url, alamat, sandi_kuat)
            if not ok_reg:
                return _tdv(metode, "Gagal mendaftarkan pengguna uji untuk alur reset.", tinjau=True, bukti=bukti_reg)
            sejak = email_reset._sekarang()
            bukti_picu = _picu_lupa_sandi(ctx, reset_url, alamat)
            isi = resend.tunggu_email(alamat, sejak)
            if not isi:
                return _tdv(metode, "Email reset tak diterima dalam batas waktu (periksa domain inbound Resend & pengiriman target).", tinjau=True, bukti=bukti_reg + bukti_picu)
            link = email_reset.ekstrak_link_reset(isi, host_izin=izin_host)
            if not link:
                return _tdv(metode, "Tautan reset tak ditemukan dalam email.", tinjau=True, bukti=bukti_reg + bukti_picu)
    except Exception as e:
        return _tdv(metode, f"Gagal menjalankan alur reset: {type(e).__name__}", detail=str(e)[:300], tinjau=True)

    bukti_awal = bukti_reg + bukti_picu + [Bukti(jenis="dokumen", judul="Tautan reset diterima", isi="(disamarkan) host=" + (urlsplit(link).hostname or "?"))]
    if metode.check_id == "auth.password_policy.min_length+complexity":
        # Jalur API (tajam, beratribusi) bila endpoint penyelesaian reset & token tersedia; browser = cadangan.
        url_konf = ctx.url_titik("reset_password_konfirmasi")
        token = email_reset.ekstrak_token(isi) or email_reset.ekstrak_token(link)
        if url_konf and token:
            return _reset_kebijakan_api(ctx, metode, url_konf, token, bukti_awal)
        return _reset_kebijakan_sandi(ctx, metode, link, bukti_awal)
    return _reset_sekali_pakai(ctx, metode, link, bukti_awal)


def _reset_kebijakan_api(ctx: ScanContext, metode: MetodeSpec, url: str, token: str, bukti: list[Bukti]) -> HasilMetode:
    """AUTH-1.3-T03 via API: token reset valid + sandi LEMAH → lalu pembanding sandi KUAT dengan token
    yang sama (sekaligus menghabiskan token). Penolakan diatribusikan (lihat atribusi_sandi)."""
    from ..models import FormTitikUji
    from ..peristiwa_uji import payload_aman

    form = ctx.form.get("reset_password_konfirmasi") or FormTitikUji()
    field_token = form.field_token or "token"
    sukses = tuple(form.status_sukses or asd.STATUS_SUKSES)
    dasar, _ = asd.payload_valid(form)
    dasar[field_token] = token
    lemah, kuat = "ab", asd.sandi_kuat()
    p_lemah = asd.pasang_sandi(dasar, form, lemah)
    ctx.langkah("siapkan_payload", "Payload penyelesaian reset: token valid + kata sandi lemah",
                payload=payload_aman(p_lemah, tampilkan=[form.field_sandi]), tipe_body=form.tipe_body, tujuan=url)

    def kirim(klien: Any, body: dict[str, Any], judul: str, sandi: str):
        return klien.kirim(ctx.titik_uji["reset_password_konfirmasi"].metode_http, url,
                           json=body if form.tipe_body == "json" else None, data=body if form.tipe_body == "form" else None,
                           judul_bukti=judul, sandi_disamarkan=sandi)

    r_kuat = None
    try:
        with buat_klien(ctx) as klien:
            r_lemah = kirim(klien, p_lemah, f"{metode.id} — reset dengan sandi lemah", lemah)
            if r_lemah.status_code not in sukses:
                ctx.langkah("pembanding_kuat", "Pembanding: token yang sama dengan sandi KUAT")
                r_kuat = kirim(klien, asd.pasang_sandi(dasar, form, kuat), f"{metode.id} — pembanding: reset dengan sandi kuat", kuat)
            bukti = bukti + list(klien.bukti)
    except (LuarRuangLingkup, Exception) as e:
        return _tdv(metode, f"Gagal menghubungi endpoint penyelesaian reset: {type(e).__name__}.", tinjau=True, bukti=bukti)

    atribusi = asd.atribusikan(r_lemah, field_sandi=form.field_sandi, payload=p_lemah, sandi_lemah=lemah, resp_kuat=r_kuat, status_sukses=sukses)
    ctx.langkah("atribusi", f"Penyebab: {atribusi['penyebab']} — {atribusi['alasan'][:120]}",
                hasil={"kebijakan_sandi": "ditolak", "diterima": "diterima"}.get(atribusi["penyebab"], "tidak_jelas"), status=r_lemah.status_code)
    status = asd.vonis(atribusi)
    bukti = bukti + [Bukti(jenis="dokumen", judul="Atribusi penolakan", isi=f"penyebab={atribusi['penyebab']}; sumber={atribusi.get('sumber')}\n{atribusi['alasan']}")]
    if status == "gagal":
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Sandi lemah DITERIMA saat reset — kebijakan tak ditegakkan.", detail=metode.kriteria_lulus, bukti=bukti)
    if status == "lulus":
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Kebijakan kata sandi ditegakkan saat reset ({atribusi['alasan']})"[:480], detail=metode.kriteria_lulus, bukti=bukti)
    return _tdv(metode, f"Reset dengan sandi lemah ditolak, tetapi penyebabnya belum dapat dipastikan: {atribusi['alasan']}"[:480], tinjau=True, bukti=bukti)


def _reset_kebijakan_sandi(ctx: ScanContext, metode: MetodeSpec, link: str, bukti: list[Bukti]) -> HasilMetode:
    """AUTH-1.3-T03: submit sandi LEMAH di halaman reset → ditolak = lulus."""
    try:
        r = pw.submit_reset(ctx, link, "ab")  # pendek & tanpa kombinasi
    except pw.PlaywrightTidakTersedia as e:
        return _tdv(metode, "Browser tak tersedia untuk menguji halaman reset.", str(e), tinjau=True, bukti=bukti)
    if not r["ok"]:
        return _tdv(metode, "Form reset/field sandi tak ditemukan di halaman (mungkin tautan kedaluwarsa/SPA).", tinjau=True, bukti=bukti)
    vonis = _nilai_reset(r["teks"], r["url_awal"], r["url_akhir"])
    if vonis == "tolak":
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Kebijakan kata sandi ditegakkan saat reset (sandi lemah ditolak).", detail=metode.kriteria_lulus, bukti=bukti)
    if vonis == "terima":
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Sandi lemah DITERIMA saat reset — kebijakan tak ditegakkan.", detail=metode.kriteria_lulus, bukti=bukti)
    return _tdv(metode, "Hasil submit reset tak jelas (tolak/terima) — perlu tinjauan asesor.", tinjau=True, bukti=bukti)


def _reset_sekali_pakai(ctx: ScanContext, metode: MetodeSpec, link: str, bukti: list[Bukti]) -> HasilMetode:
    """AUTH-1.5-T02: pakai token sekali (sandi kuat) → ulangi token sama → ditolak = lulus.

    Kedaluwarsa tak dapat ditunggu worker; penilaian bertumpu pada sekali-pakai (dicatat jujur).
    """
    sandi_valid = "Satya9!" + secrets.token_urlsafe(10)
    try:
        r1 = pw.submit_reset(ctx, link, sandi_valid)
        if not r1["ok"]:
            return _tdv(metode, "Form reset tak ditemukan (tautan mungkin kedaluwarsa).", tinjau=True, bukti=bukti)
        v1 = _nilai_reset(r1["teks"], r1["url_awal"], r1["url_akhir"])
        r2 = pw.submit_reset(ctx, link, sandi_valid)  # token yang sama, kedua kali
    except pw.PlaywrightTidakTersedia as e:
        return _tdv(metode, "Browser tak tersedia untuk menguji token reset.", str(e), tinjau=True, bukti=bukti)
    if v1 != "terima":
        return _tdv(metode, "Reset pertama tak jelas berhasil; tak bisa menilai token sekali-pakai.", tinjau=True, bukti=bukti)
    v2 = _nilai_reset(r2["teks"], r2["url_awal"], r2["url_akhir"])
    catatan = " (kedaluwarsa tak diuji — di luar jendela waktu worker)"
    if v2 == "tolak":
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Token reset sekali pakai: pemakaian kedua ditolak" + catatan + ".", detail=metode.kriteria_lulus, bukti=bukti)
    if v2 == "terima":
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Token reset DITERIMA pada pemakaian kedua — bukan sekali pakai.", detail=metode.kriteria_lulus, bukti=bukti)
    return _tdv(metode, "Hasil pemakaian token kedua tak jelas — perlu tinjauan asesor." + catatan, tinjau=True, bukti=bukti)


# =========================================================================== dispatch per check

def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
    jenis = PETA.get(metode.check_id, {}).get("jenis")
    try:
        if jenis == "reset":
            return _jalankan_reset(ctx, metode)
        if not pw.tersedia():
            return _tdv(metode, "Playwright belum terpasang; check engine playwright tak dapat dijalankan.")
        if jenis == "global":
            try:
                g = _muat_global(ctx)
            except pw.PlaywrightTidakTersedia as e:
                return _tdv(metode, "Browser tak tersedia (jalankan `playwright install`).", str(e))
            if metode.check_id == "deps.unknown_third_party_scripts":
                izin, ditandai = _param_domain(metode)
                return evaluasi_skrip(metode, g["scripts"], urlsplit(ctx.base_url).hostname or "", izin, ditandai, muat_ok=g["ok"])
            return evaluasi_izin(metode, g["izin"], muat_ok=g["ok"])
        if jenis == "auth":  # data.browser_storage
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if akun is None or not akun.password:
                return _tdv(metode, "Membutuhkan akun uji (dengan kata sandi) untuk login browser.")
            if ctx.url_titik("area_terautentikasi") is None:
                return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan='Titik uji "area_terautentikasi" tidak tersedia.')
            try:
                r = pw.login_browser(ctx, akun)
            except pw.PlaywrightTidakTersedia as e:
                return _tdv(metode, "Browser tak tersedia untuk login.", str(e))
            rahasia = [akun.password or "", akun.username or ""]
            return evaluasi_storage(metode, r.get("storage", {}), rahasia, login_ok=r.get("ok", False))
    except Exception as e:  # jangan jatuhkan worker
        return _tdv(metode, f"Galat engine playwright: {type(e).__name__}", detail=str(e)[:300])
    return _tdv(metode, f'Check "{metode.check_id}" belum dipetakan engine playwright.')


class _CekPlaywright:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = _jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


for _cid in PETA:
    check(_cid, engine="playwright")(type(f"CekPlaywright_{_cid}", (_CekPlaywright,), {}))
