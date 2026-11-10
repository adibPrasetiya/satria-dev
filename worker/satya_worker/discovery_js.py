"""Analisis statis bundle JavaScript — menemukan endpoint backend yang tak tampak di HTML.

SPA modern memanggil API dari dalam bundle (`fetch`, `axios`, `$http`, `XMLHttpRequest`);
endpoint non-GET (simpan/hapus/unggah) jarang terpicu saat crawl GET. Modul ini mengunduh
berkas JS same-origin (dibatasi jumlah & ukuran), lalu mengekstrak panggilan API beserta
metodenya dengan regex, termasuk base URL backend (`baseURL`, `API_URL`, `VITE_API_*`, …)
yang bisa berada di domain berbeda.

Non-intrusif: hanya GET berkas statis. Best-effort: kegagalan apa pun → hasil kosong.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import httpx

from .http_client import USER_AGENT

MAKS_BERKAS = 25
MAKS_BYTE = 3 * 1024 * 1024
MAKS_ENDPOINT = 300

_METODE = ("get", "post", "put", "patch", "delete")
_Q = r"""(['"`])"""  # kutip pembuka (grup), ditutup dengan backreference

# axios.post("/x") · this.$http.put('/x') · http.delete(`/x`) · instance kustom c.patch("/x").
# Pemanggil apa pun diterima; `_normalisasi_path` menyaring argumen bukan path (mis. map.get("k")).
_RX_KLIEN = re.compile(
    r"""[\w$]\s*\.\s*(get|post|put|patch|delete)\s*\(\s*""" + _Q + r"""([^'"`]{1,200})\2""",
    re.IGNORECASE,
)
# fetch("/x", { method: "POST" ... })  — metode dicari dalam 200 karakter setelah URL
_RX_FETCH = re.compile(r"""\bfetch\s*\(\s*""" + _Q + r"""([^'"`]{1,200})\1""")
_RX_METHOD_OPSI = re.compile(r"""method\s*:\s*['"`](GET|POST|PUT|PATCH|DELETE)['"`]""", re.IGNORECASE)
# xhr.open("POST", "/x")
_RX_XHR = re.compile(r"""\.open\s*\(\s*['"](GET|POST|PUT|PATCH|DELETE)['"]\s*,\s*""" + _Q + r"""([^'"`]{1,200})\2""", re.IGNORECASE)
# axios({ url: "/x", method: "post" }) / request({method:'put', url:'/x'})
_RX_OBJ = re.compile(
    r"""\{[^{}]{0,200}?\burl\s*:\s*""" + _Q + r"""([^'"`]{1,200})\1[^{}]{0,200}?\}""",
)
# Literal path API berdiri sendiri: "/api/…", "/v1/…", "/graphql"
_RX_LITERAL = re.compile(r"""['"`](/(?:api|rest|graphql|v\d+)(?:/[A-Za-z0-9_\-{}.:$/]*)?)['"`]""")
# Base URL backend
_RX_BASE = re.compile(
    r"""\b(?:baseURL|baseUrl|BASE_URL|API_URL|API_BASE(?:_URL)?|apiUrl|apiBase|VITE_API_[A-Z_]*|NEXT_PUBLIC_API[A-Z_]*|REACT_APP_API[A-Z_]*)\s*[:=]\s*['"`](https?://[^'"`\s]{3,120})['"`]"""
)
_RX_TEMPLATE_VAR = re.compile(r"\$\{[^}]*\}")
_RX_ID = re.compile(r"^(\d+|:[A-Za-z_]\w*|\{[^}]*\})$")


def _normalisasi_path(mentah: str) -> Optional[str]:
    """`${API}/users/${id}` → `/users/{id}`; tolak yang bukan path (CSS selector, teks, URL aset)."""
    s = mentah.strip()
    awalan_var = s.startswith("${")
    s = _RX_TEMPLATE_VAR.sub("{id}", s)
    if awalan_var:
        # `${API}/x` → buang variabel basis di depan.
        s = s[4:] if s.startswith("{id}") else s
    if s.startswith(("http://", "https://")):
        return s
    if not s.startswith("/") or s.startswith("//") or " " in s:
        return None
    path = s.split("?", 1)[0].split("#", 1)[0]
    if path == "/" or path.endswith((".js", ".css", ".png", ".svg", ".jpg", ".ico", ".woff", ".woff2", ".html")):
        return None
    bagian = ["{id}" if _RX_ID.match(seg) else seg for seg in path.split("/")]
    return "/".join(bagian)


def _nama_query(mentah: str) -> list[str]:
    """Nama parameter query dari URL literal di bundle (`/cari?q=${x}&sort=asc` → ['q','sort']).

    Hanya nama yang dipertahankan (nilai sering berupa variabel `${…}` tanpa makna); segmen yang
    jelas bukan identifier (template var kosong) dibuang."""
    s = mentah.strip()
    if "?" not in s:
        return []
    qs = s.split("?", 1)[1].split("#", 1)[0]
    out: list[str] = []
    for bagian in qs.split("&"):
        nama = _RX_TEMPLATE_VAR.sub("", bagian.split("=", 1)[0]).strip()
        if re.fullmatch(r"[A-Za-z_][\w.\-\[\]]{0,40}", nama) and nama not in out:
            out.append(nama)
    return out[:20]


def ekstrak(js: str) -> dict[str, Any]:
    """Ekstrak `{endpoints: [{method, path, query}], base: [url…]}` dari teks bundle.

    `query` = nama parameter query yang terlihat pada URL literal (dikumpulkan lintas kemunculan
    path yang sama) sehingga endpoint berbasis query string tetap teridentifikasi & dapat diuji."""
    temuan: dict[tuple[str, str], str] = {}
    query: dict[tuple[str, str], list[str]] = {}

    def tambah(method: str, mentah: str) -> None:
        path = _normalisasi_path(mentah)
        if path:
            kunci = (method.upper(), path)
            temuan.setdefault(kunci, method.upper())
            qs = query.setdefault(kunci, [])
            for nama in _nama_query(mentah):
                if nama not in qs:
                    qs.append(nama)

    for m in _RX_KLIEN.finditer(js):
        tambah(m.group(1), m.group(3))
    for m in _RX_XHR.finditer(js):
        tambah(m.group(1), m.group(3))
    for m in _RX_FETCH.finditer(js):
        ekor = js[m.end(): m.end() + 200]
        mm = _RX_METHOD_OPSI.search(ekor)
        tambah(mm.group(1) if mm else "GET", m.group(2))
    for m in _RX_OBJ.finditer(js):
        mm = _RX_METHOD_OPSI.search(m.group(0))
        tambah(mm.group(1) if mm else "GET", m.group(2))
    # Literal path API tanpa metode: GET kecuali path yang sama sudah tercatat dgn metode lain.
    dengan_metode = {p for (_m, p) in temuan}
    for m in _RX_LITERAL.finditer(js):
        path = _normalisasi_path(m.group(1))
        if path and path not in dengan_metode:
            kunci = ("GET", path)
            temuan.setdefault(kunci, "GET")
            qs = query.setdefault(kunci, [])
            for nama in _nama_query(m.group(1)):
                if nama not in qs:
                    qs.append(nama)

    base = list(dict.fromkeys(m.group(1).rstrip("/") for m in _RX_BASE.finditer(js)))
    eps = [{"method": k[0], "path": k[1], "query": query.get(k, [])} for k in sorted(temuan, key=lambda k: (k[1], k[0]))]
    return {"endpoints": eps[:MAKS_ENDPOINT], "base": base[:5]}


def rangkai_url(base_url: str, basis: list[str], path: str) -> str:
    """URL absolut endpoint. Base backend terdeteksi dipakai bila ada; path yang sudah memuat
    path basis (mis. base `…/api/v1` & path `/api/v1/x`) tidak digandakan."""
    if path.startswith(("http://", "https://")):
        return path
    if not basis:
        return urljoin(base_url, path)
    b = urlsplit(basis[0])
    origin, pre = f"{b.scheme}://{b.netloc}", b.path.rstrip("/")
    if pre and not path.startswith(pre + "/"):
        return origin + pre + path
    return origin + path


def analisis(
    base_url: str,
    skrip: Iterable[str],
    *,
    timeout: float = 8.0,
    maks_berkas: int = MAKS_BERKAS,
) -> dict[str, Any]:
    """Unduh berkas JS same-origin lalu ekstrak endpoint.

    Return `{berkas: [url…], endpoints: [{method, url, path, berkas}], base: [url…]}`. `url`
    endpoint dirangkai dari base backend yang terdeteksi (bila ada) atau origin target.
    """
    host = (urlsplit(base_url).hostname or "").lower()
    daftar = [u for u in dict.fromkeys(skrip) if (urlsplit(u).hostname or "").lower() == host][:maks_berkas]
    hasil: dict[tuple[str, str], dict[str, Any]] = {}
    basis: list[str] = []
    dibaca: list[str] = []
    if not daftar:
        return {"berkas": [], "endpoints": [], "base": []}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}, verify=True) as klien:
        for u in daftar:
            try:
                with klien.stream("GET", u) as r:
                    if r.status_code != 200:
                        continue
                    isi = b""
                    for potong in r.iter_bytes():
                        isi += potong
                        if len(isi) > MAKS_BYTE:
                            break
            except httpx.HTTPError:
                continue
            dibaca.append(u)
            ex = ekstrak(isi.decode("utf-8", "replace"))
            basis.extend(b for b in ex["base"] if b not in basis)
            nama = urlsplit(u).path.rsplit("/", 1)[-1] or u
            for ep in ex["endpoints"]:
                k = (ep["method"], ep["path"])
                lama = hasil.setdefault(k, {**ep, "berkas": nama})
                for nm in ep.get("query") or []:  # gabung query lintas berkas untuk path yang sama
                    if nm not in lama.setdefault("query", []):
                        lama["query"].append(nm)

    out: list[dict[str, Any]] = []
    for ep in hasil.values():
        out.append({"method": ep["method"], "url": rangkai_url(base_url, basis, ep["path"]), "path": ep["path"],
                    "query": ep.get("query") or [], "berkas": ep["berkas"]})
    return {"berkas": dibaca, "endpoints": out[:MAKS_ENDPOINT], "base": basis}
