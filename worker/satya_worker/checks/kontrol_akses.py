"""Fungsi keamanan Kontrol Akses (ACCS) — check engine custom.

Lima check:
  access.horizontal        (ACCS-3.1-T01) IDOR baca lintas-pengguna (read-only, butuh 2 akun uji)
  access.vertical          (ACCS-3.1-T02) user biasa menolak fungsi admin
  access.rate_limit        (ACCS-3.2-T01) pembatasan laju (intrusif — butuh persetujuan)
  access.admin_panel_exposure (ACCS-3.3-T01) panel admin tak terbuka tanpa autentikasi
  access.token_validation  (ACCS-3.4-T01) token dimodifikasi/kedaluwarsa ditolak

Kasus respons ambigu (HTML/redirect/200 tak jelas kepemilikan) diserahkan ke tie-breaker AI
(`ai/akses.py`) yang menjawab pertanyaan FAKTUAL; AI tak pernah memutus lulus/gagal sendiri.
"""

from __future__ import annotations

import re as _re
import time
from urllib.parse import urlsplit, urlunsplit

from ..http_client import LuarRuangLingkup
from ..inpv.cakupan import KRITIS, _RX_ID
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, login_ambil

_JWT = _re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_MUTASI = {"PUT", "PATCH", "POST", "DELETE"}
_KUNCI_ID = ("id", "_id", "userId", "user_id", "uuid", "uid")


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "", bukti=None) -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=ringkasan, detail=detail, bukti=bukti or [])


def _akun_a(ctx: ScanContext):
    return ctx.akun("akun_uji_1") or ctx.akun("utama")


def _akun_b(ctx: ScanContext):
    return ctx.akun("akun_uji_2") or ctx.akun("penguncian")


def _id_dari_resp(resp) -> str | None:
    """Ambil identitas objek dari respons JSON (top-level atau di dalam 'data')."""
    try:
        data = resp.json()
    except Exception:
        return None
    for src in (data, data.get("data") if isinstance(data, dict) else None):
        if isinstance(src, dict):
            for k in _KUNCI_ID:
                v = src.get(k)
                if isinstance(v, (str, int)) and str(v):
                    return str(v)
    return None


def _sisip_id(url: str, path_template: str, nilai: str) -> str | None:
    """Ganti segmen ID pada URL dengan `nilai` spesifik. None bila tak ada segmen ID."""
    s = urlsplit(url)
    bagian = s.path.split("/")
    tmpl = path_template.split("/")
    diganti = False
    for i, seg in enumerate(bagian):
        if (i < len(tmpl) and tmpl[i] == "{id}") or _RX_ID.match(seg or "-"):
            bagian[i] = str(nilai)
            diganti = True
    if not diganti:
        return None
    return urlunsplit((s.scheme, s.netloc, "/".join(bagian), s.query, ""))


def _endpoint_objek(ctx: ScanContext, maks: int = 5) -> list[dict]:
    """Endpoint GET ber-`{id}` dalam ruang lingkup (kandidat IDOR), tanpa endpoint kritis."""
    out = []
    for ep in ctx.endpoints:
        if str(ep.get("metode_http") or "GET").upper() != "GET":
            continue
        path = str(ep.get("path_template") or "")
        url = str(ep.get("url") or "")
        if "{id}" not in path or not url or KRITIS.search(path):
            continue
        out.append(ep)
        if len(out) >= maks:
            break
    return out


def _rusak_token(tok: str) -> list[str]:
    """Varian token yang DIMODIFIKASI dari token valid (tanda tangan/isi dirusak)."""
    if not tok:
        return []
    if _JWT.match(tok):
        seg = tok.split(".")
        sig = seg[2] or "AAAA"
        sig_rusak = sig[:-1] + ("B" if sig[-1] != "B" else "C")
        return [".".join(seg[:2] + [sig_rusak])]
    varian = [tok[:-1] + ("B" if tok[-1] != "B" else "C")]
    if len(tok) > 6:
        varian.append(tok[: len(tok) // 2])  # dipotong
    return varian


def _tie_break(check_id: str, metadata: dict, hasil_tdv: HasilMetode, *, peta: dict[str, str],
               kunci_cache: str | None = None) -> HasilMetode:
    """Tajamkan hasil `tidak_dapat_diverifikasi` dengan AI tie-breaker (bila tersedia).

    AI hanya menjawab pertanyaan FAKTUAL; `peta` memetakan putusan faktual → status final.
    Putusan di luar `peta`, atau AI off/tak tersedia/gagal → kembalikan `hasil_tdv` apa adanya
    (degradasi anggun — hasil deterministik tetap utuh). AI tak pernah memutus lulus/gagal.
    """
    try:
        from ..ai import akses as ai_akses
        from ..ai import penggunaan
    except Exception:
        return hasil_tdv
    awal = penggunaan.potret()
    putusan, info = ai_akses.arbitrase_akses(check_id, metadata, kunci_cache=kunci_cache)
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


# =========================================================================== ACCS-3.1-T01

@check("access.horizontal")
class CekAksesHorizontal:
    """IDOR: akun A tidak boleh membaca objek milik akun B. Read-only (tak mengubah data)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun_a, akun_b = _akun_a(ctx), _akun_b(ctx)
            url_area = ctx.url_titik("area_terautentikasi")
            if akun_a is None or not akun_a.password or akun_b is None or not akun_b.password:
                hasil = _tdv(metode, "Membutuhkan DUA akun uji (akun_uji_1 & akun_uji_2) untuk uji akses horizontal.")
            elif url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "area_terautentikasi" tidak tersedia untuk menemukan identitas objek.')
            else:
                try:
                    hasil = self._uji(ctx, metode, akun_a, akun_b, url_area)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint untuk uji akses horizontal.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx, metode, akun_a, akun_b, url_area):
        endpoints = _endpoint_objek(ctx)
        if not endpoints:
            return _tdv(metode, "Tak ada endpoint objek ber-{id} (GET) hasil discovery untuk uji IDOR — dikonfirmasi asesor.")
        with buat_klien(ctx) as kB:
            rB = login_ambil(kB, ctx, akun_b, judul=f"{metode.id} — login akun B")
            id_b = _id_dari_resp(kB.kirim("GET", url_area, judul_bukti=f"{metode.id} — identitas akun B")) if rB["ok"] else None
        with buat_klien(ctx) as kA:
            rA = login_ambil(kA, ctx, akun_a, judul=f"{metode.id} — login akun A")
            id_a = _id_dari_resp(kA.kirim("GET", url_area, judul_bukti=f"{metode.id} — identitas akun A")) if rA["ok"] else None
            if not rA["ok"] or not rB["ok"] or not id_b:
                return _tdv(metode, "Gagal login dua akun atau identitas objek akun B tak terbaca dari area terautentikasi.", bukti=list(kA.bukti))
            ambigu = None
            for ep in endpoints:
                url_b = _sisip_id(str(ep.get("url")), str(ep.get("path_template")), id_b)
                if not url_b:
                    continue
                resp = kA.kirim("GET", url_b, judul_bukti=f"{metode.id} — akun A akses objek milik B: {ep.get('path_template')}")
                ctype = resp.headers.get("content-type", "").lower()
                teks = resp.text or ""
                if resp.status_code in (401, 403, 404):
                    continue  # objek B ditolak untuk A → baik
                if resp.status_code == 200 and "text/html" not in ctype and (id_b in teks) and (not id_a or id_a not in teks):
                    bukti = list(kA.bukti)
                    return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Akun A membaca objek milik akun B (IDOR) pada {ep.get('path_template')} (HTTP 200).", detail=metode.kriteria_lulus, bukti=bukti)
                if resp.status_code == 200 and ambigu is None:
                    ambigu = {
                        "endpoint": str(ep.get("path_template")),
                        "status": resp.status_code,
                        "tipe_konten": ctype,
                        "panjang": len(teks),
                        "ada_penanda_pengguna_lain": id_b in teks,
                        "mirip_milik_sendiri": bool(id_a and id_a in teks),
                    }
            bukti = list(kA.bukti)
        if ambigu is None:
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Objek milik akun B ditolak/ tak terbaca oleh akun A pada semua endpoint teruji.", detail=metode.kriteria_lulus, bukti=bukti)
        hasil_tdv = _tdv(metode, f"Respons akses objek B ambigu pada {ambigu['endpoint']} (HTTP {ambigu['status']}).", bukti=bukti)
        return _tie_break("access.horizontal", ambigu, hasil_tdv,
                          peta={"milik_lain": "gagal", "milik_sendiri": "lulus", "publik_atau_kosong": "lulus"})


# =========================================================================== ACCS-3.1-T02

@check("access.vertical")
class CekAksesVertikal:
    """Pengguna biasa tidak boleh mengakses fungsi administrator (privilege vertikal)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_a(ctx)
            url_admin = ctx.url_titik("admin")
            if url_admin is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "admin" tidak tersedia pada aplikasi.')
            elif akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji (peran biasa) untuk mengakses fungsi admin.")
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login akun biasa")
                        if not r["ok"]:
                            hasil = _tdv(metode, "Gagal login dengan akun uji.", bukti=list(klien.bukti))
                        else:
                            resp = klien.kirim("GET", url_admin, judul_bukti=f"{metode.id} — akun biasa akses fungsi admin")
                            bukti = list(klien.bukti)
                            ctype = resp.headers.get("content-type", "").lower()
                            if resp.status_code in (401, 403):
                                hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Fungsi admin menolak akun biasa (HTTP {resp.status_code}).", detail=metode.kriteria_lulus, bukti=bukti)
                            elif resp.status_code == 200 and "text/html" not in ctype:
                                hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Akun biasa mengakses fungsi admin (HTTP 200, {ctype or 'non-HTML'}).", detail=metode.kriteria_lulus, bukti=bukti)
                            else:
                                hasil_tdv = _tdv(metode, f"Respons fungsi admin ambigu (HTTP {resp.status_code}, {ctype or 'tanpa tipe'}).", bukti=bukti)
                                teks = (resp.text or "").lower()
                                metadata = {"status": resp.status_code, "tipe_konten": ctype, "panjang": len(resp.text or ""),
                                            "ada_sinyal_login": any(k in teks for k in ("type=password", "login", "masuk", "sign in")),
                                            "ada_menu_admin": any(k in teks for k in ("admin", "dashboard", "kelola", "manage", "pengguna"))}
                                hasil = _tie_break("access.vertical", metadata, hasil_tdv,
                                                   peta={"admin_tersaji": "gagal", "ditolak": "lulus"},
                                                   kunci_cache=f"vertical|{urlsplit(url_admin).path}")
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi fungsi admin.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== ACCS-3.4-T01

@check("access.token_validation")
class CekValidasiToken:
    """Token sesi yang dimodifikasi/kedaluwarsa harus ditolak pada data terbatas (401/403)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            akun = _akun_a(ctx)
            url_area = ctx.url_titik("area_terautentikasi")
            if url_area is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "area_terautentikasi" tidak tersedia pada aplikasi.')
            elif akun is None or not akun.password:
                hasil = _tdv(metode, "Membutuhkan akun uji untuk memperoleh token sah lebih dulu.")
            else:
                try:
                    with buat_klien(ctx) as klien:
                        r = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login untuk token sah")
                        token = r.get("token")
                        if not r["ok"] or not token:
                            hasil = _tdv(metode, "Uji ini memerlukan sesi berbasis token (tak ada token sah diperoleh).", bukti=list(klien.bukti))
                        else:
                            hasil = self._uji_token(ctx, metode, token)
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi endpoint sesi.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji_token(self, ctx, metode, token):
        url_area = ctx.url_titik("area_terautentikasi")
        varian = _rusak_token(token)
        if not varian:
            return _tdv(metode, "Tak dapat membentuk varian token yang dimodifikasi.")
        ambigu = None
        with buat_klien(ctx) as klien:
            for i, rusak in enumerate(varian):
                klien.pakai_token(rusak)
                resp = klien.kirim("GET", url_area, judul_bukti=f"{metode.id} — akses dengan token dimodifikasi #{i + 1}")
                ctype = resp.headers.get("content-type", "").lower()
                if resp.status_code in (401, 403):
                    continue  # ditolak → baik
                if resp.status_code == 200 and "text/html" not in ctype:
                    bukti = list(klien.bukti)
                    return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Token dimodifikasi tetap diterima (HTTP 200, {ctype or 'non-HTML'}) — validasi token lemah.", detail=metode.kriteria_lulus, bukti=bukti)
                if ambigu is None:
                    ambigu = {"status": resp.status_code, "tipe_konten": ctype, "panjang": len(resp.text or "")}
            bukti = list(klien.bukti)
        if ambigu is None:
            return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Semua varian token dimodifikasi ditolak (401/403).", detail=metode.kriteria_lulus, bukti=bukti)
        hasil_tdv = _tdv(metode, f"Respons token dimodifikasi ambigu (HTTP {ambigu['status']}, {ambigu['tipe_konten'] or 'tanpa tipe'}).", bukti=bukti)
        return _tie_break("access.token_validation", ambigu, hasil_tdv,
                          peta={"tak_autentik": "lulus", "autentik": "gagal"})


# =========================================================================== ACCS-3.2-T01 (intrusif)

@check("access.rate_limit")
class CekPembatasanLaju:
    """Pembatasan laju pada fungsi yang diakses terus-menerus (profil intrusif)."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            if not ctx.intrusif.izinkan_penguncian:
                hasil = _tdv(metode, "Uji pembatasan laju bersifat intrusif — butuh persetujuan uji (izinkan_penguncian/profil intrusif).")
            else:
                url = ctx.url_titik("form_input") or ctx.url_titik("area_terautentikasi")
                if url is None:
                    hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "form_input" tidak tersedia untuk uji pembatasan laju.')
                else:
                    n = int(metode.parameter.get("jumlah_request", 20))
                    kode: list[int] = []
                    try:
                        with buat_klien(ctx) as klien:
                            for i in range(n):
                                resp = klien.kirim("GET", url, judul_bukti=f"{metode.id} — request #{i + 1}")
                                kode.append(resp.status_code)
                                if resp.status_code == 429:
                                    break
                            bukti = list(klien.bukti)[:4]
                    except (LuarRuangLingkup, Exception) as e:
                        hasil = _tdv(metode, "Gagal menghubungi endpoint untuk uji pembatasan laju.", f"{type(e).__name__}: {e}")
                        hasil.durasi_ms = jam.durasi_ms
                        return hasil
                    if 429 in kode:
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Aplikasi membatasi request berlebih (HTTP 429 setelah {len(kode)} request).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Tidak ada pembatasan laju setelah {len(kode)} request beruntun (tak ada 429).", detail=metode.kriteria_lulus, bukti=bukti, menunggu_tinjauan=True)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# =========================================================================== ACCS-3.3-T01

@check("access.admin_panel_exposure")
class CekPaparanPanelAdmin:
    """Panel admin tidak boleh dapat diakses publik TANPA autentikasi."""

    def run(self, ctx, metode):
        with Pewaktu() as jam:
            url_admin = ctx.url_titik("admin")
            if url_admin is None:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "admin" tidak tersedia pada aplikasi.')
            else:
                try:
                    with buat_klien(ctx) as klien:  # TANPA login
                        resp = klien.kirim("GET", url_admin, judul_bukti=f"{metode.id} — akses panel admin tanpa autentikasi")
                        bukti = list(klien.bukti)
                    sc = resp.status_code
                    lokasi = resp.headers.get("location", "").lower()
                    ctype = resp.headers.get("content-type", "").lower()
                    if sc in (401, 403):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Panel admin menolak akses tanpa autentikasi (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)
                    elif sc in (301, 302, 303, 307, 308) and any(k in lokasi for k in ("login", "masuk", "auth", "signin")):
                        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=f"Panel admin mengalihkan ke login (HTTP {sc}).", detail=metode.kriteria_lulus, bukti=bukti)
                    elif sc == 200 and "text/html" not in ctype:
                        hasil = HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Panel admin mengembalikan data tanpa autentikasi (HTTP 200, {ctype or 'non-HTML'}).", detail=metode.kriteria_lulus, bukti=bukti)
                    else:
                        hasil_tdv = _tdv(metode, f"Respons panel admin tanpa autentikasi ambigu (HTTP {sc}, {ctype or 'tanpa tipe'}).", bukti=bukti)
                        teks = (resp.text or "").lower()
                        metadata = {"status": sc, "tipe_konten": ctype, "panjang": len(resp.text or ""),
                                    "ada_sinyal_login": any(k in teks for k in ("type=password", "login", "masuk", "sign in")),
                                    "ada_menu_admin": any(k in teks for k in ("admin", "dashboard", "kelola", "manage", "pengguna"))}
                        hasil = _tie_break("access.admin_panel_exposure", metadata, hasil_tdv,
                                           peta={"panel_terbuka": "gagal", "ditolak_atau_login": "lulus"},
                                           kunci_cache=f"admin_exposure|{urlsplit(url_admin).path}")
                except (LuarRuangLingkup, Exception) as e:
                    hasil = _tdv(metode, "Gagal menghubungi panel admin.", f"{type(e).__name__}: {e}")
        hasil.durasi_ms = jam.durasi_ms
        return hasil
