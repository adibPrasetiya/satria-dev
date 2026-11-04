"""Fungsi 7 — Proteksi Data (DATA). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx) + satu engine nuclei:
  headers.cache_control_sensitive (7.2-T01) halaman terautentikasi memakai Cache-Control no-store
  input.unexpected_parameters     (7.4-T01) parameter privilese tambahan diabaikan/ditolak (mass assignment)
  input.duplicate_parameters      (7.4-T02) parameter duplikat ditangani konsisten (tak crash)
  exposure.backup_files           (7.5-T01, engine nuclei) berkas cadangan/dump DB tak terunduh publik

Sudah ada (tak ditulis ulang): data.browser_storage (playwright, 7.2-T02).
Manual → asesor: data_classification (7.1), data_exchange_audit (7.3), data_at_rest (7.5-T02),
data_export_delete (7.6), memory_cleanup (7.7).

Anti-false-positif: verdict deterministik; mass-assignment hanya GAGAL bila atribut privilese
BENAR-benar direfleksikan (penanda unik). Kasus ambigu ditajamkan AI (`ai/data.py`), yang tak
memutus lulus/gagal. Bukti kurang/tak terjangkau → tidak_dapat_diverifikasi.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, login_ambil
from .. import nuclei_client as nc


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json
    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


def _eps_api(ctx: ScanContext, n: int = 10, metode_http: tuple = ()) -> list[dict]:
    out: list[dict] = []
    for ep in ctx.endpoints:
        if str(ep.get("lapisan") or "api").lower() != "api":
            continue
        if not str(ep.get("url") or ""):
            continue
        if metode_http and str(ep.get("metode_http") or "GET").upper() not in metode_http:
            continue
        out.append(ep)
        if len(out) >= n:
            break
    return out


# =========================================================================== DATA-7.2-T01

@check("headers.cache_control_sensitive")
class CekCacheSensitif:
    """Halaman terautentikasi memakai Cache-Control no-store (cegah caching data dikecualikan)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            url = ctx.url_titik("area_terautentikasi")
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if url is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "area_terautentikasi" tidak tersedia.')
            elif akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk mengakses halaman terautentikasi.")
            else:
                hasil = self._uji(ctx, metode, url, akun)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, url, akun) -> HasilMetode:
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
                if not r["ok"]:
                    return _tdv(metode, "Login akun uji gagal — tak dapat memeriksa halaman terautentikasi.")
                resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — Cache-Control halaman terautentikasi")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL di luar host yang diizinkan.", str(e))
        except Exception as e:
            return _tdv(metode, "Gagal memeriksa Cache-Control halaman terautentikasi.", f"{type(e).__name__}: {e}")

        cc = (resp.headers.get("cache-control") or "").lower()
        ctx.langkah("evaluasi", f"Cache-Control: '{cc or 'kosong'}'", no_store="no-store" in cc)
        if "no-store" in cc:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Halaman terautentikasi memakai Cache-Control no-store ('{cc}').",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="gagal",
                           ringkasan=f"Halaman terautentikasi tanpa Cache-Control no-store (sekarang: '{cc or 'tidak ada'}') — berisiko tersimpan di cache.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== DATA-7.4-T01

_PRIV = {"role": None, "is_admin": True, "isAdmin": True, "admin": True, "is_verified": True,
         "verified": True, "is_superuser": True, "balance": 987654321}


@check("input.unexpected_parameters")
class CekParameterTakTerduga:
    """Mass assignment: atribut privilese tambahan harus diabaikan/ditolak, bukan direfleksikan."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in _eps_api(ctx, 30, ("POST", "PUT", "PATCH"))
                   if any((f or {}).get("lokasi") == "body" for f in (e.get("request_fields") or []))]
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint penerima body (form_input) untuk uji mass assignment.")
            else:
                hasil = self._uji(ctx, metode, eps[:5])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        sentinel = "satyaprobe" + secrets.token_hex(4)
        injeksi = dict(_PRIV)
        injeksi["role"] = sentinel
        diterima: list[str] = []
        lulus_n = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    mh = str(ep.get("metode_http") or "POST").upper()
                    fields = [str((f or {}).get("nama")) for f in (ep.get("request_fields") or []) if (f or {}).get("lokasi") == "body"]
                    body = {f: "satya-uji" for f in fields if f not in injeksi}
                    body.update(injeksi)
                    try:
                        r = klien.kirim(mh, url, json=body, judul_bukti=f"{metode.id} — parameter privilese {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code in (401, 403):
                        continue
                    if self._direfleksikan(r, sentinel):
                        diterima.append(f"{urlsplit(url).path} (HTTP {r.status_code})")
                    elif 200 <= r.status_code < 300:
                        lulus_n += 1
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji parameter tak terduga.", f"{type(e).__name__}: {e}")

        ctx.langkah("evaluasi", "Menyuntik atribut privilese tambahan", diterima=diterima or ["tidak"], lulus=lulus_n)
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Atribut privilese tambahan DIREFLEKSIKAN server (mass assignment) pada: {', '.join(diterima[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if lulus_n:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Parameter privilese tambahan diabaikan pada {lulus_n} endpoint (tidak direfleksikan).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return _tdv(metode, "Endpoint menolak request (mis. butuh field valid lain) — mass assignment tak dapat dipastikan di sini.")

    def _direfleksikan(self, resp, sentinel: str) -> bool:
        """Atribut privilese direfleksikan? Cek sentinel role + nilai boolean/balance privilese pada respons."""
        teks = (resp.text or "")
        if sentinel in teks:
            return True
        low = teks.lower().replace(" ", "")
        if "987654321" in low:
            return True
        for k in ("is_admin", "isadmin", "is_superuser", "is_verified"):
            if f'"{k}":true' in low:
                # Tie-breaker AI bila ragu (respons besar/echo generik) — degradasi anggun.
                hasil = self._ai(resp, sentinel)
                return True if hasil is None else hasil
        return False

    def _ai(self, resp, sentinel) -> bool | None:
        try:
            from ..ai import data as ai_data
            from ..ai import penggunaan  # noqa: F401
        except Exception:
            return None
        putusan, _ = ai_data.arbitrase_mass_assignment(
            {"disuntik": list(_PRIV.keys()), "status": resp.status_code, "cuplikan": (resp.text or "")[:800]})
        return None if putusan is None else bool(putusan.get("diterima"))


# =========================================================================== DATA-7.4-T02

@check("input.duplicate_parameters")
class CekParameterDuplikat:
    """Parameter duplikat ditangani konsisten tanpa crash/efek samping (bukan 5xx)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_api(ctx, 20, ("GET",))
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint API (GET) untuk uji parameter duplikat.")
            else:
                hasil = self._uji(ctx, metode, eps[:6])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        crash: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for ep in eps:
                    url = self._duplikat(str(ep.get("url")))
                    try:
                        r = klien.kirim("GET", url, judul_bukti=f"{metode.id} — parameter duplikat {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    diuji += 1
                    if r.status_code >= 500:
                        crash.append(f"{urlsplit(url).path} (HTTP {r.status_code})")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal menguji parameter duplikat.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Endpoint tak dapat dihubungi untuk uji parameter duplikat.")
        ctx.langkah("evaluasi", "Mengirim parameter duplikat", diuji=diuji, crash=crash or ["tidak"])
        if crash:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Parameter duplikat menyebabkan error server (5xx) pada: {', '.join(crash[:3])} — penanganan tidak konsisten.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Parameter duplikat ditangani tanpa crash pada {diuji} endpoint.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    @staticmethod
    def _duplikat(url: str) -> str:
        """Gandakan satu parameter query (atau tambahkan parameter ganda) untuk uji HPP."""
        s = urlsplit(url)
        q = parse_qsl(s.query, keep_blank_values=True)
        if q:
            k, v = q[0]
            q = q + [(k, v)]  # duplikat parameter pertama
        else:
            q = [("satya_dup", "1"), ("satya_dup", "2")]
        return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q), ""))


# =========================================================================== DATA-7.5-T01 (nuclei)

_TAG_BACKUP = "backup,exposure,files,config,misconfig"
_KATA_BACKUP = ("backup", ".bak", ".sql", ".zip", ".tar", ".gz", ".dump", ".old", "database", "db-dump",
                "mysqldump", "sql-dump", "dbbackup", ".7z", ".rar", "~", ".swp")


@check("exposure.backup_files", engine="nuclei")
class CekPaparanBackup:
    """Berkas cadangan/dump basis data/arsip tidak dapat diunduh dari web."""

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
        ctx.langkah("pindai_nuclei", "Memindai paparan berkas cadangan/dump (nuclei)", target=ctx.base_url)
        try:
            temuan = nc.jalankan(ctx.base_url, tags=_TAG_BACKUP, kata_relevan=_KATA_BACKUP)
        except Exception as e:
            return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
        if not temuan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tak ada berkas cadangan/dump yang dapat diunduh terdeteksi.",
                               detail=metode.kriteria_lulus)
        nyata = self._saring(ctx, temuan)
        bukti = [_bukti_dok(f"{metode.id} — temuan berkas cadangan (nuclei)", {"temuan": temuan[:10]})]
        ctx.langkah("evaluasi", "Menilai temuan berkas cadangan", total=len(temuan), sensitif=len(nyata))
        if nyata:
            daftar = ", ".join(urlsplit(t.get("url", "")).path for t in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} berkas cadangan/dump dapat diunduh: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai berkas cadangan sensitif.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring(self, ctx, temuan: list[dict]) -> list[dict]:
        try:
            from ..ai import data as ai_data
            from ..ai import penggunaan
        except Exception:
            return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for t in temuan:
            if t.get("severity") in ("medium", "high", "critical"):
                nyata.append(t)
                continue
            putusan, _ = ai_data.arbitrase_paparan_backup(
                {"template_id": t.get("template_id"), "nama": t.get("nama"),
                 "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path})
            if putusan and putusan.get("sensitif"):
                nyata.append(t)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] adjudikasi berkas cadangan: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata
