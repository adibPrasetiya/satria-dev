"""Menjalankan satu metode uji: cari check berdasarkan (check_id, engine) lalu eksekusi.

Check yang tidak dikenal (katalog menambah metode sebelum worker mendukungnya, atau engine
yang belum diimplementasikan) menghasilkan `tidak_dapat_diverifikasi` — bukan crash.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import peristiwa_uji as pu
from .models import HasilMetode, MetodeSpec, ScanContext
from .registry import cari_check

# pastikan plugin terdaftar
from . import checks  # noqa: F401,E402

Logger = Optional[Callable[[str, str], None]]


def jalankan_metode(ctx: ScanContext, metode: MetodeSpec, log: Logger = None) -> HasilMetode:
    """Jalankan satu metode. `log(level, pesan[, data])` (opsional) menyalurkan narasi proses
    check ke UI; dipasang ke `ctx._log` agar check bisa memanggil `ctx.catat(...)`/`ctx.langkah(...)`.
    Runner memancarkan peristiwa uji `mulai` & `hasil` (animasi graf pengujian)."""
    from . import koordinasi

    koordinasi.set_tahap(metode.id)
    pu.mulai(log, metode)
    plugin = cari_check(metode.check_id, metode.engine)
    if plugin is None:
        h = HasilMetode(
            metode_id=metode.id,
            status="tidak_dapat_diverifikasi",
            ringkasan=f'Check "{metode.check_id}" (engine {metode.engine}) belum didukung worker ini.',
        )
        pu.hasil(log, metode, h)
        return h
    ctx._log = log  # kanal narasi langkah (None → ctx.catat no-op)
    ctx._metode_aktif = metode.id
    try:
        h = plugin.run(ctx, metode)
    finally:
        ctx._log = None
        ctx._metode_aktif = ""
    pu.hasil(log, metode, h)
    return h
