"""Penemuan dari spesifikasi OpenAPI/Swagger.

Jauh lebih akurat daripada crawl untuk aplikasi SPA + API: satu spec mengungkap
seluruh endpoint, method, role, dan field. Modul ini:

  1. `cari_spec(base_url)`  — temukan URL spec (lewat Swagger UI / konvensi umum),
     termasuk membaca `url:` dari swagger-ui-init.js seperti Swagger UI modern.
  2. `muat_spec(url)`       — ambil & parse spec (JSON via stdlib, YAML via ruamel).
  3. `dari_openapi(spec)`   — klasifikasikan path → titik uji + template form.

Hanya GET; dalam cakupan host target. Tidak mengeksekusi operasi apa pun dari spec.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlsplit

import httpx

from .http_client import USER_AGENT, _host

# Lokasi spec/doc umum, relatif terhadap beberapa prefiks API.
_PREFIKS_API = ("", "/api", "/api/v1", "/v1", "/api/v2", "/v2")
_SUFIKS_SPEC = (
    "/openapi.json",
    "/openapi.yaml",
    "/swagger.json",
    "/swagger.yaml",
    "/api-docs",
    "/v3/api-docs",
    "/swagger/v1/swagger.json",
)
# Halaman Swagger UI (HTML) yang memuat spec lewat init.js.
_SUFIKS_DOCS = ("/docs/", "/docs", "/swagger/", "/swagger-ui/", "/api-docs/")
_INIT_JS = ("swagger-ui-init.js", "swagger-initializer.js")

# Kata kunci path → titik uji (urutan menentukan prioritas).
_ATURAN_TITIK: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("registrasi", ("register", "registrasi", "signup", "daftar")),
    ("reset_password", ("forgot", "lupa", "reset-password", "reset_password", "atur-ulang")),
    ("ubah_password", ("change-password", "/password", "ubah-password", "ganti-password")),
    ("logout", ("logout", "signout", "keluar")),
    ("login", ("login", "signin", "masuk", "auth/token", "session")),
    ("unggah_file", ("upload", "unggah")),
    ("unduh_file", ("download", "unduh", "uploads/", "files/", "attachment")),
    ("admin", ("/users", "/admin", "/pengguna")),
    ("area_terautentikasi", ("/me", "/profile", "/profil", "/dashboard", "/akun", "account")),
)

_FIELD_SANDI = ("password", "passwd", "sandi", "kata_sandi", "pass")
_FIELD_KONFIRMASI = ("confirm", "konfirmasi", "ulang", "repeat", "retype", "verify")
_FIELD_TOKEN = ("token", "kode", "code", "otp")
# Kunci skema yang disimpan per field untuk menyusun payload valid (tanpa nilai rahasia).
_KUNCI_SKEMA = ("type", "format", "enum", "minLength", "maxLength", "minimum", "maximum", "pattern", "example", "default")
_FIELD_IDENTITAS = ("email", "username", "user", "nrp", "nip", "identitas", "login")


def _cocok(teks: str, kunci: tuple[str, ...]) -> bool:
    t = teks.lower()
    return any(k in t for k in kunci)


# --------------------------------------------------------------------------- ambil spec


def _klien(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}, verify=True)


def _parse_teks(teks: str, ctype: str) -> Optional[dict[str, Any]]:
    """Parse JSON atau YAML; kembalikan dict spec bila terlihat seperti OpenAPI."""
    data: Any = None
    t = teks.lstrip()
    if "json" in ctype or t.startswith("{"):
        try:
            data = json.loads(teks)
        except ValueError:
            data = None
    if data is None:
        try:
            from ruamel.yaml import YAML  # impor malas: hanya saat perlu YAML

            data = YAML(typ="safe").load(teks)
        except Exception:
            return None
    if isinstance(data, dict) and (data.get("openapi") or data.get("swagger")) and isinstance(data.get("paths"), dict):
        return data
    return None


def muat_spec(url: str, *, timeout: float = 15.0, klien: Optional[httpx.Client] = None) -> Optional[dict[str, Any]]:
    tutup = klien is None
    klien = klien or _klien(timeout)
    try:
        resp = klien.get(url)
        if resp.status_code != 200:
            return None
        return _parse_teks(resp.text, resp.headers.get("content-type", ""))
    except httpx.HTTPError:
        return None
    finally:
        if tutup:
            klien.close()


def _url_dari_init(teks: str, init_url: str) -> Optional[str]:
    """Ambil `"url": "..."` dari swagger-ui-init.js (abaikan default petstore)."""
    for m in re.finditer(r'["\']?url["\']?\s*[:=]\s*["\']([^"\']+)["\']', teks):
        kandidat = m.group(1)
        if "petstore.swagger.io" in kandidat:
            continue
        if kandidat.endswith((".json", ".yaml", ".yml")) or "api-docs" in kandidat:
            return urljoin(init_url, kandidat)
    return None


def cari_spec(base_url: str, *, timeout: float = 12.0, klien: Optional[httpx.Client] = None) -> Optional[str]:
    """Cari URL spec OpenAPI dari base_url (konvensi + Swagger UI init.js)."""
    host = _host(base_url)
    tutup = klien is None
    klien = klien or _klien(timeout)

    def dalam_cakupan(u: str) -> bool:
        return _host(u) == host

    try:
        # 1) Lokasi spec langsung pada beberapa prefiks.
        for pre in _PREFIKS_API:
            for suf in _SUFIKS_SPEC:
                u = urljoin(base_url, pre + suf)
                if not dalam_cakupan(u):
                    continue
                if muat_spec(u, klien=klien) is not None:
                    return u
        # 2) Halaman Swagger UI → baca init.js → url spec.
        for pre in _PREFIKS_API:
            for sdoc in _SUFIKS_DOCS:
                base_docs = urljoin(base_url, pre + sdoc)
                if not dalam_cakupan(base_docs):
                    continue
                for namajs in _INIT_JS:
                    ujs = urljoin(base_docs if base_docs.endswith("/") else base_docs + "/", namajs)
                    try:
                        r = klien.get(ujs)
                    except httpx.HTTPError:
                        continue
                    if r.status_code == 200 and "javascript" in r.headers.get("content-type", ""):
                        spec_url = _url_dari_init(r.text, ujs)
                        if spec_url and dalam_cakupan(spec_url) and muat_spec(spec_url, klien=klien) is not None:
                            return spec_url
        return None
    finally:
        if tutup:
            klien.close()


# --------------------------------------------------------------------------- klasifikasi


def _base_server(spec: dict[str, Any], spec_url: str) -> str:
    """Gabungkan servers[0].url dengan origin spec_url → base absolut endpoint."""
    bagian = urlsplit(spec_url)
    origin = f"{bagian.scheme}://{bagian.netloc}"
    servers = spec.get("servers") or []
    srv = (servers[0] or {}).get("url", "") if servers else ""
    if srv.startswith("http"):
        return srv.rstrip("/")
    return (origin + srv).rstrip("/") if srv else origin


def _titik_untuk(path: str) -> str:
    for titik, kunci in _ATURAN_TITIK:
        if _cocok(path, kunci):
            return titik
    return "api"


def _resolve_ref(node: Any, spec: dict[str, Any], _lihat: Optional[set[str]] = None) -> dict[str, Any]:
    """Selesaikan $ref (dan gabung allOf) menjadi schema dengan `properties`."""
    _lihat = _lihat or set()
    if not isinstance(node, dict):
        return {}
    ref = node.get("$ref")
    if ref and ref.startswith("#/") and ref not in _lihat:
        _lihat.add(ref)
        tujuan: Any = spec
        for bagian in ref[2:].split("/"):
            tujuan = (tujuan or {}).get(bagian) if isinstance(tujuan, dict) else None
        return _resolve_ref(tujuan or {}, spec, _lihat)
    if "allOf" in node:
        props: dict[str, Any] = {}
        for sub in node["allOf"]:
            props.update(_resolve_ref(sub, spec, _lihat).get("properties", {}))
        gabung = {k: v for k, v in node.items() if k != "allOf"}
        gabung.setdefault("properties", {}).update(props)
        return gabung
    return node


def _template_form(operasi: dict[str, Any], spec: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Susun template form dari requestBody JSON schema (nama field saja), resolve $ref."""
    rb = (operasi.get("requestBody") or {}).get("content") or {}
    multipart = any("multipart/form-data" in k for k in rb)
    schema: dict[str, Any] = {}
    for ctype, isi in rb.items():
        if "json" in ctype or "form" in ctype:
            schema = _resolve_ref((isi or {}).get("schema") or {}, spec)
            break
    props = list((schema or {}).get("properties", {}).keys())
    if not props and not multipart:
        return None
    wajib = set((schema or {}).get("required") or [])
    skema_field: dict[str, dict[str, Any]] = {}
    for nama, sub in ((schema or {}).get("properties") or {}).items():
        s = _resolve_ref(sub, spec) if isinstance(sub, dict) else {}
        info = {k: s[k] for k in _KUNCI_SKEMA if k in s}
        if isinstance(info.get("enum"), list):
            info["enum"] = info["enum"][:10]
        info["required"] = nama in wajib
        skema_field[nama] = info
    sandi_semua = [p for p in props if _cocok(p, _FIELD_SANDI)]
    konfirmasi = next((p for p in sandi_semua if _cocok(p, _FIELD_KONFIRMASI)), None)
    token = next((p for p in props if _cocok(p, _FIELD_TOKEN) and not _cocok(p, _FIELD_SANDI)), None)
    field_sandi = next((p for p in sandi_semua if p != konfirmasi and not _cocok(p, ("lama", "current", "old"))), None) or next(iter(sandi_semua), None)
    field_id = next((p for p in props if _cocok(p, _FIELD_IDENTITAS)), None)
    templat: dict[str, Any] = {"tipe_body": "form" if multipart else "json"}
    if field_id:
        templat["field_username"] = field_id
        templat["field_identitas"] = field_id
    if field_sandi:
        templat["field_password"] = field_sandi
        templat["field_sandi"] = field_sandi
    if props:
        templat["field_dasar"] = {p: "" for p in props if not _cocok(p, _FIELD_SANDI)}
        templat["field_unik"] = [p for p in props if _cocok(p, ("email", "nrp", "nip", "username"))]
        templat["skema_field"] = skema_field
    if konfirmasi:
        templat["field_konfirmasi"] = konfirmasi
    if token:
        templat["field_token"] = token
    # Field sandi lama/baru untuk titik ubah_password.
    sandi_fields = [p for p in props if _cocok(p, _FIELD_SANDI)]
    lama = next((p for p in sandi_fields if _cocok(p, ("lama", "current", "old"))), None)
    baru = next((p for p in sandi_fields if _cocok(p, ("baru", "new"))), None)
    if lama:
        templat["field_lama"] = lama
    if baru or field_sandi:
        templat["field_baru"] = baru or field_sandi
    return templat


def dari_openapi(spec: dict[str, Any], spec_url: str) -> dict[str, Any]:
    """Klasifikasikan spec → payload penemuan (test_points, forms, ringkasan)."""
    base = _base_server(spec, spec_url)
    test_points: dict[str, dict[str, Any]] = {}
    forms: dict[str, dict[str, Any]] = {}
    endpoint: list[dict[str, str]] = []
    peringkat = {"tinggi": 3, "sedang": 2, "rendah": 1}

    # Titik uji yang lebih suka method non-GET bila ada (login/registrasi POST, dsb.).
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        methods = [m for m in ("post", "put", "patch", "delete", "get") if m in ops]
        if not methods:
            continue
        titik = _titik_untuk(path)
        # Endpoint penyelesaian reset (token/kode + sandi baru) dipisah dari permintaan reset (email).
        if titik == "reset_password":
            tpl_reset = _template_form(ops.get(methods[0], {}), spec) or {}
            if tpl_reset.get("field_token") and tpl_reset.get("field_sandi"):
                titik = "reset_password_konfirmasi"
        # URL absolut; parameter {id} dibiarkan agar asesor/konfigurasi melengkapi.
        url_abs = base + path
        metode_http = methods[0].upper()
        endpoint.append({"path": path, "method": metode_http, "titik": titik})

        lama = test_points.get(titik)
        if not lama or peringkat[lama["keyakinan"]] < peringkat["tinggi"]:
            test_points[titik] = {
                "tersedia": "{" not in path,  # path berparameter perlu nilai → tandai belum siap
                "url": url_abs,
                "metode_http": metode_http,
                "sumber": "otomatis",
                "keyakinan": "tinggi",
                "catatan": f"Dari OpenAPI: {metode_http} {path}",
            }
        if titik not in forms:
            templat = _template_form(ops.get(methods[0], {}), spec)
            if templat:
                forms[titik] = templat

    ringkasan = {
        "sumber": "openapi",
        "spec_url": spec_url,
        "base_api": base,
        "judul": (spec.get("info") or {}).get("title", ""),
        "versi": (spec.get("info") or {}).get("version", ""),
        "jumlah_endpoint": len(endpoint),
        "endpoint": endpoint[:100],
        "titik_ditemukan": sorted(test_points.keys()),
    }
    return {"test_points": test_points, "forms": forms, "ringkasan": ringkasan}


# --------------------------------------------------------------------------- field detail (inventaris)


def _tipe_schema(schema: dict[str, Any]) -> str:
    """Ambil tipe skala dari schema (array → 'array[<item>]')."""
    if not isinstance(schema, dict):
        return ""
    t = schema.get("type", "")
    if t == "array":
        item = schema.get("items") or {}
        it = item.get("type", "") if isinstance(item, dict) else ""
        return f"array[{it}]" if it else "array"
    return t or ""


def _ringkas_skema(schema: Any, spec: dict[str, Any]) -> dict[str, Any]:
    """Kendala validasi satu field (format/enum/panjang/pola/contoh) — dipakai menyusun payload valid."""
    s = _resolve_ref(schema, spec) if isinstance(schema, dict) else {}
    out = {k: s[k] for k in _KUNCI_SKEMA if k in s and k != "type"}
    if isinstance(out.get("enum"), list):
        out["enum"] = out["enum"][:10]
    return out


def _field_body(operasi: dict[str, Any], spec: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Field dari requestBody (nama, tipe, wajib). Kembalikan (fields, content_type)."""
    rb = (operasi.get("requestBody") or {}).get("content") or {}
    content_type = ""
    schema: dict[str, Any] = {}
    for ctype, isi in rb.items():
        if "json" in ctype or "form" in ctype:
            content_type = ctype
            schema = _resolve_ref((isi or {}).get("schema") or {}, spec)
            break
    props = (schema or {}).get("properties", {}) or {}
    wajib = set((schema or {}).get("required", []) or [])
    out = []
    for nama, sk in props.items():
        sk_r = _resolve_ref(sk, spec) if isinstance(sk, dict) else {}
        f: dict[str, Any] = {"nama": nama, "lokasi": "body", "tipe": _tipe_schema(sk_r)}
        if nama in wajib:
            f["wajib"] = True
        skema = _ringkas_skema(sk_r, spec)
        if skema:
            f["skema"] = skema
        out.append(f)
    return out, content_type


def _field_response(operasi: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """Nama field dari schema respons 2xx (JSON) bila ada."""
    resp = operasi.get("responses") or {}
    for kode, isi in resp.items():
        if not str(kode).startswith("2"):
            continue
        content = (isi or {}).get("content") or {}
        for ctype, c in content.items():
            if "json" in ctype:
                schema = _resolve_ref((c or {}).get("schema") or {}, spec)
                props = (schema or {}).get("properties", {}) or {}
                if props:
                    return list(props.keys())
    return []


def endpoint_fields(spec: dict[str, Any], spec_url: str) -> list[dict[str, Any]]:
    """Inventaris endpoint detail dari spec: setiap (path, method) dengan field request/respons.

    Tidak mengubah `dari_openapi`; dipakai `endpoint_map` untuk membangun inventaris lengkap.
    """
    base = _base_server(spec, spec_url)
    keluar: list[dict[str, Any]] = []
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        # Parameter level-path berlaku untuk semua method.
        param_path = ops.get("parameters") or []
        for metode in ("get", "post", "put", "patch", "delete", "head", "options"):
            if metode not in ops:
                continue
            op = ops[metode] or {}
            request_fields: list[dict[str, Any]] = []
            for p in list(param_path) + list(op.get("parameters") or []):
                p = _resolve_ref(p, spec) if "$ref" in (p or {}) else p
                if not isinstance(p, dict) or not p.get("name"):
                    continue
                f = {
                    "nama": p["name"],
                    "lokasi": p.get("in", "query"),
                    "tipe": _tipe_schema(p.get("schema") or {}),
                    **({"wajib": True} if p.get("required") else {}),
                }
                skema = _ringkas_skema(p.get("schema") or {}, spec)
                if p.get("example") is not None:
                    skema.setdefault("example", p["example"])
                if skema:
                    f["skema"] = skema
                request_fields.append(f)
            body_fields, content_type = _field_body(op, spec)
            request_fields += body_fields
            keluar.append({
                "method": metode.upper(),
                "url": base + path,
                "path": path,
                "titik": _titik_untuk(path),
                "request_fields": request_fields,
                "response_fields": _field_response(op, spec),
                "content_type": content_type,
            })
    return keluar
