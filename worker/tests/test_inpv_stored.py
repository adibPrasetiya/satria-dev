"""Uji XSS tersimpan / kegagalan filter output (INPV-4.5 & 4.7) — tulis penanda lalu baca ulang."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

import satya_worker.ai as ai_mod
from satya_worker.checks import zap_scan
from satya_worker.inpv import stored
from satya_worker.models import MetodeSpec, ScanContext


@pytest.fixture(autouse=True)
def _bersih(monkeypatch):
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)
    monkeypatch.setenv("INPV_JEDA_MS", "0")
    monkeypatch.delenv("ZAP_BASE_URL", raising=False)
    stored.reset_cache()
    yield
    stored.reset_cache()


class _App(BaseHTTPRequestHandler):
    """Aplikasi contoh: POST /api/catatan menyimpan 'isi' APA ADANYA (rentan); GET /api/catatan
    menampilkannya mentah di HTML. POST /api/aman meng-encode sebelum menyimpan."""

    tersimpan: list[str] = []
    aman: list[str] = []

    def log_message(self, *a):
        pass

    def _balas(self, kode, isi, ct="application/json"):
        data = isi.encode() if isinstance(isi, str) else json.dumps(isi).encode()
        self.send_response(kode)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        p = urlsplit(self.path).path
        if p == "/api/catatan":
            isi = "".join(f"<li>{x}</li>" for x in _App.tersimpan)   # MENTAH
            return self._balas(200, f"<html><ul>{isi}</ul></html>", "text/html")
        if p == "/api/aman":
            isi = "".join(f"<li>{x}</li>" for x in _App.aman)        # sudah ter-encode saat disimpan
            return self._balas(200, f"<html><ul>{isi}</ul></html>", "text/html")
        return self._balas(404, {"message": "x"})

    def do_POST(self):
        p = urlsplit(self.path).path
        b = self._body()
        if p == "/api/catatan":
            _App.tersimpan.append(str(b.get("isi", "")))
            return self._balas(201, {"id": len(_App.tersimpan)})
        if p == "/api/aman":
            v = str(b.get("isi", "")).replace("<", "&lt;").replace(">", "&gt;")
            _App.aman.append(v)
            return self._balas(201, {"id": len(_App.aman)})
        return self._balas(404, {"message": "x"})


@pytest.fixture()
def app():
    _App.tersimpan, _App.aman = [], []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _ep(base, metode, path, fields=()):
    return {"metode_http": metode, "path_template": path, "url": base + path, "lapisan": "api",
            "request_fields": [dict(f) for f in fields], "sumber": ["browser"]}


def _ctx(base, eps, izin=True):
    return ScanContext.from_dict({
        "scan_id": f"stored-{base[-5:]}-{izin}", "aplikasi_id": "a", "base_url": base,
        "endpoints": eps, "intrusif": {"izinkan_penguncian": izin},
    })


EPS = lambda base: [  # noqa: E731
    _ep(base, "POST", "/api/catatan", ({"nama": "isi", "lokasi": "body", "tipe": "str"},)),
    _ep(base, "GET", "/api/catatan"),
    _ep(base, "POST", "/api/aman", ({"nama": "isi", "lokasi": "body", "tipe": "str"},)),
    _ep(base, "GET", "/api/aman"),
]


def test_stored_xss_mentah_terdeteksi(app):
    s = stored.probe(_ctx(app, EPS(app)))
    assert s.dijalankan and s.ditulis >= 1
    rentan = {t.baca for t in s.rentan}
    assert "GET /api/catatan" in rentan, s.teks()
    # Endpoint yang meng-encode tidak dilaporkan rentan.
    assert "GET /api/aman" not in rentan


def test_xss_check_gagal_karena_stored(app):
    m = MetodeSpec.from_dict({"id": "INPV-4.7-T01", "check_id": "zap.active.xss_policy",
                              "titik_uji": "form_input", "engine": "zap", "profil": "intrusif"})
    h = zap_scan._jalankan(_ctx(app, EPS(app)), m)
    assert h.status == "gagal" and "TERSIMPAN" in h.ringkasan, h.ringkasan
    # PoC langkah reproduksi untuk XSS tersimpan + bukti tulis/baca terlampir.
    assert h.poc and any("tersimpan" in l.lower() for l in h.poc), h.poc
    assert h.bukti, "bukti request tulis & response baca terlampir"


def test_tanpa_izin_prober_tak_dijalankan(app):
    # profil intrusif tapi TANPA izin intrusif → prober XSS tersimpan tak dijalankan & tak melapor.
    m = MetodeSpec.from_dict({"id": "INPV-4.7-T01", "check_id": "zap.active.xss_policy",
                              "titik_uji": "form_input", "engine": "zap", "profil": "intrusif"})
    h = zap_scan._jalankan(_ctx(app, EPS(app), izin=False), m)
    assert stored._cache == {}, "prober XSS tersimpan tak boleh dipanggil tanpa izin intrusif"
    assert "TERSIMPAN" not in h.ringkasan


def test_profil_aman_prober_tak_dijalankan(app):
    # Check XSS dijalankan pada profil 'aman' (walau izin ada) → prober mutatif tetap tak jalan.
    m = MetodeSpec.from_dict({"id": "INPV-4.7-T01", "check_id": "zap.active.xss_policy",
                              "titik_uji": "form_input", "engine": "zap", "profil": "aman"})
    zap_scan._jalankan(_ctx(app, EPS(app), izin=True), m)
    assert stored._cache == {}, "prober XSS tersimpan hanya untuk profil intrusif"
