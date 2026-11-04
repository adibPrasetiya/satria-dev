"""Fungsi 11 — File (FILE). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx, unggah/unduh) + satu engine nuclei:
  file.upload_size_limit       (11.1-T01) file di atas batas ukuran ditolak (intrusif)
  file.content_type_validation (11.2-T01) server memvalidasi ISI file, bukan hanya ekstensi/Content-Type
  file.filename_sanitization   (11.3-T01) nama file pengguna disanitasi (tak dipakai mentah)
  file.av_scanning             (11.4-T01) file uji EICAR ditolak/dikarantina
  file.metadata_stripped       (11.3-T02) file yang disajikan tak memuat metadata sensitif (EXIF GPS/path)
  file.download_headers        (11.5-T01) Content-Disposition attachment + X-Content-Type-Options nosniff
  file.extension_allowlist     (11.5-T02, engine nuclei) berkas konfig/sumber (.bak/.config/.sql) tak disajikan

Manual → asesor: manual.upload_quota (11.1-T02).

Anti-false-positif: verdict deterministik dari respons unggah/unduh nyata; kasus ambigu ditajamkan
AI (`ai/file.py`) yang tak memutus lulus/gagal. Prasyarat (endpoint unggah/unduh, akun) tak ada →
tidak_dapat_diverifikasi. Unggahan uji bersifat jinak (teks/EICAR penanda), bukan eksploit aktif.
"""

from __future__ import annotations

import re
import secrets
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, login_ambil
from .. import nuclei_client as nc

# String uji antivirus standar EICAR (bukan malware; dirancang untuk memicu deteksi AV).
_EICAR = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
_FIELD_UMUM = ("file", "files", "upload", "berkas", "image", "foto", "gambar",
               "document", "dokumen", "avatar", "attachment", "lampiran")
_TOLAK = {400, 413, 415, 422}  # kode penolakan unggahan yang jelas


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json
    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


def _eps_titik(ctx: ScanContext, titik: str) -> list[dict]:
    out = [e for e in ctx.endpoints if e.get("titik_uji") == titik and str(e.get("url") or "")]
    u = ctx.url_titik(titik)
    if u and not any(e.get("url") == u for e in out):
        mh = ctx.titik_uji[titik].metode_http if titik in ctx.titik_uji else ("POST" if titik == "unggah_file" else "GET")
        out.append({"url": u, "metode_http": mh, "request_fields": []})
    return out


def _field_file(ep: dict) -> str:
    for f in ep.get("request_fields") or []:
        nama = str((f or {}).get("nama") or "")
        tipe = str((f or {}).get("tipe") or "").lower()
        if nama and (tipe == "file" or (f or {}).get("lokasi") in ("file", "form") or nama.lower() in _FIELD_UMUM):
            return nama
    return "file"


def _login(ctx: ScanContext, metode: MetodeSpec):
    """Siapkan klien terautentikasi. Return (klien, akun) atau (None, HasilMetode_tdv)."""
    akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
    if akun is None or not akun.password:
        return None, _tdv(metode, "Membutuhkan akun uji untuk mengunggah berkas.")
    klien = buat_klien(ctx, follow_redirects=False, timeout=20.0)
    r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
    if not r["ok"]:
        klien.__exit__()
        return None, _tdv(metode, "Login akun uji gagal — tak dapat menguji unggahan berkas.")
    return klien, akun


def _unggah(klien, ep, metode: MetodeSpec, nama: str, isi, tipe: str):
    """Kirim satu file multipart. Return Response atau None (di luar lingkup / gagal koneksi)."""
    url = str(ep.get("url"))
    mh = str(ep.get("metode_http") or "POST").upper()
    field = _field_file(ep)
    try:
        return klien.kirim(mh, url, files={field: (nama, isi, tipe)},
                           judul_bukti=f"{metode.id} — unggah {nama} ({tipe})")
    except (LuarRuangLingkup, Exception):
        return None


def _ai_unggah(ctx, jenis: str, resp) -> bool | None:
    """AI: apakah unggahan diterima? None bila tak tersedia."""
    try:
        from ..ai import file as ai_file
        from ..ai import penggunaan
    except Exception:
        return None
    awal = penggunaan.potret()
    putusan, _ = ai_file.arbitrase_unggahan({"jenis": jenis, "status": resp.status_code, "cuplikan": (resp.text or "")[:800]})
    if putusan is None:
        return None
    pakai = penggunaan.selisih(awal)
    if pakai.get("panggilan"):
        ctx.catat("info", f"[AI] adjudikasi unggahan: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
    return bool(putusan.get("diterima"))


def _diterima(ctx, jenis: str, resp) -> bool:
    """True bila unggahan tampak DITERIMA/disimpan. 2xx = diterima; kode tolak jelas = tidak; sisanya AI."""
    if 200 <= resp.status_code < 300:
        return True
    if resp.status_code in _TOLAK:
        return False
    hasil = _ai_unggah(ctx, jenis, resp)
    return bool(hasil)  # None/False → anggap tidak diterima (konservatif, tak menuduh)


# =========================================================================== FILE-11.1-T01

@check("file.upload_size_limit")
class CekBatasUkuran:
    """File di atas batas ukuran ditolak server (profil intrusif)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_titik(ctx, "unggah_file")
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint unggah berkas hasil penemuan.")
            else:
                hasil = self._uji(ctx, metode, eps[0])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, ep) -> HasilMetode:
        maks_mb = int(metode.parameter.get("ukuran_maks_mb", 10) or 10)
        klien, akun = _login(ctx, metode)
        if klien is None:
            return akun  # HasilMetode tdv
        try:
            isi = b"A" * ((maks_mb + 1) * 1024 * 1024)  # 1 MB di atas batas
            ctx.langkah("unggah", f"Mengunggah berkas ~{maks_mb + 1} MB (di atas batas {maks_mb} MB)", ukuran_mb=maks_mb + 1)
            resp = _unggah(klien, ep, metode, f"satya-besar-{secrets.token_hex(3)}.bin", isi, "application/octet-stream")
            if resp is None:
                return _tdv(metode, "Gagal mengunggah berkas uji (koneksi/di luar lingkup).")
            bukti = list(klien.bukti)
        finally:
            klien.__exit__()
        diterima = 200 <= resp.status_code < 300
        ctx.langkah("evaluasi", f"Respons unggahan HTTP {resp.status_code}", diterima=diterima)
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Berkas di atas batas {maks_mb} MB DITERIMA (HTTP {resp.status_code}) — batas ukuran tidak ditegakkan.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Berkas di atas batas ditolak (HTTP {resp.status_code}).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== FILE-11.2-T01

@check("file.content_type_validation")
class CekValidasiKonten:
    """Server memvalidasi ISI file (magic bytes), bukan hanya ekstensi/Content-Type dari klien."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_titik(ctx, "unggah_file")
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint unggah berkas hasil penemuan.")
            else:
                hasil = self._uji(ctx, metode, eps[0])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, ep) -> HasilMetode:
        klien, akun = _login(ctx, metode)
        if klien is None:
            return akun
        try:
            # Nama & Content-Type MENGAKU gambar, tetapi isi jelas BUKAN gambar (skrip/teks).
            isi = b"<?php echo 'satya-uji'; ?>\nbukan-gambar"
            ctx.langkah("unggah", "Mengunggah berkas isi non-gambar ber-ekstensi .jpg + Content-Type image/jpeg")
            resp = _unggah(klien, ep, metode, f"satya-{secrets.token_hex(3)}.jpg", isi, "image/jpeg")
            if resp is None:
                return _tdv(metode, "Gagal mengunggah berkas uji (koneksi/di luar lingkup).")
            diterima = _diterima(ctx, "tipe konten tidak sesuai isi", resp)
            bukti = list(klien.bukti)
        finally:
            klien.__exit__()
        ctx.langkah("evaluasi", f"Respons unggahan HTTP {resp.status_code}", diterima=diterima)
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Berkas non-gambar ber-ekstensi .jpg DITERIMA (HTTP {resp.status_code}) — server hanya mempercayai ekstensi/Content-Type klien.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Berkas dengan isi tak sesuai tipe ditolak (HTTP {resp.status_code}) — server memvalidasi isi.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== FILE-11.3-T01

@check("file.filename_sanitization")
class CekSanitasiNama:
    """Nama file dari pengguna disanitasi/diganti, tidak dipakai mentah (cegah path traversal/injeksi)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_titik(ctx, "unggah_file")
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint unggah berkas hasil penemuan.")
            else:
                hasil = self._uji(ctx, metode, eps[0])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, ep) -> HasilMetode:
        klien, akun = _login(ctx, metode)
        if klien is None:
            return akun
        tok = secrets.token_hex(4)
        nama_jahat = f"../../satya-{tok}<x>.txt"  # path traversal + karakter khusus
        try:
            ctx.langkah("unggah", "Mengunggah berkas dengan nama berbahaya (path traversal + karakter khusus)")
            resp = _unggah(klien, ep, metode, nama_jahat, b"satya-uji-nama", "text/plain")
            if resp is None:
                return _tdv(metode, "Gagal mengunggah berkas uji (koneksi/di luar lingkup).")
            teks = resp.text or ""
            bukti = list(klien.bukti)
        finally:
            klien.__exit__()
        # Nama mentah (dengan ../ atau <x>) muncul di respons → dipakai tanpa sanitasi.
        mentah = ("../" in teks and tok in teks) or (f"satya-{tok}<x>" in teks) or ("<x>.txt" in teks)
        if resp.status_code in _TOLAK:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Unggahan dengan nama berbahaya ditolak (HTTP {resp.status_code}).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        ctx.langkah("evaluasi", "Memeriksa pemakaian nama file mentah pada respons", nama_mentah=mentah)
        if mentah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Nama file berbahaya dari pengguna direfleksikan mentah (tanpa sanitasi) pada respons server.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if 200 <= resp.status_code < 300:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Unggahan diterima tetapi nama berbahaya tidak direfleksikan mentah (tampak disanitasi/diganti).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return _tdv(metode, f"Respons unggahan tak konklusif (HTTP {resp.status_code}) untuk menilai sanitasi nama.")


# =========================================================================== FILE-11.4-T01

@check("file.av_scanning")
class CekPindaiAv:
    """File uji EICAR ditolak atau dikarantina (indikasi pemindaian antivirus)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_titik(ctx, "unggah_file")
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint unggah berkas hasil penemuan.")
            else:
                hasil = self._uji(ctx, metode, eps[0])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, ep) -> HasilMetode:
        klien, akun = _login(ctx, metode)
        if klien is None:
            return akun
        try:
            ctx.langkah("unggah", "Mengunggah berkas uji antivirus standar (EICAR)")
            resp = _unggah(klien, ep, metode, f"satya-eicar-{secrets.token_hex(3)}.txt", _EICAR.encode(), "text/plain")
            if resp is None:
                return _tdv(metode, "Gagal mengunggah berkas uji (koneksi/di luar lingkup).")
            diterima = _diterima(ctx, "file uji EICAR", resp)
            bukti = list(klien.bukti)
        finally:
            klien.__exit__()
        ctx.langkah("evaluasi", f"Respons unggahan EICAR HTTP {resp.status_code}", diterima=diterima)
        if diterima:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"File uji EICAR DITERIMA/disimpan (HTTP {resp.status_code}) — tidak ada pemindaian antivirus.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"File uji EICAR ditolak/dikarantina (HTTP {resp.status_code}).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== FILE-11.5-T01

@check("file.download_headers")
class CekHeaderUnduh:
    """Unduhan memakai Content-Disposition attachment + X-Content-Type-Options nosniff."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = _eps_titik(ctx, "unduh_file")
            if not eps:
                hasil = _tdv(metode, "Tak ada endpoint unduh berkas hasil penemuan.")
            else:
                hasil = self._uji(ctx, metode, eps[:5])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        masalah: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=10.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    try:
                        r = klien.kirim("GET", url, judul_bukti=f"{metode.id} — header unduhan {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code in (401, 403):
                        continue
                    diuji += 1
                    cd = (r.headers.get("content-disposition") or "").lower()
                    nosniff = (r.headers.get("x-content-type-options") or "").strip().lower() == "nosniff"
                    path = urlsplit(url).path
                    if "attachment" not in cd:
                        masalah.append(f"{path}: tanpa Content-Disposition attachment")
                    if not nosniff:
                        masalah.append(f"{path}: tanpa X-Content-Type-Options nosniff")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal memeriksa header unduhan.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Tak ada endpoint unduh yang dapat dihubungi tanpa autentikasi.")
        ctx.langkah("evaluasi", "Memeriksa header unduhan", diuji=diuji, masalah=masalah or ["aman"])
        if masalah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Header unduhan tidak aman pada {len(masalah)} respons: {'; '.join(masalah[:3])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Unduhan memakai attachment + nosniff pada {diuji} berkas.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== FILE-11.3-T02

_RX_PATH = re.compile(rb"[A-Za-z]:\\\\|/Users/|/home/[\w.-]+/|/var/www/")


@check("file.metadata_stripped")
class CekMetadataBersih:
    """Berkas gambar yang disajikan tak memuat metadata sensitif (EXIF GPS / path sistem)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            eps = [e for e in _eps_titik(ctx, "unduh_file")
                   if re.search(r"\.(jpe?g|png|tiff?)(\?|$)", str(e.get("url") or ""), re.IGNORECASE)]
            if not eps:
                hasil = _tdv(metode, "Tak ada berkas gambar yang disajikan (unduh_file) untuk diperiksa metadatanya.")
            else:
                hasil = self._uji(ctx, metode, eps[:3])
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, eps) -> HasilMetode:
        temuan: list[str] = []
        diuji = 0
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=10.0) as klien:
                for ep in eps:
                    url = str(ep.get("url"))
                    try:
                        r = klien.kirim("GET", url, judul_bukti=f"{metode.id} — unduh gambar {urlsplit(url).path}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        continue
                    if r.status_code != 200:
                        continue
                    diuji += 1
                    kat = self._exif(r.content if hasattr(r, "content") else (r.text or "").encode("latin-1", "ignore"))
                    if kat:
                        temuan.append(f"{urlsplit(url).path}: {', '.join(kat)}")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal memeriksa metadata berkas.", f"{type(e).__name__}: {e}")

        if not diuji:
            return _tdv(metode, "Berkas gambar tak dapat diunduh untuk pemeriksaan metadata.")
        ctx.langkah("evaluasi", "Memeriksa metadata sensitif pada berkas gambar", diuji=diuji, temuan=temuan or ["bersih"])
        if temuan:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Berkas gambar memuat metadata sensitif: {'; '.join(temuan[:2])}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Berkas gambar pada {diuji} berkas tidak memuat GPS/path sensitif pada metadata.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    @staticmethod
    def _exif(data: bytes) -> list[str]:
        """Metadata sensitif pada gambar: koordinat GPS atau path sistem (konservatif, minim FP)."""
        blob = data[:300000]
        kat = []
        if b"Exif" in blob[:4000] or b"Exif\x00\x00" in blob:
            if b"GPSLatitude" in blob or b"GPSInfo" in blob or re.search(rb"GPS\x00", blob):
                kat.append("GPS (EXIF)")
        if _RX_PATH.search(blob):
            kat.append("path sistem")
        return kat


# =========================================================================== FILE-11.5-T02 (nuclei)

_TAG_EXT = "exposure,config,files,misconfig,backup"
_KATA_EXT = (".bak", ".config", ".sql", ".env", ".inc", ".old", ".swp", ".ini", ".conf", ".yml",
             ".yaml", "source", "sourcecode", "git", ".svn", "web.config", "wp-config", ".dockerfile")


@check("file.extension_allowlist", engine="nuclei")
class CekEkstensiDisajikan:
    """Berkas konfigurasi/sumber (mis. .bak/.config/.sql) tidak disajikan server."""

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
        ctx.langkah("pindai_nuclei", "Memindai berkas konfig/sumber yang disajikan (nuclei)", target=ctx.base_url)
        try:
            temuan = nc.jalankan(ctx.base_url, tags=_TAG_EXT, kata_relevan=_KATA_EXT)
        except Exception as e:
            return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
        if not temuan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tak ada berkas konfigurasi/sumber yang disajikan terdeteksi.",
                               detail=metode.kriteria_lulus)
        nyata = self._saring(ctx, temuan)
        bukti = [_bukti_dok(f"{metode.id} — temuan berkas konfig/sumber (nuclei)", {"temuan": temuan[:10]})]
        ctx.langkah("evaluasi", "Menilai temuan berkas konfig/sumber", total=len(temuan), sensitif=len(nyata))
        if nyata:
            daftar = ", ".join(urlsplit(t.get("url", "")).path for t in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} berkas konfig/sumber disajikan: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai berkas konfig/sumber sensitif.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring(self, ctx, temuan: list[dict]) -> list[dict]:
        try:
            from ..ai import file as ai_file
            from ..ai import penggunaan
        except Exception:
            return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for t in temuan:
            if t.get("severity") in ("medium", "high", "critical"):
                nyata.append(t)
                continue
            putusan, _ = ai_file.arbitrase_paparan_ekstensi(
                {"template_id": t.get("template_id"), "nama": t.get("nama"),
                 "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path})
            if putusan and putusan.get("sensitif"):
                nyata.append(t)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] adjudikasi berkas ekstensi: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata
