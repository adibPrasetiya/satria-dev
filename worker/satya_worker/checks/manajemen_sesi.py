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

from .. import analisis_token as at
from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import artefak_sesi, buat_klien, ekstrak_sesi, header_artefak, login_ambil

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
    """Ciri STRUKTUR token/cookie sesi untuk fingerprint (metadata non-sensitif, tanpa nilai asli)."""
    return at.analisis(token=r.get("token"), cookie=r.get("cookie"))["metadata_ai"]


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
    """SESS-2.3-T01 — kumpulkan N sampel token lalu nilai keacakan pada bagian yang BENAR:
    untuk token opaque pada nilainya, untuk JWT pada segmen TANDA TANGAN (pembawa keacakan).
    Juga mendeteksi identitas yang BERURUTAN/ter-encode (prediktabel) lintas-login — token yang
    tampak acak di permukaan tetapi membungkus id tertebak. Kasus ambigu → AI tie-break."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            n = int(metode.parameter.get("jumlah_sampel", 30))
            min_bit = float(metode.parameter.get("entropi_minimum_bit", 64))
            hasil = None
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk mengumpulkan sampel token.")
            elif ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                sampel: list[str] = []
                bukti: list = []
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

                if hasil is None and len(sampel) < 5:
                    hasil = _tdv(metode, f"Sampel token tak cukup ({len(sampel)}) untuk analisis entropi.", bukti=bukti)
                elif hasil is None:
                    md_sampel = at.metadata_sampel(sampel)
                    analisa = [at.analisis(token=s) for s in sampel]
                    semua_jwt = all(a["metadata_ai"].get("format") == "jwt" for a in analisa)
                    ada_prediktabel = any(a["kualitas"] == "prediktabel" for a in analisa)
                    # (1) Identitas berurutan lintas login → prediktabel (walau permukaan "acak").
                    if md_sampel["identitas_berurutan"]:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                            ringkasan="Token sesi menyimpan identitas BERURUTAN/dapat ditebak lintas login.",
                                            detail=f"{metode.kriteria_lulus}\n{md_sampel}", bukti=bukti)
                    # (2) Struktur satu sampel sudah jelas prediktabel (encoded id, alg none, dsb.).
                    elif ada_prediktabel:
                        catatan = next(a["catatan"] for a in analisa if a["kualitas"] == "prediktabel")
                        hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                            ringkasan="Struktur token mengandung identitas yang dapat ditebak.",
                                            detail=f"{metode.kriteria_lulus}\n{catatan}", bukti=bukti)
                    else:
                        # (3) Entropi pada bagian yang relevan (sig JWT / nilai opaque).
                        nilai_ent = [a["nilai_entropi"] for a in analisa if a["nilai_entropi"]]
                        if not nilai_ent:
                            hasil = _tdv(metode, "Tak ada nilai token yang dapat dinilai entropinya.", bukti=bukti)
                        else:
                            unik = len(set(nilai_ent)) == len(nilai_ent)
                            panjang_min = min(len(s) for s in nilai_ent)
                            bit = _entropi_bit(nilai_ent)
                            prefiks = len({s[: max(1, panjang_min - 2)] for s in nilai_ent})
                            berurutan = prefiks <= 2 and panjang_min < 24
                            bagian = "tanda tangan JWT" if semua_jwt else "nilai token"
                            if unik and panjang_min >= 16 and bit >= min_bit and not berurutan:
                                hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                                    ringkasan=f"{len(nilai_ent)} {bagian} unik, panjang ≥ {panjang_min}, entropi ~{bit:.0f} bit (≥ {min_bit:.0f}).",
                                                    detail=metode.kriteria_lulus, bukti=bukti)
                            else:
                                alasan = []
                                if not unik:
                                    alasan.append(f"{bagian} berulang")
                                if panjang_min < 16:
                                    alasan.append(f"terlalu pendek ({panjang_min})")
                                if bit < min_bit:
                                    alasan.append(f"entropi rendah (~{bit:.0f} bit)")
                                if berurutan:
                                    alasan.append("berpola/berurutan")
                                # Opaque yang jelas lemah → gagal langsung; selebihnya (mis. JWT dengan
                                # tanda tangan identik karena iat sama, atau encoding tak terbaca) → AI.
                                if not semua_jwt and (not unik or berurutan or panjang_min < 12):
                                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                                        ringkasan=f"Token sesi lemah: {', '.join(alasan)}.",
                                                        detail=metode.kriteria_lulus, bukti=bukti)
                                else:
                                    hasil_tdv = _tdv(metode, f"Keacakan token belum pasti deterministik: {', '.join(alasan) or 'ambigu'}.", bukti=bukti)
                                    hasil = _tie_break("session.token_entropy", md_sampel, hasil_tdv,
                                                       peta={"prediktabel": "gagal", "acak_kuat": "lulus"})
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
    """SESS-2.4-T01 — login, pastikan sesi aktif, logout, lalu PAKAI ULANG artefak sesi lama DARI
    KLIEN BERSIH (artefak dilampirkan eksplisit).

    Krusial: pemakaian ulang TIDAK memakai klien yang me-logout, sebab logout biasanya mengirim
    `Set-Cookie ...; Max-Age=0` yang menghapus cookie di cookie-jar klien — request berikutnya lalu
    tak membawa sesi apa pun dan selalu 401, menutupi apakah SERVER benar-benar menginvalidasi
    (lulus palsu). Dengan melampirkan nilai artefak lama secara eksplisit pada klien baru, 401/403
    berarti penolakan server sejati. 200 non-HTML → gagal; HTML/redirect ambigu → tie-breaker AI.
    """

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_logout = ctx.url_titik("logout")
            url_area = ctx.url_titik("area_terautentikasi")
            hasil = None
            art = None
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk login lalu logout.")
            elif url_logout is None or url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "logout" dan/atau "area_terautentikasi" tidak tersedia pada aplikasi.')
            else:
                bukti: list = []
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
                        art = artefak_sesi(r)
                        if not r["ok"] or art is None:
                            bukti = list(klien.bukti)
                            hasil = _tdv(metode, "Gagal memperoleh sesi untuk uji logout.", bukti=bukti)
                        else:
                            pre = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sebelum logout")
                            if pre.status_code != 200:
                                bukti = list(klien.bukti)
                                hasil = _tdv(metode, f"Sesi tak aktif sebelum logout (HTTP {pre.status_code}); tak dapat menguji invalidasi.", bukti=bukti)
                            else:
                                klien.kirim(_metode_titik(ctx, "logout", "POST"), url_logout, judul_bukti=f"{metode.id} — logout")
                                bukti = list(klien.bukti)
                    if hasil is None:
                        with buat_klien(ctx) as klien2:
                            post = klien2.kirim("GET", url_area, headers=header_artefak(art),
                                                judul_bukti=f"{metode.id} — pakai ulang artefak sesi lama (klien bersih) setelah logout")
                            bukti = bukti + list(klien2.bukti)
                        ctype = post.headers.get("content-type", "").lower()
                        if post.status_code in (401, 403):
                            hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Artefak sesi lama ({art['jenis']}) ditolak setelah logout (HTTP {post.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
                        elif post.status_code == 200 and "text/html" not in ctype:
                            hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan="Artefak sesi lama MASIH terautentikasi setelah logout (tidak diinvalidasi di server).", detail=metode.kriteria_lulus, bukti=bukti)
                        else:
                            hasil_tdv = _tdv(metode, f"Respons setelah logout ambigu (HTTP {post.status_code}, {ctype or 'tanpa tipe'}).", bukti=bukti)
                            teks = (post.text or "").lower()
                            metadata = {
                                "status_pakai_ulang": post.status_code,
                                "tipe_konten": ctype,
                                "panjang": len(post.text or ""),
                                "jenis_artefak": art["jenis"],
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
    """SESS-2.7-T01 — login sesi A (pastikan aktif), login sesi B di klien terpisah (PASTIKAN B
    aktif), lalu cek apakah A masih berlaku. A ditolak → lulus (sesi dibatasi). Kedua terkonfirmasi
    aktif → kebijakan aplikasi (membatasi ATAU memberi tahu) → tie-breaker AI; bila tak meyakinkan,
    asesor. B tak terkonfirmasi aktif → tak konklusif (hindari vonis dari asumsi)."""

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
                        artA = artefak_sesi(rA)
                        preA = kA.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sesi A") if (rA["ok"] and artA) else None
                        with buat_klien(ctx) as kB:
                            rB = login_ambil(kB, ctx, akun, judul=f"{metode.id} — login sesi B")
                            artB = artefak_sesi(rB)
                            postB = kB.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sesi B") if (rB["ok"] and artB) else None
                            bukti_b = list(kB.bukti)
                        postA = kA.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses sesi A setelah login B")
                        bukti = list(kA.bukti) + bukti_b
                    b_aktif = postB is not None and postB.status_code == 200
                    if not rA["ok"] or not rB["ok"] or preA is None or preA.status_code != 200:
                        hasil = _tdv(metode, "Tak dapat memastikan sesi A aktif untuk uji sesi bersamaan.", bukti=bukti)
                    elif postA.status_code in (401, 403):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Sesi pertama diinvalidasi saat login kedua (sesi dibatasi).", detail=metode.kriteria_lulus, bukti=bukti)
                    elif not b_aktif:
                        hasil = _tdv(metode, "Sesi B tak terkonfirmasi aktif; uji sesi bersamaan tak konklusif.", bukti=bukti)
                    else:
                        hasil_tdv = _tdv(metode, "Sesi A & B terkonfirmasi aktif bersamaan; kebijakan sesi ganda bergantung aturan aplikasi — dikonfirmasi asesor.", bukti=bukti)
                        teks = (postA.text or "").lower()
                        metadata = {
                            "status_sesi_a_setelah_b": postA.status_code,
                            "status_sesi_b": postB.status_code,
                            "kedua_sesi_aktif": True,
                            "artefak_identik": bool(artA and artB and artA.get("nilai") == artB.get("nilai")),
                            "ada_sinyal_sesi_ganda": any(k in teks for k in ("perangkat lain", "sesi lain", "another device", "logged in elsewhere", "multiple session")),
                        }
                        hasil = _tie_break("session.concurrent_sessions", metadata, hasil_tdv,
                                           peta={"ada_pembatasan": "lulus"})
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =================================================================== metode baru (struktur & duplikasi)

@check("session.token_structure")
class CekStrukturToken:
    """SESS-2.3-T02 — bedah struktur satu token sesi: untuk JWT, dekode payload dan temukan klaim
    identitas (jti/sid/sub) serta bentuk nilainya; untuk opaque, deteksi lapisan encode (base64/hex)
    dan intip apakah membungkus identifier yang dapat ditebak. Vonis deterministik bila jelas
    (acak_kuat→lulus, prediktabel→gagal); bentuk ambigu diserahkan ke AI (prediktabel/acak_kuat)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh token sesi.")
            elif ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — ambil token untuk analisis struktur")
                        bukti = list(klien.bukti)
                    if not r["ok"] or not (r["token"] or r["cookie"]):
                        hasil = _tdv(metode, "Gagal memperoleh token sesi untuk analisis struktur.", bukti=bukti)
                    else:
                        a = at.analisis(token=r.get("token"), cookie=r.get("cookie"))
                        detail = f"{metode.kriteria_lulus}\n{a['catatan']}\nStruktur: {a['metadata_ai']}"
                        if a["kualitas"] == "prediktabel":
                            hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Identitas sesi dapat ditebak: {a['catatan']}", detail=detail, bukti=bukti)
                        elif a["kualitas"] == "acak_kuat":
                            hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Struktur token sehat: {a['catatan']}", detail=detail, bukti=bukti)
                        else:
                            hasil_tdv = _tdv(metode, f"Struktur token ambigu: {a['catatan']}", detail=detail, bukti=bukti)
                            kunci = "struktur|" + "|".join(f"{k}={a['metadata_ai'][k]}" for k in sorted(a["metadata_ai"]))
                            hasil = _tie_break("session.token_structure", a["metadata_ai"], hasil_tdv,
                                               peta={"prediktabel": "gagal", "acak_kuat": "lulus"}, kunci_cache=kunci)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.logout_client_side")
class CekLogoutBersihKlien:
    """SESS-2.4-T03 — pelengkap T01: periksa apakah respons logout turut MEMBERSIHKAN artefak sesi
    di sisi klien. Untuk sesi cookie: logout harus mengirim `Set-Cookie` yang mengosongkan/meng-
    expired-kan cookie sesi (Max-Age=0 / Expires lampau / nilai kosong). Untuk sesi token (Bearer):
    pembersihan di sisi klien tak dapat diamati lewat HTTP → tidak_berlaku."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_logout = ctx.url_titik("logout")
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk login lalu logout.")
            elif url_logout is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "logout" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
                        if not r["ok"] or not (r["token"] or r["cookie"]):
                            hasil = _tdv(metode, "Gagal memperoleh sesi untuk uji logout.", bukti=list(klien.bukti))
                        elif r["cookie"] is None:
                            hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="Sesi berbasis token (Bearer) — pembersihan artefak di klien tak teramati lewat HTTP.", bukti=list(klien.bukti))
                        else:
                            nama_cookie = r["cookie"].get("name", "")
                            resp = klien.kirim(_metode_titik(ctx, "logout", "POST"), url_logout, judul_bukti=f"{metode.id} — logout (periksa Set-Cookie)")
                            bukti = list(klien.bukti)
                            try:
                                sc_list = resp.headers.get_list("set-cookie")
                            except Exception:
                                sc = resp.headers.get("set-cookie")
                                sc_list = [sc] if sc else []
                            relevan = [s for s in sc_list if s.split("=", 1)[0].strip().lower() == nama_cookie.lower()]
                            bersih = False
                            for s in relevan:
                                low = s.lower()
                                nilai = s.split(";", 1)[0].split("=", 1)[1].strip() if "=" in s.split(";", 1)[0] else ""
                                if "max-age=0" in low.replace(" ", "") or nilai == "" or _re.search(r"expires=[^;]*(1970|19[789]\d|200[0-9])", low):
                                    bersih = True
                                    break
                            if bersih:
                                hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Logout mengosongkan/meng-expired-kan cookie sesi '{nama_cookie}' di klien.", detail=metode.kriteria_lulus, bukti=bukti)
                            elif relevan:
                                hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Logout menyetel ulang cookie '{nama_cookie}' tanpa mengosongkan/meng-expired-kannya.", detail=metode.kriteria_lulus, bukti=bukti)
                            else:
                                hasil = _tdv(metode, f"Logout tak mengirim `Set-Cookie` untuk '{nama_cookie}'; pembersihan sisi klien tak terkonfirmasi (bisa jadi klien yang menghapus). Dikonfirmasi asesor.", bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint logout.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.fixation")
class CekFiksasiSesi:
    """SESS-2.5-T03 — session fixation: ambil artefak sesi ANONIM (pra-login) dari halaman login,
    lalu login pada klien yang sama; identitas sesi HARUS berubah setelah autentikasi (sesi anonim
    tak boleh dipromosikan menjadi terautentikasi). Cookie sesi sama sebelum & sesudah login →
    gagal (rawan fiksasi). Tak ada cookie anonim pra-login (mis. sesi token murni) → tidak_berlaku."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_login = ctx.url_titik("login")
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk login.")
            elif url_login is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        # Ambil cookie sesi anonim (GET halaman login bila URL-nya laman; jika titik
                        # login adalah endpoint API POST, pakai base_url sebagai laman pembuka).
                        laman = url_login if _metode_titik(ctx, "login", "POST") == "GET" else ctx.base_url
                        pra = klien.kirim("GET", laman, judul_bukti=f"{metode.id} — ambil sesi anonim (pra-login)")
                        sesi_pra = ekstrak_sesi(pra)
                        nilai_pra = sesi_pra["cookie"]["value"] if sesi_pra["cookie"] else None
                        nama_pra = sesi_pra["cookie"]["name"] if sesi_pra["cookie"] else None
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login")
                        art = artefak_sesi(r)
                        bukti = list(klien.bukti)
                    if not r["ok"] or art is None:
                        hasil = _tdv(metode, "Gagal memperoleh sesi setelah login.", bukti=bukti)
                    elif nilai_pra is None:
                        hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="Tak ada cookie sesi anonim pra-login — vektor fiksasi berbasis cookie tak berlaku.", bukti=bukti)
                    else:
                        nilai_pasca = art["nilai"] if art["jenis"] == "cookie" else None
                        if nilai_pasca is not None and nilai_pasca == nilai_pra:
                            hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Identitas sesi (cookie '{nama_pra}') TIDAK berubah setelah login — rawan session fixation.", detail=metode.kriteria_lulus, bukti=bukti)
                        else:
                            hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Identitas sesi berubah setelah autentikasi (sesi anonim tak dipromosikan).", detail=metode.kriteria_lulus, bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.concurrent_clone")
class CekKloningSesi:
    """SESS-2.7-T03 — duplikasi/kloning sesi: SATU artefak sesi yang sama dipakai dari DUA klien
    independen secara paralel (klien asli + klien "kloning" yang melampirkan artefak eksplisit).
    Salah satu ditolak → sesi terikat/ dibatasi (lulus). Keduanya diterima → tak ada pembatasan
    teknis pada level artefak → tie-breaker AI (ada_pembatasan); bila tidak, dikonfirmasi asesor."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            url_area = ctx.url_titik("area_terautentikasi")
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk kloning sesi.")
            elif ctx.url_titik("login") is None or url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" dan/atau "area_terautentikasi" tidak tersedia pada aplikasi.')
            else:
                try:
                    klon = None
                    asli2 = None
                    bukti_klon: list = []
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login (sesi asli)")
                        art = artefak_sesi(r)
                        asli = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses dari klien asli") if (r["ok"] and art) else None
                        if r["ok"] and art and asli is not None and asli.status_code == 200:
                            with buat_klien(ctx) as kklon:
                                klon = kklon.kirim("GET", url_area, headers=header_artefak(art),
                                                   judul_bukti=f"{metode.id} — akses PARALEL dari klien kloning (artefak sama)")
                                bukti_klon = list(kklon.bukti)
                            # Pastikan sesi asli MASIH hidup setelah kloning dipakai.
                            asli2 = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses klien asli setelah kloning")
                        bukti = list(klien.bukti) + bukti_klon
                    if art is None or asli is None or asli.status_code != 200:
                        hasil = _tdv(metode, "Tak dapat memastikan sesi asli aktif untuk uji kloning.", bukti=bukti)
                    elif klon is None:
                        hasil = _tdv(metode, "Uji kloning tak terlaksana.", bukti=bukti)
                    elif klon.status_code in (401, 403):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Artefak sesi yang digandakan ditolak pada klien kedua (HTTP {klon.status_code}) — sesi terikat/dibatasi.", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        ctype = klon.headers.get("content-type", "").lower()
                        asli_tetap = asli2 is not None and asli2.status_code == 200
                        hasil_tdv = _tdv(metode, "Artefak sesi yang sama diterima pada dua klien paralel; tak ada pembatasan teknis pada level artefak — kebijakan dikonfirmasi asesor.", bukti=bukti)
                        teks = (klon.text or "").lower()
                        metadata = {
                            "status_klon": klon.status_code,
                            "tipe_konten": ctype,
                            "jenis_artefak": art["jenis"],
                            "sesi_asli_tetap_aktif": asli_tetap,
                            "kedua_klien_diterima": True,
                            "ada_sinyal_pembatasan": any(k in teks for k in ("perangkat lain", "sesi lain", "another device", "logged in elsewhere", "multiple session", "dibatasi")),
                        }
                        hasil = _tie_break("session.concurrent_clone", metadata, hasil_tdv,
                                           peta={"ada_pembatasan": "lulus"})
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.token_storage")
class CekPenyimpananToken:
    """SESS-2.6-T03 — DI MANA token sesi disimpan di sisi klien. Token diserahkan di BODY respons
    login (dikonsumsi JavaScript lalu lazim disimpan di localStorage/sessionStorage yang dapat
    dibaca skrip) ATAU cookie tanpa HttpOnly → rentan dicuri via XSS → gagal. Cookie sesi HttpOnly
    (tak terbaca JavaScript) → lulus. Konfirmasi lokasi storage persisnya bisa via engine browser."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh sesi.")
            elif ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — ambil sesi untuk cek lokasi penyimpanan")
                        bukti = list(klien.bukti)
                    c = r.get("cookie")
                    tok = r.get("token")
                    if not r["ok"] or not (tok or c):
                        hasil = _tdv(metode, "Gagal memperoleh sesi untuk menilai lokasi penyimpanan.", bukti=bukti)
                    elif tok:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                            ringkasan="Token sesi diserahkan di body respons (ditangani JavaScript, bukan cookie HttpOnly) — lazim disimpan di localStorage/sessionStorage dan dapat dicuri via XSS.",
                                            detail=f"{metode.kriteria_lulus}\nSesi token Bearer; tak ada cookie sesi HttpOnly. Rujukan: CWE-522/CWE-1004. Lokasi storage persis dapat dikonfirmasi via engine browser.",
                                            bukti=bukti)
                    elif c is not None:
                        flags = c.get("flags", "")
                        if "httponly" in flags:
                            catatan = "" if "secure" in flags else " (catatan: atribut Secure kurang — lihat SESS-2.6-T01)"
                            hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                                ringkasan=f"Sesi dibawa cookie HttpOnly '{c.get('name')}' (tak terbaca JavaScript).{catatan}",
                                                detail=metode.kriteria_lulus, bukti=bukti)
                        else:
                            hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                                ringkasan=f"Cookie sesi '{c.get('name')}' tanpa HttpOnly — dapat dibaca JavaScript; rentan pencurian via XSS.",
                                                detail=f"{metode.kriteria_lulus}\nRujukan: CWE-1004.", bukti=bukti)
                    else:
                        hasil = _tdv(metode, "Lokasi penyimpanan sesi tak dapat ditentukan dari artefak.", bukti=bukti)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint login.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


@check("session.logout_real_flow", engine="playwright")
class CekLogoutAlurNyata:
    """SESS-2.4-T04 — login via BROWSER, lakukan LOGOUT seperti pengguna (klik kontrol logout),
    lalu uji apakah token sesi LAMA masih berlaku. Token masih diterima (2xx) → gagal: logout tak
    menginvalidasi sesi di server (sering FE hanya membersihkan storage klien, token tetap hidup —
    tak tertangkap uji endpoint logout langsung). Ditolak → lulus. Kontrol logout tak ditemukan /
    browser tak tersedia → tidak_dapat_diverifikasi (degradasi anggun)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_utama(ctx)
            if akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk alur logout browser.")
            elif ctx.url_titik("login_page") is None and ctx.url_titik("login") is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji halaman login tidak tersedia pada aplikasi.')
            else:
                try:
                    from .. import playwright_driver as pw
                    if not pw.tersedia():
                        hasil = _tdv(metode, "Browser (Playwright) tak tersedia; uji alur logout UI dilewati.")
                    else:
                        fl = pw.logout_flow(ctx, akun)
                        detail = (f"{metode.kriteria_lulus}\nlogin_ok={fl['login_ok']} token_ada={fl['token_ada']} "
                                  f"logout_terpicu={fl['logout_terpicu']} logout_request={fl['logout_request']} "
                                  f"token_hapus_klien={fl['token_hapus_klien']} status_token_lama={fl['status_token_lama']}")
                        if not fl["login_ok"] or not fl["token_ada"]:
                            hasil = _tdv(metode, "Gagal login/menangkap token via browser untuk uji logout.", detail)
                        elif not fl["logout_terpicu"]:
                            hasil = _tdv(metode, "Kontrol logout tak ditemukan otomatis; konfirmasi manual oleh asesor.", detail)
                        elif fl["status_token_lama"] is not None:
                            catatan = " FE memanggil endpoint logout tetapi token tetap hidup." if fl["logout_request"] else " FE tampak tak memanggil endpoint logout (hanya bersih di klien)."
                            hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                                ringkasan=f"Setelah logout di UI, token sesi lama MASIH berlaku (HTTP {fl['status_token_lama']}) — sesi tidak diinvalidasi di server.{catatan}",
                                                detail=detail, menunggu_tinjauan=True)
                        else:
                            hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                                ringkasan="Token sesi lama ditolak setelah logout di UI (sesi diinvalidasi di server).",
                                                detail=detail)
                except Exception as e:
                    hasil = _tdv(metode, "Gagal menjalankan alur logout browser.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil
