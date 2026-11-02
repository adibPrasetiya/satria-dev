"""Orkestrasi sapuan INPV: rencanakan cakupan → profil field (+AI) → kirim varian → vonis (+AI ambigu).

Satu sapuan per scan (cache per proses, kunci `scan_id`). Pengaman:
  - batas total request `INPV_MAKS_REQUEST` (bawaan 600) — sisa endpoint dicatat `tertunda`;
  - jeda antar-request `INPV_JEDA_MS` (bawaan 50 ms);
  - mutasi (PUT/PATCH/DELETE) hanya ke ID fiktif; endpoint kritis tak disentuh (lihat cakupan.py);
  - pembatalan scan dicek di antara endpoint (`koordinasi.periksa_batal`).
Peristiwa request untuk animasi dibatasi (baseline + 2 varian pertama per endpoint + semua 5xx) agar
UI tak dibanjiri ratusan request.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from .. import atribusi_sandi as asd
from .. import koordinasi
from ..http_client import KlienScan, LuarRuangLingkup
from ..models import Bukti, ScanContext
from ..sesi import hosts_target, login
from . import cakupan as ck
from . import payload as pl
from . import profil_field as pf
from . import vonis as vn

_SUMBER_FORM = {"browser-intersep", "html", "browser"}
_TITIK_FORM = {"login", "registrasi", "reset_password", "form_input"}
MAKS_BUKTI = 25

_cache: dict[str, "Sapuan"] = {}
_kunci = threading.Lock()


@dataclass
class Sapuan:
    rencana: list[ck.Rencana] = field(default_factory=list)
    observasi: list[vn.Observasi] = field(default_factory=list)
    tertunda: list[str] = field(default_factory=list)
    bukti: list[Bukti] = field(default_factory=list)
    jumlah_request: int = 0
    login_ok: bool = False
    ai: dict[str, Any] = field(default_factory=dict)
    galat: str = ""

    def cakupan(self) -> dict[str, Any]:
        hit: dict[str, int] = {"diuji": 0, "tanpa_input": 0, "dilewati": 0}
        alasan: dict[str, int] = {}
        for r in self.rencana:
            hit[r.status] += 1
            if r.status == "dilewati":
                alasan[r.alasan] = alasan.get(r.alasan, 0) + 1
        return {"total": len(self.rencana), **hit, "tertunda": len(self.tertunda), "alasan_dilewati": alasan}

    def teks_cakupan(self, *, rencana: bool = False) -> str:
        c = self.cakupan()
        if rencana:
            return (f"Rencana cakupan INPV: {c['total']} endpoint = {c['diuji']} diuji + {c['tanpa_input']} tanpa input"
                    f" + {c['dilewati']} dilewati.")
        teks = (f"Matriks cakupan INPV: {c['total']} endpoint = {c['diuji']} diuji + {c['tanpa_input']} tanpa input"
                f" + {c['dilewati']} dilewati" + (f" + {c['tertunda']} tertunda (batas request)" if c["tertunda"] else "")
                + f"; {self.jumlah_request} request.")
        if c["alasan_dilewati"]:
            teks += " Dilewati: " + "; ".join(f"{n}× {a}" for a, n in c["alasan_dilewati"].items()) + "."
        return teks


def sapuan(ctx: ScanContext) -> Sapuan:
    """Sapuan INPV untuk scan ini (dijalankan sekali; panggilan berikutnya memakai cache)."""
    kunci = ctx.scan_id or ctx.base_url
    with _kunci:
        if kunci not in _cache:
            _cache[kunci] = _jalankan(ctx)
        return _cache[kunci]


def reset_cache() -> None:
    with _kunci:
        _cache.clear()


def _env_int(nama: str, bawaan: int) -> int:
    try:
        return int(os.environ.get(nama, str(bawaan)))
    except ValueError:
        return bawaan


def _endpoints(ctx: ScanContext) -> list[dict[str, Any]]:
    if ctx.endpoints:
        return list(ctx.endpoints)
    # Cadangan: kandidat INPV (konteks lama tanpa inventaris lengkap).
    return [{**e, "lapisan": e.get("lapisan") or "api"} for e in ctx.kandidat_untuk("INPV")]


def _asal_form(ep: dict[str, Any]) -> bool:
    return bool(set(ep.get("sumber") or []) & _SUMBER_FORM and str(ep.get("metode_http", "GET")).upper() != "GET") \
        or (ep.get("titik_uji") or "") in _TITIK_FORM


def _url_query(url: str, params: dict[str, Any]) -> str:
    s = urlsplit(url)
    q = urlencode({k: "" if v is None else (v if isinstance(v, str) else str(v)) for k, v in params.items()})
    return urlunsplit((s.scheme, s.netloc, s.path, q, ""))


def _ganti_id(url: str, path_template: str, nilai: str) -> str:
    s = urlsplit(url)
    bagian, tmpl = s.path.split("/"), path_template.split("/")
    for i in range(len(bagian)):
        if i < len(tmpl) and tmpl[i] == "{id}":
            bagian[i] = nilai
    return urlunsplit((s.scheme, s.netloc, "/".join(bagian), s.query, ""))


def _profil_semua(ctx: ScanContext, rencana: list[ck.Rencana], hasil: Sapuan) -> dict[int, dict[str, Any]]:
    """Profil tiap field (kunci id(field)); field ambigu dikirim ke AI dalam SATU panggilan."""
    from ..ai import inpv as ai_inpv

    profil: dict[int, dict[str, Any]] = {}
    ambigu: dict[str, dict[str, Any]] = {}
    sig_field: dict[int, str] = {}
    for r in rencana:
        for f in r.fields:
            p, yakin = pf.profil(f)
            profil[id(f)] = p
            if not yakin:
                k = pf.signature(f, r.endpoint.get("path_template", ""))
                sig_field[id(f)] = k
                ambigu.setdefault(k, {"k": k, "nama": str(f.get("nama", "")), "path": r.endpoint.get("path_template", ""),
                                      "bentuk": pf.bentuk_contoh(f.get("contoh"))})
    if ambigu:
        saran, info = ai_inpv.profil_validasi(list(ambigu.values()))
        hasil.ai["profil"] = {"field_ambigu": len(ambigu), **info}
        for fid, k in sig_field.items():
            if k in saran:
                profil[fid] = pf.gabung_ai(profil[fid], saran[k])
    return profil


def _jalankan(ctx: ScanContext) -> Sapuan:
    from ..ai import inpv as ai_inpv
    from ..ai import penggunaan

    hasil = Sapuan()
    awal_ai = penggunaan.potret()
    base_host = pf.host(ctx.base_url)
    izin = hosts_target(ctx)
    hasil.rencana = ck.rencanakan(_endpoints(ctx), base_host, izin)
    ctx.catat("info", "  " + hasil.teks_cakupan(rencana=True))
    profil = _profil_semua(ctx, hasil.rencana, hasil)
    if hasil.ai.get("profil"):
        i = hasil.ai["profil"]
        ctx.catat("info", f"  Profil validasi: {i['field_ambigu']} field ambigu → {i.get('dari_cache', 0)} dari cache, "
                          f"{i.get('dikirim', 0)} dikirim ke AI" + (f" (galat: {i['galat']})" if i.get("galat") else "") + ".")

    host_klien = izin | {pf.host(r.url) for r in hasil.rencana if r.status != "dilewati"}
    maks_req = _env_int("INPV_MAKS_REQUEST", 600)
    jeda = _env_int("INPV_JEDA_MS", 50) / 1000
    per_ep = {"n": 0}

    def lapor(info: dict[str, Any]) -> None:
        # Animasi/log: baseline + 2 varian pertama per endpoint + semua 5xx/galat koneksi.
        per_ep["n"] += 1
        st = info.get("status")
        if per_ep["n"] <= 3 or st is None or st >= 500:
            ctx.rekam_request(info)

    klien = KlienScan(ctx.base_url, timeout=10.0, host_izin=host_klien, saat_request=lapor)
    tok = pl.token()
    try:
        with klien:
            akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
            if akun and akun.password and ctx.url_titik("login"):
                try:
                    hasil.login_ok = login(klien, ctx, akun)
                except Exception:
                    hasil.login_ok = False
                ctx.catat("info", f"  Sesi akun uji: {'aktif' if hasil.login_ok else 'gagal — endpoint terproteksi akan terblokir'}.")
            for r in sorted(hasil.rencana, key=lambda x: (x.status != "diuji", x.label)):
                if r.status == "dilewati" or (r.status == "tanpa_input" and (r.endpoint.get("lapisan") == "frontend")):
                    continue
                koordinasi.periksa_batal()
                if hasil.jumlah_request >= maks_req:
                    hasil.tertunda.append(r.label)
                    continue
                per_ep["n"] = 0
                _uji_endpoint(ctx, klien, r, profil, tok, hasil, maks_req, jeda)
            hasil.bukti = _pilih_bukti(klien.bukti, hasil.observasi)
    except koordinasi.Dibatalkan:
        raise
    except Exception as e:  # sapuan gagal sebagian → tetap kembalikan apa yang terkumpul
        hasil.galat = f"{type(e).__name__}: {e}"

    # AI #2: kasus ambigu (input tak valid DITERIMA) — fitur ringkas saja.
    kasus = [o for o in hasil.observasi if o.kategori == "diterima" and o.kelompok == "validasi"]
    if kasus:
        fitur = [{"id": str(i), "m": o.endpoint.split(" ", 1)[0], "j": o.jenis, "s": f"{o.status}/{o.status_baseline}",
                  "d": o.beda_baseline, "ct": (o.content_type or "").split(";")[0][:30]} for i, o in enumerate(kasus)]
        nilai, info = ai_inpv.nilai_ambigu(fitur)
        hasil.ai["ambigu"] = {"kasus": len(kasus), **info, "dinilai": len(nilai)}
        for i, o in enumerate(kasus):
            o.ai = nilai.get(str(i), "")
    pakai = penggunaan.selisih(awal_ai)
    hasil.ai["pemakaian"] = pakai
    ctx.catat("info", "  " + hasil.teks_cakupan())
    if pakai["panggilan"]:
        ctx.catat("info", f"  AI: {pakai['panggilan']} panggilan, {'±' if pakai['perkiraan'] else ''}{pakai['token']} token.")
    elif ai_inpv.mode() != "off":
        ctx.catat("info", "  AI: 0 panggilan (profil dari aturan/cache).")
    return hasil


def _kirim(klien: KlienScan, metode: str, url: str, body: Optional[dict[str, Any]], form: bool, judul: str) -> Any:
    if metode in ("GET", "DELETE") or body is None:
        return klien.kirim(metode, url, judul_bukti=judul)
    return klien.kirim(metode, url, json=None if form else body, data=body if form else None, judul_bukti=judul)


def _uji_endpoint(ctx: ScanContext, klien: KlienScan, r: ck.Rencana, profil: dict[int, dict[str, Any]], tok: str,
                  hasil: Sapuan, maks_req: int, jeda: float) -> None:
    ep = r.endpoint
    metode = str(ep.get("metode_http", "GET")).upper()
    form = "x-www-form-urlencoded" in str(ep.get("content_type") or "")
    asal_form = _asal_form(ep)
    q_valid = asd.payload_endpoint(ep, "query")
    b_valid = asd.payload_endpoint(ep, "body")
    url_dasar = r.url.split("?", 1)[0]

    def kirim(url: str, body: Optional[dict[str, Any]], judul: str) -> Any:
        if hasil.jumlah_request >= maks_req:
            return None
        hasil.jumlah_request += 1
        if jeda:
            time.sleep(jeda)
        try:
            return _kirim(klien, metode, url, body, form, judul)
        except LuarRuangLingkup:
            return None
        except Exception:
            return None

    # Baseline: payload valid (query + body) — pembanding status & panjang.
    url_base = _url_query(url_dasar, q_valid) if q_valid else r.url
    base = kirim(url_base, b_valid if metode in ("POST", "PUT", "PATCH") else None, f"INPV — {r.label} (baseline valid)")
    st_b = base.status_code if base is not None else None
    len_b = len(base.text) if base is not None else None
    # Baseline valid pun ditolak validasi → penolakan varian tak bisa diatribusikan ke field uji.
    baseline_ditolak = st_b in (400, 422) and metode != "DELETE" and r.status == "diuji"
    hitung: dict[str, int] = {}

    def catat_obs(resp: Any, nama: str, lokasi: str, v: pl.Varian, dikirim: dict[str, Any]) -> None:
        if resp is None:
            return
        disebut = asd.field_disebut_galat(resp, dikirim) if dikirim else set()
        kat, cat = vn.nilai(resp, field_uji=nama, disebut=disebut, penanda=v.penanda, jenis=v.jenis)
        if baseline_ditolak and kat == "ditolak_tepat":
            kat, cat = "payload_belum_valid", f"payload dasar valid pun ditolak (HTTP {st_b})"
        hitung[kat] = hitung.get(kat, 0) + 1
        hasil.observasi.append(vn.Observasi(
            endpoint=r.label, field=nama, lokasi=lokasi, jenis=v.jenis, kelompok=v.kelompok, status=resp.status_code,
            kategori=kat, content_type=resp.headers.get("content-type", ""), panjang=len(resp.text),
            beda_baseline=vn.selisih(len(resp.text), len_b), status_baseline=st_b, disebut=sorted(disebut),
            catatan=cat, bukti_idx=len(klien.bukti) - 1, asal_form=asal_form,
        ))

    if r.status == "tanpa_input":
        for v in pl.varian_tanpa_input(tok):
            if metode == "GET":
                catat_obs(kirim(_url_query(url_dasar, {"satya_x": v.nilai}), None, f"INPV — {r.label} (parameter tak dikenal)"), "?", "query", v, {})
            else:
                catat_obs(kirim(r.url, {"satya_x": v.nilai}, f"INPV — {r.label} (field tak dikenal)"), "?", "body", v, {"satya_x": v.nilai})
    for f in r.fields:
        nama, lokasi = str(f["nama"]), f["lokasi"]
        for v in pl.varian_field(profil.get(id(f), {}), tok):
            if lokasi == "query":
                q = {**q_valid, nama: v.nilai}
                resp = kirim(_url_query(url_dasar, q), b_valid if metode in ("POST", "PUT", "PATCH") else None,
                             f"INPV — {r.label} (query '{nama}' · {v.jenis})")
                catat_obs(resp, nama, lokasi, v, q)
            else:
                b = {**b_valid, nama: v.nilai}
                resp = kirim(_url_query(url_dasar, q_valid) if q_valid else url_dasar, b, f"INPV — {r.label} (body '{nama}' · {v.jenis})")
                catat_obs(resp, nama, lokasi, v, b)
    if r.path_id:
        for v in pl.varian_path(tok):
            catat_obs(kirim(_ganti_id(url_dasar, ep.get("path_template", ""), str(v.nilai)), None, f"INPV — {r.label} (path id · {v.jenis})"),
                      "{id}", "path", v, {})
    ringkas = ", ".join(f"{k} {n}" for k, n in sorted(hitung.items(), key=lambda x: -x[1]))
    ctx.catat("info", f"  • {r.label}: baseline {st_b if st_b is not None else 'gagal'}{' (payload dasar ditolak)' if baseline_ditolak else ''}"
                      f" · {sum(hitung.values())} varian → {ringkas or '—'}")


def _pilih_bukti(semua: list[Bukti], obs: list[vn.Observasi]) -> list[Bukti]:
    """Lampirkan bukti request untuk observasi penting saja (bukan ratusan request)."""
    idx: list[int] = []
    for kat in ("crash", "indikasi_sqli", "indikasi_ssti", "refleksi", "diterima", "ditolak_tepat"):
        for o in obs:
            if o.kategori == kat and 0 <= o.bukti_idx < len(semua) and o.bukti_idx not in idx:
                idx.append(o.bukti_idx)
                if len(idx) >= MAKS_BUKTI:
                    break
    return [semua[i] for i in idx[:MAKS_BUKTI]]

