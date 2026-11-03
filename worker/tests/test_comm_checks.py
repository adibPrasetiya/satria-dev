"""Uji check Keamanan Komunikasi (COMM).

Check sslyze (COMM-8.3/8.4) diuji dengan memalsukan `sslyze_client.pindai` (tanpa jaringan/TLS).
Check custom (COMM-8.1) diuji dengan memalsukan `buat_klien` (tanpa socket). Verdict deterministik;
AI dinonaktifkan (AI_COMM=off) agar tes tak memanggil provider.
"""

from __future__ import annotations

import pytest

from satya_worker import sslyze_client
from satya_worker.checks import komunikasi as k
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check


def ctx(base: str = "https://app.test") -> ScanContext:
    return ScanContext.from_dict({
        "scan_id": "s", "aplikasi_id": "a", "base_url": base,
        "titik_uji": {"login_page": {"tersedia": True, "url": f"{base}/login", "metode_http": "GET"}},
    })


def metode(mid: str, check_id: str, engine: str = "custom", **param) -> MetodeSpec:
    return MetodeSpec.from_dict({
        "id": mid, "check_id": check_id, "titik_uji": "global", "engine": engine,
        "kriteria_lulus": "kriteria", "parameter": param,
    })


def jalankan(check_id: str, engine: str, m: MetodeSpec, c: ScanContext):
    return cari_check(check_id, engine).run(c, m)


# --------------------------------------------------------------------------- fake sslyze

def _scan_aman() -> dict:
    return {
        "ok": True,
        "protokol": {"SSL 2.0": False, "SSL 3.0": False, "TLS 1.0": False, "TLS 1.1": False, "TLS 1.2": True, "TLS 1.3": True},
        "cipher_per_protokol": {"TLS 1.2": ["TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"], "TLS 1.3": ["TLS_AES_256_GCM_SHA384"]},
        "cipher_lemah": [],
        "forward_secrecy": True,
        "sertifikat": {
            "tersedia": True, "subjek_cn": "app.test", "san": ["app.test"],
            "penerbit_o": "DigiCert Inc", "penerbit_cn": "DigiCert TLS RSA",
            "tidak_sesudah": "2027-01-01T00:00:00+00:00", "kedaluwarsa": False, "hari_tersisa": 300,
            "host_cocok": True, "urutan_rantai_valid": True, "panjang_rantai": 2,
            "trust": {"Mozilla": True, "Windows": True, "Apple": True, "Android": True},
        },
    }


def _scan_rentan() -> dict:
    return {
        "ok": True,
        "protokol": {"SSL 2.0": False, "SSL 3.0": False, "TLS 1.0": True, "TLS 1.1": True, "TLS 1.2": True, "TLS 1.3": False},
        "cipher_per_protokol": {"TLS 1.0": ["TLS_RSA_WITH_RC4_128_SHA"], "TLS 1.2": ["TLS_RSA_WITH_AES_128_CBC_SHA"]},
        "cipher_lemah": [{"protokol": "TLS 1.0", "cipher": "TLS_RSA_WITH_RC4_128_SHA"}],
        "forward_secrecy": False,
        "sertifikat": {
            "tersedia": True, "subjek_cn": "lain.test", "san": ["lain.test"],
            "penerbit_o": "Self Signed", "penerbit_cn": "Self",
            "tidak_sesudah": "2020-01-01T00:00:00+00:00", "kedaluwarsa": True, "hari_tersisa": -100,
            "host_cocok": False, "urutan_rantai_valid": False, "panjang_rantai": 1,
            "trust": {"Mozilla": False, "Windows": False, "Apple": False, "Android": False},
        },
    }


@pytest.fixture
def sslyze_fake(monkeypatch):
    monkeypatch.setenv("AI_COMM", "off")
    monkeypatch.setattr(sslyze_client, "tersedia", lambda: True)
    monkeypatch.setattr(sslyze_client, "aktif", lambda: True)

    def pasang(scan: dict):
        monkeypatch.setattr(sslyze_client, "pindai", lambda *a, **kw: scan)

    return pasang


# --------------------------------------------------------------------------- COMM-8.3-T01

def test_protokol_aman_lulus(sslyze_fake):
    sslyze_fake(_scan_aman())
    h = jalankan("tls.protocol_versions", "sslyze", metode("COMM-8.3-T01", "tls.protocol_versions", "sslyze"), ctx())
    assert h.status == "lulus"


def test_protokol_usang_gagal(sslyze_fake):
    sslyze_fake(_scan_rentan())
    h = jalankan("tls.protocol_versions", "sslyze", metode("COMM-8.3-T01", "tls.protocol_versions", "sslyze"), ctx())
    assert h.status == "gagal"
    assert "TLS 1.0" in h.ringkasan


# --------------------------------------------------------------------------- COMM-8.3-T02

def test_cipher_aman_lulus(sslyze_fake):
    sslyze_fake(_scan_aman())
    h = jalankan("tls.weak_ciphers", "sslyze", metode("COMM-8.3-T02", "tls.weak_ciphers", "sslyze"), ctx())
    assert h.status == "lulus"


def test_cipher_lemah_gagal(sslyze_fake):
    sslyze_fake(_scan_rentan())
    h = jalankan("tls.weak_ciphers", "sslyze", metode("COMM-8.3-T02", "tls.weak_ciphers", "sslyze"), ctx())
    assert h.status == "gagal"


def test_cipher_tanpa_fs_gagal(sslyze_fake):
    scan = _scan_aman()
    scan["forward_secrecy"] = False
    scan["cipher_per_protokol"] = {"TLS 1.2": ["TLS_RSA_WITH_AES_128_GCM_SHA256"]}
    scan["protokol"]["TLS 1.3"] = False
    sslyze_fake(scan)
    h = jalankan("tls.weak_ciphers", "sslyze", metode("COMM-8.3-T02", "tls.weak_ciphers", "sslyze"), ctx())
    assert h.status == "gagal"
    assert "forward secrecy" in h.ringkasan.lower()


# --------------------------------------------------------------------------- COMM-8.4-T01

def test_sertifikat_valid_lulus(sslyze_fake):
    sslyze_fake(_scan_aman())
    h = jalankan("tls.certificate_validity", "sslyze", metode("COMM-8.4-T01", "tls.certificate_validity", "sslyze"), ctx())
    assert h.status == "lulus"


def test_sertifikat_kedaluwarsa_dan_host_salah_gagal(sslyze_fake):
    sslyze_fake(_scan_rentan())
    h = jalankan("tls.certificate_validity", "sslyze", metode("COMM-8.4-T01", "tls.certificate_validity", "sslyze"), ctx())
    assert h.status == "gagal"
    assert "kedaluwarsa" in h.ringkasan


# --------------------------------------------------------------------------- COMM-8.4-T02

def test_trust_browser_lulus(sslyze_fake):
    sslyze_fake(_scan_aman())
    m = metode("COMM-8.4-T02", "tls.certificate_browser_trust", "sslyze", root_store=["mozilla", "microsoft", "apple", "android"])
    h = jalankan("tls.certificate_browser_trust", "sslyze", m, ctx())
    assert h.status == "lulus"


def test_trust_browser_gagal(sslyze_fake):
    sslyze_fake(_scan_rentan())
    m = metode("COMM-8.4-T02", "tls.certificate_browser_trust", "sslyze", root_store=["mozilla", "microsoft", "apple", "android"])
    h = jalankan("tls.certificate_browser_trust", "sslyze", m, ctx())
    assert h.status == "gagal"


# --------------------------------------------------------------------------- COMM-8.4-T03 (info)

DAFTAR_PSRE = [
    {"nama": "Balai Besar Sertifikasi Elektronik (BSrE) - BSSN"},
    {"nama": "PT Privy Identitas Digital (PrivyID)"},
]


def test_psre_cocok_string_match(sslyze_fake):
    scan = _scan_aman()
    scan["sertifikat"]["penerbit_o"] = "PT Privy Identitas Digital"
    sslyze_fake(scan)
    m = metode("COMM-8.4-T03", "tls.certificate_issuer_psre", "sslyze", daftar_psre=DAFTAR_PSRE)
    h = jalankan("tls.certificate_issuer_psre", "sslyze", m, ctx())
    assert h.status == "lulus"
    assert "PSrE" in h.ringkasan and "Privy" in h.ringkasan


def test_psre_tak_cocok_info(sslyze_fake):
    # Penerbit asing + AI off → tetap 'lulus' (info), ditandai tak terdaftar.
    sslyze_fake(_scan_aman())
    m = metode("COMM-8.4-T03", "tls.certificate_issuer_psre", "sslyze", daftar_psre=DAFTAR_PSRE)
    h = jalankan("tls.certificate_issuer_psre", "sslyze", m, ctx())
    assert h.status == "lulus"
    assert "TIDAK terdaftar" in h.ringkasan


# --------------------------------------------------------------------------- tidak_dapat_diverifikasi

def test_sslyze_tak_terpasang_tdv(monkeypatch):
    monkeypatch.setattr(sslyze_client, "tersedia", lambda: False)
    h = jalankan("tls.protocol_versions", "sslyze", metode("COMM-8.3-T01", "tls.protocol_versions", "sslyze"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
    assert h.menunggu_tinjauan is True


def test_sslyze_tak_konek_tdv(sslyze_fake):
    sslyze_fake({"ok": False, "galat": "tak dapat menjabat TLS"})
    h = jalankan("tls.certificate_validity", "sslyze", metode("COMM-8.4-T01", "tls.certificate_validity", "sslyze"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- COMM-8.1 (custom, fake klien)

class _FakeResp:
    def __init__(self, status, headers=None, text=""):
        self.status_code = status
        self.headers = headers or {}
        self.text = text


class _FakeKlien:
    def __init__(self, handler):
        self._handler = handler
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def kirim(self, metode_http, url, **kw):
        return self._handler(metode_http, url)


@pytest.fixture
def fake_klien(monkeypatch):
    def pasang(handler):
        monkeypatch.setattr(k, "buat_klien", lambda c, **kw: _FakeKlien(handler))

    return pasang


def test_https_enforced_lulus(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(301, {"location": "https://app.test/"}))
    h = jalankan("tls.https_enforced", "custom", metode("COMM-8.1-T01", "tls.https_enforced"), ctx())
    assert h.status == "lulus"


def test_https_enforced_gagal_dilayani_http(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(200, {}, "<html>ok</html>"))
    h = jalankan("tls.https_enforced", "custom", metode("COMM-8.1-T01", "tls.https_enforced"), ctx())
    assert h.status == "gagal"


def test_https_enforced_redirect_tak_permanen_gagal(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(302, {"location": "https://app.test/"}))
    h = jalankan("tls.https_enforced", "custom", metode("COMM-8.1-T01", "tls.https_enforced"), ctx())
    assert h.status == "gagal"
    assert "permanen" in h.ringkasan


def test_hsts_lulus(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(200, {"strict-transport-security": "max-age=31536000; includeSubDomains"}))
    h = jalankan("headers.hsts", "custom", metode("COMM-8.1-T02", "headers.hsts", max_age_minimum=31536000), ctx())
    assert h.status == "lulus"


def test_hsts_tidak_ada_gagal(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(200, {}))
    h = jalankan("headers.hsts", "custom", metode("COMM-8.1-T02", "headers.hsts", max_age_minimum=31536000), ctx())
    assert h.status == "gagal"


def test_hsts_max_age_pendek_gagal(fake_klien):
    fake_klien(lambda mh, url: _FakeResp(200, {"strict-transport-security": "max-age=600"}))
    h = jalankan("headers.hsts", "custom", metode("COMM-8.1-T02", "headers.hsts", max_age_minimum=31536000), ctx())
    assert h.status == "gagal"


# --------------------------------------------------------------------------- cocok_host (RFC 6125)

@pytest.mark.parametrize("host,san,cn,harap", [
    ("app.test", ["app.test"], "", True),                       # exact
    ("APP.test", ["app.test"], "", True),                       # case-insensitive
    ("api.contoh.go.id", ["*.contoh.go.id"], "", True),         # wildcard satu label
    ("a.b.contoh.go.id", ["*.contoh.go.id"], "", False),        # wildcard tak lintas label
    ("contoh.go.id", ["*.contoh.go.id"], "", False),            # wildcard tak cocok apex
    ("lain.test", ["app.test", "www.app.test"], "", False),     # tak ada yang cocok
    ("app.test", [], "app.test", True),                         # cadangan CN saat SAN kosong
    ("app.test", [], "", None),                                 # ambigu → None
])
def test_cocok_host(host, san, cn, harap):
    assert sslyze_client.cocok_host(host, san, cn) is harap
