"""Orkestrasi adaptif INPV: jadikan baseline BENAR-BENAR valid sebelum menilai validasi per field.

Masalah yang diatasi: respons 400/422 dulu dianggap "input ditolak sesuai harapan", padahal bisa
karena field LAIN salah/kurang — sehingga uji validasi field tertentu salah atribusi. Modul ini
memakai respons server sebagai umpan balik (adaptif): bila payload dasar valid pun ditolak, ia
memperbaikinya — deterministik dulu (field yang disebut galat diisi ulang; field wajib yang hilang
ditambah), lalu AI sebagai pemandu (dibatasi anggaran panggilan per scan) — dan mengulang hingga
DITERIMA atau anggaran habis. Hasilnya: baseline yang terbukti diterima → penolakan varian satu-field
bisa diatribusikan; bila tak pernah diterima → ditandai `payload_belum_valid` (tinjauan), bukan lulus palsu.

AI hanya menerima METADATA tersamar (nama/tipe/bentuk field, pesan galat tersamar) — tak pernah nilai
sensitif. Keputusan vonis tetap deterministik (lihat `vonis.py`).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .. import atribusi_sandi as asd
from . import profil_field as pf

STATUS_VALIDASI = (400, 422)
_SENSITIF = re.compile(r"pass|sandi|token|secret|otp|pin|cvv|kartu", re.I)

# Callable uji: (query_dict, body_dict|None, judul) -> resp|None
Uji = Callable[[dict[str, Any], Optional[dict[str, Any]], str], Any]


@dataclass
class AnggaranAI:
    """Anggaran panggilan AI untuk SATU scan (dibagi seluruh sapuan). Mencegah biaya meledak saat
    mode orkestrator adaptif pada aplikasi dengan banyak endpoint."""

    sisa: int

    @classmethod
    def dari_env(cls) -> "AnggaranAI":
        try:
            n = int(os.environ.get("INPV_AI_MAKS_PANGGILAN", "20"))
        except ValueError:
            n = 20
        return cls(max(0, n))

    def boleh(self) -> bool:
        return self.sisa > 0

    def pakai(self) -> None:
        if self.sisa > 0:
            self.sisa -= 1


@dataclass
class HasilBaseline:
    resp: Any                                   # respons baseline final (mungkin None bila gagal koneksi)
    query: dict[str, Any] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None
    percobaan: int = 1
    diperbaiki: list[str] = field(default_factory=list)  # field yang diperbaiki (deterministik/AI)
    diterima: bool = False
    panggilan_ai: int = 0
    catatan: str = ""


def _maks_percobaan() -> int:
    try:
        return max(1, int(os.environ.get("INPV_BASELINE_MAKS_PERCOBAAN", "3")))
    except ValueError:
        return 3


def _status(resp: Any) -> Optional[int]:
    return getattr(resp, "status_code", None) if resp is not None else None


def _sukses(sc: Optional[int]) -> bool:
    return sc is not None and 200 <= sc < 300


def _field_wajib_hilang(ep: dict[str, Any], ada: dict[str, Any], lokasi: str) -> list[dict[str, Any]]:
    """Field `lokasi` yang wajib menurut inventaris tetapi belum ada di payload."""
    out = []
    for f in ep.get("request_fields") or []:
        nama = f.get("nama")
        if (f.get("lokasi") == lokasi and nama and nama not in ada
                and (f.get("wajib") or (f.get("skema") or {}).get("required"))
                and not _SENSITIF.search(str(nama))):
            out.append(f)
    return out


_RX_UNIK = re.compile("|".join(asd._UNIK), re.I)


def _perbaiki_deterministik(ep: dict[str, Any], body: dict[str, Any], query: dict[str, Any],
                            disebut: set[str], duplikasi: bool) -> list[str]:
    """Isi ulang field yang disebut galat dengan nilai valid baru; tambah field wajib yang hilang.
    Mengubah `body`/`query` di tempat. Return daftar nama field yang disentuh.

    Untuk field yang ADA tapi disebut galat, regenerasi deterministik hanya berguna bila field itu
    UNIK (email/username/NIP…) atau galat menandakan duplikasi — field generik (nilai domain spesifik
    seperti kategori/kode) diserahkan ke AI, bukan diacak ulang tanpa arah."""
    disentuh: list[str] = []
    peta_field = {f.get("nama"): f for f in ep.get("request_fields") or []}
    # 1) Field wajib yang hilang (penyebab umum 400 "field harus diisi").
    for lok, tujuan in (("body", body), ("query", query)):
        if tujuan is None:
            continue
        for f in _field_wajib_hilang(ep, tujuan, lok):
            tujuan[f["nama"]] = asd.nilai_field_endpoint(f)
            disentuh.append(f["nama"])
    # 2) Field unik/duplikat yang disebut galat & ADA di payload → nilai baru (hindari "sudah terpakai").
    for nama in disebut:
        if _SENSITIF.search(str(nama)) or not (duplikasi or _RX_UNIK.search(str(nama))):
            continue
        for tujuan in (body, query):
            if tujuan is not None and nama in tujuan:
                f = peta_field.get(nama) or {"nama": nama}
                tujuan[nama] = asd.nilai_field_endpoint(f)
                if nama not in disentuh:
                    disentuh.append(nama)
    return disentuh


def _meta_ai(ep: dict[str, Any], metode: str, body: dict[str, Any], query: dict[str, Any],
             disebut: set[str], resp: Any) -> dict[str, Any]:
    peta_field = {f.get("nama"): f for f in ep.get("request_fields") or []}
    ada = {**(body or {}), **(query or {})}
    bermasalah = sorted(disebut | {f["nama"] for lok in ("body", "query")
                                   for f in _field_wajib_hilang(ep, body if lok == "body" else query, lok)})
    fb = []
    for nama in bermasalah:
        if _SENSITIF.search(str(nama)):
            continue
        f = peta_field.get(nama, {})
        sk = f.get("skema") or {}
        fb.append({k: v for k, v in {
            "nama": nama, "tipe": str(f.get("tipe") or sk.get("type") or ""),
            "format": sk.get("format") or "", "bentuk": pf.bentuk_contoh(f.get("contoh")),
        }.items() if v})
    teks = (getattr(resp, "text", "") or "")[:600]
    for k, v in ada.items():  # samarkan nilai payload yang muncul di pesan galat
        if isinstance(v, str) and len(v) >= 3:
            teks = teks.replace(v, f"[{k}]")
    return {"m": metode, "path": ep.get("path_template", ""), "field_bermasalah": fb,
            "field_ada": [k for k in ada if not _SENSITIF.search(str(k))], "pesan_galat": teks}


def baseline_tervalidasi(
    ep: dict[str, Any], metode: str, q_valid: dict[str, Any], b_valid: Optional[dict[str, Any]],
    uji: Uji, *, anggaran: AnggaranAI, pakai_ai: bool = True,
    catat_ai: Optional[Callable[[dict[str, Any]], None]] = None,
) -> HasilBaseline:
    """Kirim baseline valid; bila ditolak validasi, perbaiki (deterministik → AI berbatas) & ulang.

    `uji(query, body, judul) -> resp`. Return HasilBaseline (baseline final + payload terpakai)."""
    query = dict(q_valid)
    body = dict(b_valid) if b_valid is not None else None
    diperbaiki: list[str] = []
    panggilan_ai = 0
    maks = _maks_percobaan()
    resp = uji(query, body, "baseline valid")
    for percobaan in range(1, maks + 1):
        sc = _status(resp)
        if _sukses(sc) or sc not in STATUS_VALIDASI:
            # Diterima, atau penolakan bukan-validasi (401/403/404/5xx) → tak perlu/tak bisa diperbaiki.
            return HasilBaseline(resp, query, body, percobaan, diperbaiki, _sukses(sc), panggilan_ai,
                                 "baseline diterima" if _sukses(sc) else f"status {sc} (bukan validasi)")
        if percobaan == maks:
            break
        disebut = asd.field_disebut_galat(resp, {**(body or {}), **query})
        teks = (getattr(resp, "text", "") or "")[:2000]
        duplikasi = bool(asd._KW_DUPLIKASI.search(teks))
        disentuh = _perbaiki_deterministik(ep, body if body is not None else {}, query, disebut, duplikasi)
        sumber = "deterministik"
        if not disentuh and pakai_ai and anggaran.boleh():
            from ..ai import inpv as ai_inpv
            meta = _meta_ai(ep, metode, body or {}, query, disebut, resp)
            nilai, info = ai_inpv.perbaiki_payload(meta)
            anggaran.pakai()
            panggilan_ai += 1
            if catat_ai:
                catat_ai(info)
            for k, v in nilai.items():
                if body is not None and k in (body or {}):
                    body[k] = v
                    disentuh.append(k)
                elif k in query:
                    query[k] = v
                    disentuh.append(k)
                elif body is not None:  # field wajib yang hilang → tambahkan ke body
                    body[k] = v
                    disentuh.append(k)
            sumber = "AI"
        if not disentuh:
            return HasilBaseline(resp, query, body, percobaan, diperbaiki, False, panggilan_ai,
                                 f"ditolak (HTTP {sc}); tak ada perbaikan yang bisa diterapkan")
        diperbaiki += [d for d in disentuh if d not in diperbaiki]
        resp = uji(query, body, f"baseline valid (perbaikan {sumber} #{percobaan})")
    sc = _status(resp)
    return HasilBaseline(resp, query, body, maks, diperbaiki, _sukses(sc), panggilan_ai,
                         "baseline diterima setelah perbaikan" if _sukses(sc)
                         else f"baseline tetap ditolak (HTTP {sc}) setelah {len(diperbaiki)} perbaikan")
