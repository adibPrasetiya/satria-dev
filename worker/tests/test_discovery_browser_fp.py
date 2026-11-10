"""Regresi false positive rute frontend (sumber BRW) pada SPA/PWA.

Kasus nyata: situs Netlify PWA — server membalas 404 untuk /admin, /beranda, dll., tetapi
service worker (navigateFallback) menyajikan index.html dari cache sehingga semua rute tebakan
tampak "terender". Juga: SPA dengan rewrite catch-all `/* → /index.html 200` yang merender
beranda untuk path apa pun.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from satya_worker import discovery_browser as DB
from satya_worker import playwright_driver as pw

pytestmark = pytest.mark.skipif(not pw.tersedia(), reason="Playwright/Chromium tak tersedia")

_INDEX = b"""<!doctype html><html><head><title>Game</title></head><body>
<div id="app">Game Beranda - Tap to start</div>
<script>
if (window.__PWA && navigator.serviceWorker) navigator.serviceWorker.register('/sw.js');
</script></body></html>"""

# SW: semua navigasi → index.html dari cache (meniru Workbox navigateFallback).
_SW = b"""
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open('c').then(c => c.add('/'))); });
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.mode === 'navigate') e.respondWith(caches.match('/'));
});
"""


def _server(mode: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # senyap
            pass

        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0]
            if mode == "pwa" and path == "/sw.js":
                body, ct, st = _SW, "application/javascript", 200
            elif path == "/" or mode == "catchall":
                body = _INDEX.replace(b"window.__PWA", b"true" if mode == "pwa" else b"false")
                ct, st = "text/html", 200
            else:
                body, ct, st = b"<html><title>Page not found</title><body>Not found</body></html>", "text/html", 404
            self.send_response(st)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://localhost:{srv.server_address[1]}/"


@pytest.mark.parametrize("mode", ["pwa", "catchall"])
def test_rute_tebakan_palsu_tidak_dilaporkan(mode, monkeypatch):
    halaman: list[str] = []
    asli = DB.pr.pancar

    def pancar(log, pesan, data, **k):
        if data.get("jenis") == "halaman":
            halaman.extend(i["url"] for i in data["items"])
        return asli(log, pesan, data, **k)

    monkeypatch.setattr(DB.pr, "pancar", pancar)
    srv, base = _server(mode)
    try:
        if mode == "pwa":
            # Pasang SW lebih dulu di konteks yang sama → tanpa pemblokiran, /admin dkk. jadi 200.
            orig_goto = DB._goto_status
            pertama = {"ya": True}

            def goto(page, url):
                hasil = orig_goto(page, url)
                if pertama.pop("ya", False):
                    orig_goto(page, base)
                    page.wait_for_timeout(1500)
                return hasil

            monkeypatch.setattr(DB, "_goto_status", goto)
        hasil = DB.jelajah_browser(base, lambda *a, **k: None, timeout=8, maks_rute=8)
    finally:
        srv.shutdown()

    assert hasil.get("tersedia") is True
    paths = {u[len(base):] for u in halaman}
    assert paths <= {""}, f"rute palsu dilaporkan: {sorted(paths)}"
