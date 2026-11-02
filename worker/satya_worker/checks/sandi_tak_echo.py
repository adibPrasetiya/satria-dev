"""AUTH-1.6-T01 — auth.password_not_echoed (butuh login).

Setelah login dengan akun uji, kata sandi — maupun HASH-nya — tidak boleh pernah dikembalikan server,
baik di respons login maupun di endpoint profil/pengguna.
Diperiksa: respons login MENTAH, titik area terautentikasi, dan endpoint profil dari inventaris
penemuan (/me, /profile, /profil, /account, /akun, /users/me) — maks 5.
  sandi utuh muncul                        → GAGAL (teks asli bocor)
  hash sandi muncul ($2b$, $argon2, pbkdf2_, sha-256 hex pada field sandi/hash) → GAGAL (hash terekspos)
  tak ada                                  → LULUS
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..http_client import LuarRuangLingkup
from ..models import HasilMetode, MetodeSpec, Pewaktu, ScanContext
from ..registry import check
from ..sesi import buat_klien, login_ambil

_RX_HASH = re.compile(r"\$2[abxy]?\$\d{2}\$[./A-Za-z0-9]{53}|\$argon2(id|i|d)\$[^\"'\s]{20,}|pbkdf2_sha\d+\$\d+\$[^\"'\s]+|\$6\$[^\"'\s$]{1,16}\$[./A-Za-z0-9]{40,}")
_FIELD_HASH = re.compile(r"pass|sandi|hash|digest|salt", re.I)
_RX_HEX = re.compile(r"^[0-9a-f]{40,128}$", re.I)
_PROFIL = re.compile(r"/(me|profile|profil|account|akun|users/me)/?$", re.I)


def _hash_di_json(obj: Any) -> list[str]:
    """Nama field yang berisi nilai berbentuk hash sandi (bcrypt/argon2/pbkdf2/sha hex) pada key sandi/hash."""
    out: list[str] = []

    def jalan(x: Any, jalur: str) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and _FIELD_HASH.search(str(k)) and (_RX_HASH.search(v) or _RX_HEX.match(v)):
                    out.append(f"{jalur}{k}")
                jalan(v, f"{jalur}{k}.")
        elif isinstance(x, list):
            for i in x[:20]:
                jalan(i, jalur)

    jalan(obj, "")
    return out


def _periksa(resp: Any, sandi: str) -> dict[str, Any]:
    teks = resp.text or ""
    temuan: dict[str, Any] = {"sandi": sandi in teks, "hash": []}
    try:
        temuan["hash"] = _hash_di_json(json.loads(teks))
    except ValueError:
        pass
    if not temuan["hash"] and _RX_HASH.search(teks):
        temuan["hash"] = ["(teks respons)"]
    return temuan


@check("auth.password_not_echoed")
class CekSandiTakEcho:
    def run(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        with Pewaktu() as jam:
            hasil = self._jalankan(ctx, metode)
        hasil.durasi_ms = jam.durasi_ms
        return hasil

    def _jalankan(self, ctx: ScanContext, metode: MetodeSpec) -> HasilMetode:
        akun = ctx.akun("akun_uji_1") or ctx.akun("utama")
        if akun is None or not akun.password:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Membutuhkan akun uji (dengan kata sandi), tetapi belum diisi.")
        if ctx.url_titik("login") is None:
            return HasilMetode(metode_id=metode.id, status="tidak_berlaku", ringkasan='Titik uji "login" tidak tersedia pada aplikasi.')

        # Endpoint profil: titik area terautentikasi + endpoint GET profil dari inventaris penemuan.
        target: list[str] = []
        area = ctx.url_titik("area_terautentikasi")
        if area:
            target.append(area)
        for ep in ctx.endpoints or []:
            u = str(ep.get("url", ""))
            if ep.get("metode_http", "GET") == "GET" and "{" not in str(ep.get("path_template", "")) and _PROFIL.search(str(ep.get("path_template", ""))) and u not in target:
                target.append(u)
        target = target[:5]

        sandi = akun.password
        ctx.langkah("login", f"Login akun uji '{akun.kunci}', lalu periksa apakah kata sandi/hash-nya dikembalikan server")
        temuan: list[tuple[str, dict[str, Any]]] = []
        try:
            with buat_klien(ctx) as klien:
                s = login_ambil(klien, ctx, akun, judul=f"{metode.id} — login akun uji (periksa respons login)")
                if s["resp"] is not None:
                    temuan.append(("respons login", _periksa(s["resp"], sandi)))
                if not s["ok"]:
                    return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal login dengan akun uji.",
                                       detail="\n".join(b.isi or "" for b in klien.bukti))
                for u in target:
                    ctx.langkah("ambil_profil", f"Mengambil {u} dengan sesi akun uji")
                    r = klien.kirim("GET", u, judul_bukti=f"{metode.id} — ambil profil/area terautentikasi")
                    if r.status_code < 400:
                        temuan.append((u, _periksa(r, sandi)))
                bukti = list(klien.bukti)
        except LuarRuangLingkup as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="URL di luar host yang diizinkan.", detail=str(e))
        except Exception as e:
            return HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Gagal menghubungi endpoint.", detail=f"{type(e).__name__}: {e}")

        bocor = [lok for lok, t in temuan if t["sandi"]]
        hash_ = [f"{lok}: {', '.join(t['hash'])}" for lok, t in temuan if t["hash"]]
        diperiksa = ", ".join(lok for lok, _ in temuan) or "—"
        if bocor:
            ctx.langkah("evaluasi", "Kata sandi MUNCUL dalam respons", hasil="bocor")
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Kata sandi teks asli dikembalikan server pada: {', '.join(bocor)}.", detail=metode.kriteria_lulus, bukti=bukti)
        if hash_:
            ctx.langkah("evaluasi", "HASH kata sandi terekspos dalam respons", hasil="bocor")
            return HasilMetode(metode_id=metode.id, status="gagal", ringkasan=f"Hash kata sandi terekspos pada: {'; '.join(hash_)[:300]}.", detail=metode.kriteria_lulus, bukti=bukti)
        ctx.langkah("evaluasi", "Kata sandi maupun hash-nya tidak dikembalikan", hasil="aman")
        return HasilMetode(metode_id=metode.id, status="lulus",
                           ringkasan=f"Kata sandi maupun hash-nya tidak dikembalikan (diperiksa: {diperiksa}).", detail=metode.kriteria_lulus, bukti=bukti)
