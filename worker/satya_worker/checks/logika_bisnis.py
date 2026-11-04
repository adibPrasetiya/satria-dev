"""Fungsi 10 — Keamanan Logika Bisnis (BLOG). Lihat katalog `controls/bssn_web.yaml`.

Sebagian besar BLOG bersifat manual (butuh pemahaman alur bisnis spesifik) sehingga
diserahkan ke asesor:
  manual.workflow_order      (10.1) urutan langkah alur tak dapat dilompati
  manual.business_limits     (10.2) nilai di luar batas bisnis ditolak
  manual.anomaly_monitoring  (10.3) aktivitas tak biasa terpantau
  manual.alert_on_attack     (10.5) peringatan terkirim ke admin/CSIRT

Dapat diotomatiskan:
  antiauto.challenge_present (10.4-T01) → custom (DI SINI) — tantangan antiotomatisasi
                                          (CAPTCHA/reCAPTCHA/hCaptcha/Turnstile dll.) pada form publik
  access.rate_limit          (10.4-T02) → custom, dipakai ulang dari checks/kontrol_akses.py

Kontrol BLOG-10.4 beragregasi `minimal_satu`: lulus bila tantangan antiotomatisasi ADA
atau pembatasan laju aktif. Karena itu check ini bersikap konservatif — hanya memastikan
"lulus" saat penanda tantangan benar-benar terdeteksi; bila tak ada penanda (tantangan
mungkin disuntik JS runtime atau diberlakukan sisi server) ia melapor
`tidak_dapat_diverifikasi` + menunggu tinjauan, TIDAK langsung menghakimi gagal.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien

# Penanda penyedia tantangan antiotomatisasi (dicari pada HTML/skrip halaman form publik).
# Pasangan (label, regex) — regex sudah lower-case.
_PENANDA = [
    ("Google reCAPTCHA", r"recaptcha|grecaptcha|g-recaptcha|www\.google\.com/recaptcha|recaptcha\.net"),
    ("hCaptcha", r"hcaptcha|h-captcha|js\.hcaptcha\.com"),
    ("Cloudflare Turnstile", r"cf-turnstile|challenges\.cloudflare\.com/turnstile|turnstile\.min\.js"),
    ("FriendlyCaptcha", r"friendly-?captcha|friendlycaptcha\.com"),
    ("Arkose/FunCaptcha", r"arkoselabs|funcaptcha"),
    ("GeeTest", r"geetest|gt_captcha"),
    ("data-sitekey", r"data-sitekey\s*="),
    ("CAPTCHA generik", r"\bcaptcha\b"),
]


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "", bukti=None) -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus,
                       bukti=bukti or [], menunggu_tinjauan=True)


@check("antiauto.challenge_present")
class CekTantanganAntiotomatisasi:
    """Form publik (registrasi/login) dilindungi tantangan antiotomatisasi.

    Mengambil halaman form publik (registrasi, login, dan URL dasar) lalu memindai
    penanda penyedia CAPTCHA/tantangan pada HTML & skrip yang ter-render server.
    """

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        # Kumpulkan halaman kandidat: titik uji registrasi/login (bila dipetakan) + URL dasar.
        kandidat: list[str] = []
        for titik in ("registrasi", "login"):
            u = ctx.url_titik(titik)
            if u:
                kandidat.append(u)
        if ctx.base_url and ctx.base_url not in kandidat:
            kandidat.append(ctx.base_url)
        # Hilangkan duplikat sambil mempertahankan urutan.
        kandidat = list(dict.fromkeys(kandidat))
        if not kandidat:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku",
                               ringkasan="Tidak ada form publik (registrasi/login) maupun URL dasar untuk diperiksa.")

        gabungan = ""
        bukti: list = []
        diperiksa: list[str] = []
        galat: list[str] = []
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=8.0) as klien:
                for url in kandidat:
                    try:
                        resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — halaman {urlsplit(url).path or '/'}")
                    except LuarRuangLingkup as e:
                        galat.append(f"{url}: di luar ruang lingkup ({e})")
                        continue
                    diperiksa.append(url)
                    ctype = (resp.headers.get("content-type") or "").lower()
                    if "html" in ctype or not ctype:
                        gabungan += "\n" + (resp.text or "")
                bukti = list(klien.bukti)[:4]
        except Exception as e:
            return _tdv(metode, "Gagal menghubungi aplikasi untuk memeriksa tantangan antiotomatisasi.",
                        f"{type(e).__name__}: {e}")

        if not diperiksa:
            return _tdv(metode, "Semua halaman kandidat di luar ruang lingkup / tak dapat diambil.",
                        "; ".join(galat))

        low = gabungan.lower()
        ditemukan = [label for label, pola in _PENANDA if re.search(pola, low)]
        # 'captcha' generik hanya dihitung bila tak ada penanda penyedia spesifik (hindari ganda).
        if len(ditemukan) > 1 and "CAPTCHA generik" in ditemukan:
            ditemukan = [d for d in ditemukan if d != "CAPTCHA generik"]
        ctx.langkah("evaluasi", "Memindai penanda tantangan antiotomatisasi",
                    halaman=len(diperiksa), ditemukan=", ".join(ditemukan) or "-")

        if ditemukan:
            return HasilMetode(metode_id=metode.id, status="lulus",
                               ringkasan=f"Tantangan antiotomatisasi terdeteksi pada form publik: {', '.join(ditemukan)}.",
                               detail=metode.kriteria_lulus, bukti=bukti)

        # Tidak ada penanda statis — bisa jadi disuntik JS runtime atau diberlakukan sisi server
        # (mis. pembatasan laju; lihat access.rate_limit). Serahkan ke asesor, jangan hakimi gagal.
        return _tdv(metode,
                    f"Tidak ada penanda tantangan antiotomatisasi pada {len(diperiksa)} halaman form publik "
                    "(mungkin disuntik JavaScript runtime atau diberlakukan sisi server).",
                    metode.kriteria_lulus, bukti=bukti)
