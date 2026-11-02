"""AUTH-1.4-T01 — auth.lockout_threshold (profil intrusif).

Beberapa login gagal berturut-turut harus memicu penguncian/penundaan/CAPTCHA.
Pakai akun uji cadangan (penguncian) bila ada; coba sandi SALAH batas+1 kali, lalu VERIFIKASI dengan
sandi BENAR: bila login benar pun ditolak, penguncian terbukti (bukan sekadar teks respons).
  423/429 / penanda kunci spesifik / login benar ditolak / penundaan jelas → LULUS
  semua percobaan ditolak biasa & login benar tetap berhasil                → GAGAL
DAPAT MENGUNCI akun uji — hanya dijalankan bila diizinkan.
"""

from __future__ import annotations

import re
import time

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..peristiwa_uji import payload_aman
from ..registry import check
from ..sesi import buat_klien

# Penanda spesifik (bukan sekadar "lock" yang bisa cocok dengan kata lain, mis. "block"/"clock").
_PETUNJUK_LOCK = re.compile(
    r"account\s+(is\s+)?locked|akun\s+(anda\s+)?(terkunci|dikunci|diblokir)|too many (attempts|requests|login)|"
    r"terlalu banyak (percobaan|permintaan|upaya)|coba lagi (dalam|setelah)|try again (in|later|after)|captcha|"
    r"temporarily (locked|blocked)|sementara (dikunci|diblokir)",
    re.I,
)


@check("auth.lockout_threshold")
class CekPenguncianAkun:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        if not ctx.intrusif.izinkan_penguncian:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Izin uji penguncian akun belum diberikan.")
        url = ctx.url_titik("login")
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')
        akun = ctx.akun("akun_uji_2") or ctx.akun("penguncian") or ctx.akun("akun_uji_1") or ctx.akun("utama")
        if akun is None:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Membutuhkan akun uji untuk diuji penguncian, tetapi belum diisi.")

        batas = int(metode.parameter.get("batas_percobaan", 5))
        f = ctx.form_untuk("login")
        field_user = f.field_username if f else "email"
        field_pass = f.field_password if f else "password"
        tipe = f.tipe_body if f else "json"
        metode_http = ctx.titik_uji["login"].metode_http

        def kirim(klien, sandi: str, judul: str):
            body = {field_user: akun.username, field_pass: sandi}
            return klien.kirim(metode_http, url, json=body if tipe == "json" else None, data=body if tipe == "form" else None,
                               judul_bukti=judul, sandi_disamarkan=sandi)

        durasi_terakhir = 0.0
        terpicu = None  # (percobaan_ke, status, retry_after)
        ctx.langkah(
            "siapkan_payload", f"Menyiapkan {batas + 1} percobaan login dengan kata sandi salah untuk akun '{akun.kunci}'",
            payload=payload_aman({field_user: akun.username, field_pass: "salah"}), percobaan=batas + 1, tujuan=url,
        )
        try:
            with buat_klien(ctx) as klien:
                for i in range(batas + 1):
                    t0 = time.perf_counter()
                    resp = kirim(klien, f"Salah-{i}-{akun.username[:3]}xZ9!", f"{metode.id} — percobaan login gagal #{i + 1}")
                    durasi_terakhir = time.perf_counter() - t0
                    if resp.status_code in (423, 429) or _PETUNJUK_LOCK.search(resp.text[:3000]):
                        terpicu = (i + 1, resp.status_code, resp.headers.get("retry-after", ""))
                        break
                # Verifikasi: login dengan sandi BENAR setelah rentetan gagal.
                ctx.langkah("verifikasi", "Verifikasi: login dengan kata sandi BENAR setelah rentetan kegagalan")
                r_benar = kirim(klien, akun.password or "", f"{metode.id} — verifikasi: login sandi benar setelah kegagalan")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi endpoint.", detail=f"{type(e).__name__}: {e}")

        benar_ditolak = r_benar.status_code >= 400
        retry = (terpicu[2] if terpicu else "") or r_benar.headers.get("retry-after", "")
        ket_retry = f"; Retry-After {retry}" if retry else ""
        if terpicu and benar_ditolak:
            ctx.langkah("evaluasi", f"Terkunci pada percobaan ke-{terpicu[0]}; login benar pun ditolak (HTTP {r_benar.status_code})", status=r_benar.status_code, hasil="terkunci", percobaan=terpicu[0])
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Penguncian terpicu setelah {terpicu[0]} percobaan (HTTP {terpicu[1]}); login dengan sandi benar pun ditolak (HTTP {r_benar.status_code}){ket_retry}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if terpicu:
            ctx.langkah("evaluasi", f"Pembatasan terpicu pada percobaan ke-{terpicu[0]} (login benar tetap diizinkan)", status=terpicu[1], hasil="tertunda", percobaan=terpicu[0])
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Pembatasan percobaan terpicu setelah {terpicu[0]} kegagalan (HTTP {terpicu[1]}){ket_retry}; login dengan sandi benar tetap diizinkan (pembatasan, bukan penguncian akun).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if benar_ditolak:
            ctx.langkah("evaluasi", f"Login benar ditolak (HTTP {r_benar.status_code}) setelah {batas + 1} kegagalan — penguncian senyap", status=r_benar.status_code, hasil="terkunci", percobaan=batas + 1)
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Setelah {batas + 1} kegagalan, login dengan sandi benar ditolak (HTTP {r_benar.status_code}) — akun dikunci tanpa pesan eksplisit{ket_retry}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        ctx.langkah(
            "evaluasi",
            f"{batas + 1} percobaan selesai tanpa penguncian; login benar tetap berhasil" + (f" (respons melambat {durasi_terakhir:.1f}s)" if durasi_terakhir > 3.0 else ""),
            hasil="tertunda" if durasi_terakhir > 3.0 else "tanpa_penguncian", percobaan=batas + 1,
        )
        if durasi_terakhir > 3.0:
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Respons melambat ({durasi_terakhir:.1f}s) setelah {batas + 1} percobaan (indikasi penundaan).", detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(
            metode_id=metode.id,
            status="gagal",
            ringkasan=f"Tidak ada penguncian/penundaan/CAPTCHA setelah {batas + 1} percobaan gagal; login dengan sandi benar tetap berhasil (HTTP {r_benar.status_code}).",
            detail=metode.kriteria_lulus,
            bukti=bukti,
        )
