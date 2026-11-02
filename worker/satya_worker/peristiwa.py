"""Peristiwa penemuan terstruktur untuk visualisasi UI.

Menumpang pada callback log yang sudah ada: `log(level, pesan, data)`. Baris `pesan`
tetap tampil di terminal; `data` (JSON) dibaca frontend untuk adegan per tahap & graf
temuan. Callback lama `log(level, pesan)` tetap didukung (data dibuang).

Kontrak `data` (v=1): {"v": 1, "jenis": "tahap"|"situs"|"docs"|"halaman"|"titik"|"sesi"|
"endpoint"|"alur"|"kandidat"|"zap"|"katana", ...}. Lihat frontend `lib/penemuan/graf.ts`.

Field berlapis (opsional, log lama tetap terbaca): endpoint `lapisan` (frontend|api);
`halaman.items[].sumber` (html|browser); `katana`/`zap` membawa `ringkas` {frontend,api,aset}
dan `items` [{url, metode_http, lapisan, status?}]; `zap.alert_url` [{url, nama, risk}].
Tahap tambahan: "intersep" (aksi form tanpa kirim) dan "bundle" (analisis bundle JS).
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit

Logger = Optional[Any]

# Batas ukuran agar satu peristiwa tetap kecil (backend menolak data > 64 KB).
BATCH_ENDPOINT = 20
MAKS_FIELD = 40


def pancar(log: Logger, pesan: str, data: dict[str, Any], level: str = "info") -> None:
    """Kirim satu baris log + data terstruktur. Best-effort: tak pernah melempar."""
    if not log:
        return
    payload = {"v": 1, **data}
    try:
        log(level, pesan, payload)
    except TypeError:
        try:
            log(level, pesan)  # callback lama tanpa parameter data
        except Exception:
            pass
    except Exception:
        pass


def tahap(log: Logger, kode: str, pesan: str, **extra: Any) -> None:
    # Batas tahap = titik aman untuk berhenti bila scan dibatalkan; tahap juga dilaporkan di heartbeat.
    from . import koordinasi

    koordinasi.periksa_batal()
    koordinasi.set_tahap(f"penemuan · {kode}")
    pancar(log, pesan, {"jenis": "tahap", "tahap": kode, **extra})


def origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


def tanpa_query(url: str) -> str:
    """Buang query string/fragmen: nilai query bisa memuat token."""
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}{p.path}" if p.scheme and p.netloc else url.split("?", 1)[0]


def id_endpoint(ep: dict[str, Any]) -> str:
    """Id stabil endpoint — format sama dengan `flow_map` langkah.endpoint & `kandidat` per_endpoint.endpoint
    ("METODE /path/template"), sehingga alur & kandidat bisa ditautkan ke node graf."""
    return f"{ep.get('metode_http', 'GET')} {ep.get('path_template', '')}"


def _field(f: dict[str, Any]) -> dict[str, Any]:
    # Nilai `contoh` SENGAJA dibuang: body request terpantau (mis. login) bisa memuat sandi.
    out: dict[str, Any] = {"nama": str(f.get("nama", ""))[:80], "lokasi": f.get("lokasi", "")}
    if f.get("tipe"):
        out["tipe"] = str(f["tipe"])[:40]
    if f.get("wajib"):
        out["wajib"] = True
    return out


def ringkas_endpoint(ep: dict[str, Any]) -> dict[str, Any]:
    """Endpoint inventaris → bentuk aman & ringkas untuk UI (tanpa nilai contoh)."""
    resp: list[str] = []
    for r in (ep.get("response_fields") or [])[:MAKS_FIELD]:
        nama = r.get("nama") if isinstance(r, dict) else r
        if nama:
            resp.append(str(nama)[:80])
    return {
        "id": id_endpoint(ep),
        "metode_http": ep.get("metode_http", "GET"),
        "path_template": ep.get("path_template", ""),
        "url": tanpa_query(ep.get("url", "")),
        "origin": origin(ep.get("url", "")),
        "sumber": list(ep.get("sumber") or []),
        "butuh_autentikasi": bool(ep.get("butuh_autentikasi")),
        "request_fields": [_field(f) for f in (ep.get("request_fields") or [])[:MAKS_FIELD]],
        "response_fields": resp,
        "content_type": ep.get("content_type") or None,
        "status_terlihat": list(ep.get("status_terlihat") or []),
        "titik_uji": ep.get("titik_uji"),
        "lapisan": ep.get("lapisan") or "api",
    }


def pancar_endpoint(log: Logger, endpoints: list[dict[str, Any]]) -> None:
    """Kirim inventaris endpoint per batch kecil."""
    for i in range(0, len(endpoints), BATCH_ENDPOINT):
        batch = [ringkas_endpoint(e) for e in endpoints[i : i + BATCH_ENDPOINT]]
        pancar(log, f"  ↳ peta endpoint {i + 1}–{i + len(batch)} dari {len(endpoints)}", {"jenis": "endpoint", "items": batch})
