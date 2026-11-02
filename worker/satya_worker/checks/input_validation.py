"""Fungsi Validasi Input (INPV) — check yang membaca SAPUAN bersama (`satya_worker.inpv`).

Sapuan menguji seluruh endpoint inventaris sekali per scan; tiap check menilai observasi dari
sudut kriterianya sendiri:

  INPV-4.1-T01 input.server_side_validation  input tak valid dikirim langsung ke server (tanpa
               validasi klien) → harus ditolak; cakupan: endpoint asal form (cadangan: semua)
  INPV-4.2-T01/T02 input.reject_on_error     input tak valid ditolak dan TIDAK diproses
               (T01: endpoint asal form; T02: semua endpoint API); 5xx = galat tak tertangani
  INPV-4.4-T01 input.allowlist_validation    validasi positif tipe/format/rentang/enum per field
  INPV-4.7-T02 headers.csp                   Content-Security-Policy pada halaman frontend
  INPV-4.3-T01 input.runtime_known_cves      versi server/runtime terekspos + pustaka JS rentan (ZAP)

Vonis: GAGAL bila ada crash (5xx/stack trace) atau input tak valid yang DIPROSES; LULUS bila ada
penolakan nyata dan tak ada pelanggaran; selain itu TIDAK DAPAT DIVERIFIKASI (dengan alasannya).
Setiap hasil memuat matriks cakupan agar "semua endpoint diuji" dapat diaudit.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import httpx

from .. import inpv
from ..http_client import USER_AGENT
from ..inpv import vonis as vn
from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check

_JENIS_ALLOWLIST = {"tipe_salah", "format", "rentang", "enum", "ai"}


def _dengan_pewaktu(fn: Callable[[ScanContext, MetodeSpec], HasilMetode]) -> Callable[..., HasilMetode]:
    def run(self: Any, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            h = fn(ctx, metode)
        h.durasi_ms = jam.durasi_ms
        return h

    return run


def _daftar(obs: Iterable[vn.Observasi], n: int = 8) -> str:
    xs = [o.ringkas + (f" ({o.catatan})" if o.catatan else "") for o in obs]
    return "; ".join(xs[:n]) + (f"; … +{len(xs) - n}" if len(xs) > n else "")


def _field_unik(obs: Iterable[vn.Observasi]) -> list[str]:
    return sorted({f"{o.endpoint}:{o.field}" for o in obs})


def _detail(s: "inpv.Sapuan", obs: list[vn.Observasi], judul: str) -> str:
    hit: dict[str, int] = {}
    for o in obs:
        hit[o.kategori] = hit.get(o.kategori, 0) + 1
    ai = s.ai.get("pemakaian") or {}
    return (
        f"{s.teks_cakupan()}\n{judul}: {len(obs)} observasi — "
        + ", ".join(f"{k} {v}" for k, v in sorted(hit.items(), key=lambda x: -x[1]))
        + (f"\nAI: {ai.get('panggilan', 0)} panggilan, ±{ai.get('token', 0)} token." if ai.get("panggilan") else "")
        + (f"\nTertunda (batas request): {', '.join(s.tertunda[:20])}" if s.tertunda else "")
        + (f"\nCatatan sapuan: {s.galat}" if s.galat else "")
    )


def evaluasi(metode: MetodeSpec, s: "inpv.Sapuan", obs: list[vn.Observasi], *, judul: str, cakupan_kosong: str) -> HasilMetode:
    """Vonis bersama 4.1/4.2/4.4 dari observasi kelompok validasi (fungsi murni; dipakai tes)."""
    detail = _detail(s, obs, judul)
    if not obs:
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=cakupan_kosong,
                           detail=detail, menunggu_tinjauan=True)
    crash = [o for o in obs if o.kategori == "crash"]
    diproses, tak_pasti = [], []
    for o in obs:
        if o.kategori == "diterima":
            v = vn.diterima_diproses(o, o.endpoint.split(" ", 1)[0])
            (diproses if v else tak_pasti if v is None else []).append(o)
    ditolak = [o for o in obs if o.kategori == "ditolak_tepat"]
    tepat = [o for o in ditolak if o.field in o.disebut]
    belum_valid = [o for o in obs if o.kategori == "payload_belum_valid"]
    auth = [o for o in obs if o.kategori == "terblokir_auth"]
    bukti = list(s.bukti)

    if crash:
        return HasilMetode(
            metode_id=metode.id, status="gagal",
            ringkasan=f"{len(crash)} input tak valid memicu galat server (5xx/stack trace) pada {len(_field_unik(crash))} field — input tak ditangani.",
            detail=detail + "\nCrash: " + _daftar(crash), bukti=bukti,
        )
    if diproses:
        return HasilMetode(
            metode_id=metode.id, status="gagal",
            ringkasan=f"Input tak valid DITERIMA & diproses pada {len(_field_unik(diproses))} field: {', '.join(_field_unik(diproses)[:5])}.",
            detail=detail + "\nDiproses: " + _daftar(diproses) + (f"\nTak pasti: {_daftar(tak_pasti)}" if tak_pasti else ""), bukti=bukti,
        )
    if ditolak and len(tak_pasti) <= len(ditolak):
        return HasilMetode(
            metode_id=metode.id, status="lulus",
            ringkasan=(f"Server menolak input tak valid pada {len(_field_unik(ditolak))} field ({len(ditolak)} varian)"
                       + (f", {len(tepat)} galat menunjuk field yang diuji" if tepat else "")
                       + (f"; {len(tak_pasti)} varian diterima tanpa efek terlihat (dicatat)" if tak_pasti else "") + "."),
            detail=detail + (f"\nTak pasti: {_daftar(tak_pasti)}" if tak_pasti else ""), bukti=bukti,
        )
    if tak_pasti:
        return HasilMetode(
            metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
            ringkasan=f"{len(tak_pasti)} varian tak valid diterima (2xx) tanpa bukti diproses/ditolak — perlu tinjauan asesor.",
            detail=detail + "\nTak pasti: " + _daftar(tak_pasti), bukti=bukti,
        )
    if belum_valid:
        return HasilMetode(
            metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
            ringkasan=f"{len(belum_valid)} penolakan disebabkan field LAIN (payload dasar belum valid) — validasi field uji belum terbukti.",
            detail=detail + "\nField lain: " + _daftar(belum_valid), bukti=bukti,
        )
    if auth:
        return HasilMetode(
            metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
            ringkasan=f"Lapisan validasi tak tercapai: {len(auth)} request terblokir autentikasi (401/403)"
                      + ("" if s.login_ok else " — login akun uji gagal") + ".",
            detail=detail, bukti=bukti,
        )
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
                       ringkasan="Tidak ada respons yang menunjukkan penolakan maupun penerimaan input tak valid.",
                       detail=detail, bukti=bukti)


def _validasi(s: "inpv.Sapuan", *, form: bool | None = None, jenis: set[str] | None = None) -> list[vn.Observasi]:
    obs = [o for o in s.observasi if o.kelompok == "validasi" and (jenis is None or o.jenis in jenis)]
    if form is True:
        pilih = [o for o in obs if o.asal_form]
        return pilih or obs  # tanpa endpoint asal form → semua endpoint (dicatat di ringkasan cakupan)
    return obs


def _sapu(ctx: ScanContext) -> "inpv.Sapuan":
    return inpv.sapuan(ctx)


def _kosong(s: "inpv.Sapuan") -> str:
    c = s.cakupan()
    if not c["total"]:
        return "Inventaris endpoint belum tersedia (jalankan fase penemuan dulu)."
    return f"Tidak ada field yang bisa diuji ({c['dilewati']} endpoint dilewati, {c['tanpa_input']} tanpa input)."


@check("input.server_side_validation")
class CekValidasiServer:
    @staticmethod
    def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        s = _sapu(ctx)
        return evaluasi(metode, s, _validasi(s, form=True), judul="Validasi sisi server (endpoint asal form)", cakupan_kosong=_kosong(s))

    run = _dengan_pewaktu(_jalankan)


@check("input.reject_on_error")
class CekTolakInputTakValid:
    @staticmethod
    def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        s = _sapu(ctx)
        form = metode.titik_uji != "api"
        obs = _validasi(s, form=True) if form else _validasi(s)
        return evaluasi(metode, s, obs, judul="Penolakan input tak valid" + (" (form)" if form else " (API)"), cakupan_kosong=_kosong(s))

    run = _dengan_pewaktu(_jalankan)


@check("input.allowlist_validation")
class CekValidasiPositif:
    @staticmethod
    def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        s = _sapu(ctx)
        return evaluasi(metode, s, _validasi(s, jenis=_JENIS_ALLOWLIST), judul="Validasi tipe/format/rentang/enum",
                        cakupan_kosong=_kosong(s))

    run = _dengan_pewaktu(_jalankan)


# ------------------------------------------------------------------ indikasi injeksi (dipakai check ZAP)

INDIKASI_ZAP = {
    "zap.active.sqli_policy": {"indikasi_sqli"},
    "zap.active.xss_policy": {"refleksi"},
    "zap.active.code_injection_policy": {"indikasi_ssti"},
    "zap.active.injection_policy": {"indikasi_sqli", "indikasi_ssti"},
}


def indikasi_injeksi(ctx: ScanContext, check_id: str) -> tuple[list[vn.Observasi], "inpv.Sapuan | None"]:
    kat = INDIKASI_ZAP.get(check_id)
    if not kat:
        return [], None
    try:
        s = _sapu(ctx)
    except Exception:
        return [], None
    return [o for o in s.observasi if o.kategori in kat], s


# ------------------------------------------------------------------ CSP & versi runtime

def _ambil(url: str) -> httpx.Response | None:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as k:
            return k.get(url)
    except httpx.HTTPError:
        return None


_META_CSP = re.compile(r"<meta[^>]+http-equiv=[\"']content-security-policy[\"'][^>]*content=[\"']([^\"']+)", re.IGNORECASE)


def nilai_csp(header: str) -> tuple[str, str]:
    """Return (status, alasan) untuk satu kebijakan CSP (fungsi murni)."""
    arahan = {}
    for bagian in header.split(";"):
        t = bagian.strip().split()
        if t:
            arahan[t[0].lower()] = [x.lower() for x in t[1:]]
    skrip = arahan.get("script-src") or arahan.get("default-src")
    if skrip is None:
        return "gagal", "tidak ada script-src maupun default-src — skrip tak dibatasi"
    nonce_hash = any(x.startswith(("'nonce-", "'sha256-", "'sha384-", "'sha512-")) for x in skrip)
    if "'unsafe-inline'" in skrip and not nonce_hash:
        return "gagal", "script-src mengizinkan 'unsafe-inline' tanpa nonce/hash"
    if "*" in skrip or "data:" in skrip or "http:" in skrip:
        return "gagal", "script-src terlalu longgar (*, data:, atau http:)"
    catatan = " (catatan: 'unsafe-eval' diizinkan)" if "'unsafe-eval'" in skrip else ""
    return "lulus", "CSP membatasi sumber skrip" + catatan


@check("headers.csp")
class CekCsp:
    @staticmethod
    def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        url = ctx.url_titik("login_page") or ctx.base_url
        resp = _ambil(url)
        if resp is None:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=f"Halaman {url} tak dapat diambil.")
        ctx.langkah("periksa_header", "Memeriksa header Content-Security-Policy halaman frontend", url=url, status=resp.status_code)
        csp = resp.headers.get("content-security-policy", "")
        sumber = "header"
        if not csp:
            m = _META_CSP.search(resp.text[:100_000])
            csp, sumber = (m.group(1), "meta") if m else ("", "")
        bukti = [Bukti(jenis="request_response", judul=f"{metode.id} — header respons {url}",
                       isi=f"HTTP {resp.status_code}\nContent-Security-Policy: {csp or '(tidak ada)'}\n"
                           f"Content-Security-Policy-Report-Only: {resp.headers.get('content-security-policy-report-only', '(tidak ada)')}")]
        if not csp:
            ro = resp.headers.get("content-security-policy-report-only")
            return HasilMetode(metode_id=metode.id, status="gagal", bukti=bukti,
                               ringkasan="Content-Security-Policy tidak diterapkan" + (" (hanya Report-Only, tidak ditegakkan)." if ro else "."))
        st, alasan = nilai_csp(csp)
        return HasilMetode(metode_id=metode.id, status=st, ringkasan=f"CSP ({sumber}): {alasan}.", detail=csp[:1500], bukti=bukti)

    run = _dengan_pewaktu(_jalankan)


_HEADER_VERSI = ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator", "x-runtime-version")
_ADA_VERSI = re.compile(r"\d+\.\d+")


@check("input.runtime_known_cves")
class CekVersiRuntime:
    @staticmethod
    def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        from . import zap_scan

        origins = {ctx.base_url.rstrip("/")}
        for e in ctx.endpoints:
            u = httpx.URL(str(e.get("url") or ""))
            if u.host and (e.get("lapisan") or "api") == "api":
                origins.add(f"{u.scheme}://{u.host}" + (f":{u.port}" if u.port else ""))
        terekspos: list[str] = []
        for o in sorted(origins)[:6]:
            r = _ambil(o + "/")
            if r is None:
                continue
            for h in _HEADER_VERSI:
                v = r.headers.get(h, "")
                if v and _ADA_VERSI.search(v):
                    terekspos.append(f"{o} {h}: {v[:80]}")
        ctx.langkah("periksa_versi", "Memeriksa versi server/runtime yang terekspos", origin=len(origins), terekspos=len(terekspos))
        entri = zap_scan._cache.get(ctx.base_url) or {}  # noqa: SLF001 — pakai hasil ZAP yang sudah ada, tak memicu scan baru
        rentan = [a for a in entri.get("alerts", []) if str(a.get("pluginId")) == "10003" or str(a.get("cweid")) in ("1104", "829")]
        detail = ("Versi terekspos:\n" + "\n".join(terekspos) if terekspos else "Tidak ada header versi terekspos.") + \
                 (f"\nPustaka JS rentan (ZAP): {len(rentan)}" if entri else "\nData ZAP tidak tersedia pada worker ini.")
        if rentan:
            nama = ", ".join(sorted({str(a.get("alert") or a.get("name")) + " @ " + str(a.get("url", ""))[:60] for a in rentan}))[:300]
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Pustaka/kerangka kerja dengan kerentanan diketahui terdeteksi: {nama}.", detail=detail)
        if terekspos:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
                               ringkasan=f"{len(terekspos)} versi server/runtime terekspos — cocokkan dengan basis data CVE (tinjauan asesor).",
                               detail=detail)
        if not entri:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", menunggu_tinjauan=True,
                               ringkasan="Tidak ada versi terekspos, tetapi pemeriksaan pustaka JS (ZAP) tidak tersedia.", detail=detail)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan="Tidak ada versi server/runtime terekspos dan tidak ada pustaka JS rentan terdeteksi.", detail=detail)

    run = _dengan_pewaktu(_jalankan)
