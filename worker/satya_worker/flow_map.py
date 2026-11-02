"""Pemetaan alur proses bisnis dari inventaris endpoint.

Menyusun kandidat alur (urutan langkah lintas endpoint) secara deterministik:
  - alur autentikasi (login → akses sumber daya terproteksi);
  - alur CRUD per sumber daya (buat → daftar → detail → ubah → hapus);
  - alur terpantau dari urutan navigasi/XHR di browser (bila tersedia).

Opsional diperkaya AI (penamaan & narasi) di `discovery.temukan`. Tetap berguna
tanpa AI: hasil ini sudah berbasis struktur endpoint nyata.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# Prefiks API yang tidak membawa makna sumber daya.
_PREFIKS = {"api", "v1", "v2", "v3", "rest", "public", "internal"}

# Urutan & label langkah CRUD.
_CRUD = [
    ("POST", "koleksi", "Buat", "create"),
    ("GET", "koleksi", "Daftar", "list"),
    ("GET", "item", "Detail", "read"),
    ("PUT", "item", "Ubah (penuh)", "update"),
    ("PATCH", "item", "Ubah (sebagian)", "update"),
    ("DELETE", "item", "Hapus", "delete"),
]


def _nama_sumberdaya(path_template: str) -> str:
    """Nama sumber daya dari path_template (buang prefiks api/versi & segmen {id})."""
    seg = [s for s in path_template.split("/") if s and s != "{id}" and s.lower() not in _PREFIKS]
    return seg[-1] if seg else "root"


def _is_item(path_template: str) -> bool:
    """True bila path menunjuk satu item (berakhiran {id})."""
    seg = [s for s in path_template.split("/") if s]
    return bool(seg) and seg[-1] == "{id}"


def _resource_key(path_template: str) -> str:
    """Kunci pengelompokan: path tanpa segmen {id} di akhir."""
    seg = [s for s in path_template.split("/") if s]
    if seg and seg[-1] == "{id}":
        seg = seg[:-1]
    return "/" + "/".join(seg)


def _langkah(urutan: int, ep: dict[str, Any], deskripsi: str, prasyarat: str = "") -> dict[str, Any]:
    return {
        "urutan": urutan,
        "endpoint": f"{ep['metode_http']} {ep['path_template']}",
        "deskripsi": deskripsi,
        "prasyarat": prasyarat,
    }


def _ada_auth(endpoints: list[dict[str, Any]], test_points: Optional[dict[str, Any]]) -> bool:
    if test_points and "login" in test_points:
        return True
    return any(e.get("butuh_autentikasi") or e.get("titik_uji") == "login" for e in endpoints)


def bangun_flows(
    endpoints: list[dict[str, Any]],
    *,
    urutan_terpantau: Optional[list[dict[str, str]]] = None,
    test_points: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Kembalikan daftar alur proses bisnis kandidat dari inventaris endpoint."""
    flows: list[dict[str, Any]] = []
    punya_auth = _ada_auth(endpoints, test_points)

    # (1) Alur autentikasi.
    login_eps = [e for e in endpoints if e.get("titik_uji") == "login"]
    if login_eps:
        lf = login_eps[0]
        langkah = [_langkah(1, lf, "Autentikasi pengguna (login)")]
        reg = [e for e in endpoints if e.get("titik_uji") == "registrasi"]
        if reg:
            langkah = [_langkah(1, reg[0], "Registrasi akun")] + [_langkah(2, lf, "Login")]
        flows.append({"nama": "Autentikasi", "sumber": "heuristik", "langkah": langkah})

    # (2) Alur CRUD per sumber daya.
    grup: dict[str, list[dict[str, Any]]] = {}
    for e in endpoints:
        grup.setdefault(_resource_key(e["path_template"]), []).append(e)

    for key, eps in sorted(grup.items()):
        if len(eps) < 2:
            continue  # butuh ≥2 operasi agar bermakna sebagai alur
        nama = _nama_sumberdaya(eps[0]["path_template"])
        langkah: list[dict[str, Any]] = []
        urut = 1
        for metode, lingkup, label, _aksi in _CRUD:
            for e in eps:
                cocok_lingkup = _is_item(e["path_template"]) if lingkup == "item" else not _is_item(e["path_template"])
                if e["metode_http"] == metode and cocok_lingkup:
                    prasyarat = "sesi login" if (punya_auth and e.get("butuh_autentikasi")) else ""
                    langkah.append(_langkah(urut, e, f"{label} {nama}", prasyarat))
                    urut += 1
                    break
        if len(langkah) >= 2:
            flows.append({"nama": f"Kelola {nama}", "sumber": "heuristik", "langkah": langkah})

    # (3) Alur terpantau dari urutan navigasi/XHR browser.
    if urutan_terpantau:
        terlihat: set[str] = set()
        langkah = []
        urut = 1
        from .endpoint_map import path_template as _pt

        for obs in urutan_terpantau:
            metode = (obs.get("method") or "GET").upper()
            url = obs.get("url") or ""
            if not url:
                continue
            tanda = f"{metode} {_pt(url)}"
            if tanda in terlihat:
                continue
            terlihat.add(tanda)
            langkah.append({
                "urutan": urut,
                "endpoint": tanda,
                "deskripsi": "Teramati dari navigasi browser",
                "prasyarat": "",
            })
            urut += 1
            if urut > 30:
                break
        if len(langkah) >= 3:
            flows.append({"nama": "Alur teramati (browser)", "sumber": "terpantau", "langkah": langkah})

    return flows
