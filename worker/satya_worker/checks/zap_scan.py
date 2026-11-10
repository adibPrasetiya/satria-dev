"""Engine `zap` — memetakan temuan OWASP ZAP ke metode katalog BSSN.

Satu scan ZAP (spider + passive, dan active scan untuk metode intrusif) dijalankan
per target lalu dipakai ulang oleh semua check zap pada target yang sama (cache
per-proses). Tiap check_id memfilter alert ZAP yang relevan (berdasarkan pluginId,
CWE, dan ambang risiko), lalu menilai lulus/gagal.

Butuh ZAP terkonfigurasi (ZAP_BASE_URL + ZAP_API_KEY). Bila tidak, semua check zap
mengembalikan `tidak_dapat_diverifikasi` (bukan gagal) — tidak menghakimi tanpa bukti.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from ..models import Bukti, HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from .. import zap_client as zc

_RISK = {"Informational": 0, "Low": 1, "Medium": 2, "High": 3}


# Pemetaan check_id → tanda pengenal alert ZAP.
# plugin: set pluginId; cwe: set CWE id; min_risk: ambang (nama risiko ZAP); aktif: perlu active scan.
PETA: dict[str, dict[str, Any]] = {
    # --- pasif (profil aman) ---
    "session.token_not_in_url": {"plugin": {3}, "cwe": {200, 598}, "min_risk": "Low", "aktif": False},
    "access.csrf_token": {"plugin": {10202}, "cwe": {352}, "min_risk": "Low", "aktif": False},
    "tls.mixed_content": {"plugin": {10040}, "cwe": {311}, "min_risk": "Low", "aktif": False},
    "deps.vulnerable_js_libraries": {"plugin": {10003}, "cwe": {1104, 829}, "min_risk": "Low", "aktif": False},
    "api.sensitive_in_uri": {"plugin": {10024}, "cwe": {200, 598}, "min_risk": "Low", "aktif": False},
    "conf.directory_listing": {"plugin": {0}, "cwe": {548}, "min_risk": "Low", "aktif": False},
    # --- aktif (profil intrusif) ---
    "zap.active.xss_policy": {"plugin": {40012, 40014, 40016, 40017, 40026}, "cwe": {79}, "min_risk": "Medium", "aktif": True},
    "zap.active.sqli_policy": {"plugin": {40018, 40019, 40020, 40021, 40022, 40024, 40027, 90018}, "cwe": {89}, "min_risk": "Medium", "aktif": True},
    "zap.active.code_injection_policy": {"plugin": {90019, 90035, 90036}, "cwe": {94, 95, 96, 1336}, "min_risk": "Medium", "aktif": True},
    "zap.active.injection_policy": {
        "plugin": {90020, 40003, 40015, 90021, 90024, 90017},
        "cwe": {77, 78, 90, 91, 113, 643},
        "min_risk": "Medium",
        "aktif": True,
    },
}


def _cocok(alert: dict[str, Any], spec: dict[str, Any]) -> bool:
    try:
        pid = int(alert.get("pluginId", -1))
    except (TypeError, ValueError):
        pid = -1
    try:
        cwe = int(alert.get("cweid", -1))
    except (TypeError, ValueError):
        cwe = -1
    if pid in spec["plugin"] or cwe in spec["cwe"]:
        return _RISK.get(alert.get("risk", "Informational"), 0) >= _RISK[spec["min_risk"]]
    return False


def _bukti_alert(alerts: list[dict[str, Any]]) -> list[Bukti]:
    baris = []
    for a in alerts[:10]:
        baris.append(f"[{a.get('risk')}] {a.get('alert') or a.get('name')} — {a.get('url','')} (pluginId={a.get('pluginId')}, CWE={a.get('cweid')})")
    return [Bukti(jenis="dokumen", judul="Temuan ZAP terkait", isi="\n".join(baris))] if baris else []


def evaluasi(metode: MetodeSpec, alerts: list[dict[str, Any]], *, scan_ok: bool, aktif_ok: bool) -> HasilMetode:
    """Nilai satu metode zap dari daftar alert (fungsi murni; dipakai juga oleh tes)."""
    spec = PETA.get(metode.check_id)
    if spec is None:
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=f'Pemetaan ZAP untuk "{metode.check_id}" belum ada.')
    if not scan_ok:
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Pemindaian ZAP tidak selesai dalam batas waktu.")
    if spec["aktif"] and not aktif_ok:
        return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Active scan ZAP tidak berjalan/selesai untuk metode intrusif ini.")
    cocok = [a for a in alerts if _cocok(a, spec)]
    if cocok:
        nama = ", ".join(sorted({(a.get("alert") or a.get("name") or "?") for a in cocok}))[:200]
        return HasilMetode(
            metode_id=metode.id,
            status="gagal",
            ringkasan=f"ZAP menemukan {len(cocok)} temuan ({nama}).",
            detail=metode.kriteria_lulus,
            bukti=_bukti_alert(cocok),
        )
    return HasilMetode(metode_id=metode.id, status="lulus", ringkasan="Tidak ada temuan ZAP yang relevan pada ambang risiko ini.", detail=metode.kriteria_lulus)


# --------------------------------------------------------------------------- orkestrasi scan (cache per target)

_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}  # base_url -> {alerts, spider_ok, aktif_ok}


def prime_cache(base_url: str, alerts: list[dict[str, Any]], *, scan_ok: bool) -> None:
    """Isi cache dari hasil spider fase penemuan agar check zap pasif tak mem-spider ulang.
    Active scan tetap dijalankan terpisah oleh check intrusif (aktif_ok=False)."""
    with _lock:
        _cache[base_url] = {"alerts": alerts, "spider_ok": scan_ok, "aktif_ok": False}


def _alerts_untuk(ctx: ScanContext, aktif: bool) -> tuple[list[dict[str, Any]], bool, bool]:
    """Pastikan target sudah dipindai (cache per-proses) lalu kembalikan (alerts, scan_ok, aktif_ok).
    Lempar ZapTidakTersedia bila ZAP belum dikonfigurasi."""
    base = ctx.base_url
    with _lock:
        entri = _cache.get(base)
        if entri and (entri["aktif_ok"] or not aktif):
            return entri["alerts"], entri["spider_ok"], entri["aktif_ok"]

        klien = zc.dari_env()
        if klien is None:
            raise zc.ZapTidakTersedia("ZAP belum dikonfigurasi (set ZAP_BASE_URL & ZAP_API_KEY).")
        with klien:
            klien.version()  # validasi koneksi + API key (gagal → httpx error)
            spider_ok = (entri or {}).get("spider_ok", False)
            if not spider_ok:
                spider_ok = klien.jalankan_spider(base, batas=zc.batas_spider())
            # Target benar-benar terjangkau ZAP? (0 URL = tak terjangkau → jangan klaim lulus)
            terjangkau = klien.jumlah_url(base) > 0
            scan_ok = spider_ok and terjangkau
            aktif_ok = (entri or {}).get("aktif_ok", False)
            origins = [base]
            if aktif and scan_ok and not aktif_ok:
                # Semai endpoint inventaris (API di host lain, POST JSON) agar active scan menjangkaunya.
                origins = _semai_endpoint(klien, ctx)
                batas = zc.batas_ascan() / max(len(origins), 1)
                hasil_ascan = [klien.jalankan_ascan(o, batas=batas) for o in origins]
                aktif_ok = any(hasil_ascan)
            alerts = [a for o in origins for a in klien.alerts(o)] if len(origins) > 1 else klien.alerts(base)
        _cache[base] = {"alerts": alerts, "spider_ok": scan_ok, "aktif_ok": aktif_ok}
        return alerts, scan_ok, aktif_ok


def _semai_endpoint(klien: "zc.ZapClient", ctx: ScanContext) -> list[str]:
    """Kirim request valid untuk endpoint inventaris (GET/POST, bukan kritis, dalam lingkup) lewat ZAP.
    Return daftar origin yang akan dipindai aktif (frontend dulu, lalu origin API)."""
    import json as _json
    from urllib.parse import urlsplit

    from .. import atribusi_sandi as asd
    from ..inpv import cakupan as ck
    from ..sesi import hosts_target

    base = ctx.base_url.rstrip("/")
    origins = [base]
    izin = hosts_target(ctx)
    host0 = urlsplit(ctx.base_url).hostname or ""
    for e in ctx.endpoints:
        metode = str(e.get("metode_http") or "GET").upper()
        url = str(e.get("url") or "")
        u = urlsplit(url)
        if metode not in ("GET", "POST") or (e.get("lapisan") or "api") != "api" or not u.hostname:
            continue
        if not ck.host_dalam_lingkup(u.hostname, host0, izin) or ck.KRITIS.search(str(e.get("path_template") or "")):
            continue
        origin = f"{u.scheme}://{u.netloc}"
        if origin not in origins:
            origins.append(origin)
        jalur = u.path + (f"?{u.query}" if u.query else "")
        if metode == "GET":
            raw = f"GET {url} HTTP/1.1\r\nHost: {u.netloc}\r\nUser-Agent: satya-zap\r\n\r\n"
        else:
            body = _json.dumps(asd.payload_endpoint(e, "body"))
            raw = (f"POST {u.scheme}://{u.netloc}{jalur} HTTP/1.1\r\nHost: {u.netloc}\r\nContent-Type: application/json\r\n"
                   f"Content-Length: {len(body.encode())}\r\nUser-Agent: satya-zap\r\n\r\n{body}")
        klien.send_request(raw)
    return origins


def _jalankan(ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
    spec = PETA.get(metode.check_id, {})
    aktif = bool(spec.get("aktif"))
    try:
        alerts, scan_ok, aktif_ok = _alerts_untuk(ctx, aktif)
    except zc.ZapTidakTersedia as e:
        return gabung_sapuan(ctx, metode, HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan=str(e)))
    except Exception as e:  # koneksi/API ZAP gagal → jangan crash, jangan menghakimi
        return gabung_sapuan(ctx, metode, HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                                                      ringkasan=f"Gagal menghubungi ZAP: {type(e).__name__}", detail=str(e)[:300]))
    return gabung_sapuan(ctx, metode, evaluasi(metode, alerts, scan_ok=scan_ok, aktif_ok=aktif_ok))


# Check yang juga diperkaya uji XSS TERSIMPAN (menulis penanda → baca ulang). Mutatif → hanya intrusif+izin.
_STORED_CHECKS = {"zap.active.xss_policy", "zap.active.injection_policy"}


def _uji_tersimpan(ctx: ScanContext, metode: MetodeSpec) -> Any:
    """Jalankan prober XSS tersimpan bila check relevan DAN diizinkan (profil intrusif + izin intrusif).
    Return HasilStored | None."""
    if metode.check_id not in _STORED_CHECKS:
        return None
    if metode.profil != "intrusif" or not getattr(ctx.intrusif, "izinkan_penguncian", False):
        return None
    from ..inpv import stored
    try:
        return stored.probe(ctx)
    except Exception:
        return None


def gabung_sapuan(ctx: ScanContext, metode: MetodeSpec, h: HasilMetode) -> HasilMetode:
    """Gabungkan indikasi injeksi dari sapuan INPV (sisi worker) + uji XSS tersimpan dengan vonis ZAP:
    GAGAL bila salah satu menemukan indikasi. Bila ZAP tak tersedia dan semuanya bersih, tetap
    tidak_dapat_diverifikasi."""
    from . import input_validation as iv

    if metode.check_id not in iv.INDIKASI_ZAP:
        return h
    temuan, s = iv.indikasi_injeksi(ctx, metode.check_id)
    if s is None:
        return h

    st = _uji_tersimpan(ctx, metode)
    stored_rentan = st.rentan if st is not None else []
    pesan_stored = (f"\nUji XSS tersimpan: {st.teks()}" + ("".join(f"\n  • {t.ringkas}" for t in st.temuan[:8]))) if st is not None and st.dijalankan else ""
    bukti_stored = list(st.bukti) if st is not None else []

    if temuan or stored_rentan:
        bagian = []
        if stored_rentan:
            bagian.append(f"{len(stored_rentan)} XSS TERSIMPAN (data tak difilter, muncul mentah saat dibaca ulang): "
                          + "; ".join(t.ringkas for t in stored_rentan[:5]))
        if temuan:
            bagian.append(f"{len(temuan)} indikasi injeksi: " + "; ".join(f"{o.ringkas} ({o.kategori})" for o in temuan[:6]))
        return HasilMetode(
            metode_id=metode.id, status="gagal",
            ringkasan=("Sapuan INPV menemukan " + " | ".join(bagian))[:400]
                      + (f" | ZAP: {h.ringkasan}" if h.status == "gagal" else ""),
            detail=(h.detail or "") + f"\nSapuan INPV: {'; '.join(f'{o.ringkas} ({o.kategori}: {o.catatan})' for o in temuan[:8]) or 'tak ada refleksi'}"
                   + pesan_stored + f"\n{s.teks_cakupan()}",
            bukti=list(h.bukti) + list(s.bukti) + bukti_stored, durasi_ms=h.durasi_ms,
        )
    h.detail = ((h.detail or "") + f"\nSapuan INPV: tidak ada indikasi ({s.teks_cakupan()})" + pesan_stored).strip()
    return h


class _CekZap:
    """Basis check engine zap: delegasikan ke orkestrator + pewaktu."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = _jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil


# Daftarkan satu instance per check_id zap (semua berbagi logika _CekZap).
for _cid in PETA:
    check(_cid, engine="zap")(type(f"CekZap_{_cid}", (_CekZap,), {}))
