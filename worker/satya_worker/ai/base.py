"""Abstraksi provider AI + pembangun prompt & parser JSON bersama.

Peran AI dalam discovery murni ENRICHMENT: memberi deskripsi endpoint, menebak
semantik/sensitivitas field, dan menarasikan alur proses bisnis. AI TIDAK pernah
memutuskan lulus/gagal — keputusan itu milik pemeriksaan & asesor manusia.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    nama: str
    model: str

    def enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Kembalikan dict enrichment (lihat skema di `bangun_prompt`)."""
        ...


def bangun_prompt_login(metadata: dict[str, Any], bahasa: str = "id") -> str:
    """Prompt arbiter login: putuskan terautentikasi/tidak dari METADATA non-sensitif.

    `metadata` TIDAK memuat nilai token/sandi — hanya nama key, panjang, bentuk,
    path URL, dan sinyal deterministik yang sudah dihitung worker.
    """
    konteks = json.dumps(metadata, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda arbiter untuk asesmen keamanan web yang SAH/berizin. Worker mencoba login "
        "lewat browser dan sinyal deterministiknya tak meyakinkan. Berdasarkan METADATA "
        "(tanpa nilai rahasia) di bawah, putuskan apakah sesi kemungkinan TERAUTENTIKASI.\n"
        "Pertimbangkan: perpindahan dari halaman login, hilangnya field sandi, munculnya "
        "entri storage baru berbentuk token (jwt/uuid/opaque), dan sinyal lain.\n"
        f"Tulis alasan dalam {bhs}. Keluarkan HANYA satu objek JSON:\n"
        '  { "ok": true|false, "keyakinan": 0.0-1.0, "alasan": "<ringkas>" }\n\n'
        "Metadata:\n```json\n" + konteks + "\n```"
    )


# Kode fungsi keamanan katalog (untuk penyempurnaan kandidat uji).
_KODE_FUNGSI = "AUTH SESS ACCS INPV ERRL DATA COMM FILE APIS CONF"


def bangun_prompt_kandidat(metadata: list[Any], bahasa: str = "id") -> str:
    """Prompt penyempurnaan kandidat uji: AI menambah kategori & menandai info kurang.

    `metadata` = ringkasan per endpoint TANPA nilai sensitif (hanya nama field, kategori
    heuristik, dan gap yang sudah terdeteksi). AI mengoreksi/menambah, tak menilai lulus/gagal.
    """
    konteks = json.dumps(metadata, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda asisten pemetaan uji keamanan web yang SAH/berizin. Di bawah ada daftar endpoint "
        "hasil discovery dengan kategori kandidat uji HEURISTIK dan info yang mungkin kurang.\n"
        f"Kategori fungsi valid: {_KODE_FUNGSI}.\n"
        "Tugas: untuk endpoint yang kategorinya kurang tepat/kurang lengkap, sarankan kategori "
        "tambahan yang relevan, dan tandai informasi yang masih kurang untuk mengujinya. "
        "Jangan menilai lulus/gagal; jangan mengarang field yang tak ada.\n"
        f"Tulis catatan dalam {bhs}. Keluarkan HANYA satu objek JSON:\n"
        '  { "saran": [ { "endpoint": "<METODE path>", "tambah_kategori": ["KODE"], '
        '"info_kurang": ["<slug>"], "catatan": "<ringkas>" } ] }\n\n'
        "Endpoint:\n```json\n" + konteks + "\n```"
    )


def bangun_prompt_klasifikasi(metadata: list[Any], bahasa: str = "id") -> str:
    """Prompt penajaman lapisan endpoint: frontend (halaman), api (backend) atau aset (statis).

    `metadata` hanya memuat METODE+path, origin, sumber temuan, content-type, nama field
    (tanpa nilai) dan lapisan heuristik. AI mengoreksi klasifikasi, tak menilai lulus/gagal.
    """
    konteks = json.dumps(metadata, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda asisten pemetaan permukaan serangan untuk asesmen keamanan web yang SAH/berizin. "
        "Di bawah ada endpoint hasil discovery yang klasifikasi lapisannya AMBIGU.\n"
        "Lapisan: 'frontend' = halaman/rute yang dirender untuk pengguna (HTML/SPA route); "
        "'api' = endpoint backend yang menerima/mengembalikan data (JSON/form/upload); "
        "'aset' = berkas statis (JS/CSS/gambar/font).\n"
        "Tugas: tentukan lapisan yang paling mungkin untuk tiap endpoint, dan tandai `upload: true` "
        "bila endpoint kemungkinan menerima unggahan berkas. Jangan mengarang endpoint baru.\n"
        f"Tulis alasan singkat dalam {bhs}. Keluarkan HANYA satu objek JSON:\n"
        '  { "saran": [ { "endpoint": "<METODE path>", "lapisan": "frontend|api|aset", '
        '"upload": true|false, "alasan": "<ringkas>" } ] }\n\n'
        "Endpoint:\n```json\n" + konteks + "\n```"
    )


def bangun_prompt_atribusi(metadata: dict[str, Any], bahasa: str = "id") -> str:
    """Prompt atribusi penolakan uji kebijakan sandi: apa penyebab server menolak request?

    `metadata` berisi status, body error yang SUDAH disamarkan (nilai payload/sandi diganti
    placeholder), daftar nama field, field yang divariasikan, dan ciri nilai lemah (panjang, kelas).
    """
    konteks = json.dumps(metadata, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda asisten asesmen keamanan web yang SAH/berizin. Worker mengirim request (mis. registrasi/"
        "ubah/reset kata sandi) dengan nilai LEMAH pada satu field kredensial, dan server MENOLAK.\n"
        "Tentukan penyebab penolakan dari pesan error berikut:\n"
        "  'kebijakan_sandi' = ditolak karena aturan kekuatan kata sandi (panjang/kombinasi karakter);\n"
        "  'field_lain' = ditolak karena field lain tidak valid/kurang;\n"
        "  'duplikasi' = data sudah terdaftar;\n"
        "  'tidak_jelas' = tidak dapat dipastikan.\n"
        "Jangan menebak 'kebijakan_sandi' tanpa dasar di pesan error.\n"
        f"Tulis alasan ringkas dalam {bhs}. Keluarkan HANYA satu objek JSON:\n"
        '  { "penyebab": "kebijakan_sandi|field_lain|duplikasi|tidak_jelas", "field": ["<nama>"], "alasan": "<ringkas>" }\n\n'
        "Data:\n```json\n" + konteks + "\n```"
    )


def bangun_prompt_isi_payload(metadata: dict[str, Any], bahasa: str = "id") -> str:
    """Prompt pengisian nilai dummy VALID untuk field form (tanpa data nyata/rahasia)."""
    konteks = json.dumps(metadata, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda asisten asesmen keamanan web yang SAH/berizin. Worker perlu mengisi form uji dengan "
        "nilai DUMMY yang lolos validasi server (bukan data orang nyata). Berdasarkan nama field, "
        "skema (tipe, format, enum, panjang, pola), dan pesan galat server (bila ada), usulkan nilai "
        "yang paling mungkin valid untuk tiap field yang diminta. Jangan isi field kata sandi/token.\n"
        f"Konteks bahasa: {bhs}. Keluarkan HANYA satu objek JSON:\n"
        '  { "nilai": { "<nama_field>": <nilai> } }\n\n'
        "Data:\n```json\n" + konteks + "\n```"
    )


def bangun_prompt(payload: dict[str, Any], bahasa: str = "id") -> str:
    """Prompt tunggal: minta JSON enrichment dari inventaris discovery."""
    konteks = json.dumps(payload, ensure_ascii=False, indent=2)
    bhs = "Bahasa Indonesia" if bahasa == "id" else "English"
    return (
        "Anda asisten pemetaan API untuk asesmen keamanan aplikasi web yang SAH/berizin. "
        "Berdasarkan inventaris endpoint & alur hasil discovery di bawah, hasilkan enrichment.\n"
        "Jangan menilai lulus/gagal; cukup jelaskan & petakan. "
        f"Tulis semua teks dalam {bhs}.\n\n"
        "Keluarkan HANYA satu objek JSON valid dengan kunci:\n"
        '  "deskripsi_endpoint": { "<METODE path>": "<fungsi singkat endpoint>" },\n'
        '  "semantik_field": { "<nama_field>": "<arti & sensitivitas (mis. PII/kredensial)>" },\n'
        '  "flows_ternarasi": [ { "nama": "...", "narasi": "...", "langkah": ["..."] } ],\n'
        '  "ringkasan_risiko": "<ringkasan permukaan serangan & area perlu uji>"\n\n'
        "Inventaris discovery:\n```json\n" + konteks + "\n```"
    )


def parse_json(teks: str) -> Optional[dict[str, Any]]:
    """Ambil objek JSON pertama dari teks respons model (toleran terhadap code fence)."""
    if not teks:
        return None
    t = teks.strip()
    # Buang pagar kode ```json ... ```
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except ValueError:
        pass
    # Fallback: cari blok { ... } terluar.
    mulai = t.find("{")
    akhir = t.rfind("}")
    if mulai >= 0 and akhir > mulai:
        try:
            obj = json.loads(t[mulai : akhir + 1])
            return obj if isinstance(obj, dict) else None
        except ValueError:
            return None
    return None
