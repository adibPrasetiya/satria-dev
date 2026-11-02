"""AUTH-1.1-T02 — auth.password_field_masked.

Input kata sandi pada halaman login harus bertipe password (tersamarkan). Ambil HTML
halaman login dan periksa elemen <input> kata sandi:
  ada input type=password                 → LULUS
  input kata sandi ada tapi bukan password → GAGAL
  input kata sandi tak ditemukan di HTML   → tidak_dapat_diverifikasi (mungkin dirender JS/SPA)
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien


def _tampak_api(url: str) -> bool:
    """URL tampak endpoint API (bukan halaman frontend)?"""
    p = urlsplit(url).path.lower()
    return "/api/" in p or p.endswith("/api") or bool(re.search(r"/v\d+/", p))


def _is_html(resp) -> bool:
    return "html" in resp.headers.get("content-type", "").lower()


class _ParserInput(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "input":
            self.inputs.append({(k or "").lower(): (v or "") for k, v in attrs})


@check("auth.password_field_masked")
class CekFieldSandiTersamar:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        f = ctx.form_untuk("login")
        nama_sandi = (f.field_password if f else "password").lower()

        # Metode ini memeriksa HALAMAN LOGIN FRONTEND (HTML), bukan endpoint API aksi login.
        url = ctx.url_titik("login_page")
        if url is None:
            kandidat = ctx.url_titik("login")
            if kandidat and not _tampak_api(kandidat):
                url = kandidat
            else:
                # Hanya endpoint API login yang terpetakan → JANGAN GET API (menyesatkan); render frontend.
                via = _render_dan_nilai(ctx, ctx.base_url, nama_sandi, metode, [])
                if via is not None:
                    return via
                if kandidat is None:
                    return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Halaman login tidak tersedia pada aplikasi.')
                return HasilMetode(
                    metode_id=metode.id, status="tidak_dapat_diverifikasi",
                    ringkasan="Titik uji 'login' menunjuk endpoint API, bukan halaman login frontend; isi 'login_page' pada persiapan atau jalankan penemuan ulang.",
                )

        ctx.langkah("ambil_halaman", "Mengambil HTML halaman login (frontend)", tujuan=url)
        try:
            with buat_klien(ctx) as klien:
                resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — ambil HTML halaman login")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal mengambil halaman login.", detail=f"{type(e).__name__}: {e}")

        # Respons bukan HTML (mis. titik mengarah ke API) → render frontend di browser.
        if not _is_html(resp):
            via = _render_dan_nilai(ctx, ctx.url_titik("login_page") or ctx.base_url, nama_sandi, metode, bukti)
            if via is not None:
                return via
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Respons halaman login bukan HTML (kemungkinan endpoint API); perlu halaman login frontend.", bukti=bukti)

        p = _ParserInput()
        try:
            p.feed(resp.text)
        except Exception:
            pass

        type_pw = [i for i in p.inputs if i.get("type", "").lower() == "password"]
        kandidat = [i for i in p.inputs if i.get("name", "").lower() == nama_sandi or "password" in i.get("name", "").lower() or "sandi" in i.get("name", "").lower()]

        ctx.langkah(
            "periksa_input",
            "Input kata sandi bertipe password" if type_pw else ("Input kata sandi BUKAN tipe password" if kandidat else "Input kata sandi tak ada di HTML awal"),
            hasil="tersamar" if type_pw else ("terbuka" if kandidat else "tak_ditemukan"),
        )
        if type_pw:
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Input kata sandi bertipe password (tersamarkan).", detail=metode.kriteria_lulus, bukti=bukti)
        if kandidat:
            tp = kandidat[0].get("type", "text") or "text"
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f'Input kata sandi ditemukan tetapi bertipe "{tp}", bukan password.', detail=metode.kriteria_lulus, bukti=bukti)
        # HTML awal tak punya input sandi (kemungkinan SPA) → coba render di browser.
        via_pw = _render_dan_nilai(ctx, url, nama_sandi, metode, bukti)
        if via_pw is not None:
            return via_pw
        return HasilMetode(
            metode_id=metode.id,
            status="tidak_dapat_diverifikasi",
            ringkasan="Input kata sandi tidak ditemukan di HTML awal (mungkin dirender JavaScript/SPA; Playwright tak tersedia).",
            bukti=bukti,
        )


def _render_dan_nilai(ctx: ScanContext, url: str, nama_sandi: str, metode: MetodeSpec, bukti):
    """Fallback SPA: render halaman login di browser dan periksa input sandi nyata.

    Return HasilMetode (lulus/gagal) bila konklusif; None bila Playwright tak tersedia/tak konklusif.
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
            ada_pw = bool(page.query_selector("input[type=password]"))
            inputs = page.eval_on_selector_all(
                "input",
                "els => els.map(e => ({type:(e.getAttribute('type')||'').toLowerCase(), name:(e.getAttribute('name')||'').toLowerCase()}))",
            ) or []
    except Exception:
        return None

    if ada_pw:
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Input kata sandi bertipe password (terverifikasi via render browser/SPA).", detail=metode.kriteria_lulus, bukti=bukti)
    mismatch = [i for i in inputs if (i.get("name") == nama_sandi or "password" in i.get("name", "") or "sandi" in i.get("name", "")) and i.get("type") != "password"]
    if mismatch:
        tp = mismatch[0].get("type") or "text"
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f'Input kata sandi (render SPA) bertipe "{tp}", bukan password.', detail=metode.kriteria_lulus, bukti=bukti)
    return None
