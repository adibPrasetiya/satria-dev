"""Uji check File (FILE).

Check unggah diuji dengan memalsukan `buat_klien` + `login_ambil`; check unduh dengan `buat_klien`;
check nuclei dengan `nuclei_client`. AI dinonaktifkan (AI_FILE=off).
"""

from __future__ import annotations

import pytest

from satya_worker import nuclei_client
from satya_worker.checks import berkas as B
from satya_worker.models import MetodeSpec, ScanContext
from satya_worker.registry import cari_check

BASE = "https://app.test"

EP_UPLOAD = {"url": f"{BASE}/api/upload", "metode_http": "POST", "titik_uji": "unggah_file",
             "request_fields": [{"nama": "file", "lokasi": "file", "tipe": "file"}]}
EP_DOWNLOAD = {"url": f"{BASE}/files/doc.pdf", "metode_http": "GET", "titik_uji": "unduh_file"}
EP_IMAGE = {"url": f"{BASE}/img/photo.jpg", "metode_http": "GET", "titik_uji": "unduh_file"}


def ctx(*, endpoints=None, akun=False) -> ScanContext:
    d = {"scan_id": "s", "aplikasi_id": "a", "base_url": BASE, "endpoints": endpoints or []}
    if akun:
        d["akun_uji"] = [{"kunci": "akun_uji_1", "username": "uji@contoh.go.id", "password": "X", "terisi": True}]
    return ScanContext.from_dict(d)


def metode(mid, check_id, engine="custom", **param):
    return MetodeSpec.from_dict({"id": mid, "check_id": check_id, "titik_uji": "unggah_file",
                                 "engine": engine, "kriteria_lulus": "kriteria", "parameter": param})


def jalankan(check_id, engine, m, c):
    return cari_check(check_id, engine).run(c, m)


class _Resp:
    def __init__(self, status, headers=None, text="", content=b""):
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.text = text
        self.content = content or text.encode("utf-8", "ignore")


class _Klien:
    def __init__(self, handler):
        self._h = handler
        self.bukti = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def kirim(self, metode_http, url, *, json=None, data=None, content=None, files=None, headers=None, judul_bukti="", sandi_disamarkan=None):
        return self._h(metode_http, url, {"files": files, "headers": headers or {}})


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("AI_FILE", "off")
    monkeypatch.setattr(B, "login_ambil", lambda klien, ctx, akun, judul="": {"ok": True, "token": "t", "cookie": None, "resp": None})

    def pasang(handler):
        monkeypatch.setattr(B, "buat_klien", lambda c, **kw: _Klien(handler))

    return pasang


# --------------------------------------------------------------------------- 11.1-T01 size

def test_size_diterima_gagal(fake):
    fake(lambda mh, url, i: _Resp(201, text='{"id":1}'))
    h = jalankan("file.upload_size_limit", "custom",
                 metode("FILE-11.1-T01", "file.upload_size_limit", ukuran_maks_mb=1), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "gagal"


def test_size_ditolak_lulus(fake):
    fake(lambda mh, url, i: _Resp(413, text="too large"))
    h = jalankan("file.upload_size_limit", "custom",
                 metode("FILE-11.1-T01", "file.upload_size_limit", ukuran_maks_mb=1), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "lulus"


def test_size_tanpa_endpoint_tdv(fake):
    fake(lambda mh, url, i: _Resp(200))
    h = jalankan("file.upload_size_limit", "custom",
                 metode("FILE-11.1-T01", "file.upload_size_limit", ukuran_maks_mb=1), ctx(endpoints=[], akun=True))
    assert h.status == "tidak_dapat_diverifikasi"


# --------------------------------------------------------------------------- 11.2-T01 content-type

def test_content_type_diterima_gagal(fake):
    fake(lambda mh, url, i: _Resp(201, text='{"url":"/x.jpg"}'))
    h = jalankan("file.content_type_validation", "custom",
                 metode("FILE-11.2-T01", "file.content_type_validation"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "gagal"


def test_content_type_ditolak_lulus(fake):
    fake(lambda mh, url, i: _Resp(415, text="invalid image"))
    h = jalankan("file.content_type_validation", "custom",
                 metode("FILE-11.2-T01", "file.content_type_validation"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 11.3-T01 filename

def test_filename_mentah_gagal(fake):
    # Server menggaungkan nama file mentah (dengan <x>.txt) → tak disanitasi.
    def h(mh, url, i):
        nama = i["files"]["file"][0]
        return _Resp(201, text='{"stored":"%s"}' % nama)
    fake(h)
    r = jalankan("file.filename_sanitization", "custom",
                 metode("FILE-11.3-T01", "file.filename_sanitization"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert r.status == "gagal"


def test_filename_disanitasi_lulus(fake):
    fake(lambda mh, url, i: _Resp(201, text='{"stored":"a1b2c3.txt"}'))
    r = jalankan("file.filename_sanitization", "custom",
                 metode("FILE-11.3-T01", "file.filename_sanitization"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert r.status == "lulus"


# --------------------------------------------------------------------------- 11.4-T01 AV/EICAR

def test_av_diterima_gagal(fake):
    fake(lambda mh, url, i: _Resp(201, text='{"id":9}'))
    h = jalankan("file.av_scanning", "custom",
                 metode("FILE-11.4-T01", "file.av_scanning"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "gagal"


def test_av_ditolak_lulus(fake):
    fake(lambda mh, url, i: _Resp(400, text="malware detected"))
    h = jalankan("file.av_scanning", "custom",
                 metode("FILE-11.4-T01", "file.av_scanning"), ctx(endpoints=[EP_UPLOAD], akun=True))
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 11.5-T01 download headers

def test_download_headers_aman_lulus(fake):
    fake(lambda mh, url, i: _Resp(200, headers={"Content-Disposition": "attachment; filename=doc.pdf",
                                                 "X-Content-Type-Options": "nosniff"}))
    h = jalankan("file.download_headers", "custom",
                 metode("FILE-11.5-T01", "file.download_headers"), ctx(endpoints=[EP_DOWNLOAD]))
    assert h.status == "lulus"


def test_download_headers_kurang_gagal(fake):
    fake(lambda mh, url, i: _Resp(200, headers={"Content-Type": "application/pdf"}))
    h = jalankan("file.download_headers", "custom",
                 metode("FILE-11.5-T01", "file.download_headers"), ctx(endpoints=[EP_DOWNLOAD]))
    assert h.status == "gagal"


# --------------------------------------------------------------------------- 11.3-T02 metadata

def test_metadata_gps_gagal(fake):
    exif = b"\xff\xd8\xff\xe1" + b"Exif\x00\x00" + b"....GPSLatitude...." + b"\xff\xd9"
    fake(lambda mh, url, i: _Resp(200, content=exif))
    h = jalankan("file.metadata_stripped", "custom",
                 metode("FILE-11.3-T02", "file.metadata_stripped"), ctx(endpoints=[EP_IMAGE]))
    assert h.status == "gagal"


def test_metadata_bersih_lulus(fake):
    fake(lambda mh, url, i: _Resp(200, content=b"\xff\xd8\xff\xe0JFIF-bersih\xff\xd9"))
    h = jalankan("file.metadata_stripped", "custom",
                 metode("FILE-11.3-T02", "file.metadata_stripped"), ctx(endpoints=[EP_IMAGE]))
    assert h.status == "lulus"


# --------------------------------------------------------------------------- 11.5-T02 nuclei

@pytest.fixture
def nuclei_fake(monkeypatch):
    monkeypatch.setenv("AI_FILE", "off")
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: True)

    def pasang(temuan):
        monkeypatch.setattr(nuclei_client, "jalankan", lambda *a, **kw: temuan)

    return pasang


def test_extension_disajikan_gagal(nuclei_fake):
    nuclei_fake([{"template_id": "exposed-config", "nama": "Exposed .env", "severity": "high",
                  "tags": ["exposure", "config"], "url": f"{BASE}/.env"}])
    h = jalankan("file.extension_allowlist", "nuclei", metode("FILE-11.5-T02", "file.extension_allowlist", "nuclei"), ctx())
    assert h.status == "gagal"


def test_extension_bersih_lulus(nuclei_fake):
    nuclei_fake([])
    h = jalankan("file.extension_allowlist", "nuclei", metode("FILE-11.5-T02", "file.extension_allowlist", "nuclei"), ctx())
    assert h.status == "lulus"


def test_extension_nuclei_absen_tdv(monkeypatch):
    monkeypatch.setattr(nuclei_client, "tersedia", lambda: False)
    h = jalankan("file.extension_allowlist", "nuclei", metode("FILE-11.5-T02", "file.extension_allowlist", "nuclei"), ctx())
    assert h.status == "tidak_dapat_diverifikasi"
