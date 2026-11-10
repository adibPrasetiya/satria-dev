"""Render potongan HTML tertangkap menjadi gambar PNG (bukti visual) via Playwright.

Dipakai untuk bukti XSS tersimpan: HTML respons yang memuat payload tersimpan di-render di browser
headless lalu ditangkap layarnya — memperlihatkan bahwa masukan tak dipercaya benar-benar muncul pada
halaman. Non-eksekutif: JavaScript DIMATIKAN saat render (cukup tampilkan DOM; tak menjalankan skrip
dari target). Best-effort: bila Playwright/browser tak tersedia, kembalikan None (bukti teks tetap ada).
"""

from __future__ import annotations

import os
from typing import Optional

MAKS_HTML = 2_000_000


def _timeout_ms() -> int:
    try:
        return int(os.environ.get("SHOT_TIMEOUT_MS", "8000"))
    except ValueError:
        return 8000


def dari_html(html: str, *, base_url: str = "", lebar: int = 1200, tinggi: int = 900) -> Optional[bytes]:
    """Render `html` lalu kembalikan PNG (bytes) atau None bila gagal/tak tersedia.

    `base_url` dipakai sebagai alamat dasar agar aset relatif (mungkin) termuat; tetap aman karena
    JavaScript dimatikan. Ukuran HTML dibatasi."""
    if not html:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    potongan = html[:MAKS_HTML]
    pw = browser = None
    try:
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
        except Exception:
            return None
        context = browser.new_context(
            viewport={"width": lebar, "height": tinggi},
            java_script_enabled=False,          # jangan jalankan skrip dari target
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(_timeout_ms())
        try:
            # `base_url` lewat <base> agar aset relatif bisa dicoba dimuat; gagal-muat tak masalah.
            isi = potongan
            if base_url and "<base" not in potongan[:2000].lower():
                isi = potongan.replace("<head>", f'<head><base href="{base_url}">', 1) if "<head>" in potongan else \
                    f'<base href="{base_url}">' + potongan
            page.set_content(isi, wait_until="domcontentloaded", timeout=_timeout_ms())
            return page.screenshot(full_page=True, type="png")
        except Exception:
            return None
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:
            pass
