"""Koordinasi worker ↔ backend: heartbeat, lease, dan pembatalan kooperatif."""

from __future__ import annotations

import pytest

from satya_worker import koordinasi, peristiwa as pr


class _BackendPalsu:
    def __init__(self, batalkan: bool = False):
        self.terima: list[dict] = []
        self.batalkan = batalkan

    def heartbeat(self, status):
        self.terima.append(status)
        return {"batalkan": self.batalkan}


@pytest.fixture(autouse=True)
def _bersih():
    koordinasi.STATUS.selesai_task()
    yield
    koordinasi.STATUS.selesai_task()


def test_heartbeat_siaga_lalu_sibuk_dengan_tahap():
    be = _BackendPalsu()
    d = koordinasi.Detak(be, ["custom", "discovery"])
    d.kirim_sekali()
    koordinasi.STATUS.mulai_task("41", "AUTH-1.2-T01")
    koordinasi.set_tahap("penemuan · katana")
    d.kirim_sekali()
    assert be.terima[0]["status"] == "siaga" and be.terima[0]["task_id"] is None
    assert be.terima[1] == {**be.terima[1], "status": "sibuk", "task_id": 41, "tahap": "penemuan · katana"}
    assert be.terima[1]["engines"] == ["custom", "discovery"] and be.terima[1]["versi"]


def test_sinyal_batal_menghentikan_di_batas_tahap():
    koordinasi.STATUS.mulai_task("7")
    koordinasi.Detak(_BackendPalsu(batalkan=True), ["discovery"]).kirim_sekali()
    with pytest.raises(koordinasi.Dibatalkan):
        pr.tahap(None, "katana", "Menjalankan katana…")


def test_batal_tak_tertelan_except_exception():
    koordinasi.STATUS.mulai_task("7")
    koordinasi.STATUS.batal.set()
    with pytest.raises(koordinasi.Dibatalkan):
        try:
            koordinasi.periksa_batal()
        except Exception:  # jalur best-effort di discovery memakai except Exception
            pytest.fail("Dibatalkan tertelan except Exception")


def test_task_baru_mereset_sinyal_batal():
    koordinasi.STATUS.mulai_task("7")
    koordinasi.STATUS.batal.set()
    koordinasi.STATUS.mulai_task("8")
    koordinasi.periksa_batal()  # tak melempar


def test_heartbeat_gagal_tidak_menghentikan_worker(capsys):
    class _Rusak:
        def heartbeat(self, status):
            raise ConnectionError("backend mati")

    koordinasi.Detak(_Rusak(), ["custom"]).kirim_sekali()
    assert "Heartbeat gagal" in capsys.readouterr().err
