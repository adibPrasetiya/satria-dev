"""Fungsi 12 — Keamanan API dan Web Service (APIS). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx) + satu engine nuclei:
  api.cors_policy               (12.1-T01) CORS tidak memantulkan origin bebas / wildcard+credentials
  api.http_methods              (12.1-T02) TRACE & metode berbahaya nonaktif
  api.auth_required             (12.3-T01) endpoint non-publik menolak tanpa token (401/403)
  api.method_enforcement        (12.4-T01) metode tak didukung → 405 (bukan diproses)
  api.schema_validation         (12.5-T01) payload JSON rusak ditolak (400/422)
  api.content_type_enforcement  (12.5-T02) Content-Type salah ditolak (415)
  headers.api_security_headers  (12.6-T01) nosniff + Content-Type tepat + Cache-Control
  exposure.api_docs_debug       (12.2-T02, engine nuclei) dok API/endpoint debug tak terbuka publik

Sudah ditangani check lain (tak ditulis ulang): api.sensitive_in_uri (zap, 12.2-T01),
access.horizontal (12.3-T02), access.rate_limit (12.7-T01). manual.api_gateway_waf → asesor.

Anti-false-positif: verdict deterministik dari respons nyata; endpoint tak ada / tak terjangkau /
alat absen → `tidak_dapat_diverifikasi`. Request bersifat read-safe (metode non-mutasi; body sengaja
rusak/salah-tipe sehingga tak membuat data). AI (`ai/api.py`) hanya menajamkan auth_required &
exposure — tak memutus lulus/gagal.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien
from .. import nuclei_client as nc

_ORIGIN_UJI = "https://satya-cors-probe.example"
_METODE_PALSU = "SATYACHECK"  # metode HTTP tak ada → server benar membalas 405/501 (read-safe)
_METODE_AMAN = {"GET", "HEAD", "OPTIONS"}


# --------------------------------------------------------------------------- util

def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _eps_api(ctx: ScanContext, n: int = 10) -> list[dict]:
    """Sampel endpoint lapisan API dalam ruang lingkup (default: lapisan 'api')."""
    out: list[dict] = []
    for ep in ctx.endpoints:
        if str(ep.get("lapisan") or "api").lower() != "api":
            continue
        if not str(ep.get("url") or ""):
            continue
        out.append(ep)
        if len(out) >= n:
            break
    return out


def _punya_body(ep: dict) -> bool:
    return any((f or {}).get("lokasi") == "body" for f in (ep.get("request_fields") or []))


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json

    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


# =========================================================================== APIS-12.1-T01

@check("api.cors_policy")
class CekCors:
    """CORS: origin sembarang tidak dipantulkan; wildcard '*' tidak digabung credentials."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_api(ctx, 8)
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint API hasil penemuan untuk uji CORS.")
            else:
                hasil = self._uji(ctx, metode, eps)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        temuan: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    try:
                        r = klien.kirim("GET", url, headers={"Origin": _ORIGIN_UJI},
                                        judul_bukti=f"{metode.id} — CORS {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    acao = (r.headers.get("access-control-allow-origin") or "").strip()
                    acac = (r.headers.get("access-control-allow-credentials") or "").strip().lower()
                    path = urlsplit(url).path
                    if acao == _ORIGIN_UJI:
                        temuan.append(f"{path} memantulkan Origin sembarang" + (" + credentials" if acac == "true" else ""))
                    elif acao == "*" and acac == "true":
                        temuan.append(f"{path} memakai ACAO '*' digabung Allow-Credentials")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji kebijakan CORS.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Tak ada endpoint API yang dapat dihubungi untuk uji CORS.")
        ctx.langkah("evaluasi", "Memeriksa kebijakan CORS", diuji=diuji, temuan=temuan or ["aman"])
        if temuan:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"CORS terlalu longgar pada {len(temuan)} endpoint: {'; '.join(temuan[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"CORS aman pada {diuji} endpoint: origin sembarang tidak dipantulkan; tak ada '*'+credentials.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== APIS-12.1-T02

@check("api.http_methods")
class CekMetodeHttp:
    """TRACE (dan metode berbahaya) dinonaktifkan — mencegah Cross-Site Tracing."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            host = urlsplit(ctx.base_url).hostname or ""
            if not host:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
            else:
                hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode) -> HasilMetode:
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                try:
                    r = klien.kirim("TRACE", ctx.base_url, judul_bukti=f"{metode.id} — TRACE")
                except LuarRuangLingkup as e:
                    return _tdv(metode, "URL di luar host yang diizinkan.", str(e))
                except Exception as e:
                    # TRACE ditolak di lapisan koneksi → aman.
                    return HasilMetode(metode_id=metode.id, status="lulus",
                                       ringkasan=f"Metode TRACE tidak dilayani ({type(e).__name__}).", detail=metode.kriteria_lulus)
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji metode HTTP.", f"{type(e).__name__}: {e}")

        sc = r.status_code
        echo = "trace" in (r.text or "").lower()[:200] or "method: trace" in (r.text or "").lower()
        ctx.langkah("evaluasi", f"TRACE → HTTP {sc}", status=sc, echo=echo)
        if sc < 300 and (echo or "message/http" in (r.headers.get("content-type", "").lower())):
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Metode TRACE aktif (HTTP {sc}) dan memantulkan request — rawan Cross-Site Tracing.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if sc < 300:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Metode TRACE diproses (HTTP {sc}); seharusnya dinonaktifkan (405/501).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Metode TRACE dinonaktifkan (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== APIS-12.3-T01

@check("api.auth_required")
class CekAuthWajib:
    """Endpoint yang (menurut penemuan) butuh autentikasi harus menolak request tanpa token (401/403)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            # Hanya endpoint ter-tandai butuh_autentikasi & metode aman (non-mutasi).
            kandidat = [e for e in _eps_api(ctx, 40)
                        if e.get("butuh_autentikasi") and str(e.get("metode_http") or "GET").upper() in _METODE_AMAN]
            if not kandidat:
                hasil = _tdv(metode, "Tak ada endpoint API ber-autentikasi (GET/HEAD) hasil penemuan untuk diuji.")
            else:
                hasil = self._uji(ctx, metode, kandidat[:10])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, kandidat) -> HasilMetode:
        bocor: list[dict] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:  # tanpa login → tanpa token
                for ep in kandidat:
                    url = str(ep.get("url"))
                    mh = str(ep.get("metode_http") or "GET").upper()
                    try:
                        r = klien.kirim(mh, url, judul_bukti=f"{metode.id} — {mh} {urlsplit(url).path} tanpa token")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    if 200 <= r.status_code < 300:
                        bocor.append({"metode": mh, "path": urlsplit(url).path,
                                      "fields": [str((f or {}).get("nama")) for f in (ep.get("request_fields") or [])][:8]})
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji kebutuhan autentikasi.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint ber-autentikasi tak dapat dihubungi tanpa token.")
        # Tajamkan: buang endpoint yang AI nilai memang publik (kurangi positif palsu).
        nyata = self._saring_publik(ctx, bocor)
        ctx.langkah("evaluasi", "Memeriksa pemberlakuan autentikasi", diuji=diuji, bocor=[b["path"] for b in nyata] or ["aman"])
        if nyata:
            daftar = ", ".join(f"{b['metode']} {b['path']}" for b in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} endpoint non-publik membalas data TANPA token: {daftar}"
                                         + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Seluruh {diuji} endpoint ber-autentikasi menolak request tanpa token (401/403).",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring_publik(self, ctx, bocor: list[dict]) -> list[dict]:
        """Buang endpoint yang AI nilai 'publik' dengan keyakinan tinggi (tie-breaker; degradasi anggun)."""
        if not bocor:
            return bocor
        try:
            from ..ai import api as ai_api
            from ..ai import penggunaan
        except Exception:
            return bocor
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for b in bocor:
            putusan, info = ai_api.klasifikasi_publik(
                {"metode": b["metode"], "path": b["path"], "fields": b["fields"]},
                kunci_cache=f"{b['metode']} {b['path']}",
            )
            if putusan and putusan.get("publik") and (putusan.get("keyakinan") or 0) >= 0.7:
                ctx.catat("info", f"[AI] {b['path']} dinilai publik — tak dihitung sebagai temuan.")
                continue
            nyata.append(b)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] klasifikasi endpoint: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata


# =========================================================================== APIS-12.4-T01

@check("api.method_enforcement")
class CekMetodeEnforcement:
    """Metode HTTP tak didukung ditolak (405), bukan diproses."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in _eps_api(ctx, 20) if str(e.get("metode_http") or "GET").upper() == "GET"]
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint API (GET) hasil penemuan untuk uji penegakan metode.")
            else:
                hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        diproses: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    try:
                        r = klien.kirim(_METODE_PALSU, url, judul_bukti=f"{metode.id} — metode tak dikenal {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    if 200 <= r.status_code < 300:
                        diproses.append(f"{urlsplit(url).path} (HTTP {r.status_code})")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji penegakan metode.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint tak dapat dihubungi untuk uji penegakan metode.")
        ctx.langkah("evaluasi", "Mengirim metode HTTP tak dikenal", diuji=diuji, diproses=diproses or ["ditolak"])
        if diproses:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Metode HTTP tak dikenal DIPROSES (bukan 405) pada: {', '.join(diproses[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Metode tak didukung ditolak pada {diuji} endpoint (tidak diproses).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== APIS-12.5-T01

@check("api.schema_validation")
class CekSkema:
    """Payload JSON rusak / tak sesuai skema ditolak (400/422), bukan diterima."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in _eps_api(ctx, 30)
                   if str(e.get("metode_http") or "").upper() in ("POST", "PUT", "PATCH") and _punya_body(e)]
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint API penerima body (POST/PUT/PATCH) hasil penemuan untuk uji skema.")
            else:
                hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        diterima: list[str] = []
        diuji = 0
        rusak = '{"satya_uji": '  # JSON sengaja rusak (tak mungkin membuat data valid)
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    mh = str(ep.get("metode_http") or "POST").upper()
                    try:
                        r = klien.kirim(mh, url, content=rusak, headers={"Content-Type": "application/json"},
                                        judul_bukti=f"{metode.id} — JSON rusak {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code in (401, 403):
                        continue  # butuh auth → tak dapat diuji di sini
                    diuji += 1
                    if 200 <= r.status_code < 300:
                        diterima.append(f"{urlsplit(url).path} (HTTP {r.status_code})")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji validasi skema.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint penerima body tak dapat diuji tanpa autentikasi.")
        ctx.langkah("evaluasi", "Mengirim payload JSON rusak", diuji=diuji, diterima=diterima or ["ditolak"])
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Payload JSON rusak DITERIMA (bukan 400/422) pada: {', '.join(diterima[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Payload JSON rusak ditolak (400/422) pada {diuji} endpoint.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== APIS-12.5-T02

@check("api.content_type_enforcement")
class CekContentType:
    """Content-Type request yang tidak sesuai ditolak (415)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in _eps_api(ctx, 30)
                   if str(e.get("metode_http") or "").upper() in ("POST", "PUT", "PATCH") and _punya_body(e)]
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint API penerima body untuk uji Content-Type.")
            else:
                hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        diterima: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    mh = str(ep.get("metode_http") or "POST").upper()
                    try:
                        r = klien.kirim(mh, url, content="satya-uji-teks-biasa",
                                        headers={"Content-Type": "text/plain"},
                                        judul_bukti=f"{metode.id} — Content-Type salah {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code in (401, 403):
                        continue
                    diuji += 1
                    if 200 <= r.status_code < 300:
                        diterima.append(f"{urlsplit(url).path} (HTTP {r.status_code})")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji penegakan Content-Type.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint penerima body tak dapat diuji tanpa autentikasi.")
        ctx.langkah("evaluasi", "Mengirim Content-Type tidak sesuai (text/plain)", diuji=diuji, diterima=diterima or ["ditolak"])
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Request Content-Type salah DITERIMA (bukan 415) pada: {', '.join(diterima[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Request Content-Type tidak sesuai ditolak pada {diuji} endpoint.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== APIS-12.6-T01

@check("headers.api_security_headers")
class CekHeaderApi:
    """Respons API: X-Content-Type-Options nosniff, Content-Type tepat, Cache-Control sesuai."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_api(ctx, 8) or [{"url": ctx.base_url, "metode_http": "GET"}]
            hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        masalah: list[str] = []
        catatan: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    try:
                        r = klien.kirim("GET", url, judul_bukti=f"{metode.id} — header {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    path = urlsplit(url).path
                    nosniff = (r.headers.get("x-content-type-options") or "").strip().lower() == "nosniff"
                    ct = (r.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    cache = (r.headers.get("cache-control") or "").lower()
                    badan_json = (r.text or "").lstrip()[:1] in ("{", "[")
                    if not nosniff:
                        masalah.append(f"{path}: tanpa X-Content-Type-Options: nosniff")
                    if badan_json and "json" not in ct:
                        masalah.append(f"{path}: respons JSON tetapi Content-Type '{ct or 'kosong'}'")
                    if badan_json and not any(k in cache for k in ("no-store", "no-cache", "private")):
                        catatan.append(f"{path}: Cache-Control tidak membatasi penyimpanan")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal memeriksa header keamanan API.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Tak ada endpoint API yang dapat dihubungi untuk memeriksa header.")
        detail = metode.kriteria_lulus + (f"\nCatatan Cache-Control: {'; '.join(catatan)}" if catatan else "")
        ctx.langkah("evaluasi", "Memeriksa header keamanan respons API", diuji=diuji, masalah=masalah or ["lengkap"])
        if masalah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Header keamanan API kurang pada {len(masalah)} respons: {'; '.join(masalah[:3])}.",
                               detail=detail, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Header keamanan API memadai pada {diuji} respons (nosniff + Content-Type tepat)."
                                     + (" Lihat catatan Cache-Control." if catatan else ""),
                           detail=detail, bukti=bukti)


# =========================================================================== APIS-12.2-T02 (nuclei)

@check("exposure.api_docs_debug", engine="nuclei")
class CekPaparanDok:
    """Dokumentasi API / endpoint debug (Swagger/OpenAPI/GraphQL/actuator/debug) tak terbuka publik."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            host = urlsplit(ctx.base_url).hostname or ""
            if not host:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
            elif not nc.tersedia():
                hasil = _tdv(metode, "Biner nuclei belum terpasang pada worker — diserahkan asesor.",
                             "Pasang: `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` lalu `nuclei -update-templates`.")
            else:
                hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode) -> HasilMetode:
        ctx.langkah("pindai_nuclei", "Memindai paparan dokumentasi/debug API (nuclei)", target=ctx.base_url)
        try:
            temuan = nc.jalankan(ctx.base_url)
        except Exception as e:
            return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
        if not temuan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tak ada dokumentasi API / endpoint debug terbuka terdeteksi.",
                               detail=metode.kriteria_lulus)
        nyata = self._saring(ctx, temuan)
        bukti = [_bukti_dok(f"{metode.id} — temuan paparan (nuclei)", {"temuan": temuan[:10]})]
        ctx.langkah("evaluasi", "Menilai temuan paparan", total=len(temuan), sensitif=len(nyata))
        if nyata:
            daftar = ", ".join(f"{t.get('nama') or t.get('template_id')} @ {urlsplit(t.get('url','')).path}" for t in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} paparan dok/debug API terbuka: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai paparan sensitif.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring(self, ctx, temuan: list[dict]) -> list[dict]:
        """Severity medium+ dianggap nyata; low/info ditajamkan AI (sensitif?). Degradasi anggun."""
        try:
            from ..ai import api as ai_api
            from ..ai import penggunaan
        except Exception:
            return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for t in temuan:
            if t.get("severity") in ("medium", "high", "critical"):
                nyata.append(t)
                continue
            putusan, _ = ai_api.arbitrase_exposure(
                {"template_id": t.get("template_id"), "nama": t.get("nama"),
                 "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path, "tags": t.get("tags")}
            )
            if putusan and putusan.get("sensitif"):
                nyata.append(t)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] adjudikasi paparan: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata
