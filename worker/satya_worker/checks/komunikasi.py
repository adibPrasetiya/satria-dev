"""Fungsi 8 — Keamanan Komunikasi (COMM). Lihat katalog `controls/bssn_web.yaml` (COMM-8.1…8.4).

Dua lapis alat:
  - **custom (httpx)**  COMM-8.1: `tls.https_enforced`, `headers.hsts` — probing HTTP/header.
  - **sslyze**          COMM-8.3/8.4: `tls.protocol_versions`, `tls.weak_ciphers`,
                        `tls.certificate_validity`, `tls.certificate_browser_trust`,
                        `tls.certificate_issuer_psre`.
(`tls.mixed_content` COMM-8.2-T01 ditangani engine `zap` di `zap_scan.py`; `manual.outbound_tls`
COMM-8.2-T02 diserahkan asesor.)

Prinsip anti-false-positif: verdict deterministik dari handshake TLS/respons nyata. Bila target
bukan HTTPS / tak terjangkau / alat (sslyze) tak terpasang → `tidak_dapat_diverifikasi` +
`menunggu_tinjauan` (TIDAK `gagal` tanpa bukti). AI (lih. `ai/komunikasi.py`) hanya menajamkan:
klasifikasi penerbit→PSrE (info) dan adjudikasi kecocokan host yang ambigu; AI tak memutus lulus/gagal.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from ..http_client import LuarRuangLingkup
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, hosts_target
from .. import sslyze_client as ssl


# --------------------------------------------------------------------------- util bersama

def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


def _skema(url: str) -> str:
    return urlsplit(url).scheme.lower()


def _versi(url: str, skema: str) -> str:
    b = urlsplit(url)
    return urlunsplit((skema, b.netloc, b.path or "/", b.query, ""))


def _dalam_lingkup(ctx: ScanContext, host: str) -> bool:
    izin = hosts_target(ctx)
    return bool(host) and (not izin or host in izin)


def _scan_tls(ctx: ScanContext, metode: MetodeSpec) -> tuple[dict | None, HasilMetode | None]:
    """Jalankan/ambil cache scan sslyze untuk host base_url. Return (hasil, None) atau (None, HasilMetode_tdv)."""
    host, port = ssl.host_port(ctx.base_url)
    if not host:
        return None, HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
    if not _dalam_lingkup(ctx, host):
        return None, _tdv(metode, "Host di luar lingkup yang diizinkan.")
    if not ssl.aktif():
        return None, _tdv(metode, "Engine sslyze dinonaktifkan (SSLYZE_ENABLE=0).")
    if not ssl.tersedia():
        return None, _tdv(metode, "Paket sslyze belum terpasang pada worker — diserahkan asesor.",
                          "Pasang `sslyze` di requirements worker untuk mengotomasi uji TLS.")
    ctx.langkah("handshake_tls", f"Menjabat TLS ke {host}:{port} (sslyze)", host=host, port=port)
    hasil = ssl.pindai(ctx.base_url)
    if not hasil.get("ok"):
        return None, _tdv(metode, f"Tidak dapat menjabat TLS pada {host}:{port}.", str(hasil.get("galat") or ""))
    return hasil, None


def _bukti_tls(judul: str, data: dict) -> Bukti:
    import json

    return Bukti(jenis="dokumen", judul=judul, isi=json.dumps(data, ensure_ascii=False, indent=2))


# =========================================================================== COMM-8.1-T01

@check("tls.https_enforced")
class CekHttpsEnforced:
    """Seluruh path dilayani lewat HTTPS: akses HTTP harus dialihkan ke HTTPS (atau tak melayani)."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _paths(self, ctx: ScanContext) -> list[str]:
        """Beberapa path wakil: root + path titik uji + sampel endpoint discovery (maks 5 path unik)."""
        paths = ["/"]
        for t in ctx.titik_uji.values():
            if t.url:
                p = urlsplit(t.url).path or "/"
                if p not in paths:
                    paths.append(p)
        for ep in ctx.endpoints[:20]:
            u = str(ep.get("url") or "")
            if u:
                p = urlsplit(u).path or "/"
                if p not in paths:
                    paths.append(p)
            if len(paths) >= 5:
                break
        return paths[:5]

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        host = urlsplit(ctx.base_url).hostname or ""
        if not host:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
        paths = self._paths(ctx)
        ctx.langkah("kumpul_path", f"Memeriksa {len(paths)} path lewat HTTP (tanpa enkripsi)", path=paths)

        gagal: list[str] = []
        tidak_permanen: list[str] = []
        aman: list[str] = []
        dapat_dihubungi = False
        bukti: list[Bukti] = []
        try:
            with buat_klien(ctx, follow_redirects=False, timeout=8.0) as klien:
                for p in paths:
                    url_http = urlunsplit(("http", urlsplit(ctx.base_url).netloc, p, "", ""))
                    try:
                        resp = klien.kirim("GET", url_http, judul_bukti=f"{metode.id} — akses HTTP {p}")
                    except LuarRuangLingkup:
                        continue
                    except Exception:
                        # Port HTTP tidak melayani path ini → aman (tak ada kanal tanpa enkripsi).
                        aman.append(p)
                        continue
                    dapat_dihubungi = True
                    lok = resp.headers.get("location", "").lower()
                    sc = resp.status_code
                    if 300 <= sc < 400 and lok.startswith("https://"):
                        aman.append(p)
                        if sc not in (301, 308):
                            tidak_permanen.append(p)
                    elif 300 <= sc < 400:
                        gagal.append(f"{p} (redirect ke non-HTTPS, HTTP {sc})")
                    else:
                        gagal.append(f"{p} (dilayani lewat HTTP {sc})")
                bukti = list(klien.bukti)
        except Exception as e:
            return _tdv(metode, "Gagal memeriksa pemberlakuan HTTPS.", f"{type(e).__name__}: {e}")

        if gagal:
            ctx.langkah("evaluasi", "Ada path yang tidak memberlakukan HTTPS", hasil="tidak_aman", path_gagal=gagal)
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"{len(gagal)} path tidak dialihkan ke HTTPS: {', '.join(gagal[:3])}"
                                         + ("…" if len(gagal) > 3 else "") + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if not dapat_dihubungi and _skema(ctx.base_url) != "https":
            return _tdv(metode, "Kanal HTTP tak melayani dan aplikasi tidak diakses via HTTPS — tak dapat dipastikan.")
        if tidak_permanen:
            ctx.langkah("evaluasi", "Dialihkan ke HTTPS tetapi tidak permanen (301/308)", path=tidak_permanen)
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Akses HTTP dialihkan ke HTTPS tetapi tidak permanen pada: {', '.join(tidak_permanen)} (gunakan 301/308).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        ctx.langkah("evaluasi", "Semua path memberlakukan HTTPS", hasil="aman", path_aman=aman)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Seluruh {len(aman)} path diakses memberlakukan HTTPS (redirect permanen / HTTP tak melayani).",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== COMM-8.1-T02

@check("headers.hsts")
class CekHsts:
    """Header HTTP Strict-Transport-Security ada dengan max-age memadai."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        host = urlsplit(ctx.base_url).hostname or ""
        if not host:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
        min_age = int(metode.parameter.get("max_age_minimum", 31536000) or 31536000)
        url_https = _versi(ctx.base_url, "https")
        ctx.langkah("ambil_header", "Mengambil header respons HTTPS", url=url_https)
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=8.0) as klien:
                resp = klien.kirim("GET", url_https, judul_bukti=f"{metode.id} — header HSTS")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL di luar host yang diizinkan.", str(e))
        except Exception as e:
            return _tdv(metode, "Gagal menghubungi aplikasi via HTTPS untuk memeriksa HSTS.", f"{type(e).__name__}: {e}")

        raw = resp.headers.get("strict-transport-security", "")
        if not raw:
            ctx.langkah("evaluasi", "Header Strict-Transport-Security tidak ada", hasil="tidak_ada")
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Respons HTTPS tidak mengirim header Strict-Transport-Security (HSTS).",
                               detail=metode.kriteria_lulus, bukti=bukti)
        max_age = self._max_age(raw)
        sub = "includesubdomains" in raw.lower()
        preload = "preload" in raw.lower()
        detail = f"HSTS: {raw}\nmax-age={max_age} (min {min_age}); includeSubDomains={sub}; preload={preload}"
        if max_age is None:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Header HSTS ada tetapi tanpa max-age yang valid: '{raw}'.",
                               detail=detail, bukti=bukti)
        if max_age < min_age:
            ctx.langkah("evaluasi", f"max-age HSTS terlalu pendek ({max_age} < {min_age})", hasil="lemah")
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"HSTS max-age={max_age} detik kurang dari minimum {min_age} (≈1 tahun).",
                               detail=detail, bukti=bukti)
        ctx.langkah("evaluasi", f"HSTS memadai (max-age={max_age})", hasil="aman")
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Header HSTS aktif dengan max-age={max_age} detik (≥ {min_age}).",
                           detail=detail, bukti=bukti)

    @staticmethod
    def _max_age(raw: str) -> int | None:
        for bagian in raw.split(";"):
            bagian = bagian.strip().lower()
            if bagian.startswith("max-age"):
                _, _, nilai = bagian.partition("=")
                try:
                    return int(nilai.strip().strip('"'))
                except ValueError:
                    return None
        return None


# =========================================================================== COMM-8.3-T01

@check("tls.protocol_versions", engine="sslyze")
class CekVersiProtokol:
    """Hanya TLS 1.2 & 1.3 aktif; SSL 2.0/3.0 dan TLS 1.0/1.1 harus nonaktif."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                proto = scan["protokol"]
                usang = [n for n in ("SSL 2.0", "SSL 3.0", "TLS 1.0", "TLS 1.1") if proto.get(n) is True]
                modern = [n for n in ("TLS 1.2", "TLS 1.3") if proto.get(n) is True]
                bukti = [_bukti_tls(f"{metode.id} — versi protokol TLS", {"protokol": proto})]
                ctx.langkah("evaluasi", "Memeriksa versi protokol aktif", usang=usang, modern=modern)
                if usang:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan=f"Protokol usang masih aktif: {', '.join(usang)}. Hanya TLS 1.2/1.3 yang boleh.",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                elif not modern:
                    hasil = _tdv(metode, "Tidak dapat memastikan versi TLS yang didukung server.")
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                        ringkasan=f"Hanya protokol modern aktif: {', '.join(modern)}; tak ada SSL/TLS usang.",
                                        detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== COMM-8.3-T02

@check("tls.weak_ciphers", engine="sslyze")
class CekCipherLemah:
    """Tak ada cipher NULL/EXPORT/RC4/3DES; forward secrecy didukung."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                lemah = scan["cipher_lemah"]
                fs = scan["forward_secrecy"]
                ada_data = bool(scan["cipher_per_protokol"])
                bukti = [_bukti_tls(f"{metode.id} — cipher suite", {
                    "cipher_lemah": lemah, "forward_secrecy": fs,
                    "cipher_per_protokol": scan["cipher_per_protokol"],
                })]
                ctx.langkah("evaluasi", "Memeriksa cipher suite & forward secrecy",
                            jumlah_lemah=len(lemah), forward_secrecy=fs)
                if not ada_data:
                    hasil = _tdv(metode, "Tidak dapat mengenumerasi cipher suite server.")
                elif lemah:
                    daftar = ", ".join(f"{c['cipher']} ({c['protokol']})" for c in lemah[:4])
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan=f"{len(lemah)} cipher lemah aktif: {daftar}" + ("…" if len(lemah) > 4 else "") + ".",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                elif not fs:
                    hasil = HasilMetode(metode_id=metode.id, status="gagal",
                                        ringkasan="Tidak ada cipher dengan forward secrecy (ECDHE/DHE atau TLS 1.3).",
                                        detail=metode.kriteria_lulus, bukti=bukti)
                else:
                    hasil = HasilMetode(metode_id=metode.id, status="lulus",
                                        ringkasan="Tak ada cipher lemah (NULL/EXPORT/RC4/3DES); forward secrecy didukung.",
                                        detail=metode.kriteria_lulus, bukti=bukti)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== COMM-8.4-T01

@check("tls.certificate_validity", engine="sslyze")
class CekValiditasSertifikat:
    """Sertifikat valid: belum kedaluwarsa, cocok dengan host, rantai lengkap."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                hasil = self._nilai(ctx, metode, scan)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx: ScanContext, metode: MetodeSpec, scan: dict) -> HasilMetode:
        cert = scan.get("sertifikat") or {}
        if not cert.get("tersedia"):
            return _tdv(metode, "Server tidak menyajikan sertifikat yang dapat dianalisis.", str(cert.get("galat") or ""))
        bukti = [_bukti_tls(f"{metode.id} — sertifikat", {k: cert.get(k) for k in
                 ("subjek_cn", "san", "penerbit_o", "penerbit_cn", "tidak_sesudah", "hari_tersisa",
                  "host_cocok", "urutan_rantai_valid", "panjang_rantai")})]
        host = urlsplit(ctx.base_url).hostname or ""
        masalah: list[str] = []
        if cert.get("kedaluwarsa") is True:
            masalah.append(f"kedaluwarsa (berakhir {cert.get('tidak_sesudah')})")

        host_cocok = cert.get("host_cocok")
        if host_cocok is None:
            # Ambigu (sslyze tak memastikan) → tie-break AI faktual dari SAN; AI tak memutus lulus/gagal.
            host_cocok = self._tie_break_host(ctx, host, cert)
        if host_cocok is False:
            masalah.append(f"nama host '{host}' tak cocok dengan sertifikat (SAN: {', '.join(cert.get('san') or []) or '-'})")

        if cert.get("urutan_rantai_valid") is False:
            masalah.append("urutan rantai sertifikat tidak valid")
        if int(cert.get("panjang_rantai") or 0) <= 1:
            masalah.append("rantai sertifikat tidak lengkap (tanpa intermediate)")

        ctx.langkah("evaluasi", "Memeriksa validitas sertifikat", masalah=masalah or ["tidak ada"])
        if masalah:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Sertifikat bermasalah: " + "; ".join(masalah) + ".",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if host_cocok is None:
            return _tdv(metode, "Kecocokan nama host sertifikat tak dapat dipastikan — diserahkan asesor.",
                        metode.kriteria_lulus)
        sisa = cert.get("hari_tersisa")
        catatan = f" Sisa masa berlaku {sisa} hari." if isinstance(sisa, int) else ""
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Sertifikat valid: belum kedaluwarsa, cocok dengan host, rantai lengkap.{catatan}",
                           detail=metode.kriteria_lulus, bukti=bukti)

    def _tie_break_host(self, ctx: ScanContext, host: str, cert: dict) -> bool | None:
        try:
            from ..ai import komunikasi as ai_comm
            from ..ai import penggunaan
        except Exception:
            return None
        awal = penggunaan.potret()
        putusan, info = ai_comm.arbitrase_host({"host_diminta": host, "subjek_cn": cert.get("subjek_cn"), "san": cert.get("san")})
        if putusan is None:
            return None
        pakai = penggunaan.selisih(awal)
        ctx.catat("info", f"[AI] kecocokan host: {putusan['putusan']} ({pakai.get('panggilan', 0)} panggilan)")
        if putusan["putusan"] == "cocok":
            return True
        if putusan["putusan"] == "tidak_cocok":
            return False
        return None


# =========================================================================== COMM-8.4-T02

@check("tls.certificate_browser_trust", engine="sslyze")
class CekTrustBrowser:
    """Rantai sertifikat tervalidasi terhadap root store web browser (mozilla/microsoft/apple/android)."""

    # Peta slug katalog → substring nama trust store bawaan sslyze (nabla-c0d3/trust_stores_observatory).
    # Nilai = tuple substring yang diterima (nama Microsoft pernah berganti "Windows"↔"Microsoft").
    _PETA = {
        "mozilla": ("mozilla",),
        "microsoft": ("windows", "microsoft"),
        "apple": ("apple",),
        "android": ("android",),
        "google": ("google", "chrome"),
        "java": ("java", "oracle"),
    }

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                hasil = self._nilai(ctx, metode, scan)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx: ScanContext, metode: MetodeSpec, scan: dict) -> HasilMetode:
        cert = scan.get("sertifikat") or {}
        trust: dict[str, bool] = cert.get("trust") or {}
        if not cert.get("tersedia") or not trust:
            return _tdv(metode, "Tidak ada hasil validasi trust store dari sslyze.")
        diminta = [str(s).lower() for s in (metode.parameter.get("root_store") or ["mozilla", "microsoft", "apple", "android"])]
        bukti = [_bukti_tls(f"{metode.id} — validasi trust store", {"diminta": diminta, "hasil": trust})]

        gagal: list[str] = []
        tervalidasi: list[str] = []
        tak_tersedia: list[str] = []
        for slug in diminta:
            subs = self._PETA.get(slug, (slug,))
            cocok = {nama: ok for nama, ok in trust.items() if any(s in nama.lower() for s in subs)}
            if not cocok:
                tak_tersedia.append(slug)
            elif all(cocok.values()):
                tervalidasi.append(slug)
            else:
                gagal.append(slug)

        ctx.langkah("evaluasi", "Memvalidasi rantai terhadap root store browser",
                    tervalidasi=tervalidasi, gagal=gagal, tak_tersedia=tak_tersedia)
        if gagal:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Rantai sertifikat tidak dipercaya root store: {', '.join(gagal)}. "
                                         f"(Sertifikat PSrE Indonesia umumnya belum ada di root store browser.)",
                               detail=metode.kriteria_lulus, bukti=bukti)
        if not tervalidasi:
            return _tdv(metode, f"Root store yang diminta ({', '.join(diminta)}) tak tersedia pada sslyze untuk divalidasi.")
        cat = f" (root store tak tersedia di sslyze: {', '.join(tak_tersedia)})" if tak_tersedia else ""
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Rantai sertifikat dipercaya root store: {', '.join(tervalidasi)}.{cat}",
                           detail=metode.kriteria_lulus, bukti=bukti)


# =========================================================================== COMM-8.4-T03

@check("tls.certificate_issuer_psre", engine="sslyze")
class CekPenerbitPsre:
    """Informasional: apakah penerbit sertifikat termasuk PSrE yang diakui Komdigi.

    Severity info (katalog) → tak memengaruhi status kontrol; status selalu 'lulus'/'tidak_dapat_diverifikasi'.
    String-match dulu; bila tak cocok, AI mencoba fuzzy-match (varian nama/anak usaha).
    """

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            scan, tdv = _scan_tls(ctx, metode)
            if tdv is not None:
                hasil = tdv
            else:
                hasil = self._nilai(ctx, metode, scan)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _nilai(self, ctx: ScanContext, metode: MetodeSpec, scan: dict) -> HasilMetode:
        cert = scan.get("sertifikat") or {}
        org = str(cert.get("penerbit_o") or "")
        cn = str(cert.get("penerbit_cn") or "")
        if not cert.get("tersedia") or not (org or cn):
            return _tdv(metode, "Penerbit sertifikat tak dapat dibaca.")
        daftar = list(metode.parameter.get("daftar_psre") or [])
        penerbit = {"penerbit_o": org, "penerbit_cn": cn}
        bukti = [_bukti_tls(f"{metode.id} — penerbit sertifikat", penerbit)]

        cocok = self._string_match(org, cn, daftar)
        sumber = "pencocokan nama"
        if cocok is None and daftar:
            cocok = self._ai_match(ctx, penerbit, daftar)
            sumber = "AI (fuzzy)"

        ctx.langkah("evaluasi", "Mengidentifikasi penerbit sertifikat", penerbit_o=org, psre=bool(cocok))
        if cocok:
            ringkasan = f"[Info] Penerbit '{org or cn}' teridentifikasi sebagai PSrE: {cocok} ({sumber})."
        else:
            ringkasan = f"[Info] Penerbit '{org or cn}' TIDAK terdaftar pada daftar PSrE Komdigi — dikonfirmasi asesor."
        return HasilMetode(metode_id=metode.id, status="lulus", ringkasan=ringkasan,
                           detail=metode.kriteria_lulus, bukti=bukti)

    @staticmethod
    def _norm(s: str) -> str:
        return "".join(c for c in s.lower() if c.isalnum())

    def _string_match(self, org: str, cn: str, daftar: list[dict]) -> str | None:
        gabung = f"{self._norm(org)} {self._norm(cn)}"
        for p in daftar:
            nama = str(p.get("nama") or "")
            n = self._norm(nama)
            if not n:
                continue
            # Cocok bila nama PSrE (atau token khasnya) muncul pada nama penerbit, atau sebaliknya.
            if n in self._norm(org) or n in self._norm(cn):
                return nama
            for token in nama.replace("(", " ").replace(")", " ").split():
                tn = self._norm(token)
                if len(tn) >= 4 and (tn in gabung):
                    return nama
        return None

    def _ai_match(self, ctx: ScanContext, penerbit: dict, daftar: list[dict]) -> str | None:
        try:
            from ..ai import komunikasi as ai_comm
            from ..ai import penggunaan
        except Exception:
            return None
        awal = penggunaan.potret()
        kunci = "psre:" + self._norm(str(penerbit.get("penerbit_o") or penerbit.get("penerbit_cn") or ""))
        putusan, info = ai_comm.klasifikasi_psre(penerbit, daftar, kunci_cache=kunci)
        if putusan is None:
            return None
        pakai = penggunaan.selisih(awal)
        if not info.get("dari_cache") and pakai.get("panggilan"):
            ctx.catat("info", f"[AI] klasifikasi PSrE: {pakai['panggilan']} panggilan, ±{pakai['token']} token.")
        return str(putusan.get("nama_psre") or "") if putusan.get("psre_cocok") else None
