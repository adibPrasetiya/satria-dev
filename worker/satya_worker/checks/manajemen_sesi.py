"""Fungsi keamanan Manajemen Sesi (SESS) — check engine custom.

Enam check andal + tiga diserahkan asesor (lihat katalog). Memakai artefak sesi dari
respons login: token (body) atau cookie sesi (Set-Cookie). Endpoint probe sesi =
`area_terautentikasi` (idealnya endpoint API yang 401 tanpa token, 200 dengan token).
"""

from __future__ import annotations

import base64
import json
import math
import secrets
import time
from collections import Counter
from datetime import datetime
from typing import Optional

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, ekstrak_sesi, login_ambil

# Pola token JWT (tiga segmen base64url).
import re as _re

_JWT = _re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "", bukti=None) -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=ringkasan, detail=detail, bukti=bukti or [])


def _akun_utama(ctx: ScanContext):
    return ctx.akun("akun_uji_1") or ctx.akun("utama")


def _entropi_bit(sampel: list[str]) -> float:
    """Perkiraan entropi (bit) = panjang rata-rata × entropi Shannon per karakter."""
    gabung = "".join(sampel)
    if not gabung:
        return 0.0
    freq = Counter(gabung)
    total = len(gabung)
    h = -sum((n / total) * math.log2(n / total) for n in freq.values())
    panjang_rata = sum(len(s) for s in sampel) / len(sampel)
    return panjang_rata * h


def _metode_titik(ctx: ScanContext, titik: str, default: str = "GET") -> str:
    t = ctx.titik_uji.get(titik)
    return (t.metode_http if t and t.metode_http else default).upper()


def _jwt_exp(tok: str) -> Optional[float]:
    """Baca klaim `exp` (epoch detik) dari payload JWT tanpa verifikasi tanda tangan."""
    try:
        bagian = tok.split(".")
        if len(bagian) < 2:
            return None
        p = bagian[1] + "=" * (-len(bagian[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(p.encode()))
        exp = data.get("exp")
        return float(exp) if isinstance(exp, (int, float)) else None
    except Exception:
        return None


def _ttl_sesi(r: dict) -> Optional[float]:
    """Perkiraan masa berlaku sesi (detik) dari klaim `exp` JWT atau Max-Age/Expires cookie.

    Ini batas ATAS masa hidup sesi (absolut), dipakai sebagai proksi untuk uji idle: worker
    tak bisa menunggu idle sungguhan, jadi hanya menyimpulkan bila sesi dibatasi waktu atau tidak.
    """
    tok = r.get("token")
    if tok and _JWT.match(tok):
        exp = _jwt_exp(tok)
        if exp is not None:
            return exp - time.time()
    c = r.get("cookie")
    if c:
        raw = f"{c.get('raw', '')} {c.get('flags', '')}"
        m = _re.search(r"max-age=(\d+)", raw, _re.IGNORECASE)
        if m:
            return float(m.group(1))
        e = _re.search(r"expires=([^;]+)", raw, _re.IGNORECASE)
        if e:
            try:
                from email.utils import parsedate_to_datetime

                dt = parsedate_to_datetime(e.group(1).strip())
                return (dt - datetime.now(dt.tzinfo)).total_seconds()
            except Exception:
                return None
    return None


def _fitur_token(r: dict) -> dict:
    """Ciri NON-sensitif token/cookie sesi untuk fingerprint (tanpa nilai asli)."""
    tok = r.get("token")
    c = r.get("cookie")
    if tok:
        n = len(tok)
        return {
            "wadah": "header",
            "format": "jwt" if _JWT.match(tok) else "opaque",
            "segmen": (tok.count(".") + 1) if "." in tok else 1,
            "panjang_kira": "<=16" if n <= 16 else "17-32" if n <= 32 else ">32",
            "ada_strip": "-" in tok,
        }
    if c:
        return {"wadah": "cookie", "nama_pola": c.get("name", ""), "atribut": c.get("flags", "")}
    return {"wadah": "tidak_ada"}


def _tie_break(check_id: str, metadata: dict, hasil_tdv: HasilMetode, *, peta: dict[str, str],
               kunci_cache: Optional[str] = None) -> HasilMetode:
    """Tajamkan hasil `tidak_dapat_diverifikasi` dengan AI tie-breaker (bila tersedia).

    AI hanya menjawab pertanyaan FAKTUAL; `peta` memetakan putusan faktual → status final.
    Putusan di luar `peta`, atau AI off/tak tersedia/gagal → kembalikan `hasil_tdv` apa adanya
    (degradasi anggun — hasil deterministik tetap utuh). AI tak pernah memutus lulus/gagal.
    """
    try:
        from ..ai import penggunaan
        from ..ai import sesi as ai_sesi
    except Exception:
        return hasil_tdv
    awal = penggunaan.potret()
    putusan, info = ai_sesi.arbitrase_sesi(check_id, metadata, kunci_cache=kunci_cache)
    if putusan is None:
        return hasil_tdv
    status = peta.get(str(putusan.get("putusan")))
    if status is None:
        return hasil_tdv  # putusan faktual tak memetakan ke vonis → tetap serahkan asesor
    pakai = penggunaan.selisih(awal)
    alasan = str(putusan.get("alasan") or "").strip()
    detail = (hasil_tdv.detail or "")
    detail += f"\n[AI tie-breaker] putusan={putusan.get('putusan')} · keyakinan={putusan.get('keyakinan')}"
    if alasan:
        detail += f" — {alasan}"
    if info.get("dari_cache"):
        detail += " (dari cache)"
    elif pakai.get("panggilan"):
        detail += f"\nAI: {pakai['panggilan']} panggilan, ±{pakai['token']} token."
    return HasilMetode(metode_id=hasil_tdv.metode_id, status=status,
                       ringkasan=(f"[AI] {alasan or putusan.get('putusan')}")[:300],
                       detail=detail, bukti=hasil_tdv.bukti, menunggu_tinjauan=True)


# =========================================================================== andal

@check("session.token_issued")
class CekTokenDiterbitkan:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk login, tetapi belum diisi.")
            elif ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login untuk cek penerbitan sesi")
                        bukti = list(klien.bukti)
                    if not r["ok"]:
                        hasil = _tdv(metode, "Gagal login dengan akun uji.", bukti=bukti)
                    elif r["token"] or r["cookie"]:
                        jenis = "token" if r["token"] else f"cookie '{r['cookie']['name']}'"
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Sesi dikelola dengan {jenis} setelah login.", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Login berhasil tetapi tak ada token/cookie sesi diterbitkan.", detail=metode.kriteria_lulus, bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.framework_fingerprint")
class CekFingerprintKerangka:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh token sesi.")
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — ambil token sesi")
                        bukti = list(klien.bukti)
                    if not r["ok"]:
                        hasil = _tdv(metode, "Gagal login dengan akun uji.", bukti=bukti)
                    elif r["cookie"] is not None:
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Cookie sesi '{r['cookie']['name']}' sesuai pola pengendali sesi kerangka kerja.", detail=metode.kriteria_lulus, bukti=bukti)
                    elif r["token"] and _JWT.match(r["token"]):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Token sesi berformat JWT standar (tiga segmen).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil_tdv = _tdv(metode, "Token sesi tak dikenali sebagai pola kerangka kerja umum; konfirmasi asesor (2.2-T02).", bukti=bukti)
                        fitur = _fitur_token(r)
                        kunci = "framework|" + "|".join(f"{k}={fitur[k]}" for k in sorted(fitur))
                        hasil = _tie_break("session.framework_fingerprint", {"ciri_sesi": fitur}, hasil_tdv,
                                           peta={"cocok_kerangka": "lulus"}, kunci_cache=kunci)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.token_entropy")
class CekEntropiToken:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk mengumpulkan sampel token.")
            else:
                n = int(metode.parameter.get("jumlah_sampel", 30))
                min_bit = float(metode.parameter.get("entropi_minimum_bit", 64))
                sampel: list[str] = []
                try:
                    with buat_klien(ctx) as klien:
                        for i in range(n):
                            r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — sampel token #{i + 1}")
                            if r["resp"] is not None and r["resp"].status_code == 429:
                                break
                            val = r["token"] or (r["cookie"]["value"] if r["cookie"] else None)
                            if val:
                                sampel.append(val)
                        bukti = list(klien.bukti)[:3]  # cukup beberapa bukti
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
                    hasil.durasi_ms = jam.durasi_ms
                    return hasil

                if len(sampel) < 5:
                    hasil = _tdv(metode, f"Sampel token tak cukup ({len(sampel)}) untuk analisis entropi.", bukti=bukti)
                elif all(_JWT.match(s) for s in sampel):
                    # Token JWT (stateless): keacakan ada pada tanda tangan, bukan session-ID acak.
                    # Analisis entropi session-ID tidak berlaku; sampel bisa identik bila iat sama.
                    hasil = _tdv(metode, "Token berformat JWT (stateless) — analisis entropi session-ID tidak berlaku; dikonfirmasi asesor.", bukti=bukti)
                else:
                    unik = len(set(sampel)) == len(sampel)
                    panjang_min = min(len(s) for s in sampel)
                    bit = _entropi_bit(sampel)
                    # Deteksi berurutan: banyak pasangan berbagi prefiks panjang.
                    prefiks = len({s[: max(1, panjang_min - 2)] for s in sampel})
                    berurutan = prefiks <= 2 and panjang_min < 24
                    if unik and panjang_min >= 16 and bit >= min_bit and not berurutan:
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"{len(sampel)} token unik, panjang ≥ {panjang_min}, entropi ~{bit:.0f} bit (≥ {min_bit:.0f}).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        alasan = []
                        if not unik:
                            alasan.append("token berulang")
                        if panjang_min < 16:
                            alasan.append(f"terlalu pendek ({panjang_min})")
                        if bit < min_bit:
                            alasan.append(f"entropi rendah (~{bit:.0f} bit)")
                        if berurutan:
                            alasan.append("berpola/berurutan")
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Token sesi lemah: {', '.join(alasan)}.", detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.rotation_on_login")
class CekRotasiSaatLogin:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk dua kali login.")
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r1 = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login pertama")
                    # Jeda >1 detik agar token berbasis waktu (mis. JWT iat per-detik) berbeda.
                    time.sleep(1.2)
                    with buat_klien(ctx) as klien2:
                        r2 = login_ambil(klien2, ctx, akun, judul=f"{metode.id} — login kedua")
                        bukti = list(klien2.bukti)
                    v1 = r1["token"] or (r1["cookie"]["value"] if r1["cookie"] else None)
                    v2 = r2["token"] or (r2["cookie"]["value"] if r2["cookie"] else None)
                    if not r1["ok"] or not r2["ok"] or not v1 or not v2:
                        hasil = _tdv(metode, "Gagal memperoleh token sesi pada dua login.", bukti=bukti)
                    elif v1 != v2:
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Token sesi berbeda antar login (sesi dirotasi, bukan statis).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Token sesi SAMA pada setiap login (tidak dirotasi).", detail=metode.kriteria_lulus, bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.reject_unknown_id")
class CekTolakTokenAsing:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            url = ctx.url_titik("area_terautentikasi")
            if url is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Endpoint sesi (area terautentikasi) tidak tersedia pada aplikasi.')
            else:
                palsu = secrets.token_urlsafe(24)
                try:
                    with buat_klien(ctx) as klien:
                        klien.pakai_token(palsu)  # Bearer palsu
                        resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — akses dengan token sesi palsu")
                        bukti = list(klien.bukti)
                    ctype = resp.headers.get("content-type", "").lower()
                    if resp.status_code in (401, 403):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Token sesi palsu ditolak (HTTP {resp.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
                    elif resp.status_code == 200 and "text/html" not in ctype:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Token palsu menghasilkan sesi terautentikasi (HTTP 200, {ctype or 'non-HTML'}).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil_tdv = _tdv(metode, f"HTTP {resp.status_code} (HTML) — perlu endpoint API sesi untuk memastikan; arahkan area terautentikasi ke API.", bukti=bukti)
                        teks = (resp.text or "").lower()
                        metadata = {
                            "status": resp.status_code,
                            "tipe_konten": ctype,
                            "panjang": len(resp.text or ""),
                            "ada_sinyal_login": any(k in teks for k in ("type=password", "name=password", "login", "masuk", "sign in")),
                        }
                        hasil = _tie_break("session.reject_unknown_id", metadata, hasil_tdv,
                                           peta={"publik": "lulus", "autentik": "gagal"})
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.cookie_flags")
class CekFlagCookie:
    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh cookie sesi.")
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — ambil cookie sesi")
                        bukti = list(klien.bukti)
                    if not r["ok"]:
                        hasil = _tdv(metode, "Gagal login dengan akun uji.", bukti=bukti)
                    elif r["cookie"] is None:
                        hasil = _tdv(metode, "Sesi berbasis token (bukan cookie) — atribut cookie tidak berlaku.", bukti=bukti)
                    else:
                        flags = r["cookie"]["flags"]
                        kurang = [f for f in ("secure", "httponly", "samesite") if f not in flags]
                        if not kurang:
                            hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Cookie sesi '{r['cookie']['name']}' memiliki Secure, HttpOnly, dan SameSite.", detail=metode.kriteria_lulus, bukti=bukti)
                        else:
                            hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Cookie sesi kurang atribut: {', '.join(kurang)}.", detail=metode.kriteria_lulus, bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =================================================================== semi-otomatis + AI

@check("session.logout_invalidates")
class CekLogoutInvalidasi:
    """SESS-2.4-T01 — login, pastikan sesi aktif, logout, lalu coba PAKAI ULANG sesi lama.

    Sesi lama ditolak (401/403) → lulus. Masih terautentikasi (200 non-HTML) → gagal.
    Respons HTML/redirect yang ambigu → serahkan tie-breaker AI (autentik/tak_autentik).
    """

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_logout = ctx.url_titik("logout")
            url_area = ctx.url_titik("area_terautentikasi")
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk login lalu logout.")
            elif url_logout is None or url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "logout" dan/atau "area_terautentikasi" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
                        if not r["ok"] or not (r["token"] or r["cookie"]):
                            hasil = _tdv(metode, "Gagal memperoleh sesi untuk uji logout.", bukti=list(klien.bukti))
                        else:
                            pre = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sebelum logout")
                            if pre.status_code != 200:
                                hasil = _tdv(metode, f"Sesi tak aktif sebelum logout (HTTP {pre.status_code}); tak dapat menguji invalidasi.", bukti=list(klien.bukti))
                            else:
                                klien.kirim(_metode_titik(ctx, "logout", "POST"), url_logout, judul_bukti=f"{metode.id} — logout")
                                post = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses dengan sesi lama setelah logout")
                                bukti = list(klien.bukti)
                                ctype = post.headers.get("content-type", "").lower()
                                if post.status_code in (401, 403):
                                    hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Sesi lama ditolak setelah logout (HTTP {post.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
                                elif post.status_code == 200 and "text/html" not in ctype:
                                    hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Sesi lama MASIH terautentikasi setelah logout (tidak diinvalidasi di server).", detail=metode.kriteria_lulus, bukti=bukti)
                                else:
                                    hasil_tdv = _tdv(metode, f"Respons setelah logout ambigu (HTTP {post.status_code}, {ctype or 'tanpa tipe'}).", bukti=bukti)
                                    teks = (post.text or "").lower()
                                    metadata = {
                                        "status_sebelum_logout": pre.status_code,
                                        "status_pakai_ulang": post.status_code,
                                        "tipe_konten": ctype,
                                        "panjang": len(post.text or ""),
                                        "ada_sinyal_login": any(k in teks for k in ("type=password", "name=password", "login", "masuk", "sign in")),
                                    }
                                    hasil = _tie_break("session.logout_invalidates", metadata, hasil_tdv,
                                                       peta={"tak_autentik": "lulus", "autentik": "gagal"})
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint logout/sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.idle_timeout")
class CekIdleTimeout:
    """SESS-2.4-T02 — worker tak bisa menunggu idle sungguhan, jadi simpulkan dari masa berlaku
    sesi: klaim `exp` JWT atau Max-Age/Expires cookie. ≤ batas → lulus; jauh melebihi → gagal
    (sesi terlalu lama); tak terbaca (opaque tanpa TTL) → serahkan asesor."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            batas_menit = float(metode.parameter.get("batas_idle_menit", 30))
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh sesi.")
            elif ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — ambil sesi")
                        bukti = list(klien.bukti)
                    if not r["ok"] or not (r["token"] or r["cookie"]):
                        hasil = _tdv(metode, "Gagal memperoleh sesi untuk membaca masa berlaku.", bukti=bukti)
                    else:
                        ttl = _ttl_sesi(r)
                        if ttl is None:
                            hasil = _tdv(metode, "Masa berlaku sesi tak terbaca dari token/cookie (opaque, tanpa Max-Age) — uji idle dikonfirmasi asesor.", bukti=bukti)
                        elif ttl <= 0:
                            hasil = _tdv(metode, "Masa berlaku sesi sudah lewat/tidak wajar saat diterbitkan — dikonfirmasi asesor.", bukti=bukti)
                        else:
                            menit = ttl / 60.0
                            detail = f"{metode.kriteria_lulus}\nMasa berlaku sesi ~{menit:.0f} mnt (batas {batas_menit:.0f} mnt). Catatan: ini batas atas absolut dari exp/Max-Age, bukan idle sejati; asesor mengonfirmasi perilaku idle."
                            if menit <= batas_menit + 1e-9:
                                hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Sesi kedaluwarsa dalam ~{menit:.0f} mnt (≤ batas {batas_menit:.0f} mnt).", detail=detail, bukti=bukti, menunggu_tinjauan=True)
                            else:
                                hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Masa berlaku sesi ~{menit:.0f} mnt melebihi batas idle {batas_menit:.0f} mnt.", detail=detail, bukti=bukti, menunggu_tinjauan=True)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.concurrent_sessions")
class CekSesiBersamaan:
    """SESS-2.7-T01 — login sesi A, login sesi B (klien terpisah), lalu cek apakah sesi A masih
    berlaku. A ditolak → lulus (sesi dibatasi). Kedua aktif → kebijakan bergantung aplikasi
    (kriteria: membatasi ATAU memberi tahu) → serahkan tie-breaker AI; bila tak meyakinkan, asesor."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_area = ctx.url_titik("area_terautentikasi")
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk dua sesi.")
            elif ctx.url_titik("login") is None or url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" dan/atau "area_terautentikasi" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as kA:
                        rA = login_ambil(kA, ctx, akun, judul=f"{metode.id} — login sesi A")
                        preA = None
                        if rA["ok"] and (rA["token"] or rA["cookie"]):
                            preA = kA.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sesi A")
                        with buat_klien(ctx) as kB:
                            rB = login_ambil(kB, ctx, akun, judul=f"{metode.id} — login sesi B")
                        postA = kA.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sesi A setelah login B")
                        bukti = list(kA.bukti)
                    if not rA["ok"] or not rB["ok"] or preA is None or preA.status_code != 200:
                        hasil = _tdv(metode, "Tak dapat memastikan sesi A aktif untuk uji sesi bersamaan.", bukti=bukti)
                    elif postA.status_code in (401, 403):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Sesi pertama diinvalidasi saat login kedua (sesi dibatasi).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil_tdv = _tdv(metode, "Kedua sesi tetap aktif; kebijakan sesi ganda bergantung aturan aplikasi — dikonfirmasi asesor.", bukti=bukti)
                        teks = (postA.text or "").lower()
                        metadata = {
                            "status_sesi_a_setelah_b": postA.status_code,
                            "kedua_sesi_aktif": True,
                            "ada_sinyal_sesi_ganda": any(k in teks for k in ("perangkat lain", "sesi lain", "another device", "logged in elsewhere", "multiple session")),
                        }
                        hasil = _tie_break("session.concurrent_sessions", metadata, hasil_tdv,
                                           peta={"ada_pembatasan": "lulus"})
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil
