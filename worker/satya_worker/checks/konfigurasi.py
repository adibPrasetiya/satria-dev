"""Fungsi 13 — Konfigurasi (CONF). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx) + tiga check engine nuclei:
  headers.server_banner        (13.1-T01) Server/X-Powered-By tak mengungkap produk+versi detail
  headers.security_baseline    (13.5-T01) nosniff + perlindungan framing + Referrer-Policy
  headers.content_type_charset (13.5-T02) Content-Type tepat beserta charset
  integrity.sri                (13.4-T01) aset eksternal (CDN) memiliki atribut integrity (SRI)
  conf.debug_mode              (13.1-T03, nuclei) mode debug kerangka kerja nonaktif
  exposure.default_sample_pages(13.3-T01, nuclei) halaman default/sampel/instalasi tak tersedia
  exposure.config_vcs_files    (13.3-T02, nuclei) berkas .env/.git/konfig tak terekspos

Sudah ada (tak ditulis ulang): conf.directory_listing (zap, 13.1-T02).
Manual → asesor: manual.config_documentation (13.2).

Anti-false-positif: verdict deterministik dari respons/header nyata; temuan nuclei low/info
ditajamkan AI (`ai/konfigurasi.py`) yang tak memutus lulus/gagal.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien
from .. import nuclei_client as nc

_VERSI = re.compile(r"\d+\.\d+")  # pola versi (mis. 1.18.0, 2.4)


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json
    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


def _ambil_root(ctx: ScanContext, metode: MetodeSpec, judul: str):
    """GET root aplikasi. Return (Response, bukti) atau (None, HasilMetode_tdv)."""
    host = urlsplit(ctx.base_url).hostname or ""
    if not host:
        return None, HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
    try:
        with buat_klien(ctx, follow_redirects=True, timeout=10.0) as klien:
            resp = klien.kirim("GET", ctx.base_url, judul_bukti=f"{metode.id} — {judul}")
            return resp, list(klien.bukti)
    except LuarRuangLingkup as e:
        return None, _tdv(metode, "URL di luar host yang diizinkan.", str(e))
    except Exception as e:
        return None, _tdv(metode, "Gagal menghubungi aplikasi.", f"{type(e).__name__}: {e}")


# =========================================================================== CONF-13.1-T01

@check("headers.server_banner")
class CekBannerServer:
    """Header Server/X-Powered-By tidak mengungkap produk & versi detail."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            resp, bukti = _ambil_root(ctx, metode, "banner server")
            if resp is None:
                hasil = bukti
            else:
                server = (resp.headers.get("server") or "").strip()
                xpb = (resp.headers.get("x-powered-by") or "").strip()
                masalah: list[str] = []
                if server and _VERSI.search(server):
                    masalah.append(f"Server: '{server}' (memuat versi)")
                if xpb:
                    masalah.append(f"X-Powered-By: '{xpb}' (mengungkap teknologi)")
                ctx.langkah("evaluasi", "Memeriksa banner server", server=server or "-", x_powered_by=xpb or "-")
                if masalah:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan="Banner server mengungkap teknologi/versi: " + "; ".join(masalah) + ".",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                        ringkasan=f"Banner server tidak mengungkap versi detail (Server: '{server or 'tidak ada'}').",
                                        detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== CONF-13.5-T01

@check("headers.security_baseline")
class CekBaselineHeader:
    """X-Content-Type-Options nosniff, perlindungan framing, dan Referrer-Policy ada."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            resp, bukti = _ambil_root(ctx, metode, "header keamanan")
            if resp is None:
                hasil = bukti
            else:
                hilang: list[str] = []
                nosniff = (resp.headers.get("x-content-type-options") or "").strip().lower() == "nosniff"
                xfo = (resp.headers.get("x-frame-options") or "").strip().lower()
                csp = (resp.headers.get("content-security-policy") or "").lower()
                framing = xfo in ("deny", "sameorigin") or "frame-ancestors" in csp
                referrer = bool((resp.headers.get("referrer-policy") or "").strip())
                if not nosniff:
                    hilang.append("X-Content-Type-Options: nosniff")
                if not framing:
                    hilang.append("perlindungan framing (X-Frame-Options / CSP frame-ancestors)")
                if not referrer:
                    hilang.append("Referrer-Policy")
                ctx.langkah("evaluasi", "Memeriksa header keamanan dasar", hilang=hilang or ["lengkap"])
                if hilang:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan=f"Header keamanan dasar belum lengkap — kurang: {', '.join(hilang)}.",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                        ringkasan="Header keamanan dasar lengkap (nosniff, perlindungan framing, Referrer-Policy).",
                                        detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== CONF-13.5-T02

@check("headers.content_type_charset")
class CekContentTypeCharset:
    """Respons memiliki Content-Type yang benar beserta charset (untuk tipe teks/HTML)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            resp, bukti = _ambil_root(ctx, metode, "Content-Type")
            if resp is None:
                hasil = bukti
            else:
                ct = (resp.headers.get("content-type") or "").strip().lower()
                tipe = ct.split(";", 1)[0].strip()
                butuh_charset = tipe.startswith("text/") or tipe in ("application/json", "application/xhtml+xml")
                ctx.langkah("evaluasi", f"Content-Type: '{ct or 'kosong'}'", tipe=tipe or "-", ada_charset="charset=" in ct)
                if not ct:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan="Respons tidak menyertakan header Content-Type.",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                elif tipe.startswith("text/") and "charset=" not in ct:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan=f"Respons teks tanpa charset pada Content-Type ('{ct}').",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                        ringkasan=f"Content-Type tepat{' beserta charset' if 'charset=' in ct else ''} ('{ct}').",
                                        detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== CONF-13.4-T01

_TAG_ASET = re.compile(r"<(script|link)\b([^>]*)>", re.IGNORECASE)


def _attr(nama: str, s: str) -> str:
    m = re.search(rf'{nama}\s*=\s*["\']([^"\']+)["\']', s, re.IGNORECASE)
    return m.group(1) if m else ""


@check("integrity.sri")
class CekSri:
    """Aset dari origin eksternal (CDN) memiliki atribut integrity (Subresource Integrity)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            resp, bukti = _ambil_root(ctx, metode, "SRI aset eksternal")
            if resp is None:
                hasil = bukti
            else:
                hasil = self._nilai(ctx, metode, resp, bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx, metode, resp, bukti) -> HasilMetode:
        host = (urlsplit(ctx.base_url).hostname or "").lower()
        html = resp.text or ""
        eksternal: list[str] = []
        tanpa_sri: list[str] = []
        for tag, isi in _TAG_ASET.findall(html):
            tag = tag.lower()
            if tag == "script":
                url = _attr("src", isi)
            else:  # link
                rel = _attr("rel", isi).lower()
                if not any(r in rel for r in ("stylesheet", "preload", "modulepreload")):
                    continue
                url = _attr("href", isi)
            if not url:
                continue
            h = (urlsplit(url).hostname or "").lower()
            if not h or h == host:
                continue  # relatif / origin sama = bukan aset eksternal
            eksternal.append(url)
            if not _attr("integrity", isi):
                tanpa_sri.append(url)
        ctx.langkah("evaluasi", "Memeriksa SRI aset eksternal", eksternal=len(eksternal), tanpa_sri=len(tanpa_sri))
        if not eksternal:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tidak ada aset dari origin eksternal (CDN) pada halaman — SRI tidak diperlukan.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if tanpa_sri:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(tanpa_sri)} dari {len(eksternal)} aset eksternal tanpa atribut integrity (SRI): "
                                         + ", ".join(urlsplit(u).path or u for u in tanpa_sri[:3]) + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Seluruh {len(eksternal)} aset eksternal memiliki atribut integrity (SRI).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== nuclei (13.1-T03, 13.3-T01/T02)

def _nuclei_paparan(ctx: ScanContext, metode: MetodeSpec, *, tags: str, kata: tuple, jenis: str, label: str) -> HasilMetode:
    """Helper bersama untuk check paparan konfigurasi berbasis nuclei."""
    host = urlsplit(ctx.base_url).hostname or ""
    if not host:
        return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
    if not nc.tersedia():
        return _tdv(metode, "Biner nuclei belum terpasang pada worker — diserahkan asesor.",
                    "Pasang nuclei + `nuclei -update-templates` untuk mengotomasi uji ini.")
    ctx.langkah("pindai_nuclei", f"Memindai {label} (nuclei)", target=ctx.base_url)
    try:
        temuan = nc.jalankan(ctx.base_url, tags=tags, kata_relevan=kata)
    except Exception as e:
        return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
    if not temuan:
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Tak ada {label} terdeteksi.", detail=metode.kriteria_lulus)
    nyata = _saring(ctx, temuan, jenis)
    bukti = [_bukti_dok(f"{metode.id} — temuan {label} (nuclei)", {"temuan": temuan[:10]})]
    ctx.langkah("evaluasi", f"Menilai temuan {label}", total=len(temuan), sensitif=len(nyata))
    if nyata:
        daftar = ", ".join(urlsplit(t.get("url", "")).path for t in nyata[:3])
        return HasilMetode(metode_id=metode.id, status="gagal",
                           ringkasan=f"{len(nyata)} {label} terdeteksi: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                           detail=metode.kriteria_lulus, bukti=bukti)
    return HasilMetode(metode_id=metode.id, status="lulus",
                       ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai sensitif.",
                       detail=metode.kriteria_lulus, bukti=bukti)


def _saring(ctx: ScanContext, temuan: list[dict], jenis: str) -> list[dict]:
    try:
        from ..ai import konfigurasi as ai_conf
        from ..ai import penggunaan
    except Exception:
        return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
    awal = penggunaan.potret()
    nyata: list[dict] = []
    for t in temuan:
        if t.get("severity") in ("medium", "high", "critical"):
            nyata.append(t)
            continue
        putusan, _ = ai_conf.arbitrase_paparan(
            {"jenis": jenis, "template_id": t.get("template_id"), "nama": t.get("nama"),
             "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path})
        if putusan and putusan.get("sensitif"):
            nyata.append(t)
    pakai = penggunaan.selisih(awal)
    if pakai.get("panggilan"):
        ctx.catat("info", f"[AI] adjudikasi {jenis}: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
    return nyata


@check("conf.debug_mode", engine="nuclei")
class CekModeDebug:
    """Mode/halaman debug kerangka kerja (Flask/Werkzeug/Symfony/Laravel/actuator) nonaktif."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = _nuclei_paparan(
                ctx, metode,
                tags="exposure,debug,misconfig,config",
                kata=("debug", "whoops", "werkzeug", "symfony", "laravel", "rails", "flask", "django",
                      "stacktrace", "trace", "actuator", "phpinfo", "env", "profiler", "_debugbar"),
                jenis="mode_debug", label="halaman/mode debug kerangka kerja")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("exposure.default_sample_pages", engine="nuclei")
class CekHalamanDefault:
    """Halaman default/sampel/instalasi bawaan server tidak tersedia."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = _nuclei_paparan(
                ctx, metode,
                tags="exposure,default-login,misconfig,tech,panel",
                kata=("default", "sample", "example", "welcome", "it-works", "iisstart", "apache2",
                      "nginx-default", "test-page", "installer", "install", "setup", "phpinfo", "server-status"),
                jenis="halaman_default", label="halaman default/sampel/instalasi")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("exposure.config_vcs_files", engine="nuclei")
class CekBerkasKonfigVcs:
    """Berkas konfigurasi/VCS (.env, .git, konfig) tidak dapat diakses."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = _nuclei_paparan(
                ctx, metode,
                tags="exposure,config,files,misconfig",
                kata=(".env", ".git", ".svn", ".hg", "git-config", "gitexposed", "web.config", "wp-config",
                      ".htaccess", "docker-compose", ".dockerenv", "config", ".ds_store", ".npmrc", ".aws"),
                jenis="berkas_konfig_vcs", label="berkas konfigurasi/VCS terekspos")
        hasil.durasi_ms = jam.durasi_ms
        return hasil
