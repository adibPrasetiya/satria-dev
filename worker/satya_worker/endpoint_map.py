"""Inventaris endpoint terpadu + pemetaan field.

Discovery mengumpulkan endpoint dari banyak sumber (OpenAPI, form HTML, lalu lintas
browser XHR/fetch, katana, ZAP). Modul ini menyatukannya menjadi satu inventaris
yang dideduplikasi per `METODE + path_template`, lengkap dengan field request
(query/body/path/header) dan inferensi "butuh autentikasi".

Tidak menggantikan `test_points`/`forms` (yang menggerakkan seed fase-2); ini
tambahan di `ringkasan.endpoints_lengkap` untuk pemetaan & laporan.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import parse_qsl, urlsplit

# Segmen path yang kemungkinan adalah identifier → dinormalisasi jadi {id}.
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HEX_PANJANG = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)
_ANGKA = re.compile(r"^\d+$")


def _segmen_id(seg: str) -> bool:
    return bool(_ANGKA.match(seg) or _UUID.match(seg) or _HEX_PANJANG.match(seg))


def path_template(url: str) -> str:
    """Path dengan segmen identifier dinormalisasi jadi {id}. Query dibuang."""
    path = urlsplit(url).path or "/"
    bagian = [("{id}" if _segmen_id(s) else s) for s in path.split("/")]
    tmpl = "/".join(bagian)
    return tmpl or "/"


def _origin(url: str) -> str:
    s = urlsplit(url)
    return f"{s.scheme}://{s.netloc}" if s.scheme else ""


# --------------------------------------------------------------------------- lapisan (frontend/api/aset)

_EKS_ASET = (
    ".js", ".mjs", ".cjs", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".avif", ".bmp", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".mp3", ".pdf",
)
_CT_ASET = re.compile(r"javascript|ecmascript|text/css|^image/|^font/|^video/|^audio/|application/pdf", re.IGNORECASE)
_CT_API = re.compile(r"json|xml|graphql|event-stream|protobuf|msgpack", re.IGNORECASE)
_PATH_API = re.compile(r"/(api|rest|graphql|gql|rpc|oauth2?|v\d+)(/|$)|\.json$", re.IGNORECASE)
_SUMBER_API = {"openapi", "browser", "browser-intersep", "js"}
# Berkas build/metadata framework frontend (SvelteKit `_app/version.json`, Next `_next/…`, Nuxt
# `_nuxt/…`, manifest PWA) — bukan backend walau berupa JSON yang diambil lewat fetch.
_PATH_BUILD = re.compile(
    r"^/(_app|_next|_nuxt|__nextjs[^/]*|_astro|_expo)/|/(manifest|site|asset-manifest|build-manifest)\.(json|webmanifest)$|\.webmanifest$",
    re.IGNORECASE,
)

LAPISAN = ("frontend", "api", "aset")


def klasifikasi_lapisan(
    method: str,
    url: str,
    *,
    base_url: str = "",
    sumber: str = "",
    content_type: Optional[str] = None,
) -> str:
    """Tentukan lapisan sebuah URL temuan: 'aset' (berkas statis), 'api' (backend) atau 'frontend'
    (halaman/rute yang dirender untuk pengguna). Heuristik deterministik — lihat juga frontend
    `lapisanDari` (port aturan yang sama untuk log lama)."""
    path = (urlsplit(url).path or "/").lower()
    ct = (content_type or "").split(";", 1)[0].strip()
    if path.endswith(_EKS_ASET) or (ct and _CT_ASET.search(ct)) or _PATH_BUILD.search(path):
        return "aset"
    if sumber in _SUMBER_API:
        return "api"
    if method.upper() not in ("GET", "HEAD"):
        return "api"
    if ct and _CT_API.search(ct):
        return "api"
    if _PATH_API.search(path):
        return "api"
    if base_url and _origin(url) and _origin(url) != _origin(base_url):
        return "api"
    return "frontend"


def field(nama: str, lokasi: str, *, tipe: str = "", wajib: bool = False, contoh: Any = None) -> dict[str, Any]:
    """Bangun satu field request. lokasi ∈ query|body|path|header."""
    f: dict[str, Any] = {"nama": nama, "lokasi": lokasi}
    if tipe:
        f["tipe"] = tipe
    if wajib:
        f["wajib"] = True
    if contoh is not None:
        f["contoh"] = contoh
    return f


def field_dari_query(url: str) -> list[dict[str, Any]]:
    """Ekstrak field query string dari sebuah URL."""
    out: list[dict[str, Any]] = []
    for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        out.append(field(k, "query", contoh=v or None))
    return out


# Nilai contoh dari lalu lintas nyata TIDAK disimpan untuk field kredensial/token/identitas pribadi.
_CONTOH_SENSITIF = re.compile(
    r"pass|sandi|token|secret|auth|key|cookie|session|otp|totp|mfa|credential|kredensial|bearer|jwt|"
    r"nik|nip|nrp|ktp|kartu|card|cvv|pin|npwp|rekening|account_number",
    re.IGNORECASE,
)


def _contoh_aman(nama: str, nilai: Any) -> Any:
    """Contoh nilai yang boleh disimpan (skalar pendek, field non-sensitif) — dasar payload valid saat
    tidak ada dokumentasi API. None bila tak boleh/tak berguna."""
    if _CONTOH_SENSITIF.search(nama or ""):
        return None
    if isinstance(nilai, bool) or isinstance(nilai, (int, float)):
        return nilai
    if isinstance(nilai, str) and 0 < len(nilai) <= 200:
        return nilai
    return None


def field_dari_body(post_data: Any, content_type: str = "") -> list[dict[str, Any]]:
    """Ekstrak field dari body request terpantau (JSON object atau form-urlencoded), beserta contoh
    nilai non-sensitif (lihat `_contoh_aman`)."""
    out: list[dict[str, Any]] = []
    if post_data is None:
        return out
    teks = post_data if isinstance(post_data, str) else str(post_data)
    teks = teks.strip()
    # JSON object → kunci level atas.
    if teks.startswith("{"):
        try:
            import json

            obj = json.loads(teks)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    out.append(field(k, "body", tipe=type(v).__name__, contoh=_contoh_aman(k, v)))
                return out
        except ValueError:
            pass
    # form-urlencoded.
    if "=" in teks and ("application/x-www-form-urlencoded" in content_type or "&" in teks or "{" not in teks):
        for k, v in parse_qsl(teks, keep_blank_values=True):
            out.append(field(k, "body", contoh=_contoh_aman(k, v)))
    return out


class InventarisEndpoint:
    """Kumpulan endpoint terdeduplikasi per (METODE, path_template)."""

    def __init__(self) -> None:
        self._ep: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _kunci(method: str, url: str) -> str:
        return f"{method.upper()} {path_template(url)}"

    def tambah(
        self,
        method: str,
        url: str,
        *,
        sumber: str,
        request_fields: Optional[list[dict[str, Any]]] = None,
        response_fields: Optional[list[str]] = None,
        content_type: Optional[str] = None,
        status: Optional[int] = None,
        terautentikasi: Optional[bool] = None,
        titik_uji: Optional[str] = None,
        catatan: Optional[str] = None,
        lapisan: Optional[str] = None,
    ) -> None:
        """Gabungkan satu observasi endpoint ke inventaris (union field & sumber)."""
        if not url or not method:
            return
        kunci = self._kunci(method, url)
        ep = self._ep.get(kunci)
        if ep is None:
            ep = {
                "metode_http": method.upper(),
                "path_template": path_template(url),
                "url": url,
                "origin": _origin(url),
                "sumber": [],
                "request_fields": [],
                "response_fields": [],
                "status_terlihat": [],
                "content_type": content_type or "",
                "terlihat_anonim": False,
                "terlihat_terautentikasi": False,
                "titik_uji": titik_uji or "",
                "catatan": catatan or "",
                "lapisan": lapisan or "",
            }
            self._ep[kunci] = ep

        if sumber and sumber not in ep["sumber"]:
            ep["sumber"].append(sumber)
        if content_type and not ep["content_type"]:
            ep["content_type"] = content_type
        if titik_uji and not ep["titik_uji"]:
            ep["titik_uji"] = titik_uji
        if catatan and not ep["catatan"]:
            ep["catatan"] = catatan
        # 'api' menang atas 'frontend' (rute yang sama dipakai juga sebagai endpoint data).
        if lapisan and (not ep["lapisan"] or lapisan == "api"):
            ep["lapisan"] = lapisan
        if status is not None and status not in ep["status_terlihat"]:
            ep["status_terlihat"].append(status)
        if terautentikasi is True:
            ep["terlihat_terautentikasi"] = True
        elif terautentikasi is False:
            ep["terlihat_anonim"] = True

        # Union request_fields berdasar (nama, lokasi).
        ada = {(f["nama"], f.get("lokasi")): f for f in ep["request_fields"]}
        for f in request_fields or []:
            kf = (f.get("nama"), f.get("lokasi"))
            if not kf[0]:
                continue
            lama = ada.get(kf)
            if lama is None:
                ep["request_fields"].append(f)
                ada[kf] = f
            else:
                # Lengkapi info yang belum ada (mis. skema dari OpenAPI + contoh dari lalu lintas nyata).
                for k in ("tipe", "wajib", "skema", "contoh"):
                    if k in f and k not in lama:
                        lama[k] = f[k]
        # Union response_fields (nama saja).
        for rf in response_fields or []:
            if rf and rf not in ep["response_fields"]:
                ep["response_fields"].append(rf)

    def sebagai_list(self) -> list[dict[str, Any]]:
        """Daftar endpoint final, diurutkan path lalu metode; derive `butuh_autentikasi`."""
        keluar: list[dict[str, Any]] = []
        for ep in self._ep.values():
            butuh = ep["terlihat_terautentikasi"] and not ep["terlihat_anonim"]
            keluar.append({
                "metode_http": ep["metode_http"],
                "path_template": ep["path_template"],
                "url": ep["url"],
                "sumber": ep["sumber"],
                "butuh_autentikasi": butuh,
                "request_fields": ep["request_fields"],
                "response_fields": ep["response_fields"],
                "content_type": ep["content_type"],
                "status_terlihat": sorted(ep["status_terlihat"]),
                "titik_uji": ep["titik_uji"],
                "catatan": ep["catatan"],
                "lapisan": ep["lapisan"] or "api",
            })
        keluar.sort(key=lambda e: (e["path_template"], e["metode_http"]))
        return keluar

    def __len__(self) -> int:
        return len(self._ep)
