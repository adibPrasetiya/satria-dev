"""Fungsi 6 — Penanganan Error dan Pencatatan Log (ERRL). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx) + satu engine nuclei:
  error.verbose_messages       (6.1-T01) halaman 4xx/5xx tak membocorkan detail teknis
  error.generic_login_message  (6.1-T02) pesan error login generik (tak membedakan user/sandi)
  error.unhandled_exception    (6.2-T01) input tak terduga → error terkendali, bukan crash/debug
  time.server_clock_drift      (6.7-T01) selisih header Date server dalam toleransi
  exposure.log_files           (6.5-T01, engine nuclei) file log tak dapat diunduh publik

Manual (→ asesor, tak ditulis): manual.log_sensitive_data (6.3), manual.log_coverage (6.4),
manual.log_protection (6.5-T02), manual.log_injection_protection (6.6).

Anti-false-positif: deteksi deterministik (regex pola kebocoran yang spesifik); kasus ambigu
ditajamkan AI (`ai/errl.py`) yang menjawab faktual, TIDAK memutus lulus/gagal. Bukti kurang /
tak terjangkau → tidak_dapat_diverifikasi. Request read-safe (GET path acak, login gagal 1x).
"""

from __future__ import annotations

import re
import secrets
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien
from .. import nuclei_client as nc

# Pola kebocoran detail teknis (spesifik agar minim positif palsu).
_POLA = {
    "stack_trace": re.compile(
        r"(Traceback \(most recent call last\)|Exception in thread|\bat [\w.$]+\([\w.]+\.(?:java|kt|scala):\d+\)"
        r"|\b(?:py|rb|php)\b.{0,12}\bline \d+|goroutine \d+ \[|System\.[\w.]+Exception|\bpanic:\s)",
        re.IGNORECASE),
    "sql": re.compile(
        r"(SQL syntax|SQLSTATE\[|ORA-\d{5}|You have an error in your SQL|Unclosed quotation mark"
        r"|PDOException|org\.hibernate|PG::\w+Error|psycopg2\.)", re.IGNORECASE),
    "debug_page": re.compile(
        r"(Whoops\b|Werkzeug|Flask Debugger|Symfony\\|Laravel\b|DEBUG\s*=\s*True|Rails\.application"
        r"|Microsoft OLE DB|ASP\.NET.{0,40}(?:Exception|Stack))", re.IGNORECASE),
    "path": re.compile(
        r"(/var/www/|/usr/share/nginx|/home/[\w.-]+/|/app/[\w./-]+\.(?:py|js|php|rb)"
        r"|[A-Za-z]:\\(?:inetpub|xampp|wwwroot|Users)\\)"),
}


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json
    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


def _deteksi_bocor(teks: str) -> list[str]:
    """Kategori kebocoran teknis yang terdeteksi pada badan respons (potongan awal)."""
    cuplik = (teks or "")[:8000]
    return [nama for nama, pola in _POLA.items() if pola.search(cuplik)]


def _ai_kebocoran(ctx: ScanContext, status: int, teks: str) -> bool | None:
    """Tie-breaker AI untuk respons error ambigu (mis. 5xx tanpa pola jelas). None bila tak tersedia."""
    try:
        from ..ai import errl as ai_errl
        from ..ai import penggunaan
    except Exception:
        return None
    awal = penggunaan.potret()
    putusan, info = ai_errl.arbitrase_kebocoran({"status": status, "cuplikan": (teks or "")[:1200]})
    if putusan is None:
        return None
    pakai = penggunaan.selisih(awal)
    if pakai.get("panggilan"):
        ctx.catat("info", f"[AI] adjudikasi kebocoran error: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
    return bool(putusan.get("bocor"))


# =========================================================================== ERRL-6.1-T01

@check("error.verbose_messages")
class CekPesanVerbose:
    """Halaman error (404 path acak, 400 query rusak) tak memuat stack trace/SQL/path/debug."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            host = urlsplit(ctx.base_url).hostname or ""
            if not host:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
            else:
                hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _sasaran(self, ctx: ScanContext) -> list[str]:
        b = urlsplit(ctx.base_url)
        acak = secrets.token_hex(6)
        return [
            urlunsplit((b.scheme, b.netloc, f"/satya-uji-404-{acak}", "", "")),           # 404
            urlunsplit((b.scheme, b.netloc, f"/satya-uji-{acak}", "id=%27%22%3C%3E", "")),  # query aneh
        ]

    def _uji(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        temuan: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for url in self._sasaran(ctx):
                    try:
                        r = klien.kirim("GET", url, judul_bukti=f"{metode.id} — error {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    kat = _deteksi_bocor(r.text)
                    if not kat and r.status_code >= 500:
                        if self._ai(ctx, r):
                            kat = ["ai_terindikasi"]
                    if kat:
                        temuan.append(f"{urlsplit(url).path} (HTTP {r.status_code}): {', '.join(kat)}")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji halaman error.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Tak ada respons error yang dapat diperiksa.")
        ctx.langkah("evaluasi", "Memeriksa kebocoran detail pada halaman error", diuji=diuji, temuan=temuan or ["bersih"])
        if temuan:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Halaman error membocorkan detail teknis: {'; '.join(temuan[:2])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Halaman error pada {diuji} probe tidak membocorkan stack trace/SQL/path/debug.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _ai(self, ctx, r) -> bool | None:
        return _ai_kebocoran(ctx, r.status_code, r.text)


# =========================================================================== ERRL-6.1-T02

@check("error.generic_login_message")
class CekPesanLoginGenerik:
    """Pesan error login sama untuk username salah maupun kata sandi salah (cegah enumerasi)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            url = ctx.url_titik("login")
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if not url:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="Endpoint login tidak tersedia.")
            elif akun is None or not akun.username:
                hasil = _tdv(metode, "Membutuhkan satu akun uji (username valid) untuk membandingkan pesan login.")
            else:
                hasil = self._uji(ctx, metode, url, akun)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, url, akun) -> HasilMetode:
        f = ctx.form_untuk("login")
        fu = f.field_username if f else "email"
        fp = f.field_password if f else "password"
        tipe = f.tipe_body if f else "json"
        mh = ctx.titik_uji["login"].metode_http if "login" in ctx.titik_uji else "POST"
        user_tak_ada = f"satya-uji-{secrets.token_hex(5)}@contoh.go.id"
        sandi = secrets.token_urlsafe(12)

        def kirim(username):
            body = {fu: username, fp: sandi}
            return klien.kirim(mh, url, json=body if tipe == "json" else None,
                               data=body if tipe == "form" else None,
                               judul_bukti=f"{metode.id} — login gagal ({'user tak ada' if username == user_tak_ada else 'sandi salah'})",
                               sandi_disamarkan=sandi)
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                ra = kirim(user_tak_ada)      # username tidak ada
                rb = kirim(akun.username)     # username valid, sandi salah
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL di luar host yang diizinkan.", str(e))
        except Exception as e:
            return _tdv(metode, "Gagal menguji pesan error login.", f"{type(e).__name__}: {e}")

        pa, pb = self._pesan(ra, user_tak_ada, akun.username), self._pesan(rb, user_tak_ada, akun.username)
        beda_status = ra.status_code != rb.status_code
        ctx.langkah("evaluasi", "Membandingkan pesan error login",
                    status=(ra.status_code, rb.status_code), beda_status=beda_status, beda_pesan=(pa != pb))
        if beda_status or pa != pb:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Pesan/status login berbeda untuk username tak ada vs sandi salah "
                                         f"(HTTP {ra.status_code} vs {rb.status_code}) — memungkinkan enumerasi pengguna.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan="Pesan error login generik & konsisten (tak membedakan username vs kata sandi salah).",
                           detail=metode.kriteria_lulus, bukti=bukti)

    @staticmethod
    def _pesan(resp, u1, u2) -> str:
        """Normalisasi pesan: ambil field pesan JSON / teks, buang nilai username agar banding adil."""
        teks = ""
        try:
            d = resp.json()
            if isinstance(d, dict):
                for k in ("message", "error", "msg", "detail", "error_description", "errors"):
                    v = d.get(k)
                    if isinstance(v, str):
                        teks = v
                        break
        except Exception:
            pass
        if not teks:
            teks = resp.text or ""
        teks = teks.strip().lower()[:300]
        for u in (u1.lower(), u2.lower()):
            teks = teks.replace(u, "<user>")
        return teks


# =========================================================================== ERRL-6.2-T01

@check("error.unhandled_exception")
class CekExceptionTakTertangani:
    """Input tak terduga (tipe salah) → error GENERIK terkendali, bukan crash 5xx + debug page."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in ctx.endpoints
                   if str(e.get("lapisan") or "api").lower() == "api"
                   and str(e.get("metode_http") or "").upper() in ("POST", "PUT", "PATCH")
                   and any((fd or {}).get("lokasi") == "body" for fd in (e.get("request_fields") or []))]
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint penerima body (form_input) untuk uji exception.")
            else:
                hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        temuan: list[str] = []
        diuji = 0
        # Payload tipe-salah: field body diisi objek bersarang/array (bukan skalar) → rawan TypeError.
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    mh = str(ep.get("metode_http") or "POST").upper()
                    fields = [str((fd or {}).get("nama")) for fd in (ep.get("request_fields") or []) if (fd or {}).get("lokasi") == "body"]
                    body = {(fields[0] if fields else "data"): {"satya": [1, {"x": None}]}}
                    try:
                        r = klien.kirim(mh, url, json=body, judul_bukti=f"{metode.id} — input tipe salah {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code in (401, 403):
                        continue
                    diuji += 1
                    kat = _deteksi_bocor(r.text)
                    if not kat and r.status_code >= 500 and _ai_kebocoran(ctx, r.status_code, r.text):
                        kat = ["ai_terindikasi"]
                    if kat:
                        # Bocor detail teknis (stack/SQL/path/debug) = berat.
                        temuan.append(f"{urlsplit(url).path} (HTTP {r.status_code}): {', '.join(kat)}")
                    elif r.status_code >= 500:
                        # 5xx pada input tipe salah = exception tak tertangani (seharusnya 400/422 terkendali).
                        temuan.append(f"{urlsplit(url).path} (HTTP {r.status_code}): crash tak terkendali")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji penanganan exception.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint penerima body tak dapat diuji tanpa autentikasi.")
        ctx.langkah("evaluasi", "Mengirim input tipe salah", diuji=diuji, temuan=temuan or ["terkendali"])
        if temuan:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Input tak terduga menimbulkan error tak terkendali/bocor pada: {'; '.join(temuan[:2])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Input tak terduga ditangani sebagai error generik terkendali pada {diuji} endpoint.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== ERRL-6.7-T01

@check("time.server_clock_drift")
class CekDriftJam:
    """Selisih header Date server terhadap jam worker (acuan) dalam toleransi."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            tol = int(metode.parameter.get("toleransi_detik", 60) or 60)
            try:
                with buat_klien(ctx, follow_redirects=True, timeout=8.0) as klien:
                    r = klien.kirim("GET", ctx.base_url, judul_bukti=f"{metode.id} — header Date")
                    bukti = list(klien.bukti)
            except LuarRuangLingkup as e:
                hasil = _tdv(metode, "URL di luar host yang diizinkan.", str(e))
            except Exception as e:
                hasil = _tdv(metode, "Gagal menghubungi aplikasi untuk membaca header Date.", f"{type(e).__name__}: {e}")
            else:
                hasil = self._nilai(ctx, metode, r, tol, bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx, metode, r, tol, bukti) -> HasilMetode:
        raw = r.headers.get("date", "")
        if not raw:
            return _tdv(metode, "Respons tidak menyertakan header Date — tak dapat menilai drift.")
        try:
            from datetime import datetime, timezone
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            drift = abs((datetime.now(timezone.utc) - dt).total_seconds())
        except Exception as e:
            return _tdv(metode, f"Header Date tidak dapat diurai: '{raw}'.", str(e))
        ctx.langkah("evaluasi", f"Selisih waktu server {int(drift)} dtk (toleransi {tol})", drift=int(drift), toleransi=tol)
        if drift > tol:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Selisih jam server {int(drift)} detik melebihi toleransi {tol} detik (Date: {raw}).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Selisih jam server {int(drift)} detik dalam toleransi {tol} detik.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== ERRL-6.5-T01 (nuclei)

_TAG_LOG = "exposure,logs,files,config,misconfig"
_KATA_LOG = ("log", ".log", "access.log", "error.log", "debug.log", "laravel.log", "logs", "log4j", "catalina", "application.log")


@check("exposure.log_files", engine="nuclei")
class CekPaparanLog:
    """File log aplikasi tidak dapat diunduh dari web root."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            host = urlsplit(ctx.base_url).hostname or ""
            if not host:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
            elif not nc.tersedia():
                hasil = _tdv(metode, "Biner nuclei belum terpasang pada worker — diserahkan asesor.",
                             "Pasang nuclei + `nuclei -update-templates` untuk mengotomasi uji ini.")
            else:
                hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode) -> HasilMetode:
        ctx.langkah("pindai_nuclei", "Memindai paparan file log (nuclei)", target=ctx.base_url)
        try:
            temuan = nc.jalankan(ctx.base_url, tags=_TAG_LOG, kata_relevan=_KATA_LOG)
        except Exception as e:
            return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
        if not temuan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tak ada file log yang dapat diunduh dari web root terdeteksi.",
                               detail=metode.kriteria_lulus)
        nyata = self._saring(ctx, temuan)
        bukti = [_bukti_dok(f"{metode.id} — temuan file log (nuclei)", {"temuan": temuan[:10]})]
        ctx.langkah("evaluasi", "Menilai temuan file log", total=len(temuan), sensitif=len(nyata))
        if nyata:
            daftar = ", ".join(urlsplit(t.get("url", "")).path for t in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} file log dapat diakses publik: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai file log sensitif.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring(self, ctx, temuan: list[dict]) -> list[dict]:
        try:
            from ..ai import errl as ai_errl
            from ..ai import penggunaan
        except Exception:
            return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for t in temuan:
            if t.get("severity") in ("medium", "high", "critical"):
                nyata.append(t)
                continue
            putusan, _ = ai_errl.arbitrase_paparan_log(
                {"template_id": t.get("template_id"), "nama": t.get("nama"),
                 "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path})
            if putusan and putusan.get("sensitif"):
                nyata.append(t)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] adjudikasi file log: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata
