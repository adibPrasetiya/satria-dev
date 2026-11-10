"""Preflight keterjangkauan target, pemutus sirkuit, dan proses/tunggu yang bisa disela."""

from __future__ import annotations

import socket
import sys
import time

import pytest

from satya_worker import keterjangkauan as kt
from satya_worker import koordinasi
from satya_worker.main import proses_satu
from tests.backend_palsu import TOKEN, BackendPalsu
from tests.target_palsu import TargetPalsu



@pytest.fixture(autouse=True)
def _bersih():
    kt.hapus_cache()
    koordinasi.STATUS.selesai_task()
    yield
    kt.hapus_cache()
    koordinasi.STATUS.selesai_task()


def _port_tertutup() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # tak ada yang mendengarkan → koneksi ditolak
    return port


def test_preflight_ok_untuk_target_hidup():
    with TargetPalsu("aman") as t:
        assert kt.preflight(t.base_url).ok


def test_preflight_gagal_port_tertutup_dan_dicache(monkeypatch):
    url = f"http://127.0.0.1:{_port_tertutup()}/"
    h = kt.preflight(url, timeout=2)
    assert not h.ok and ("ditolak" in h.alasan or "timeout" in h.alasan)  # Windows: port tertutup → timeout
    # Hasil negatif di-cache: panggilan berikutnya tak membuka koneksi lagi.
    monkeypatch.setattr(kt, "cek_tcp", lambda *a, **k: pytest.fail("seharusnya dari cache"))
    assert kt.preflight(url).alasan == h.alasan


def test_preflight_timeout_disebut_kemungkinan_diblokir(monkeypatch):
    def timeout(*a, **k):
        raise socket.timeout()

    monkeypatch.setattr(kt.socket, "create_connection", timeout)
    h = kt.preflight("https://target.contoh:443/", timeout=1)
    assert not h.ok and "diblokir" in h.alasan


def test_preflight_bisa_dinonaktifkan(monkeypatch):
    monkeypatch.setenv("TARGET_CEK_AKTIF", "0")
    assert kt.preflight(f"http://127.0.0.1:{_port_tertutup()}/").ok


def test_pengawas_memicu_pemutus_sirkuit_setelah_gagal_beruntun():
    koordinasi.STATUS.mulai_task("1", "uji")
    p = kt.Pengawas(f"http://127.0.0.1:{_port_tertutup()}/", maks_gagal=3, timeout=1)
    assert p.cek_sekali() is False and p.cek_sekali() is False
    koordinasi.periksa_batal()  # belum terpicu
    assert p.cek_sekali() is True
    with pytest.raises(koordinasi.TargetTakTerjangkau) as e:
        koordinasi.periksa_batal()
    assert "3×" in e.value.alasan


def test_pengawas_reset_saat_target_kembali():
    koordinasi.STATUS.mulai_task("1", "uji")
    with TargetPalsu("aman") as t:
        p = kt.Pengawas(t.base_url, maks_gagal=2, timeout=1)
        p.gagal_beruntun = 1
        assert p.cek_sekali() is False and p.gagal_beruntun == 0


def test_jalankan_proses_dimatikan_saat_target_tak_terjangkau():
    koordinasi.STATUS.mulai_task("1", "uji")
    koordinasi.STATUS.tandai_tak_terjangkau("uji")
    t0 = time.monotonic()
    with pytest.raises(koordinasi.TargetTakTerjangkau):
        koordinasi.jalankan_proses([sys.executable, "-c", "import time; time.sleep(30)"], timeout=60)
    assert time.monotonic() - t0 < 5


def test_jalankan_proses_normal_dan_timeout():
    p = koordinasi.jalankan_proses([sys.executable, "-c", "print('halo')"], text=True, timeout=20)
    assert p.returncode == 0 and p.stdout.strip() == "halo"
    with pytest.raises(__import__("subprocess").TimeoutExpired):
        koordinasi.jalankan_proses([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)


def test_tunggu_disela_pembatalan():
    koordinasi.STATUS.mulai_task("1", "uji")
    koordinasi.STATUS.batal.set()
    with pytest.raises(koordinasi.Dibatalkan):
        koordinasi.tunggu(10)


def test_loop_task_target_tak_terjangkau_selesai_cepat_dengan_alasan():
    url = f"http://127.0.0.1:{_port_tertutup()}"
    with BackendPalsu(url) as backend:
        from satya_worker.backend_client import BackendClient

        with BackendClient(backend.base_url, TOKEN, worker_id="worker-uji") as klien:
            t0 = time.monotonic()
            assert proses_satu(klien, ["custom"]) is True
            assert time.monotonic() - t0 < 30
        hasil = list(backend.hasil)
    assert hasil and hasil[0]["status"] == "tidak_dapat_diverifikasi"
    assert "tidak terjangkau" in hasil[0]["ringkasan"]
