"""Kontrol AUTH-1.2 / AUTH-1.3 — kebijakan kata sandi di sisi server.

Check (engine custom):
  auth.password_policy.min_length               (1.3-T01, registrasi)
  auth.password_policy.complexity               (1.3-T02, registrasi)
  auth.password_policy.server_side              (1.2-T02, registrasi — gabungan lemah)
  auth.password_policy.min_length+complexity    (1.3-T04, ubah_password — butuh login & izin uji berisiko)
(1.3-T03 — saat reset — ada di engine playwright: `playwright_scan`, memakai fondasi yang sama.)

Prinsip (black-box, sisi server), kini TAJAM (lihat `atribusi_sandi`):
  1. Payload VALID — field lain diisi nilai dummy yang lolos validasi (skema OpenAPI, + AI bila perlu),
     agar penolakan tidak disebabkan field lain.
  2. Pembanding — payload identik dengan sandi KUAT harus diterima (registrasi: membuat akun uji
     berawalan `satya-uji-`, tercatat di bukti; ubah sandi: diubah sementara lalu DIPULIHKAN).
  3. Atribusi — sandi lemah ditolak + sandi kuat diterima → kebijakan terbukti (LULUS). Sandi lemah
     diterima → GAGAL. Penolakan yang tak bisa diatribusikan ke sandi → PERLU TINJAUAN (bukan lulus).
"""

from __future__ import annotations

from typing import Any, Optional

from .. import atribusi_sandi as asd
from ..http_client import LuarRuangLingkup
from ..models import AkunUji, Bukti, FormTitikUji, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..peristiwa_uji import payload_aman
from ..registry import check
from ..sesi import buat_klien, login

_LABEL_PENYEBAB = {
    "kebijakan_sandi": "karena kebijakan kata sandi",
    "field_lain": "karena field lain",
    "duplikasi": "karena data duplikat",
    "tidak_jelas": "dengan penyebab tak jelas",
    "diterima": "— sandi lemah diterima",
}


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "", bukti: Optional[list[Bukti]] = None) -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=ringkasan, detail=detail, bukti=bukti or [])


def _hasil(metode: MetodeSpec, atribusi: dict[str, Any], alasan_lemah: str, titik_label: str, bukti: list[Bukti], tambahan: str = "") -> HasilMetode:
    status = asd.vonis(atribusi)
    if status == "gagal":
        ringkasan = f"Kata sandi lemah ({alasan_lemah}) DITERIMA saat {titik_label}; kebijakan tidak ditegakkan di sisi server."
    elif status == "lulus":
        ringkasan = f"Kata sandi lemah ({alasan_lemah}) ditolak saat {titik_label} karena kebijakan kata sandi ({atribusi['alasan']})"
    else:
        ringkasan = (
            f"Request {titik_label} ditolak {_LABEL_PENYEBAB.get(atribusi['penyebab'], '')}, sehingga penegakan kebijakan "
            f"kata sandi belum dapat dipastikan: {atribusi['alasan']}"
        )
    bukti = bukti + [Bukti(jenis="dokumen", judul="Atribusi penolakan", isi=f"penyebab={atribusi['penyebab']}; sumber={atribusi.get('sumber')}; keyakinan={atribusi.get('keyakinan')}\n{atribusi['alasan']}")]
    return HasilMetode(metode_id=metode.id, status=status, ringkasan=(ringkasan + tambahan)[:480], detail=metode.kriteria_lulus, bukti=bukti)


def _kirim(klien: Any, ctx: ScanContext, titik: str, url: str, form: FormTitikUji, body: dict[str, Any], judul: str, sandi: list[str]):
    tipe = form.tipe_body
    return klien.kirim(
        ctx.titik_uji[titik].metode_http if titik in ctx.titik_uji else "POST",
        url,
        json=body if tipe == "json" else None,
        data=body if tipe == "form" else None,
        judul_bukti=judul,
        sandi_disamarkan=next((s for s in sandi if s), None),
    )


class _BasisKebijakanSandi:
    """Varian sandi lemah ditentukan subkelas; alur pengujian di sini."""

    def _sandi_lemah(self, panjang_minimum: int, wajib: list[str]) -> str:
        raise NotImplementedError

    def _alasan_lemah(self) -> str:
        raise NotImplementedError

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan_ubah(ctx, metode) if metode.titik_uji == "ubah_password" else self._jalankan_registrasi(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    # ------------------------------------------------------------------ registrasi
    def _jalankan_registrasi(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        titik = metode.titik_uji
        url = ctx.url_titik(titik)
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan=f'Titik uji "{titik}" tidak tersedia pada aplikasi.')
        form = ctx.form_untuk(titik)
        if form is None or not (form.field_dasar or form.skema_field):
            tp = ctx.titik_uji[titik]
            return _tdv(
                metode,
                f'Endpoint {titik} ditemukan ({tp.metode_http} {url}), tetapi field body-nya tidak diketahui — '
                "jalankan ulang penemuan (intersep form) atau atur template form secara manual.",
            )

        panjang = int(metode.parameter.get("panjang_minimum", 8))
        wajib = list(metode.parameter.get("wajib", ["huruf_besar", "huruf_kecil", "angka", "simbol"]))
        lemah = self._sandi_lemah(panjang, wajib)
        kuat = asd.sandi_kuat()
        sukses = tuple(form.status_sukses or asd.STATUS_SUKSES)

        dasar, ditebak = asd.payload_valid(form)
        ctx.catat("info", f"  Strategi: payload registrasi VALID + pembanding sandi kuat, lalu sandi lemah ({self._alasan_lemah()}); penolakan diatribusikan.")
        if ditebak:
            ctx.catat("info", f"  Nilai field ditebak (skema minim): {', '.join(ditebak)}.")
        p_kuat = asd.pasang_sandi(dasar, form, kuat)
        ctx.langkah("siapkan_payload", "Menyusun payload registrasi valid (field lain lolos validasi)",
                    payload=payload_aman(p_kuat), tipe_body=form.tipe_body, tujuan=url)

        try:
            with buat_klien(ctx) as klien:
                # (1) Pembanding: sandi kuat harus diterima → membuktikan payload valid.
                ctx.langkah("pembanding_kuat", "Pembanding: payload identik dengan sandi KUAT (akun uji satya-uji-… dibuat)")
                r_kuat = _kirim(klien, ctx, titik, url, form, p_kuat, f"{metode.id} — pembanding: registrasi sandi kuat", [kuat])
                if r_kuat.status_code not in sukses:
                    # Payload belum valid → satu kali perbaikan dengan umpan balik galat (AI bila tersedia).
                    a = asd.analisis_body(r_kuat, form.field_sandi, p_kuat)
                    perlu = a.get("field") or ditebak
                    if perlu:
                        ctx.langkah("perbaiki_payload", f"Pembanding ditolak ({a['alasan']}); memperbaiki field: {', '.join(perlu)}")
                        asd._isi_dengan_ai(dasar, list(perlu), form.skema_field, galat=asd._redaksi_body(r_kuat.text, dasar, [kuat]))
                        dasar = asd.segarkan_unik(dasar, form)
                        p_kuat = asd.pasang_sandi(dasar, form, kuat)
                        r_kuat = _kirim(klien, ctx, titik, url, form, p_kuat, f"{metode.id} — pembanding (perbaikan): registrasi sandi kuat", [kuat])
                if r_kuat.status_code in sukses:
                    ctx.catat("info", f"  Pembanding diterima (HTTP {r_kuat.status_code}); akun uji pembanding dibuat dengan field unik baru.")

                # (2) Sandi lemah dengan payload identik (field unik baru agar tak bentrok duplikasi).
                p_lemah = asd.pasang_sandi(asd.segarkan_unik(dasar, form), form, lemah)
                ctx.langkah("kirim", f"Mengirim payload identik dengan sandi lemah ({self._alasan_lemah()})",
                            payload=payload_aman(p_lemah, tampilkan=[form.field_sandi]), tujuan=url)
                r_lemah = _kirim(klien, ctx, titik, url, form, p_lemah, f"{metode.id} — registrasi sandi lemah ({self._alasan_lemah()})", [lemah])
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL titik uji di luar host yang diizinkan.", str(e))
        except Exception as e:
            ctx.catat("peringatan", f"  Gagal menghubungi endpoint: {type(e).__name__}.")
            return _tdv(metode, "Gagal menghubungi endpoint.", f"{type(e).__name__}: {e}")

        atribusi = asd.atribusikan(r_lemah, field_sandi=form.field_sandi, payload=p_lemah, sandi_lemah=lemah,
                                   resp_kuat=r_kuat, status_sukses=sukses)
        ctx.langkah("atribusi", f"Penyebab: {atribusi['penyebab']} — {atribusi['alasan'][:120]}",
                    hasil={"kebijakan_sandi": "ditolak", "diterima": "diterima"}.get(atribusi["penyebab"], "tidak_jelas"),
                    status=r_lemah.status_code, sumber=atribusi.get("sumber"))
        tambahan = "" if r_kuat.status_code in sukses else " (pembanding sandi kuat juga ditolak — payload registrasi belum dapat dibuat valid)."
        return _hasil(metode, atribusi, self._alasan_lemah(), "registrasi", bukti, tambahan)

    # ------------------------------------------------------------------ ubah kata sandi
    def _jalankan_ubah(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        url = ctx.url_titik("ubah_password")
        if url is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "ubah_password" tidak tersedia pada aplikasi.')
        # Uji ini MENGGANTI kata sandi akun uji → hanya dengan izin uji berisiko eksplisit dari
        # pengguna (wizard "Izinkan uji berisiko"). Persetujuan pemindaian aktif saja tidak cukup.
        if not ctx.intrusif.izinkan_penguncian:
            return _tdv(metode, "Uji ubah kata sandi dilewati: izin uji berisiko (ubah kata sandi akun uji) tidak diberikan.")
        akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
        if akun is None or not akun.password:
            return _tdv(metode, "Membutuhkan akun uji (dengan kata sandi), tetapi belum diisi.")
        form = ctx.form.get("ubah_password") or FormTitikUji()
        if not ctx.form.get("ubah_password"):
            form.field_lama, form.field_baru = "current_password", "new_password"
        sukses = tuple(form.status_sukses or asd.STATUS_SUKSES)
        panjang = int(metode.parameter.get("panjang_minimum", 8))
        lemah = self._sandi_lemah(panjang, [])
        asli = akun.password

        def body(lama: str, baru: str) -> dict[str, Any]:
            b = {form.field_lama: lama, form.field_baru: baru}
            if form.field_konfirmasi:
                b[form.field_konfirmasi] = baru
            return b

        ctx.catat("info", f"  Strategi: login akun uji '{akun.kunci}', ubah sandi ke sandi lemah; bila diterima → SEGERA dipulihkan ke sandi asli.")
        catatan_pulih = ""
        r_kuat = None
        try:
            with buat_klien(ctx) as klien:
                ctx.langkah("login", f"Login akun uji '{akun.kunci}' untuk mendapatkan sesi")
                if not login(klien, ctx, akun):
                    return _tdv(metode, "Gagal login dengan akun uji; tidak bisa menguji ubah kata sandi.", "\n".join(b.isi or "" for b in klien.bukti))
                b_lemah = body(asli, lemah)
                ctx.langkah("siapkan_payload", "Payload ubah kata sandi menjadi lemah (sandi lama benar)",
                            payload=payload_aman(b_lemah, tampilkan=[form.field_baru]), tipe_body=form.tipe_body, tujuan=url)
                r_lemah = _kirim(klien, ctx, "ubah_password", url, form, b_lemah, f"{metode.id} — ubah kata sandi menjadi lemah", [asli, lemah])

                if r_lemah.status_code in sukses:
                    # Sandi akun uji kini lemah → pulihkan ke sandi asli SEKARANG.
                    catatan_pulih = self._pulihkan(klien, ctx, metode, akun, url, form, body, dari=lemah, ke=asli)
                else:
                    a = asd.analisis_body(r_lemah, form.field_baru, b_lemah)
                    if a["penyebab"] != "kebijakan_sandi":
                        # Tak konklusif → pembanding: ubah ke sandi kuat sementara lalu kembalikan.
                        kuat = asd.sandi_kuat()
                        ctx.langkah("pembanding_kuat", "Pembanding: ubah ke sandi KUAT sementara (akan dipulihkan)")
                        r_kuat = _kirim(klien, ctx, "ubah_password", url, form, body(asli, kuat), f"{metode.id} — pembanding: ubah ke sandi kuat sementara", [asli, kuat])
                        if r_kuat.status_code in sukses:
                            catatan_pulih = self._pulihkan(klien, ctx, metode, akun, url, form, body, dari=kuat, ke=asli)
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL titik uji di luar host yang diizinkan.", str(e))
        except Exception as e:
            ctx.catat("peringatan", f"  Gagal menghubungi endpoint: {type(e).__name__}.")
            return _tdv(metode, "Gagal menghubungi endpoint.", f"{type(e).__name__}: {e}")

        atribusi = asd.atribusikan(r_lemah, field_sandi=form.field_baru, payload=b_lemah, sandi_lemah=lemah,
                                   resp_kuat=r_kuat, status_sukses=sukses)
        ctx.langkah("atribusi", f"Penyebab: {atribusi['penyebab']} — {atribusi['alasan'][:120]}",
                    hasil={"kebijakan_sandi": "ditolak", "diterima": "diterima"}.get(atribusi["penyebab"], "tidak_jelas"),
                    status=r_lemah.status_code, sumber=atribusi.get("sumber"))
        return _hasil(metode, atribusi, "di bawah panjang minimum dan tanpa kombinasi", "ubah kata sandi", bukti, catatan_pulih)

    def _pulihkan(self, klien: Any, ctx: ScanContext, metode: MetodeSpec, akun: AkunUji, url: str, form: FormTitikUji,
                  body: Any, *, dari: str, ke: str) -> str:
        """Kembalikan sandi akun uji `dari` → `ke`. Sesi bisa dicabut setelah ganti sandi → login ulang."""
        ctx.langkah("pulihkan", "Memulihkan kata sandi akun uji ke sandi asli")
        sukses = tuple(form.status_sukses or asd.STATUS_SUKSES)
        r = _kirim(klien, ctx, "ubah_password", url, form, body(dari, ke), f"{metode.id} — pemulihan kata sandi akun uji", [dari, ke])
        if r.status_code in (401, 403):
            sementara = AkunUji(kunci=akun.kunci, username=akun.username, password=dari, terisi=True)
            if login(klien, ctx, sementara):
                r = _kirim(klien, ctx, "ubah_password", url, form, body(dari, ke), f"{metode.id} — pemulihan kata sandi (login ulang)", [dari, ke])
        if r.status_code in sukses:
            ctx.catat("info", f"  Kata sandi akun uji '{akun.kunci}' berhasil dipulihkan ke sandi asli.")
            return " Kata sandi akun uji telah dipulihkan ke sandi asli."
        # Gagal pulih: beri tahu operator nilai sandi sementara agar akun uji bisa dipulihkan manual.
        ctx.catat("galat", f"  PEMULIHAN GAGAL (HTTP {r.status_code}): kata sandi akun uji '{akun.kunci}' kini = '{dari}'. Pulihkan manual!")
        return f" PERHATIAN: pemulihan kata sandi akun uji gagal (HTTP {r.status_code}); sandi sementara dicatat di log operasi."


@check("auth.password_policy.min_length")
class CekPanjangMinimum(_BasisKebijakanSandi):
    def _sandi_lemah(self, panjang_minimum: int, wajib: list[str]) -> str:
        return asd.sandi_pendek(panjang_minimum)

    def _alasan_lemah(self) -> str:
        return "satu karakter di bawah panjang minimum, kombinasi lengkap"


@check("auth.password_policy.complexity")
class CekKombinasiKarakter(_BasisKebijakanSandi):
    def _sandi_lemah(self, panjang_minimum: int, wajib: list[str]) -> str:
        return asd.sandi_tanpa_kombinasi(panjang_minimum)

    def _alasan_lemah(self) -> str:
        return "panjang cukup tetapi hanya huruf kecil"


@check("auth.password_policy.server_side")
@check("auth.password_policy.min_length+complexity")
class CekPanjangDanKombinasi(_BasisKebijakanSandi):
    """1.3-T04 (ubah_password, butuh login) & 1.2-T02 (registrasi, gabungan lemah)."""

    def _sandi_lemah(self, panjang_minimum: int, wajib: list[str]) -> str:
        return "ab"  # pendek dan hanya huruf kecil

    def _alasan_lemah(self) -> str:
        return "pendek dan tanpa kombinasi"
