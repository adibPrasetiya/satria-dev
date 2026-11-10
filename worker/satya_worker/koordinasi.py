"""Koordinasi worker ↔ backend: heartbeat berkala, status pekerjaan, dan pembatalan kooperatif.

- `STATUS` (global, thread-safe) menyimpan task/scan/tahap yang sedang dikerjakan worker.
- `Detak` (thread) mengirim heartbeat tiap `HEARTBEAT_INTERVAL` detik ke
  `POST /internal/workers/heartbeat`: backend memperbarui registry worker, MEMPERPANJANG lease task
  (agar task panjang seperti discovery tak dikembalikan ke antrean saat masih berjalan), dan
  membalas `batalkan: true` bila scan task itu sudah dibatalkan pengguna.
- `periksa_batal()` dipanggil di batas tahap (lihat `peristiwa.tahap`) & langkah panjang; melempar
  `Dibatalkan` (turunan BaseException agar tak tertelan `except Exception` di jalur best-effort).
- Pemutus sirkuit: `keterjangkauan.Pengawas` menandai `STATUS` bila target berulang kali tak
  terjangkau; `periksa_batal()` lalu melempar `TargetTakTerjangkau` (turunan `Dibatalkan`).
- `tunggu()` / `jalankan_proses()` = pengganti `time.sleep` / `subprocess.run` yang bisa disela
  pembatalan atau pemutus sirkuit (alat eksternal dihentikan, bukan ditunggu sampai timeout).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from typing import Any, Optional

VERSI = "satya-worker 0.2"


class Dibatalkan(BaseException):
    """Scan task yang sedang dikerjakan dibatalkan pengguna (sinyal dari backend)."""


class TargetTakTerjangkau(Dibatalkan):
    """Target tak terjangkau dari worker (mis. IP worker diblokir firewall/WAF target)."""

    def __init__(self, alasan: str = "") -> None:
        super().__init__(alasan)
        self.alasan = alasan


class StatusWorker:
    def __init__(self) -> None:
        self._kunci = threading.Lock()
        self.task_id: Optional[str] = None
        self.tahap: str = ""
        self.batal = threading.Event()
        self.tak_terjangkau: Optional[str] = None  # alasan; diisi Pengawas (pemutus sirkuit)

    def mulai_task(self, task_id: str, tahap: str = "") -> None:
        with self._kunci:
            self.task_id, self.tahap = task_id, tahap
            self.batal.clear()
            self.tak_terjangkau = None

    def tandai_tak_terjangkau(self, alasan: str) -> None:
        with self._kunci:
            if self.task_id and not self.tak_terjangkau:
                self.tak_terjangkau = alasan

    def set_tahap(self, tahap: str) -> None:
        with self._kunci:
            self.tahap = tahap[:120]

    def selesai_task(self) -> None:
        with self._kunci:
            self.task_id, self.tahap = None, ""
            self.batal.clear()
            self.tak_terjangkau = None

    def potret(self) -> dict[str, Any]:
        with self._kunci:
            return {"task_id": self.task_id, "tahap": self.tahap}


STATUS = StatusWorker()


def set_tahap(tahap: str) -> None:
    STATUS.set_tahap(tahap)


def periksa_batal() -> None:
    """Lempar `Dibatalkan` bila backend menandai scan task aktif sudah dibatalkan, atau
    `TargetTakTerjangkau` bila pemutus sirkuit terpicu."""
    if not STATUS.task_id:
        return
    alasan = STATUS.tak_terjangkau
    if alasan:
        raise TargetTakTerjangkau(alasan)
    if STATUS.batal.is_set():
        raise Dibatalkan()


def tunggu(detik: float) -> None:
    """`time.sleep` yang memeriksa pembatalan/pemutus sirkuit tiap ≤0,5 dtk."""
    batas = time.monotonic() + max(0.0, detik)
    while True:
        periksa_batal()
        sisa = batas - time.monotonic()
        if sisa <= 0:
            return
        time.sleep(min(0.5, sisa))


def jalankan_proses(perintah: list[str], *, timeout: Optional[float] = None, **kw: Any) -> subprocess.CompletedProcess:
    """Seperti `subprocess.run(perintah, capture_output=True, check=False, ...)`, tetapi proses anak
    dimatikan & `Dibatalkan`/`TargetTakTerjangkau` dilempar begitu scan dibatalkan atau target
    dinyatakan tak terjangkau. Melempar `subprocess.TimeoutExpired` bila melewati `timeout`."""
    kw.pop("capture_output", None)
    kw.pop("check", None)
    proc = subprocess.Popen(perintah, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    batas = time.monotonic() + timeout if timeout is not None else None
    while True:
        try:
            out, err = proc.communicate(timeout=1.0)
            return subprocess.CompletedProcess(perintah, proc.returncode, stdout=out, stderr=err)
        except subprocess.TimeoutExpired:
            pass
        try:
            periksa_batal()
        except Dibatalkan:
            proc.kill()
            proc.communicate()
            raise
        if batas is not None and time.monotonic() > batas:
            proc.kill()
            proc.communicate()
            raise subprocess.TimeoutExpired(perintah, timeout or 0)


class Detak(threading.Thread):
    """Thread heartbeat. Memakai klien HTTP sendiri (httpx.Client tak dibagi antar-thread)."""

    def __init__(self, backend: Any, engines: list[str], interval: float = 10.0) -> None:
        super().__init__(name="satya-heartbeat", daemon=True)
        self._backend = backend
        self._engines = engines
        self._interval = interval
        self._henti = threading.Event()
        self._bangun = threading.Event()
        self._host = socket.gethostname()

    def segera(self) -> None:
        """Kirim heartbeat sekarang (mis. tepat setelah klaim task)."""
        self._bangun.set()

    def hentikan(self) -> None:
        self._henti.set()
        self._bangun.set()

    def kirim_sekali(self) -> None:
        p = STATUS.potret()
        try:
            balas = self._backend.heartbeat({
                "engines": self._engines,
                "status": "sibuk" if p["task_id"] else "siaga",
                "task_id": int(p["task_id"]) if p["task_id"] else None,
                "tahap": p["tahap"] or None,
                "versi": VERSI,
                "host": self._host,
            })
        except Exception as e:  # heartbeat best-effort: jangan hentikan worker
            print(f"Heartbeat gagal: {type(e).__name__}: {e}", file=sys.stderr)
            return
        if balas.get("batalkan") and p["task_id"] and STATUS.task_id == p["task_id"]:
            if not STATUS.batal.is_set():
                print(f"Backend: scan task {p['task_id']} dibatalkan — menghentikan di batas tahap berikutnya.", file=sys.stderr)
            STATUS.batal.set()

    def run(self) -> None:
        while not self._henti.is_set():
            self.kirim_sekali()
            self._bangun.wait(self._interval)
            self._bangun.clear()
