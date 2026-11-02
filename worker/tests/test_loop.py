"""Uji mode loop: worker klaim task dari backend palsu, uji target palsu, kirim hasil."""

from __future__ import annotations

from satya_worker.backend_client import BackendClient
from satya_worker.main import proses_satu
from tests.backend_palsu import TOKEN, BackendPalsu
from tests.target_palsu import TargetPalsu


def test_loop_memproses_satu_task_dan_mengirim_hasil():
    # Target rentan -> check complexity harus GAGAL (sandi lemah diterima).
    with TargetPalsu("rentan") as target, BackendPalsu(target.base_url) as backend:
        with BackendClient(backend.base_url, TOKEN, worker_id="worker-uji") as klien:
            ada = proses_satu(klien, ["custom"])
            assert ada is True
            # Panggilan kedua: antrean kosong.
            assert proses_satu(klien, ["custom"]) is False

        assert len(backend.hasil) == 1
        hasil = backend.hasil[0]
        assert hasil["metode_id"] == "AUTH-1.3-T02"
        assert hasil["status"] == "gagal"


def test_loop_target_aman_lulus():
    with TargetPalsu("aman") as target, BackendPalsu(target.base_url) as backend:
        with BackendClient(backend.base_url, TOKEN, worker_id="worker-uji") as klien:
            assert proses_satu(klien, ["custom"]) is True
        assert backend.hasil[0]["status"] == "lulus"
