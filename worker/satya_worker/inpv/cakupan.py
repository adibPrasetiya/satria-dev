"""Cakupan INPV: setiap endpoint inventaris masuk tepat satu baris matriks cakupan.

  diuji        punya field body/query, atau segmen path `{id}`
  tanpa_input  endpoint API tanpa parameter → satu probe parameter tak dikenal (refleksi/crash);
               halaman frontend tanpa parameter dicatat tanpa request (bukan permukaan input)
  dilewati     dengan alasan: endpoint kritis (sandi/reset/logout…), unggah berkas (fungsi FILE),
               mutasi tanpa ID (akan mengubah data akun uji), atau di luar ruang lingkup host

Mutasi aman: PUT/PATCH/DELETE ber-`{id}` diuji dengan ID FIKTIF sehingga resource nyata tak tersentuh.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Tak pernah difuzz otomatis: mengubah kredensial/sesi atau status akun (risiko lockout / akun rusak).
KRITIS = re.compile(
    r"(password|passwd|sandi|reset|logout|signout|sign-out|revoke|deactivate|nonaktif|suspend|"
    r"/ban\b|2fa|mfa|otp|totp|verify-email|verifikasi)",
    re.IGNORECASE,
)
_RX_ID = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,})$", re.IGNORECASE)
_MUTASI = {"PUT", "PATCH", "DELETE"}
ID_FIKTIF_ANGKA = "987654321"


@dataclass
class Rencana:
    """Satu baris matriks cakupan."""

    endpoint: dict[str, Any]
    status: str                      # diuji | tanpa_input | dilewati
    alasan: str = ""
    url: str = ""                    # URL yang dipakai (ID fiktif untuk mutasi)
    fields: list[dict[str, Any]] = field(default_factory=list)   # field body/query yang diuji
    path_id: bool = False            # segmen {id} ikut difuzz (GET)

    @property
    def label(self) -> str:
        return f"{self.endpoint.get('metode_http', 'GET')} {self.endpoint.get('path_template', '')}"


def host_dalam_lingkup(host: str, base_host: str, host_izin: set[str]) -> bool:
    """Host target, host titik uji terkonfigurasi, atau subdomain domain target (mis. api.x.go.id)."""
    host = (host or "").lower()
    dasar = (base_host or "").lower().removeprefix("www.")
    return bool(host) and (host in host_izin or host == dasar or host.endswith("." + dasar))


def id_fiktif(url: str, path_template: str) -> str:
    """Ganti segmen ID nyata pada URL dengan ID fiktif sejenis (angka/uuid) — resource tak ada."""
    s = urlsplit(url)
    bagian = s.path.split("/")
    tmpl = path_template.split("/")
    for i, seg in enumerate(bagian):
        if (i < len(tmpl) and tmpl[i] == "{id}") or _RX_ID.match(seg or "-"):
            bagian[i] = str(uuid.uuid4()) if "-" in seg else ID_FIKTIF_ANGKA
    return urlunsplit((s.scheme, s.netloc, "/".join(bagian), s.query, ""))


def rencanakan(endpoints: list[dict[str, Any]], base_host: str, host_izin: set[str],
               *, izin_tulis: bool = False) -> list[Rencana]:
    """Rencana cakupan. `izin_tulis` (dari `ctx.intrusif.izinkan_penguncian`): bila False, endpoint
    POST (create — menyimpan data persisten) TIDAK difuzz; mutasi PUT/PATCH/DELETE tetap diuji karena
    diarahkan ke ID FIKTIF (non-destruktif). GET query/path-fuzz selalu aman."""
    out: list[Rencana] = []
    for ep in endpoints:
        metode = str(ep.get("metode_http") or "GET").upper()
        path = str(ep.get("path_template") or "")
        url = str(ep.get("url") or "")
        lapisan = ep.get("lapisan") or "api"
        fields = [f for f in ep.get("request_fields") or [] if f.get("nama") and f.get("lokasi") in ("body", "query")]
        ada_id = "{id}" in path

        def lewati(alasan: str) -> None:
            out.append(Rencana(ep, "dilewati", alasan, url))

        if lapisan == "aset":
            continue  # bukan permukaan uji (tak masuk inventaris normalnya)
        if not host_dalam_lingkup(urlsplit(url).hostname or "", base_host, host_izin):
            lewati("di luar ruang lingkup host target")
            continue
        if KRITIS.search(path) or (ep.get("titik_uji") or "") in ("reset_password", "ubah_password", "logout"):
            lewati("endpoint kritis (sandi/reset/sesi) — diuji fungsi AUTH, tidak difuzz")
            continue
        if (ep.get("titik_uji") or "") in ("unggah_file", "unduh_file") or "multipart" in str(ep.get("content_type") or ""):
            lewati("operasi berkas — diuji fungsi FILE")
            continue
        if metode == "POST" and not izin_tulis:
            # POST membuat data persisten di aplikasi → hanya difuzz saat izin intrusif diberikan.
            lewati("uji menulis (POST) butuh izin intrusif — tidak difuzz tanpa persetujuan")
            continue
        if metode in _MUTASI and not ada_id:
            lewati(f"{metode} tanpa ID — akan mengubah data akun uji")
            continue
        if metode not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            lewati(f"metode {metode} tidak difuzz")
            continue
        url_uji = id_fiktif(url, path) if metode in _MUTASI else url
        if metode == "DELETE":
            fields = []  # DELETE: cukup ID tak valid (tanpa body)
        if fields or ada_id:
            # Segmen {id} difuzz pada GET/DELETE, atau bila tak ada field body/query lain untuk diuji.
            path_id = ada_id and (metode in ("GET", "DELETE") or not fields)
            out.append(Rencana(ep, "diuji", "", url_uji, fields, path_id=path_id))
        elif lapisan == "frontend":
            out.append(Rencana(ep, "tanpa_input", "halaman frontend tanpa parameter (bukan permukaan input)", url))
        else:
            out.append(Rencana(ep, "tanpa_input", "tanpa parameter — probe parameter tak dikenal", url_uji))
    return out
