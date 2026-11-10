"""Uji integrasi check INPV-4.1 dengan payload valid & atribusi penolakan (lihat juga test_inpv.py)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import satya_worker.ai as ai_mod
from satya_worker import inpv
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode


@pytest.fixture(autouse=True)
def _bersih(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)
    monkeypatch.setenv("INPV_JEDA_MS", "0")
    monkeypatch.setenv("AI_INPV_CACHE", str(tmp_path / "cache.json"))
    inpv.sapu.reset_cache()


def _server_validasi(wajib_kode_unit: bool):
    """POST /api/cuti: 400 bila `kode_unit` bukan 'U01' (field lain, dicek dulu) atau `alasan` tak valid (field uji)."""

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            galat = []
            if wajib_kode_unit and body.get("kode_unit") != "U01":
                # Berhenti di galat pertama (seperti banyak API): field uji tak sempat divalidasi.
                galat.append({"field": "kode_unit", "message": "unit tidak dikenal"})
            elif not isinstance(body.get("alasan"), str) or len(body.get("alasan", "")) > 200 or "<" in body.get("alasan", "") or "'" in body.get("alasan", "") or "{" in body.get("alasan", ""):
                galat.append({"field": "alasan", "message": "tidak valid"})
            data = json.dumps({"errors": galat} if galat else {"ok": True}).encode()
            self.send_response(400 if galat else 201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _jalankan_inpv(base: str, kode_unit_field: dict) -> object:
    ep = {
        "endpoint": "POST /api/cuti", "metode_http": "POST", "path_template": "/api/cuti", "url": f"{base}/api/cuti",
        "titik_uji": "", "kategori": ["INPV"],
        "request_fields": [{"nama": "alasan", "lokasi": "body", "tipe": "string", "contoh": "cuti tahunan"}, {"nama": "kode_unit", "lokasi": "body", **kode_unit_field}],
    }
    # Konteks lama: hanya kandidat INPV (tanpa inventaris lengkap) — sapuan memakai kandidat sebagai cadangan.
    ctx = ScanContext.from_dict({"scan_id": "s", "aplikasi_id": "a", "base_url": base, "kandidat_uji": {"per_endpoint": [ep]},
                                 "intrusif": {"izinkan_penguncian": True}})
    m = MetodeSpec.from_dict({"id": "INPV-4.1-T01", "check_id": "input.server_side_validation", "titik_uji": "api", "profil": "intrusif"})
    return jalankan_metode(ctx, m)


def test_inpv_contoh_nilai_membuat_payload_valid_dan_terkonfirmasi():
    srv = _server_validasi(True)
    try:
        h = _jalankan_inpv(f"http://127.0.0.1:{srv.server_address[1]}", {"tipe": "str", "contoh": "U01"})
    finally:
        srv.shutdown()
    assert h.status == "lulus", h.ringkasan
    assert "galat menunjuk field yang diuji" in h.ringkasan


def test_inpv_ditolak_field_lain_bukan_lulus():
    srv = _server_validasi(True)
    try:
        h = _jalankan_inpv(f"http://127.0.0.1:{srv.server_address[1]}", {"tipe": "string"})  # tanpa contoh → nilai salah
    finally:
        srv.shutdown()
    assert h.status != "lulus", h.ringkasan
