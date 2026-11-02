"""AUTH-1.1-T01 — auth.login_required.

Area terbatas tidak boleh diakses tanpa autentikasi. GET area tanpa kredensial:
  401/403 atau redirect ke login  → LULUS (terlindungi)
  200 berisi data non-HTML        → GAGAL (data terekspos tanpa auth)
  200 HTML                        → tidak_dapat_diverifikasi (kemungkinan shell SPA; perlu titik uji API)
"""

from __future__ import annotations

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien


@check("auth.login_required")
class CekLoginRequired:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        url = ctx.url_titik("area_terautentikasi")
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "area terautentikasi" tidak tersedia pada aplikasi.')
        ctx.langkah("akses_tanpa_sesi", "Mengakses area terbatas TANPA sesi login", tujuan=url)
        try:
            with buat_klien(ctx) as klien:
                resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — akses area terbatas tanpa autentikasi")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi endpoint.", detail=f"{type(e).__name__}: {e}")

        sc = resp.status_code
        lokasi = resp.headers.get("location", "").lower()
        ditolak = sc in (401, 403) or (300 <= sc < 400 and any(k in lokasi for k in ("login", "masuk", "auth")))
        ctx.langkah("evaluasi", "Akses ditolak / dialihkan ke login" if ditolak else f"Area merespons HTTP {sc} tanpa sesi",
                    status=sc, hasil="ditolak" if ditolak else "diterima")
        if sc in (401, 403):
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Akses tanpa autentikasi ditolak (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)
        if sc in (301, 302, 303, 307, 308) and ("login" in lokasi or "masuk" in lokasi or "auth" in lokasi):
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Dialihkan ke halaman login (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)
        ctype = resp.headers.get("content-type", "").lower()
        if sc == 200 and "text/html" not in ctype:
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Area terbatas mengembalikan data (HTTP 200, {ctype or 'non-HTML'}) tanpa autentikasi.", detail=metode.kriteria_lulus, bukti=bukti)
        # HTML (kemungkinan shell SPA) → coba di browser: apakah dialihkan ke login?
        via_pw = _cek_redirect_browser(ctx, url, metode, bukti)
        if via_pw is not None:
            return via_pw
        return HasilMetode(
            metode_id=metode.id,
            status="tidak_dapat_diverifikasi",
            ringkasan=f"HTTP {sc} (HTML) tanpa autentikasi — proteksi tak bisa dipastikan dari luar (SPA); arahkan titik uji ke endpoint API terbatas.",
            bukti=bukti,
        )


def _cek_redirect_browser(ctx: ScanContext, url: str, metode: MetodeSpec, bukti):
    """Fallback SPA: buka area tanpa auth di browser; dialihkan ke login / form login muncul → lulus.

    Konservatif: hanya mengangkat ke `lulus` bila jelas dialihkan ke login; selain itu None
    (penelepon tetap tidak_dapat_diverifikasi — tak menuduh `gagal` tanpa bukti kuat).
    """
    try:
        from .. import playwright_driver as pw  # lazy
    except Exception:
        return None
    if not pw.tersedia():
        return None
    try:
        with pw.buka_konteks(ctx) as (context, page):
            if not pw._goto(page, url):  # noqa: SLF001
                return None
            try:
                page.wait_for_timeout(1200)
            except Exception:
                pass
            url_akhir = ""
            try:
                url_akhir = (page.url or "").lower()
            except Exception:
                pass
            ada_form_login = bool(page.query_selector("input[type=password]"))
    except Exception:
        return None

    dialihkan = any(k in url_akhir for k in ("login", "masuk", "auth", "signin", "sign-in"))
    if dialihkan or ada_form_login:
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Tanpa autentikasi, aplikasi mengalihkan ke halaman login (terverifikasi via browser/SPA).", detail=metode.kriteria_lulus, bukti=bukti)
    return None
