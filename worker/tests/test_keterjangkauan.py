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


def test_loop_task_target_tak_terjangkau_selesai_cepat_dengan_alasan(monkeypatch):
    monkeypatch.setenv("WORKER_IP_PUBLIK", "203.0.113.7")
    url = f"http://127.0.0.1:{_port_tertutup()}"
    log: list[tuple] = []
    with BackendPalsu(url) as backend:
        from satya_worker.backend_client import BackendClient

        with BackendClient(backend.base_url, TOKEN, worker_id="worker-uji") as klien:
            monkeypatch.setattr(klien, "kirim_log", lambda tid, lvl, pesan, data=None: log.append((lvl, pesan, data)))
            t0 = time.monotonic()
            assert proses_satu(klien, ["custom"]) is True
            assert time.monotonic() - t0 < 30
        hasil = list(backend.hasil)
    assert hasil and hasil[0]["status"] == "tidak_dapat_diverifikasi"
    assert "tidak terjangkau" in hasil[0]["ringkasan"] and "203.0.113.7" in hasil[0]["ringkasan"]
    # Keterangan terstruktur untuk banner UI.
    ev = [d for _, _, d in log if d and d.get("jenis") == "terblokir"]
    assert len(ev) == 1
    e = ev[0]
    assert e["fatal"] is True and e["awal"] is True and e["fase"] == "pengujian"
    assert e["lapisan"] == "tcp" and e["host"] == "127.0.0.1" and e["ip_worker"] == "203.0.113.7"
    assert "whitelist" in e["saran"]


# --------------------------------------------------------------------------- blokir tingkat HTTP (WAF)


def test_tanda_blokir_http():
    assert kt.tanda_blokir_http(403, {"cf-mitigated": "challenge"}, "") == "HTTP 403 — halaman blokir Cloudflare"
    assert "F5" in kt.tanda_blokir_http(403, {}, "<html>The requested URL was rejected. Please consult</html>")
    assert "rate-limit" in kt.tanda_blokir_http(429, {}, "")
    assert kt.tanda_blokir_http(403, {}, "<h1>Forbidden</h1>") is None   # 403 biasa aplikasi, bukan WAF
    assert kt.tanda_blokir_http(200, {}, "access denied") is None          # status bukan penolakan


def test_pengawas_melapor_blokir_waf_yang_muncul_di_tengah_task(monkeypatch):
    koordinasi.STATUS.mulai_task("1", "uji")
    lapor: list[tuple] = []
    with TargetPalsu("aman") as t:
        p = kt.Pengawas(t.base_url, fase="recon", status_dasar=200, timeout=2,
                        lapor=lambda lvl, pesan, data: lapor.append((lvl, pesan, data)))
        monkeypatch.setattr(kt, "_probe_http", lambda url, to: (403, "HTTP 403 — halaman blokir Cloudflare"))
        assert p.cek_sekali() is False and not lapor          # satu probe belum cukup
        assert p.cek_sekali() is False and len(lapor) == 1    # dua beruntun → lapor sekali
        p.cek_sekali()
        assert len(lapor) == 1                                # tidak berulang
    lvl, pesan, data = lapor[0]
    assert lvl == "peringatan" and "Cloudflare" in pesan and "awalnya HTTP 200" in pesan
    assert data["jenis"] == "terblokir" and data["fatal"] is False and data["lapisan"] == "http"
    koordinasi.periksa_batal()  # peringatan WAF tidak menghentikan task


def test_pengawas_abaikan_status_blokir_yang_sudah_ada_sejak_awal(monkeypatch):
    koordinasi.STATUS.mulai_task("1", "uji")
    lapor: list[tuple] = []
    with TargetPalsu("aman") as t:
        p = kt.Pengawas(t.base_url, status_dasar=403, timeout=2, lapor=lambda *a: lapor.append(a))
        monkeypatch.setattr(kt, "_probe_http", lambda url, to: (403, "HTTP 403 — halaman blokir WAF"))
        p.cek_sekali(); p.cek_sekali()
    assert not lapor
