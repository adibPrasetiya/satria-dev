"""Uji check Kriptografi (CRYP)."""

from __future__ import annotations

import secrets

import pytest

from satya_worker import nuclei_client, sslyze_client
from satya_worker.checks import kriptografi as C
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"


def ctx(*, area=False, akun=False) -> ScanContext:
    d = {"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": []}
    if area:
        d["titik_uji"] = {
            "area_terautentikasi": {"tersedia": True, "url": f"{BASE}/api/me", "metode_http": "GET"},
            "login": {"tersedia": True, "url": f"{BASE}/api/login", "metode_http": "POST"},
        }
    if akun:
        d["akun_uji"] = [{"kunci": "akun_uji_1", "username": "uji@contoh.go.id", "password": "X", "terisi": True}]
    return ScanContext.from_dict(d)


def metode(mid, check_id, engine="custom", **param):
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "global",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


class _Resp:
    def __init__(self, status=200, headers=None, text=""):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = text


# --------------------------------------------------------------------------- 5.1-T01 sslyze keys

@pytest.fixture
def sslyze_fake(monkeypatch):
    monkeypatch.setattr(sslyze_client, "tersedia", lambda: True)
    monkeypatch.setattr(sslyze_client, "aktif", lambda: True)

    def pasang(tipe, ukuran, sig):
        scan = {"ok": True, "sertifikat": {"tersedia": True, "tipe_kunci": tipe, "ukuran_kunci": ukuran,
                                           "kurva": None, "algoritma_tanda_tangan": sig}}
        monkeypatch.setattr(sslyze_client, "pindai", lambda *a, **kw: scan)

    return pasang


def test_key_kuat_lulus(sslyze_fake):
    sslyze_fake("EC", 256, "sha256")
    h = jalankan("tls.key_and_algorithms", "sslyze", metode("CRYP-5.1-T01", "tls.key_and_algorithms", "sslyze"), ctx())
    assert h.status == "lulus"


def test_key_rsa_pendek_gagal(sslyze_fake):
    sslyze_fake("RSA", 1024, "sha256")
    h = jalankan("tls.key_and_algorithms", "sslyze", metode("CRYP-5.1-T01", "tls.key_and_algorithms", "sslyze"), ctx())
    assert h.status == "gagal"


def test_key_sig_lemah_gagal(sslyze_fake):
    sslyze_fake("RSA", 2048, "sha1")
    h = jalankan("tls.key_and_algorithms", "sslyze", metode("CRYP-5.1-T01", "tls.key_and_algorithms", "sslyze"), ctx())
    assert h.status == "gagal"


def test_key_sslyze_absen_tdv(monkeypatch):
    monkeypatch.setattr(sslyze_client, "tersedia", lambda: False)
    h = jalankan("tls.key_and_algorithms", "sslyze", metode("CRYP-5.1-T01", "tls.key_and_algorithms", "sslyze"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 5.2-T01 token integrity

class _Klien:
    def __init__(self, resp):
        self._r = resp
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def pakai_token(self, t):
        pass

    def kirim(self, metode_http, url, **kw):
        return self._r


@pytest.fixture
def token_fake(monkeypatch):
    monkeypatch.setattr(C, "login_ambil", lambda klien, ctx, akun, judul="": {"ok": True, "token": "aaa.bbb.ccc", "cookie": None, "resp": None})

    def pasang(resp):
        monkeypatch.setattr(C, "buat_klien", lambda c, **kw: _Klien(resp))

    return pasang


def test_token_integrity_ditolak_lulus(token_fake):
    token_fake(_Resp(401))
    h = jalankan("crypto.client_token_integrity", "custom",
                 metode("CRYP-5.2-T01", "crypto.client_token_integrity"), ctx(area=True, akun=True))
    assert h.status == "lulus"


def test_token_integrity_diterima_gagal(token_fake):
    token_fake(_Resp(200, headers={"Content-Type": "application/json"}, text='{"id":1}'))
    h = jalankan("crypto.client_token_integrity", "custom",
                 metode("CRYP-5.2-T01", "crypto.client_token_integrity"), ctx(area=True, akun=True))
    assert h.status == "gagal"


def test_token_integrity_tanpa_akun_tdv(token_fake):
    token_fake(_Resp(401))
    h = jalankan("crypto.client_token_integrity", "custom",
                 metode("CRYP-5.2-T01", "crypto.client_token_integrity"), ctx(area=True, akun=False))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 5.4-T01 token randomness

@pytest.fixture
def cookie_seq(monkeypatch):
    """Monkeypatch buat_klien agar tiap pemanggilan mengembalikan cookie berikutnya dari daftar."""
    def pasang(nilai_list):
        it = iter(nilai_list)

        def buat(c, **kw):
            try:
                val = next(it)
            except StopIteration:
                val = None
            resp = _Resp(200, headers={"Set-Cookie": f"sessionid={val}; Path=/; HttpOnly"} if val else {})
            return _Klien(resp)

        monkeypatch.setattr(C, "buat_klien", buat)

    return pasang


def test_randomness_acak_lulus(cookie_seq):
    cookie_seq([secrets.token_hex(20) for _ in range(20)])
    h = jalankan("crypto.token_randomness", "custom",
                 metode("CRYP-5.4-T01", "crypto.token_randomness", jumlah_sampel=20), ctx())
    assert h.status == "lulus"


def test_randomness_berurutan_gagal(cookie_seq):
    cookie_seq([str(100000 + i) for i in range(20)])
    h = jalankan("crypto.token_randomness", "custom",
                 metode("CRYP-5.4-T01", "crypto.token_randomness", jumlah_sampel=20), ctx())
    assert h.status == "gagal"


def test_randomness_sampel_kurang_tdv(cookie_seq):
    cookie_seq(["samevalue123456"] * 20)  # 1 unik → < 8
    h = jalankan("crypto.token_randomness", "custom",
                 metode("CRYP-5.4-T01", "crypto.token_randomness", jumlah_sampel=20), ctx())
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 5.3-T01 nuclei secrets

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_CRYP", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


def test_secrets_terekspos_gagal(nuclei_fake):
    nuclei_fake([{"template_id": "aws-key", "nama": "AWS Access Key", "severity": "high",
                  "tags": ["token", "exposure"], "url": f"{BASE}/js/app.js"}])
    h = jalankan("crypto.exposed_secrets", "nuclei", metode("CRYP-5.3-T01", "crypto.exposed_secrets", "nuclei"), ctx())
    assert h.status == "gagal"


def test_secrets_bersih_lulus(nuclei_fake):
    nuclei_fake([])
    h = jalankan("crypto.exposed_secrets", "nuclei", metode("CRYP-5.3-T01", "crypto.exposed_secrets", "nuclei"), ctx())
    assert h.status == "lulus"


def test_secrets_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("crypto.exposed_secrets", "nuclei", metode("CRYP-5.3-T01", "crypto.exposed_secrets", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
