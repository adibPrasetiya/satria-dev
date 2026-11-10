"""Sapuan Validasi Input (INPV): cakupan seluruh endpoint, pengaman mutasi, vonis per metode, AI hemat."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

import satya_worker.ai as ai_mod
from satya_worker import inpv
from satya_worker.checks.input_validation import nilai_csp
from satya_worker.inpv import cakupan as ck
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.runner import jalankan_metode


@pytest.fixture(autouse=True)
def _bersih(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)
    monkeypatch.setenv("INPV_JEDA_MS", "0")
    monkeypatch.setenv("AI_INPV_CACHE", str(tmp_path / "cache.json"))
    inpv.sapu.reset_cache()
    yield
    inpv.sapu.reset_cache()


class _Api(BaseHTTPRequestHandler):
    hit: list[str] = []

    def log_message(self, *a):
        pass

    def _balas(self, kode: int, isi: object, ct: str = "application/json"):
        data = isi.encode() if isinstance(isi, str) else json.dumps(isi).encode()
        self.send_response(kode)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        u = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        _Api.hit.append(f"GET {u.path}")
        if u.path == "/api/crash":
            v = q.get("q", "")
            if "'" in v or len(v) > 100:
                return self._balas(500, "Traceback (most recent call last):\n  File app.py", "text/plain")
            return self._balas(200, {"hasil": []})
        if u.path == "/api/cari":
            return self._balas(200, f"<html><body>Hasil untuk {q.get('q', '')}</body></html>", "text/html")
        if u.path == "/api/sql":
            if "'" in q.get("id", ""):
                return self._balas(500, "You have an error in your SQL syntax near ''", "text/plain")
            return self._balas(200, {"ok": True})
        if u.path == "/api/banners":
            return self._balas(200, [{"id": 1}])
        if u.path.startswith("/api/item/"):
            return self._balas(404 if not u.path.endswith("/7") else 200, {"id": u.path.rsplit("/", 1)[1]})
        return self._balas(404, {"message": "not found"})

    def do_POST(self):
        u = urlsplit(self.path)
        b = self._body()
        _Api.hit.append(f"POST {u.path}")
        if u.path == "/api/validasi":
            galat = []
            if not isinstance(b.get("email"), str) or "@" not in b.get("email", "") or len(b.get("email", "")) > 100:
                galat.append({"field": "email", "message": "email tidak valid"})
            if not isinstance(b.get("umur"), int) or not 0 <= b["umur"] <= 150:
                galat.append({"field": "umur", "message": "umur harus 0-150"})
            if galat:
                return self._balas(422, {"errors": galat})
            return self._balas(201, {"ok": True})
        if u.path == "/api/terima":
            return self._balas(201, {"id": 99, "nama": "tersimpan"})
        if u.path == "/api/berjenjang":
            # Server menolak dulu karena field LAIN (kategori wajib == 'resmi') sebelum menilai 'judul'.
            if b.get("kategori") != "resmi":
                return self._balas(422, {"errors": [{"field": "kategori", "message": "kategori harus 'resmi'"}]})
            if not isinstance(b.get("judul"), str) or len(b.get("judul", "")) > 50 or "<" in b.get("judul", ""):
                return self._balas(422, {"errors": [{"field": "judul", "message": "judul tidak valid"}]})
            return self._balas(201, {"ok": True})
        return self._balas(404, {"message": "not found"})

    def do_PUT(self):
        _Api.hit.append(f"PUT {urlsplit(self.path).path}")
        self._body()
        return self._balas(404, {"message": "item tidak ada"})

    def do_DELETE(self):
        _Api.hit.append(f"DELETE {urlsplit(self.path).path}")
        return self._balas(404, {"message": "item tidak ada"})


@pytest.fixture()
def api():
    _Api.hit = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Api)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _ep(base: str, metode: str, path: str, fields=(), url_path: str | None = None, **extra) -> dict:
    return {"metode_http": metode, "path_template": path, "url": base + (url_path or path), "lapisan": "api",
            "request_fields": [dict(f) for f in fields], "sumber": ["browser"], **extra}


def _ctx(base: str, endpoints: list[dict], sid: str = "s-inpv") -> ScanContext:
    return ScanContext.from_dict({"scan_id": sid, "aplikasi_id": "a", "base_url": base, "endpoints": endpoints})


def _metode(mid: str, check_id: str, titik: str = "api") -> MetodeSpec:
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": titik, "profil": "intrusif"})


F_VALIDASI = ({"nama": "email", "lokasi": "body", "tipe": "str", "contoh": "a@b.co"}, {"nama": "umur", "lokasi": "body", "tipe": "int", "contoh": 30})


def test_cakupan_semua_endpoint_dan_pengaman_mutasi(api):
    eps = [
        _ep(api, "POST", "/api/validasi", F_VALIDASI),
        _ep(api, "GET", "/api/banners"),
        _ep(api, "PUT", "/api/item/{id}", ({"nama": "nama", "lokasi": "body"},), url_path="/api/item/7"),
        _ep(api, "DELETE", "/api/item/{id}", url_path="/api/item/7"),
        _ep(api, "PUT", "/api/users/me", ({"nama": "nama", "lokasi": "body"},)),
        _ep(api, "POST", "/api/password/reset", ({"nama": "email", "lokasi": "body"},)),
        _ep("https://pihak-ketiga.example", "GET", "/collect", ({"nama": "v", "lokasi": "query"},)),
    ]
    s = inpv.sapuan(_ctx(api, eps))
    c = s.cakupan()
    assert c["total"] == len(eps)
    assert (c["diuji"], c["tanpa_input"], c["dilewati"]) == (3, 1, 3)
    assert any("kritis" in a for a in c["alasan_dilewati"]) and any("tanpa ID" in a for a in c["alasan_dilewati"])
    # Mutasi hanya ke ID fiktif: item nyata /7 tak pernah di-PUT/DELETE; endpoint kritis tak disentuh.
    assert not any(h in ("PUT /api/item/7", "DELETE /api/item/7") for h in _Api.hit)
    assert any(h.startswith("PUT /api/item/") for h in _Api.hit)
    assert "POST /api/password/reset" not in _Api.hit and "PUT /api/users/me" not in _Api.hit


def test_id_fiktif():
    assert ck.id_fiktif("https://x.test/api/item/7", "/api/item/{id}") == f"https://x.test/api/item/{ck.ID_FIKTIF_ANGKA}"


def test_validasi_ketat_lulus(api):
    ctx = _ctx(api, [_ep(api, "POST", "/api/validasi", F_VALIDASI)])
    for mid, cid in (("INPV-4.1-T01", "input.server_side_validation"), ("INPV-4.4-T01", "input.allowlist_validation")):
        h = jalankan_metode(ctx, _metode(mid, cid, "form_input"))
        assert h.status == "lulus", f"{mid}: {h.ringkasan}"
    assert "Matriks cakupan INPV" in h.detail


def test_input_tak_valid_diproses_gagal(api):
    ctx = _ctx(api, [_ep(api, "POST", "/api/terima", ({"nama": "nama", "lokasi": "body", "tipe": "str"},))])
    h = jalankan_metode(ctx, _metode("INPV-4.2-T02", "input.reject_on_error"))
    assert h.status == "gagal" and "diproses" in h.ringkasan, h.ringkasan


def test_crash_gagal(api):
    ctx = _ctx(api, [_ep(api, "GET", "/api/crash", ({"nama": "q", "lokasi": "query", "tipe": "str"},))])
    h = jalankan_metode(ctx, _metode("INPV-4.1-T01", "input.server_side_validation", "form_input"))
    assert h.status == "gagal" and "galat server" in h.ringkasan, h.ringkasan
    assert h.bukti, "bukti request crash dilampirkan"


def test_indikasi_injeksi_digabung_ke_check_zap(api, monkeypatch):
    monkeypatch.delenv("ZAP_BASE_URL", raising=False)
    eps = [_ep(api, "GET", "/api/cari", ({"nama": "q", "lokasi": "query", "tipe": "str"},)),
           _ep(api, "GET", "/api/sql", ({"nama": "id", "lokasi": "query", "tipe": "str"},))]
    ctx = _ctx(api, eps)
    xss = jalankan_metode(ctx, MetodeSpec.from_dict({"id": "INPV-4.7-T01", "check_id": "zap.active.xss_policy", "titik_uji": "form_input", "engine": "zap", "profil": "intrusif"}))
    sqli = jalankan_metode(ctx, MetodeSpec.from_dict({"id": "INPV-4.8-T02", "check_id": "zap.active.sqli_policy", "titik_uji": "api", "engine": "zap", "profil": "intrusif"}))
    assert xss.status == "gagal" and "refleksi" in xss.ringkasan, xss.ringkasan
    assert sqli.status == "gagal" and "indikasi_sqli" in sqli.ringkasan, sqli.ringkasan


def test_batas_request_menghasilkan_tertunda(api, monkeypatch):
    monkeypatch.setenv("INPV_MAKS_REQUEST", "3")
    eps = [_ep(api, "POST", "/api/validasi", F_VALIDASI), _ep(api, "POST", "/api/terima", ({"nama": "nama", "lokasi": "body"},))]
    s = inpv.sapuan(_ctx(api, eps))
    assert s.jumlah_request == 3
    assert s.tertunda == ["POST /api/validasi"] or s.tertunda == ["POST /api/terima"]
    assert "tertunda" in s.teks_cakupan()


class _AiPalsu:
    nama, model = "palsu", "uji"

    def __init__(self):
        self.prompt: list[str] = []

    def tanya_json(self, prompt: str, max_tokens: int = 2000) -> dict:
        self.prompt.append(prompt)
        if '"v":' in prompt and "diproses" in prompt:
            return {"v": {"0": "diabaikan"}}
        return {"p": {"kode_promo|string|promo": {"tipe": "string", "format": "kata", "invalid": ["PROMO-TIDAK-ADA"]},
                      "token_undangan|string|promo": {"tipe": "string"}}}


def test_ai_hemat_berkelompok_ter_cache_dan_tersamar(api, monkeypatch):
    ai = _AiPalsu()
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: ai)
    fields = ({"nama": "kode_promo", "lokasi": "query", "tipe": "str", "contoh": "HEMAT50"},
              {"nama": "token_undangan", "lokasi": "query", "tipe": "str", "contoh": "rahasia-123"})
    eps = [_ep(api, "GET", "/api/promo", fields), _ep(api, "GET", "/api/promo/cek", fields)]
    inpv.sapuan(_ctx(api, eps, sid="ai-1"))
    profil = [p for p in ai.prompt if '"p":' in p]
    assert len(profil) == 1, "profil field dikirim dalam SATU panggilan berkelompok"
    assert "rahasia-123" not in profil[0] and "HEMAT50" not in profil[0], "nilai contoh tak pernah dikirim"
    assert "aaaaa99" in profil[0] or "aaaaa" in profil[0]  # hanya BENTUK contoh field non-sensitif
    jumlah = len(ai.prompt)
    inpv.sapu.reset_cache()
    inpv.sapuan(_ctx(api, eps, sid="ai-2"))
    assert not any('"p":' in p for p in ai.prompt[jumlah:]), "scan ulang memakai cache profil (0 panggilan profil)"


F_BERJENJANG = ({"nama": "judul", "lokasi": "body", "tipe": "str", "contoh": "Laporan"},
                {"nama": "kategori", "lokasi": "body", "tipe": "str"})


def test_baseline_ditolak_field_lain_tanpa_ai_tidak_lulus_palsu(api, monkeypatch):
    """400/422 karena field LAIN (payload dasar belum valid) tak boleh dihitung sebagai 'ditolak tepat'
    → vonis tinjauan, bukan lulus palsu. Ini inti keluhan: 400 bukan selalu penolakan yang diharapkan."""
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: None)  # tanpa AI: deterministik tak bisa tebak 'resmi'
    ctx = _ctx(api, [_ep(api, "POST", "/api/berjenjang", F_BERJENJANG)])
    h = jalankan_metode(ctx, _metode("INPV-4.1-T01", "input.server_side_validation", "form_input"))
    assert h.status == "tidak_dapat_diverifikasi", h.ringkasan
    assert "field LAIN" in h.ringkasan or "payload dasar" in h.ringkasan, h.ringkasan


class _AiPerbaiki:
    nama, model = "perbaiki", "uji"

    def __init__(self):
        self.prompt: list[str] = []

    def tanya_json(self, prompt: str, max_tokens: int = 2000) -> dict:
        self.prompt.append(prompt)
        if "field_bermasalah" in prompt:            # orkestrasi adaptif: perbaiki payload dasar
            return {"nilai": {"kategori": "resmi"}}
        if '"p":' in prompt or "validasi" in prompt:  # profil field ambigu
            return {"p": {}}
        return {"v": {}}


def test_baseline_diperbaiki_ai_lalu_validasi_teratribusi(api, monkeypatch):
    """Orkestrator adaptif memperbaiki baseline (AI isi 'kategori'='resmi') agar DITERIMA, lalu penolakan
    varian 'judul' teratribusi ke field yang diuji — bukan lagi payload_belum_valid."""
    ai = _AiPerbaiki()
    monkeypatch.setattr(ai_mod, "muat_provider_dari_env", lambda: ai)
    ctx = _ctx(api, [_ep(api, "POST", "/api/berjenjang", F_BERJENJANG)])
    s = inpv.sapuan(ctx)
    assert s.baseline_diperbaiki >= 1 and s.panggilan_perbaikan >= 1
    assert any("field_bermasalah" in p for p in ai.prompt), "AI diminta memperbaiki payload dasar"
    # 'kategori' tak pernah dikirim sebagai nilai sensitif, tapi nilai valid diterapkan → ada baseline 201.
    judul_obs = [o for o in s.observasi if o.field == "judul"]
    assert judul_obs, "field judul teruji"
    # Setelah baseline valid, penolakan judul tak lagi diatribusikan ke field lain.
    assert not any(o.kategori == "payload_belum_valid" for o in judul_obs), [o.kategori for o in judul_obs]


def test_tanpa_ai_tetap_berjalan(api, monkeypatch):
    monkeypatch.setenv("AI_INPV", "off")
    s = inpv.sapuan(_ctx(api, [_ep(api, "POST", "/api/validasi", F_VALIDASI)]))
    assert s.observasi and s.ai.get("pemakaian", {}).get("panggilan", 0) == 0


@pytest.mark.parametrize("csp,status", [
    ("default-src 'self'", "lulus"),
    ("script-src 'self' 'unsafe-inline'", "gagal"),
    ("script-src 'self' 'unsafe-inline' 'nonce-abc'", "lulus"),
    ("script-src *", "gagal"),
    ("img-src 'self'", "gagal"),
])
def test_nilai_csp(csp, status):
    assert nilai_csp(csp)[0] == status
