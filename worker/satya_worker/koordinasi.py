"""Koordinasi worker ↔ backend: heartbeat berkala, status pekerjaan, dan pembatalan kooperatif.

- `STATUS` (global, thread-safe) menyimpan task/scan/tahap yang sedang dikerjakan worker.
- `Detak` (thread) mengirim heartbeat tiap `HEARTBEAT_INTERVAL` detik ke
  `POST /internal/workers/heartbeat`: backend memperbarui registry worker, MEMPERPANJANG lease task
  (agar task panjang seperti discovery tak dikembalikan ke antrean saat masih berjalan), dan
  membalas `batalkan: true` bila scan task itu sudah dibatalkan pengguna.
- `periksa_batal()` dipanggil di batas tahap (lihat `peristiwa.tahap`) & langkah panjang; melempar
  `Dibatalkan` (turunan BaseException agar tak tertelan `except Exception` di jalur best-effort).
"""

from __future__ import annotations

import socket
import sys
import threading
from typing import Any, Optional

VERSI = "satya-worker 0.2"


class Dibatalkan(BaseException):
    """Scan task yang sedang dikerjakan dibatalkan pengguna (sinyal dari backend)."""


class StatusWorker:
    def __init__(self) -> None:
        self._kunci = threading.Lock()
        self.task_id: Optional[str] = None
        self.tahap: str = ""
        self.batal = threading.Event()

    def mulai_task(self, task_id: str, tahap: str = "") -> None:
        with self._kunci:
            self.task_id, self.tahap = task_id, tahap
            self.batal.clear()

    def set_tahap(self, tahap: str) -> None:
        with self._kunci:
            self.tahap = tahap[:120]

    def selesai_task(self) -> None:
        with self._kunci:
            self.task_id, self.tahap = None, ""
            self.batal.clear()

    def potret(self) -> dict[str, Any]:
        with self._kunci:
            return {"task_id": self.task_id, "tahap": self.tahap}


STATUS = StatusWorker()


def set_tahap(tahap: str) -> None:
    STATUS.set_tahap(tahap)


def periksa_batal() -> None:
    """Lempar `Dibatalkan` bila backend menandai scan task aktif sudah dibatalkan."""
    if STATUS.task_id and STATUS.batal.is_set():
        raise Dibatalkan()


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
