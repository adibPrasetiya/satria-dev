"""AUTH-1.2-T01 — auth.server_side_validation.

Validasi tetap berlaku walau tanpa JavaScript klien: kirim login LANGSUNG ke endpoint.
Ditajamkan dengan KONTROL POSITIF: login benar dengan akun uji harus diterima — membuktikan nama
field & format payload tepat — sehingga penolakan kredensial acak memang karena kredensialnya,
bukan karena payload salah format/field salah nama.
  kontrol diterima + acak ditolak 4xx            → LULUS
  acak DITERIMA (2xx)                            → GAGAL
  kontrol pun ditolak (format login belum tepat)  → tidak_dapat_diverifikasi
"""

from __future__ import annotations

import re
import secrets

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..peristiwa_uji import payload_aman
from ..registry import check
from ..sesi import buat_klien

_KW_KREDENSIAL = re.compile(r"credential|kredensial|salah|invalid|incorrect|wrong|unauthori[sz]ed|tidak (valid|cocok|ditemukan)|not found|gagal masuk", re.I)


@check("auth.server_side_validation")
class CekValidasiServer:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        url = ctx.url_titik("login")
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" (endpoint) tidak tersedia pada aplikasi.')
        f = ctx.form_untuk("login")
        field_user = f.field_username if f else "email"
        field_pass = f.field_password if f else "password"
        tipe = f.tipe_body if f else "json"
        metode_http = ctx.titik_uji["login"].metode_http
        akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
        sandi = secrets.token_urlsafe(12)
        body = {field_user: f"satya-uji-{secrets.token_hex(4)}@contoh.go.id", field_pass: sandi}

        def kirim(klien, b, judul, samar):
            return klien.kirim(metode_http, url, json=b if tipe == "json" else None, data=b if tipe == "form" else None,
                               judul_bukti=judul, sandi_disamarkan=samar)

        kontrol = None
        try:
            if akun and akun.password:
                ctx.langkah("kontrol_positif", f"Kontrol positif: login benar dengan akun uji '{akun.kunci}' (membuktikan format payload tepat)")
                with buat_klien(ctx) as k0:
                    kontrol = kirim(k0, {field_user: akun.username, field_pass: akun.password}, f"{metode.id} — kontrol: login akun uji", akun.password)
                    bukti_kontrol = list(k0.bukti)
            else:
                bukti_kontrol = []
            ctx.langkah("siapkan_payload", "Menyusun payload login berkredensial acak (validasi JavaScript klien dilewati)",
                        payload=payload_aman(body), tipe_body=tipe, tujuan=url)
            ctx.langkah("kirim", f"Mengirim langsung ke endpoint {metode_http} {url}", tujuan=url)
            with buat_klien(ctx) as klien:
                resp = kirim(klien, body, f"{metode.id} — login kredensial acak langsung ke endpoint", sandi)
                bukti = bukti_kontrol + list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi endpoint.", detail=f"{type(e).__name__}: {e}")

        sc = resp.status_code
        kontrol_ok = kontrol is not None and kontrol.status_code < 400
        sebut_kredensial = sc in (401, 403) or bool(_KW_KREDENSIAL.search(resp.text[:2000]))

        if 200 <= sc < 300 and (kontrol is None or kontrol_ok):
            ctx.langkah("evaluasi", "Server MENERIMA kredensial acak", status=sc, hasil="diterima")
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Kredensial acak DITERIMA (HTTP {sc}) — validasi sisi server lemah.", detail=metode.kriteria_lulus, bukti=bukti)
        if 400 <= sc < 500:
            if kontrol is not None and not kontrol_ok:
                ctx.langkah("evaluasi", f"Kontrol positif pun ditolak (HTTP {kontrol.status_code}) — format login belum tepat", status=sc, hasil="tidak_jelas")
                return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                                   ringkasan=f"Login benar dengan akun uji pun ditolak (HTTP {kontrol.status_code}); format/nama field login belum tepat sehingga penolakan kredensial acak (HTTP {sc}) tak dapat diatribusikan.",
                                   bukti=bukti)
            if kontrol_ok or sebut_kredensial:
                dasar = "kontrol positif diterima" if kontrol_ok else "respons menyebut kredensial"
                ctx.langkah("evaluasi", f"Server menolak kredensial acak (HTTP {sc}; {dasar})", status=sc, hasil="ditolak")
                return HasilMetode(metode_id=metode.id, status="lulus",
                                   ringkasan=f"Endpoint memvalidasi & menolak kredensial acak (HTTP {sc}); {dasar}.", detail=metode.kriteria_lulus, bukti=bukti)
            ctx.langkah("evaluasi", f"Ditolak HTTP {sc} tanpa bukti penyebabnya kredensial", status=sc, hasil="tidak_jelas")
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                               ringkasan=f"Kredensial acak ditolak (HTTP {sc}) tetapi tanpa akun uji/pesan kredensial — penyebab (kredensial vs format payload) tak dapat dipastikan.",
                               bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=f"Respons tak terduga (HTTP {sc}).", bukti=bukti)
