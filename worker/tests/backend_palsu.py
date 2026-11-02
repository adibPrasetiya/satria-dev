"""Backend /internal palsu untuk menguji loop worker tanpa MySQL.

Menyajikan:
  POST /api/v1/internal/tasks/claim        -> satu task (sekali), lalu 204
  POST /api/v1/internal/tasks/{id}/result  -> simpan hasil (bisa dibaca test)
  POST /api/v1/internal/tasks/{id}/log     -> simpan log

Task menunjuk ke `base_url` target yang diberikan (mis. TargetPalsu).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "token-uji-rahasia-panjang"


def buat_handler(target_base_url: str, hasil_terkumpul: list, tdiproses: dict):
    task = {
        "task_id": "101",
        "scan_id": "9",
        "metode": {
            "id": "AUTH-1.3-T02",
            "check_id": "auth.password_policy.complexity",
            "titik_uji": "registrasi",
            "nama": "Kombinasi jenis karakter saat registrasi",
            "kriteria_lulus": "Kata sandi tanpa kombinasi yang disyaratkan ditolak.",
            "parameter": {"panjang_minimum": 8, "wajib": ["huruf_besar", "huruf_kecil", "angka", "simbol"]},
        },
        "context": {
            "scan_id": "9",
            "aplikasi_id": "1",
            "base_url": target_base_url,
            "titik_uji": {"registrasi": {"tersedia": True, "url": f"{target_base_url}/auth/register", "metode_http": "POST"}},
            "form": {
                "registrasi": {
                    "field_dasar": {"nama": "Uji", "email": "u@contoh.go.id", "nrp": "1", "satuan_id": 1},
                    "field_sandi": "password",
                    "field_unik": ["email", "nrp"],
                    "tipe_body": "json",
                    "status_sukses": [200, 201, 202],
                }
            },
            "akun_uji": [],
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.headers.get("X-Worker-Token") != TOKEN:
                self._json(401, {"success": False, "message": "token salah"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            path = self.path

            if path.endswith("/internal/tasks/claim"):
                if tdiproses["claimed"]:
                    self.send_response(204)
                    self.end_headers()
                    return
                tdiproses["claimed"] = True
                self._json(200, {"success": True, "message": "ok", "data": task})
                return
            if path.endswith("/result"):
                hasil_terkumpul.append(body.get("hasil"))
                self._json(200, {"success": True, "message": "ok", "data": None})
                return
            if path.endswith("/log"):
                self._json(200, {"success": True, "message": "ok", "data": None})
                return
            self._json(404, {"success": False, "message": "tak ada"})

    return Handler


class BackendPalsu:
    def __init__(self, target_base_url: str) -> None:
        self.hasil: list = []
        self._diproses = {"claimed": False}
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), buat_handler(target_base_url, self.hasil, self._diproses))
        self.port = self._srv.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}/api/v1"

    def __enter__(self) -> "BackendPalsu":
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._srv.shutdown()
        self._srv.server_close()
