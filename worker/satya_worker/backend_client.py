"""Klien ke endpoint /internal backend SATYA (dipakai mode loop worker).

Semua request membawa header `X-Worker-Token`. Worker tak pernah menyentuh MySQL;
seluruh interaksi antrean lewat HTTP ini.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


class BackendClient:
    def __init__(self, base_url: str, token: str, *, worker_id: str = "worker", timeout: float = 20.0) -> None:
        self._base = base_url.rstrip("/")
        self._worker_id = worker_id
        self._token = token
        self._timeout = timeout
        self._klien = httpx.Client(timeout=timeout, headers={"X-Worker-Token": token})

    def salin(self) -> "BackendClient":
        """Klien baru berkonfigurasi sama — untuk dipakai dari thread lain (httpx.Client tak thread-safe)."""
        return BackendClient(self._base, self._token, worker_id=self._worker_id, timeout=self._timeout)

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self._klien.close()

    def heartbeat(self, status: dict[str, Any]) -> dict[str, Any]:
        """Heartbeat registry worker; balasan `{batalkan: bool}` untuk task yang sedang dikerjakan."""
        resp = self._klien.post(f"{self._base}/internal/workers/heartbeat", json={"worker_id": self._worker_id, **status}, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def berhenti(self) -> None:
        """Tandai worker berhenti (shutdown rapi) — best-effort."""
        try:
            self._klien.post(f"{self._base}/internal/workers/berhenti", json={"worker_id": self._worker_id}, timeout=5.0)
        except httpx.HTTPError:
            pass

    def claim(self, engines: list[str]) -> Optional[dict[str, Any]]:
        """Klaim satu task. 204 -> None (tak ada pekerjaan)."""
        resp = self._klien.post(
            f"{self._base}/internal/tasks/claim",
            json={"worker_id": self._worker_id, "engines": engines},
        )
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        # Amplop backend: { success, message, data }
        return resp.json().get("data")

    def kirim_hasil(self, task_id: str, hasil: dict[str, Any]) -> None:
        self._klien.post(
            f"{self._base}/internal/tasks/{task_id}/result",
            json={"hasil": hasil},
        ).raise_for_status()

    def kirim_penemuan(self, scan_id: str, penemuan: dict[str, Any]) -> dict[str, Any]:
        """Kirim hasil fase penemuan (mode eksploratif). Backend menyimpan ke
        scan_targets lalu menyemai task pengujian (fase 2)."""
        resp = self._klien.post(
            f"{self._base}/internal/scans/{scan_id}/discovery",
            json=penemuan,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def unggah_gambar(self, scan_id: str, gambar_png: bytes) -> Optional[str]:
        """Unggah bukti gambar (PNG) untuk sebuah scan; return URL capability atau None bila gagal.
        Best-effort: kegagalan tak boleh menjatuhkan check (bukti teks tetap ada)."""
        import base64

        try:
            resp = self._klien.post(
                f"{self._base}/internal/scans/{scan_id}/evidence",
                json={"gambar": base64.b64encode(gambar_png).decode("ascii")},
                timeout=20.0,
            )
            resp.raise_for_status()
            return (resp.json().get("data") or {}).get("url")
        except (httpx.HTTPError, ValueError):
            return None

    def kirim_log(self, task_id: str, level: str, pesan: str, data: Optional[dict[str, Any]] = None) -> None:
        # Log bersifat best-effort: kegagalan mengirim log tidak boleh menjatuhkan task.
        body: dict[str, Any] = {"level": level, "pesan": pesan[:500]}
        if data is not None:
            body["data"] = data
        try:
            self._klien.post(
                f"{self._base}/internal/tasks/{task_id}/log",
                json=body,
            ).raise_for_status()
        except httpx.HTTPError:
            pass
