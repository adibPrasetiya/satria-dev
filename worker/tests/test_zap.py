"""Uji engine ZAP: pemetaan alert → metode, dan perilaku saat ZAP tak terkonfigurasi.
Tidak membutuhkan daemon ZAP (fungsi `evaluasi` murni; orkestrasi diuji via env kosong)."""

from __future__ import annotations

import pytest

from satya_worker.checks import zap_scan as z
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check


def metode(check_id: str, **extra) -> MetodeSpec:
    return MetodeSpec.from_dict({"id": check_id, "check_id": check_id, "titik_uji": "global", "engine": "zap", "kriteria_lulus": "k", **extra})


def alert(plugin=0, cwe=-1, risk="Medium", name="Temuan"):
    return {"pluginId": plugin, "cweid": cwe, "risk": risk, "alert": name, "url": "http://t/x"}


def test_semua_check_zap_terdaftar():
    for cid in z.PETA:
        assert cari_check(cid, "zap") is not None, cid


def test_pasif_gagal_bila_ada_alert_cocok():
    h = z.evaluasi(metode("tls.mixed_content"), [alert(plugin=10040, risk="Low")], scan_ok=True, aktif_ok=False)
    assert h.status == "gagal" and h.bukti


def test_pasif_lulus_bila_tak_ada_alert():
    h = z.evaluasi(metode("tls.mixed_content"), [alert(plugin=99999, risk="High")], scan_ok=True, aktif_ok=False)
    assert h.status == "lulus"


def test_cocok_lewat_cwe():
    h = z.evaluasi(metode("zap.active.sqli_policy"), [alert(plugin=0, cwe=89, risk="High")], scan_ok=True, aktif_ok=True)
    assert h.status == "gagal"


def test_ambang_risiko_aktif_mengabaikan_low():
    # injeksi aktif: hanya 'sedang ke atas' yang dihitung.
    h = z.evaluasi(metode("zap.active.xss_policy"), [alert(cwe=79, risk="Low")], scan_ok=True, aktif_ok=True)
    assert h.status == "lulus"


def test_scan_tidak_selesai():
    h = z.evaluasi(metode("tls.mixed_content"), [], scan_ok=False, aktif_ok=False)
    assert h.status == "tidak_dapat_diverifikasi"


def test_aktif_butuh_ascan_selesai():
    h = z.evaluasi(metode("zap.active.xss_policy"), [], scan_ok=True, aktif_ok=False)
    assert h.status == "tidak_dapat_diverifikasi"


def test_zap_tak_terkonfigurasi(monkeypatch):
    monkeypatch.delenv("ZAP_BASE_URL", raising=False)
    monkeypatch.delenv("ZAP_API_KEY", raising=False)
    z._cache.clear()
    ctx = ScanContext.from_dict({"scan_id": "s", "aplikasi_id": "a", "base_url": "https://contoh.invalid"})
    plugin = cari_check("tls.mixed_content", "zap")
    h = plugin.run(ctx, metode("tls.mixed_content"))
    assert h.status == "tidak_dapat_diverifikasi"
    assert "dikonfigurasi" in h.ringkasan.lower()
