"""AUTH-1.7 — jalur komunikasi autentikasi yang aman.

auth.login_over_https (1.7-T01): halaman & endpoint login harus memakai HTTPS, dan endpoint
                      login TIDAK memproses payload yang dikirim lewat http:// (dialihkan /
                      ditolak / port tertutup = aman; diproses aplikasi = kredensial bisa
                      terkirim tanpa enkripsi). Probe memakai kredensial ACAK, bukan akun uji.
tls.http_redirect   (1.7-T02): akses HTTP ke halaman login dialihkan (301/308) ke HTTPS.

Di localhost/HTTP kedua check akan GAGAL — itu benar (tanpa TLS).
"""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit, urlunsplit

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..peristiwa_uji import payload_aman
from ..registry import check
from ..sesi import buat_klien


def _skema(url: str) -> str:
    return urlsplit(url).scheme.lower()


def _versi_http(url: str) -> str:
    b = urlsplit(url)
    return urlunsplit(("http", b.netloc, b.path or "/", b.query, ""))


def _probe_payload_http(ctx: ScanContext, metode: MetodeSpec, aksi: str) -> HasilMetode:
    """Kirim payload login berkredensial acak ke versi http:// endpoint login (redirect tak diikuti)."""
    url_http = _versi_http(aksi)
    f = ctx.form_untuk("login")
    field_user = f.field_username if f else "email"
    field_pass = f.field_password if f else "password"
    tipe = f.tipe_body if f else "json"
    sandi = secrets.token_urlsafe(12)
    body = {field_user: f"satya-uji-{secrets.token_hex(4)}@contoh.go.id", field_pass: sandi}
    ctx.langkah("ubah_skema", "Mengganti kanal ke HTTP (tanpa enkripsi) untuk payload login", dari=aksi, ke=url_http)
    ctx.langkah("siapkan_payload", "Payload login berkredensial acak (bukan akun uji)", payload=payload_aman(body), tipe_body=tipe, tujuan=url_http)
    try:
        with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
            resp = klien.kirim(
                ctx.titik_uji["login"].metode_http if "login" in ctx.titik_uji else "POST",
                url_http,
                json=body if tipe == "json" else None,
                data=body if tipe == "form" else None,
                judul_bukti=f"{metode.id} — payload login lewat HTTP (tanpa enkripsi)",
                sandi_disamarkan=sandi,
            )
            bukti = list(klien.bukti)
    except LuarRuangLingkup as e:
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
    except Exception as e:
        ctx.langkah("evaluasi", "Kanal HTTP tidak melayani (koneksi ditolak/timeout) — payload tak bisa dikirim tanpa enkripsi", hasil="ditolak")
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Login memakai HTTPS; kanal HTTP ke endpoint login tidak melayani ({type(e).__name__}).",
                           detail=metode.kriteria_lulus)

    sc = resp.status_code
    lokasi = resp.headers.get("location", "")
    if 300 <= sc < 400 and lokasi.lower().startswith("https://"):
        ctx.langkah("evaluasi", f"Kanal HTTP dialihkan ke HTTPS (HTTP {sc}) — payload tidak diproses", hasil="dialihkan", status=sc, lokasi=lokasi)
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Login memakai HTTPS; payload lewat HTTP dialihkan ke HTTPS (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)
    if sc == 400 and "https" in resp.text.lower():
        ctx.langkah("evaluasi", "Port HTTPS menolak request HTTP biasa (HTTP 400)", hasil="ditolak", status=sc)
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Login memakai HTTPS; request HTTP biasa ditolak server (HTTP 400).", detail=metode.kriteria_lulus, bukti=bukti)
    ctx.langkah("evaluasi", f"Endpoint login MEMPROSES payload lewat HTTP (HTTP {sc}) — kredensial bisa terkirim tanpa enkripsi", hasil="diterima", status=sc)
    return HasilMetode(
        metode_id=metode.id, status="gagal",
        ringkasan=f"Endpoint login memproses payload yang dikirim lewat HTTP tanpa enkripsi (HTTP {sc}); seharusnya dialihkan/ditolak.",
        detail=metode.kriteria_lulus, bukti=bukti,
    )


@check("auth.login_over_https")
class CekLoginHttps:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            halaman = ctx.url_titik("login_page") or ctx.url_titik("login")
            aksi = ctx.url_titik("login")
            if not halaman and not aksi:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="Halaman/endpoint login tidak tersedia pada aplikasi.")
            else:
                peran = [("Halaman login (frontend)", halaman, "frontend"), ("Endpoint login (backend)", aksi, "api")]
                for label, u, lapisan in peran:
                    if u:
                        ctx.langkah("periksa_skema", f"{label}: {_skema(u).upper()}", url=u, skema=_skema(u), lapisan=lapisan)
                urls = [u for u in (halaman, aksi) if u]
                non_https = [u for u in urls if _skema(u) != "https"]
                if non_https:
                    ctx.langkah("evaluasi", "Login tidak sepenuhnya memakai HTTPS", hasil="tidak_aman")
                    hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Login tidak sepenuhnya HTTPS: {', '.join(non_https)}.", detail=metode.kriteria_lulus)
                elif aksi:
                    # Kanal aman terpasang → coba kirim payload yang sama lewat HTTP.
                    hasil = _probe_payload_http(ctx, metode, aksi)
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Halaman dan endpoint login memakai HTTPS.", detail=metode.kriteria_lulus)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("tls.http_redirect")
class CekRedirectHttps:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        halaman = ctx.url_titik("login_page") or ctx.url_titik("login")
        if not halaman:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="Halaman login tidak tersedia pada aplikasi.")
        url_http = _versi_http(halaman)
        ctx.langkah("ubah_skema", "Membuka halaman login lewat HTTP (tanpa enkripsi)", dari=halaman, ke=url_http)
        try:
            with buat_klien(ctx, follow_redirects=False) as klien:
                resp = klien.kirim("GET", url_http, judul_bukti=f"{metode.id} — akses HTTP ke halaman login")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi versi HTTP halaman login.", detail=f"{type(e).__name__}: {e}")

        lokasi = resp.headers.get("location", "")
        ke_https = lokasi.lower().startswith("https://")
        ctx.langkah(
            "evaluasi",
            f"Dialihkan {'permanen ' if resp.status_code in (301, 308) else ''}ke HTTPS (HTTP {resp.status_code})" if ke_https
            else f"Tidak dialihkan ke HTTPS (HTTP {resp.status_code})",
            status=resp.status_code, lokasi=lokasi, hasil="dialihkan" if ke_https else "diterima",
        )
        if resp.status_code in (301, 308) and lokasi.lower().startswith("https://"):
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Akses HTTP dialihkan permanen ke HTTPS (HTTP {resp.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
        if resp.status_code in (302, 303, 307) and lokasi.lower().startswith("https://"):
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Dialihkan ke HTTPS tetapi tidak permanen (HTTP {resp.status_code}); gunakan 301/308.", detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Akses HTTP tidak dialihkan ke HTTPS (HTTP {resp.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
