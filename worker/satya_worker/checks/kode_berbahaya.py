"""Fungsi 9 — Pengendalian Kode Berbahaya (MALC). Lihat katalog `controls/bssn_web.yaml`.

Hampir seluruh MALC sudah ditangani check lain (dipakai otomatis via katalog):
  deps.vulnerable_js_libraries   (9.2-T01) → engine zap (zap_scan.py)
  deps.unknown_third_party_scripts (9.2-T02) → engine playwright (playwright_scan.py)
  privacy.permission_prompts     (9.3-T02) → engine playwright
  integrity.sri                  (9.4-T01) → custom (checks/konfigurasi.py, dibagi dengan CONF-13.4)

Satu-satunya check baru di sini:
  headers.permissions_policy     (9.3-T01) header Permissions-Policy membatasi fitur sensitif

Manual → asesor: manual.code_analysis (9.1), manual.sca_report (9.2-T03), manual.update_mechanism (9.5).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien

# Fitur perangkat sensitif yang sebaiknya dinonaktifkan kecuali dibutuhkan.
_SENSITIF = ("camera", "microphone", "geolocation", "payment", "usb", "magnetometer",
             "gyroscope", "accelerometer", "midi", "serial", "bluetooth")


def _tdv(metode: MetodeSpec, ringkasan: str, detail: str = "") -> HasilMetode:
    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi",
                       ringkasan=ringkasan, detail=detail or metode.kriteria_lulus, menunggu_tinjauan=True)


@check("headers.permissions_policy")
class CekPermissionsPolicy:
    """Header Permissions-Policy (atau Feature-Policy legasi) membatasi fitur sensitif."""

    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            host = urlsplit(ctx.base_url).hostname or ""
            if not host:
                hasil = HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan="URL dasar aplikasi tidak valid.")
            else:
                hasil = self._uji(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _uji(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        try:
            with buat_klien(ctx, follow_redirects=True, timeout=8.0) as klien:
                resp = klien.kirim("GET", ctx.base_url, judul_bukti=f"{metode.id} — Permissions-Policy")
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return _tdv(metode, "URL di luar host yang diizinkan.", str(e))
        except Exception as e:
            return _tdv(metode, "Gagal menghubungi aplikasi untuk memeriksa Permissions-Policy.", f"{type(e).__name__}: {e}")

        pp = (resp.headers.get("permissions-policy") or "").strip()
        fp = (resp.headers.get("feature-policy") or "").strip()
        raw = pp or fp
        ctx.langkah("evaluasi", "Memeriksa Permissions-Policy", ada=bool(raw), nilai=raw[:200] or "-")
        if not raw:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan="Tidak ada header Permissions-Policy/Feature-Policy — fitur perangkat sensitif tidak dibatasi.",
                               detail=metode.kriteria_lulus, bukti=bukti)

        low = raw.lower()
        terbuka: list[str] = []
        for fitur in _SENSITIF:
            # Permissions-Policy: "camera=*"/"camera=(*)"; Feature-Policy: "camera *".
            m = re.search(rf"{fitur}\s*=?\s*\(?\s*([^;,)]*)", low)
            if m and "*" in m.group(1):
                terbuka.append(fitur)
        if terbuka:
            return HasilMetode(metode_id=metode.id, status="gagal",
                               ringkasan=f"Permissions-Policy membuka fitur sensitif ke semua origin: {', '.join(terbuka)}.",
                               detail=metode.kriteria_lulus, bukti=bukti)
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Permissions-Policy membatasi fitur perangkat sensitif ('{raw[:120]}').",
                           detail=metode.kriteria_lulus, bukti=bukti)
