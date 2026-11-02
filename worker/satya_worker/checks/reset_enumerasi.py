"""AUTH-1.5-T01 — auth.reset.no_user_enumeration.

Respons permintaan reset untuk akun TERDAFTAR vs TIDAK TERDAFTAR harus identik
(status + isi + panjang) agar keberadaan akun tak bisa ditebak.
  identik    → LULUS
  berbeda    → GAGAL (enumerasi mungkin)
"""

from __future__ import annotations

import re
import secrets
import time

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..peristiwa_uji import payload_aman
from ..registry import check
from ..sesi import buat_klien


_TOLAK_METODE = {404, 405, 501}


def _normalisasi(teks: str, email: str) -> str:
    t = teks.lower()
    if email:
        t = t.replace(email.lower(), "<email>")
    t = re.sub(r"[0-9a-f]{16,}", "<token>", t)  # token acak
    t = re.sub(r'"request_?id"\s*:\s*"[^"]*"', "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


@check("auth.reset.no_user_enumeration")
class CekResetEnumerasi:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        url = ctx.url_titik("reset_password")
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "reset password" (endpoint) tidak tersedia pada aplikasi.')
        f = ctx.form_untuk("reset_password")
        field_id = f.field_identitas if f else "email"
        # Akun TERDAFTAR: email reset yang dikonfigurasi, atau username akun uji yang berformat email.
        email_ada = (f.email if f else "") or next((a.username for a in ctx.akun_uji if a.terisi and "@" in (a.username or "")), "")
        if not email_ada:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                               ringkasan="Butuh email akun terdaftar untuk uji enumerasi (isi email reset atau gunakan akun uji dengan username berformat email).")
        tipe = f.tipe_body if f else "json"
        email_tiada = f"satya-tiada-{secrets.token_hex(6)}@contoh.go.id"
        metode_http = ctx.titik_uji["reset_password"].metode_http
        ctx.langkah("siapkan_payload", "Dua payload reset: akun terdaftar vs akun fiktif", payload=payload_aman({field_id: email_ada}),
                    pembanding=payload_aman({field_id: email_tiada}), tujuan=url)

        try:
            with buat_klien(ctx) as klien:
                t0 = time.perf_counter()
                r_ada = klien.kirim(metode_http, url, json={field_id: email_ada} if tipe == "json" else None, data={field_id: email_ada} if tipe == "form" else None, judul_bukti=f"{metode.id} — reset untuk akun terdaftar")
                d_ada = time.perf_counter() - t0
                t1 = time.perf_counter()
                r_tiada = klien.kirim(metode_http, url, json={field_id: email_tiada} if tipe == "json" else None, data={field_id: email_tiada} if tipe == "form" else None, judul_bukti=f"{metode.id} — reset untuk akun tak terdaftar")
                d_tiada = time.perf_counter() - t1
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi endpoint.", detail=f"{type(e).__name__}: {e}")

        # 404/405/501 untuk keduanya = endpoint tak menerima permintaan reset (mis. titik uji menunjuk
        # halaman frontend SPA, bukan API) — "identik" di sini bukan bukti apa pun.
        if r_ada.status_code in _TOLAK_METODE and r_tiada.status_code in _TOLAK_METODE:
            return HasilMetode(
                metode_id=metode.id, status="tidak_dapat_diverifikasi",
                ringkasan=f"Endpoint reset menolak permintaan (HTTP {r_ada.status_code}) — titik uji kemungkinan halaman frontend, bukan API reset. Jalankan ulang penemuan atau atur titik uji manual.",
                bukti=bukti,
            )
        sama_status = r_ada.status_code == r_tiada.status_code
        n_ada = _normalisasi(r_ada.text, email_ada)
        n_tiada = _normalisasi(r_tiada.text, email_tiada)
        sama_isi = n_ada == n_tiada
        # Panjang asli (sebelum normalisasi) tak boleh beda jauh.
        beda_panjang = abs(len(r_ada.text) - len(r_tiada.text))

        ctx.langkah(
            "bandingkan", "Membandingkan dua respons (status, isi, panjang)",
            status_a=r_ada.status_code, status_b=r_tiada.status_code, sama_status=sama_status, sama_isi=sama_isi, beda_panjang=beda_panjang,
        )
        # Selisih waktu besar (mis. kirim email hanya untuk akun ada) = indikasi enumerasi berbasis waktu.
        beda_waktu = abs(d_ada - d_tiada)
        catatan_waktu = (
            f" Catatan: waktu respons berbeda jelas ({d_ada:.2f}s vs {d_tiada:.2f}s) — kemungkinan enumerasi berbasis waktu."
            if beda_waktu > 1.0 and max(d_ada, d_tiada) > 2 * max(min(d_ada, d_tiada), 0.05) else ""
        )
        if sama_status and sama_isi and beda_panjang <= max(len(email_ada), len(email_tiada)) + 5:
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Respons akun terdaftar & tak terdaftar identik (HTTP {r_ada.status_code}).{catatan_waktu}", detail=metode.kriteria_lulus, bukti=bukti)
        beda = []
        if not sama_status:
            beda.append(f"status {r_ada.status_code} vs {r_tiada.status_code}")
        if not sama_isi:
            beda.append("isi respons berbeda")
        elif beda_panjang:
            beda.append(f"panjang beda {beda_panjang} karakter")
        return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Respons membedakan akun terdaftar/tidak ({'; '.join(beda)}) — enumerasi mungkin.", detail=metode.kriteria_lulus, bukti=bukti)
