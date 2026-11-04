"""Fungsi 5 — Kriptografi pada Verifikasi Statis (CRYP). Lihat katalog `controls/bssn_web.yaml`.

Check engine custom (httpx) + sslyze + nuclei:
  tls.key_and_algorithms      (5.1-T01, sslyze) kunci & algoritma tanda tangan sertifikat ≥ minimum
  crypto.client_token_integrity (5.2-T01) token/cookie bertanda tangan yang dimodifikasi ditolak
  crypto.exposed_secrets      (5.3-T01, nuclei) kunci/API key/rahasia tak terekspos di aset publik
  crypto.token_randomness     (5.4-T01) token aplikasi (sesi/CSRF/reset) acak, tak berpola/berurutan

Manual → asesor: manual.crypto_compliance (5.1-T02), manual.key_management (5.3-T02).

Anti-false-positif: verdict deterministik dari sertifikat/respons/sampel token nyata; temuan nuclei
low/info ditajamkan AI (`ai/kriptografi.py`) yang tak memutus lulus/gagal.
"""

from __future__ import annotations

import math
import re
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, hosts_target, login_ambil
from .. import nuclei_client as nc
from .. import sslyze_client as ssl

# Ambang minimum kriptografi (ASVS V6.2): RSA ≥ 2048, EC ≥ 256; hash tanda tangan ≥ SHA-256.
_RSA_MIN = 2048
_EC_MIN = 256
_HASH_LEMAH = re.compile(r"\b(md5|sha1|sha-1)\b", re.IGNORECASE)
_COOKIE_SESI = re.compile(r"(session|sid|sess|jsessionid|phpsessid|connect\.sid|laravel_session|auth|token)", re.IGNORECASE)


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _bukti_dok(judul: str, data: dict) -> Bukti:
    import json
    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


def _scan_tls(ctx: ScanContext, metode: MetodeSpec):
    host, port = ssl.host_port(ctx.base_url)
    if not host:
        return None, HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
    izin = hosts_target(ctx)
    if izin and host not in izin:
        return None, _tdv(metode, "Host di luar lingkup yang diizinkan.")
    if not ssl.aktif():
        return None, _tdv(metode, "Engine sslyze dinonaktifkan (SSLYZE_ENABLE=0).")
    if not ssl.tersedia():
        return None, _tdv(metode, "Paket sslyze belum terpasang pada worker — diserahkan asesor.")
    hasil = ssl.pindai(ctx.base_url)
    if not hasil.get("ok"):
        return None, _tdv(metode, f"Tidak dapat menjabat TLS pada {host}:{port}.", str(hasil.get("galat") or ""))
    return hasil, None


# =========================================================================== CRYP-5.1-T01

@check("tls.key_and_algorithms", engine="sslyze")
class CekKunciAlgoritma:
    """Ukuran kunci publik & algoritma tanda tangan sertifikat memenuhi batas minimum."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                hasil = self._nilai(ctx, metode, scan)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx, metode, scan) -> HasilMetode:
        cert = scan.get("sertifikat") or {}
        if not cert.get("tersedia"):
            return _tdv(metode, "Server tidak menyajikan sertifikat yang dapat dianalisis.")
        tipe = cert.get("tipe_kunci")
        ukuran = cert.get("ukuran_kunci")
        alg = str(cert.get("algoritma_tanda_tangan") or "")
        bukti = [_bukti_dok(f"{metode.id} — kunci & tanda tangan", {k: cert.get(k) for k in
                 ("tipe_kunci", "ukuran_kunci", "kurva", "algoritma_tanda_tangan")})]
        masalah: list[str] = []
        if tipe == "RSA" and isinstance(ukuran, int) and ukuran < _RSA_MIN:
            masalah.append(f"kunci RSA {ukuran}-bit < {_RSA_MIN}")
        if tipe == "EC" and isinstance(ukuran, int) and ukuran < _EC_MIN:
            masalah.append(f"kunci EC {ukuran}-bit < {_EC_MIN}")
        if alg and _HASH_LEMAH.search(alg):
            masalah.append(f"tanda tangan lemah ({alg})")
        ctx.langkah("evaluasi", "Memeriksa kunci & algoritma tanda tangan", tipe=tipe, ukuran=ukuran, algoritma=alg, masalah=masalah or ["ok"])
        if masalah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Kriptografi sertifikat di bawah minimum: " + "; ".join(masalah) + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if not tipe or ukuran is None:
            return _tdv(metode, "Tipe/ukuran kunci sertifikat tak dapat ditentukan.")
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Kunci {tipe} {ukuran}-bit & tanda tangan {alg or '?'} memenuhi batas minimum.",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== CRYP-5.2-T01

def _rusak(nilai: str) -> str:
    """Modifikasi satu karakter token/cookie (untuk JWT: rusak segmen tanda tangan)."""
    if not nilai:
        return nilai
    if nilai.count(".") == 2:  # JWT: rusak signature
        seg = nilai.split(".")
        sig = seg[2] or "AAAA"
        seg[2] = sig[:-1] + ("B" if sig[-1:] != "B" else "C")
        return ".".join(seg)
    return nilai[:-1] + ("B" if nilai[-1:] != "B" else "C")


@check("crypto.client_token_integrity")
class CekIntegritasToken:
    """Token/cookie bertanda tangan sisi klien yang dimodifikasi harus ditolak server."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            url_area = ctx.url_titik("area_terautentikasi")
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "area_terautentikasi" tidak tersedia.')
            elif akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh token/cookie sah lebih dulu.")
            else:
                hasil = self._uji(ctx, metode, url_area, akun)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, url_area, akun) -> HasilMetode:
        try:
            with buat_klien(ctx) as k0:
                r = login_ambil(k0, ctx, akun, judul=f"{metode.id} — login untuk artefak sesi sah")
                token = r.get("token")
                cookie = r.get("cookie")
            if not r["ok"] or not (token or cookie):
                return _tdv(metode, "Tak ada token/cookie bertanda tangan sah yang diperoleh dari login.")
            host = urlsplit(ctx.base_url).hostname or ""
            with buat_klien(ctx) as k2:
                if token:
                    k2.pakai_token(_rusak(token))
                if cookie and cookie.get("name"):
                    try:
                        k2._klien.cookies.set(cookie["name"], _rusak(cookie.get("value", "")), domain=host)  # noqa: SLF001
                    except Exception:
                        pass
                resp = k2.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses dengan token/cookie dimodifikasi")
                bukti = list(k2.bukti)
        except (LuarRuangLingkup, Exception) as e:
            return _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")

        ctype = (resp.headers.get("content-type") or "").lower()
        ctx.langkah("evaluasi", f"Akses dengan artefak dimodifikasi → HTTP {resp.status_code}", status=resp.status_code)
        if resp.status_code in (401, 403):
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Token/cookie yang dimodifikasi ditolak server (HTTP 401/403) — integritas diverifikasi.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if resp.status_code == 200 and "text/html" not in ctype:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Token/cookie dimodifikasi tetap diterima (HTTP 200, {ctype or 'non-HTML'}) — integritas tidak diverifikasi.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
                           ringkasan=f"Respons dengan artefak dimodifikasi ambigu (HTTP {resp.status_code}, {ctype or 'tanpa tipe'}).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== CRYP-5.4-T01

@check("crypto.token_randomness")
class CekKeacakanToken:
    """Token yang diterbitkan aplikasi (cookie sesi) acak — tak berpola/berurutan, entropi memadai."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            n = min(int(metode.parameter.get("jumlah_sampel", 30) or 30), 24)
            sampel = self._kumpul(ctx, n)
            if len(set(sampel)) < 8:
                hasil = _tdv(metode, f"Hanya {len(set(sampel))} token unik terkumpul (butuh ≥8) — aplikasi tak menerbitkan cookie sesi baru per permintaan.")
            else:
                hasil = self._nilai(ctx, metode, sampel)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _kumpul(self, ctx: ScanContext, n: int) -> list[str]:
        """Kumpulkan nilai cookie sesi dari N permintaan GET dengan klien baru (tanpa cookie lama)."""
        sampel: list[str] = []
        sasaran = ctx.url_titik("login_page") or ctx.url_titik("login") or ctx.base_url
        for _ in range(n):
            try:
                with buat_klien(ctx, follow_redirects=False, timeout=6.0) as klien:
                    resp = klien.kirim("GET", sasaran, judul_bukti="")
            except (LuarRuangLingkup, Exception):
                break
            nilai = self._cookie_sesi(resp)
            if nilai:
                sampel.append(nilai)
        return sampel

    @staticmethod
    def _cookie_sesi(resp) -> str | None:
        try:
            raw_list = resp.headers.get_list("set-cookie")
        except Exception:
            sc = resp.headers.get("set-cookie")
            raw_list = [sc] if sc else []
        for raw in raw_list:
            nv = raw.split(";", 1)[0]
            if "=" not in nv:
                continue
            nama, nilai = nv.split("=", 1)
            if _COOKIE_SESI.search(nama.strip()) and len(nilai.strip()) >= 6:
                return nilai.strip()
        return None

    def _nilai(self, ctx, metode, sampel: list[str]) -> HasilMetode:
        uniq = list(dict.fromkeys(sampel))
        panjang = sum(len(t) for t in uniq) / len(uniq)
        entropi = sum(self._entropi(t) for t in uniq) / len(uniq)      # bit/karakter rata-rata
        prefix = self._prefix_bersama(uniq)
        min_len = min(len(t) for t in uniq)
        berurutan = self._berurutan(uniq)
        bukti = [_bukti_dok(f"{metode.id} — analisis keacakan token", {
            "jumlah_unik": len(uniq), "panjang_rata2": round(panjang, 1),
            "entropi_bit_per_char": round(entropi, 2), "prefix_bersama": prefix,
            "pola_berurutan": berurutan, "contoh": [t[:6] + "…" for t in uniq[:3]]})]
        masalah: list[str] = []
        if panjang < 16:
            masalah.append(f"token pendek (rata-rata {panjang:.0f} char)")
        if entropi < 3.0:
            masalah.append(f"entropi rendah ({entropi:.1f} bit/char)")
        if prefix >= 0.6 * min_len and min_len > 0:
            masalah.append("prefiks panjang sama (indikasi berbasis pencacah)")
        if berurutan:
            masalah.append("nilai tampak berurutan")
        ctx.langkah("evaluasi", "Menganalisis keacakan token", jumlah=len(uniq), entropi=round(entropi, 2), masalah=masalah or ["acak"])
        if masalah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Token aplikasi kurang acak: " + "; ".join(masalah) + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"{len(uniq)} token acak & berentropi memadai (rata-rata {panjang:.0f} char, {entropi:.1f} bit/char).",
                           detail=metode.kriteria_lulus, bukti=bukti)

    @staticmethod
    def _entropi(s: str) -> float:
        if not s:
            return 0.0
        frek = {c: s.count(c) for c in set(s)}
        return -sum((f / len(s)) * math.log2(f / len(s)) for f in frek.values())

    @staticmethod
    def _prefix_bersama(tokens: list[str]) -> int:
        t = sorted(tokens)
        a, b = t[0], t[-1]
        i = 0
        while i < min(len(a), len(b)) and a[i] == b[i]:
            i += 1
        return i

    @staticmethod
    def _berurutan(tokens: list[str]) -> bool:
        # Semua numerik & rentang kecil → counter.
        if all(t.isdigit() for t in tokens):
            nums = sorted(int(t) for t in tokens)
            return (nums[-1] - nums[0]) <= len(nums) * 50
        return False


# =========================================================================== CRYP-5.3-T01 (nuclei)

_TAG_RAHASIA = "exposure,token,secret,misconfig,config"
_KATA_RAHASIA = ("api-key", "apikey", "api_key", "secret", "token", "private-key", "privatekey", "private_key",
                 "aws", "jwt", "credential", "bearer", "access-key", "accesskey", "begin rsa", "begin private",
                 "gcp", "firebase", "slack", "stripe", "google-api")


@check("crypto.exposed_secrets", engine="nuclei")
class CekRahasiaTerekspos:
    """Kunci privat / API key / rahasia tidak terekspos di JavaScript atau berkas publik."""

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
        ctx.langkah("pindai_nuclei", "Memindai rahasia yang terekspos (nuclei)", target=ctx.base_url)
        try:
            temuan = nc.jalankan(ctx.base_url, tags=_TAG_RAHASIA, kata_relevan=_KATA_RAHASIA)
        except Exception as e:
            return _tdv(metode, "nuclei gagal dijalankan.", f"{type(e).__name__}: {e}")
        if not temuan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan="Tak ada kunci/API key/rahasia terekspos terdeteksi.",
                               detail=metode.kriteria_lulus)
        nyata = self._saring(ctx, temuan)
        bukti = [_bukti_dok(f"{metode.id} — temuan rahasia (nuclei)", {"temuan": temuan[:10]})]
        ctx.langkah("evaluasi", "Menilai temuan rahasia", total=len(temuan), sensitif=len(nyata))
        if nyata:
            daftar = ", ".join(f"{t.get('nama') or t.get('template_id')} @ {urlsplit(t.get('url','')).path}" for t in nyata[:3])
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(nyata)} rahasia terekspos di aset publik: {daftar}" + ("…" if len(nyata) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"nuclei menemukan {len(temuan)} sinyal tetapi tak ada yang dinilai rahasia sensitif.",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _saring(self, ctx, temuan: list[dict]) -> list[dict]:
        try:
            from ..ai import kriptografi as ai_cryp
            from ..ai import penggunaan
        except Exception:
            return [t for t in temuan if t.get("severity") in ("medium", "high", "critical")]
        awal = penggunaan.potret()
        nyata: list[dict] = []
        for t in temuan:
            if t.get("severity") in ("high", "critical"):
                nyata.append(t)
                continue
            putusan, _ = ai_cryp.arbitrase_rahasia(
                {"template_id": t.get("template_id"), "nama": t.get("nama"),
                 "severity": t.get("severity"), "path": urlsplit(t.get("url", "")).path})
            if putusan and putusan.get("sensitif"):
                nyata.append(t)
        pakai = penggunaan.selisih(awal)
        if pakai.get("panggilan"):
            ctx.catat("info", f"[AI] adjudikasi rahasia: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return nyata
