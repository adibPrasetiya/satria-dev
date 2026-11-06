"""Analisis struktur token sesi — membedah token untuk uji keacakan & prediktabilitas.

Lapisan deterministik yang menjawab: APA sebenarnya pembawa identitas sesi di dalam token?

- JWT: bongkar header+payload (TANPA verifikasi tanda tangan), temukan klaim identitas sesi
  (`jti`/`sid`/`session_id`/`sub`), klasifikasi bentuk nilainya (uuid/int/opaque), baca `alg`
  serta `exp`/`iat`. Token yang "panjang & acak" di permukaan bisa menyimpan identifier yang
  dapat ditebak (mis. `sub`=angka pengguna berurutan) — itu yang dicari.
- Opaque ter-encode: deteksi base64/base64url/hex, dekode SATU lapis, klasifikasi isi
  (uuid / "id:123" / angka sekuensial / username / email) → token yang tampak acak padahal
  membungkus identifier prediktabel ("kadang dalam bentuk encode saja").

Semua keluaran untuk AI (`metadata_ai`) bersifat METADATA NON-SENSITIF: nama klaim, bentuk &
panjang nilai, lapisan encode — TANPA nilai mentah. Nilai token asli tak pernah keluar dari worker.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, Optional

# JWT: tiga segmen base64url.
_RE_JWT = re.compile(r"^[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*$")
_RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_RE_HEX = re.compile(r"^[0-9a-f]+$", re.IGNORECASE)
_RE_INT = re.compile(r"^\d+$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_USERNAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9._-]{2,40}$")
_RE_B64 = re.compile(r"^[A-Za-z0-9_\-+/]+=*$")

# Klaim yang lazim menjadi identitas sesi (urutan = prioritas).
_KLAIM_IDENTITAS = ("jti", "sid", "session_id", "sessionId", "sessionid", "sub", "uid", "user_id", "userId")
# Klaim waktu/standar (bukan pembawa keacakan sesi).
_KLAIM_WAKTU = ("exp", "iat", "nbf", "auth_time")


def _b64url_decode(seg: str) -> Optional[bytes]:
    try:
        return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))
    except (binascii.Error, ValueError):
        return None


def klasifikasi_nilai(v: Any) -> str:
    """Klasifikasi bentuk sebuah nilai identitas (untuk menilai prediktabilitas).

    Return: 'uuid' | 'int' | 'timestamp' | 'email' | 'username' | 'hex' | 'uuid' |
            'jwt' | 'opaque' | 'kosong' | 'lainnya'.
    """
    if v is None:
        return "kosong"
    if isinstance(v, bool):
        return "lainnya"
    if isinstance(v, int):
        return "timestamp" if 1_000_000_000 <= v <= 9_999_999_999 else "int"
    if not isinstance(v, str):
        return "lainnya"
    s = v.strip()
    if not s:
        return "kosong"
    if _RE_UUID.match(s):
        return "uuid"
    if _RE_JWT.match(s) and s.count(".") == 2:
        return "jwt"
    if _RE_INT.match(s):
        n = int(s)
        return "timestamp" if 1_000_000_000 <= n <= 9_999_999_999 else "int"
    if _RE_EMAIL.match(s):
        return "email"
    if len(s) >= 24 and _RE_HEX.match(s):
        return "hex"  # digest/acak heksadesimal panjang
    if _RE_USERNAME.match(s) and not _RE_HEX.match(s):
        return "username"
    if len(s) >= 16 and _RE_B64.match(s):
        return "opaque"
    return "lainnya"


# Bentuk nilai yang DAPAT DITEBAK bila menjadi satu-satunya identitas sesi.
_PREDIKTABEL = {"int", "timestamp", "email", "username", "kosong"}
# Bentuk nilai yang mengindikasikan keacakan memadai.
_ACAK = {"uuid", "hex", "opaque", "jwt"}


def bongkar_jwt(tok: str) -> Optional[dict[str, Any]]:
    """Bongkar JWT → {header, klaim, segmen, sig_panjang}. None bila bukan JWT yang dapat dibongkar.

    Nilai klaim hanya untuk klasifikasi LOKAL; tak diemit mentah ke AI.
    """
    if not isinstance(tok, str) or tok.count(".") != 2:
        return None
    h_seg, p_seg, s_seg = tok.split(".")
    h_raw, p_raw = _b64url_decode(h_seg), _b64url_decode(p_seg)
    if h_raw is None or p_raw is None:
        return None
    try:
        header = json.loads(h_raw)
        klaim = json.loads(p_raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(header, dict) or not isinstance(klaim, dict):
        return None
    return {"header": header, "klaim": klaim, "sig_panjang": len(s_seg)}


def dekode_lapis(v: str) -> Optional[dict[str, Any]]:
    """Coba dekode SATU lapis encoding (base64/base64url/hex) dari token opaque.

    Return {skema, bentuk_isi, isi_ringkas} bila hasilnya teks bermakna & terklasifikasi,
    selain 'opaque'/'lainnya' (yakni mengungkap sesuatu yang prediktabel). None bila tidak.
    `isi_ringkas` hanya untuk log lokal; metadata AI memakai `bentuk_isi` saja.
    """
    if not isinstance(v, str) or len(v) < 8:
        return None
    kandidat: list[tuple[str, bytes]] = []
    if _RE_B64.match(v):
        d = _b64url_decode(v)
        if d is not None:
            kandidat.append(("base64", d))
    if _RE_HEX.match(v) and len(v) % 2 == 0:
        try:
            kandidat.append(("hex", bytes.fromhex(v)))
        except ValueError:
            pass
    for skema, raw in kandidat:
        try:
            teks = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not teks.isprintable() or len(teks) < 2:
            continue
        # JSON di dalam? ambil nilai identitasnya.
        inti = teks
        if teks[:1] in "{[":
            try:
                obj = json.loads(teks)
                if isinstance(obj, dict):
                    for k in _KLAIM_IDENTITAS:
                        if k in obj:
                            inti = str(obj[k])
                            break
            except ValueError:
                pass
        # Pola "prefix:nilai" / "prefix-nilai" (mis. user:123, sess-42).
        m = re.match(r"^[a-zA-Z]+[:_-](.+)$", inti)
        inti_nilai = m.group(1) if m else inti
        bentuk = klasifikasi_nilai(inti_nilai)
        if bentuk in _PREDIKTABEL and bentuk != "kosong":
            return {"skema": skema, "bentuk_isi": bentuk, "isi_ringkas": teks[:48]}
        if bentuk in ("uuid", "jwt"):
            return {"skema": skema, "bentuk_isi": bentuk, "isi_ringkas": teks[:48]}
    return None


def identitas_sesi(klaim: dict[str, Any]) -> tuple[Optional[str], Any, str]:
    """Pilih klaim pembawa identitas sesi + klasifikasi bentuknya. (nama, nilai, bentuk)."""
    for k in _KLAIM_IDENTITAS:
        if k in klaim and klaim[k] not in (None, ""):
            return k, klaim[k], klasifikasi_nilai(klaim[k])
    # Tak ada klaim identitas baku → ambil klaim string non-waktu pertama.
    for k, v in klaim.items():
        if k not in _KLAIM_WAKTU and isinstance(v, (str, int)):
            return k, v, klasifikasi_nilai(v)
    return None, None, "kosong"


def analisis(*, token: Optional[str] = None, cookie: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Analisis struktur satu artefak sesi.

    Return dict dengan:
      - `metadata_ai`: metadata NON-SENSITIF untuk arbiter AI (tanpa nilai mentah)
      - `kualitas`: 'acak_kuat' | 'prediktabel' | 'tak_pasti' (vonis heuristik deterministik)
      - `nilai_entropi`: string yang relevan untuk analisis entropi (sig JWT / nilai opaque) atau None
      - `catatan`: penjelasan ringkas untuk detail hasil
    """
    nilai = token or (cookie.get("value") if cookie else None)
    wadah = "header" if token else ("cookie" if cookie else "tidak_ada")
    md: dict[str, Any] = {"wadah": wadah}
    if cookie:
        md["nama_cookie"] = cookie.get("name", "")
        md["atribut_cookie"] = cookie.get("flags", "")

    if not nilai:
        return {"metadata_ai": {**md, "format": "tidak_ada"}, "kualitas": "tak_pasti",
                "nilai_entropi": None, "catatan": "Tak ada artefak sesi."}

    j = bongkar_jwt(nilai)
    if j is not None:
        alg = str(j["header"].get("alg", "")).lower()
        nama_id, _nilai_id, bentuk_id = identitas_sesi(j["klaim"])
        md.update({
            "format": "jwt",
            "alg": alg or "?",
            "typ": str(j["header"].get("typ", "")) or "?",
            "daftar_klaim": sorted(str(k) for k in j["klaim"]),
            "klaim_identitas": nama_id or "(tidak ada)",
            "bentuk_identitas": bentuk_id,
            "ada_exp": "exp" in j["klaim"],
            "ada_iat": "iat" in j["klaim"],
            "sig_ada": j["sig_panjang"] > 0,
        })
        # alg=none → tanda tangan absen: token bisa dipalsukan → kredensial tak andal.
        if alg in ("none", ""):
            kualitas = "prediktabel"
            catatan = "JWT dengan alg 'none'/tanpa tanda tangan — klaim dapat dipalsukan."
        elif bentuk_id in _PREDIKTABEL and j["sig_panjang"] < 16:
            kualitas = "prediktabel"
            catatan = f"Identitas sesi JWT ('{nama_id}') berbentuk {bentuk_id} dengan tanda tangan pendek/absen."
        elif bentuk_id in _ACAK or j["sig_panjang"] >= 16:
            kualitas = "acak_kuat"
            catatan = f"JWT alg={alg}, identitas '{nama_id}'={bentuk_id}, tanda tangan {j['sig_panjang']} char."
        else:
            kualitas = "tak_pasti"
            catatan = f"JWT alg={alg}, identitas '{nama_id}'={bentuk_id}."
        # Entropi dinilai pada segmen tanda tangan (pembawa keacakan JWT).
        nilai_entropi = nilai.split(".")[2] if nilai.count(".") == 2 else None
        return {"metadata_ai": md, "kualitas": kualitas, "nilai_entropi": nilai_entropi, "catatan": catatan}

    # Non-JWT: UUID / hex / opaque, mungkin ter-encode.
    bentuk = klasifikasi_nilai(nilai)
    md["format"] = "uuid" if bentuk == "uuid" else "opaque"
    md["panjang"] = len(nilai)
    lapis = dekode_lapis(nilai)
    if lapis is not None:
        md["lapis_encode"] = lapis["skema"]
        md["bentuk_setelah_dekode"] = lapis["bentuk_isi"]
        if lapis["bentuk_isi"] in _PREDIKTABEL:
            return {"metadata_ai": md, "kualitas": "prediktabel", "nilai_entropi": nilai,
                    "catatan": f"Token ter-{lapis['skema']} membungkus identifier {lapis['bentuk_isi']} yang dapat ditebak."}
        return {"metadata_ai": md, "kualitas": "tak_pasti", "nilai_entropi": nilai,
                "catatan": f"Token ter-{lapis['skema']} berisi {lapis['bentuk_isi']}."}
    md["lapis_encode"] = "tidak_ada"
    if bentuk == "uuid":
        return {"metadata_ai": md, "kualitas": "acak_kuat", "nilai_entropi": nilai,
                "catatan": "Token berbentuk UUID."}
    if bentuk == "hex" and len(nilai) >= 24:
        return {"metadata_ai": md, "kualitas": "acak_kuat", "nilai_entropi": nilai,
                "catatan": f"Token heksadesimal panjang ({len(nilai)} char)."}
    if bentuk in ("int", "timestamp"):
        return {"metadata_ai": md, "kualitas": "prediktabel", "nilai_entropi": nilai,
                "catatan": f"Token berbentuk {bentuk} yang dapat ditebak."}
    if _opaque_kuat(nilai):
        return {"metadata_ai": md, "kualitas": "acak_kuat", "nilai_entropi": nilai,
                "catatan": f"Token opaque panjang & berentropi tinggi ({len(nilai)} char, banyak kelas karakter)."}
    return {"metadata_ai": md, "kualitas": "tak_pasti", "nilai_entropi": nilai,
            "catatan": f"Token opaque ({len(nilai)} char); keacakan dinilai via entropi/AI."}


def _opaque_kuat(v: str) -> bool:
    """Heuristik: token opaque cukup panjang dengan banyak kelas karakter & ragam tinggi → acak kuat."""
    if len(v) < 24:
        return False
    kelas = sum((
        any(c.islower() for c in v),
        any(c.isupper() for c in v),
        any(c.isdigit() for c in v),
        any(c in "_-+/=.~" for c in v),
    ))
    ragam = len(set(v)) / len(v)
    return kelas >= 3 and ragam >= 0.5


def metadata_sampel(nilai_list: list[str]) -> dict[str, Any]:
    """Metadata NON-SENSITIF dari beberapa sampel token untuk deteksi pola lintas-login.

    Mencari identifier prediktabel yang BERURUTAN (mis. 1,2,3 atau ter-encode darinya) tanpa
    membocorkan nilai: hanya melaporkan bentuk, apakah menaik, dan selisih yang konsisten.
    """
    bentuk_dekode: list[str] = []
    angka: list[int] = []
    for v in nilai_list:
        a = analisis(token=v)
        b = a["metadata_ai"].get("bentuk_setelah_dekode") or a["metadata_ai"].get("bentuk_identitas") or a["metadata_ai"].get("format")
        bentuk_dekode.append(str(b))
        # Ekstrak angka identitas untuk deteksi urutan (lokal; tak diemit).
        n = _angka_identitas(v)
        if n is not None:
            angka.append(n)
    berurutan = False
    if len(angka) >= 3:
        urut = sorted(angka)
        selisih = {urut[i + 1] - urut[i] for i in range(len(urut) - 1)}
        berurutan = selisih <= {1} or (len(selisih) == 1 and 0 < next(iter(selisih)) <= 3)
    return {
        "jumlah_sampel": len(nilai_list),
        "bentuk_dominan": max(set(bentuk_dekode), key=bentuk_dekode.count) if bentuk_dekode else "?",
        "semua_unik": len(set(nilai_list)) == len(nilai_list),
        "identitas_berurutan": berurutan,
        "jumlah_angka_terbaca": len(angka),
    }


def _angka_identitas(v: str) -> Optional[int]:
    """Angka identitas yang tersembunyi dalam token (JWT jti/sub numerik, atau hasil dekode)."""
    j = bongkar_jwt(v)
    if j is not None:
        _n, nilai_id, bentuk = identitas_sesi(j["klaim"])
        if bentuk in ("int",) and isinstance(nilai_id, (str, int)):
            try:
                return int(nilai_id)
            except (ValueError, TypeError):
                return None
        return None
    lapis = dekode_lapis(v)
    if lapis and lapis["bentuk_isi"] == "int":
        m = re.search(r"(\d+)", lapis["isi_ringkas"])
        return int(m.group(1)) if m else None
    if _RE_INT.match(v):
        return int(v)
    m = re.match(r"^[a-zA-Z]+[:_-](\d+)$", v)  # sess-1, user_2
    return int(m.group(1)) if m else None
