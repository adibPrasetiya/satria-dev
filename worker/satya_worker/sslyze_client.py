"""Engine `sslyze` — inspeksi TLS/sertifikat langsung untuk fungsi Keamanan Komunikasi (COMM).

Seperti Playwright (lihat `playwright_driver.py`), sslyze adalah **library Python** yang dipakai
worker **in-proses** dan diimpor **lazy** agar paket `satya_worker` tetap bisa diimpor walau
sslyze belum terpasang. Bila paket tak ada atau target tak punya TLS yang bisa dijabat, hasilnya
membuat check COMM berstatus `tidak_dapat_diverifikasi` (tak menghakimi tanpa bukti).

Satu scan dijalankan per (host, port) lalu **dipakai ulang** oleh semua check COMM-8.3/8.4 pada
target yang sama (cache per-proses + kunci, pola sama `zap_scan.py`). Scan sslyze bersifat
read-only (hanya handshake TLS, tak mengubah apa pun) → aman untuk profil `aman`.

Konfigurasi via env:
    SSLYZE_ENABLE       '0'/'false' untuk menonaktifkan (default aktif bila paket ada)
    SSLYZE_PORT         port TLS default bila URL tak menyebut (default 443)
    SSLYZE_TIMEOUT      batas jaringan per koneksi, detik (default 10)
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional
from urllib.parse import urlsplit

# Pola nama cipher lemah (IANA/OpenSSL). Katalog COMM-8.3-T02: NULL/EXPORT/RC4/3DES; plus anon/DES/MD5.
import re

_CIPHER_LEMAH = re.compile(r"(NULL|EXPORT|_RC4_|_RC4|RC4|_3DES_|3DES|_DES_|DES_CBC|anon|_MD5|MD5)", re.IGNORECASE)
# Pertukaran kunci dengan forward secrecy (ephemeral).
_FS = re.compile(r"(ECDHE|DHE)", re.IGNORECASE)

_cache: dict[tuple[str, int], dict[str, Any]] = {}
_kunci = threading.Lock()


class SslyzeTidakTersedia(Exception):
    """Paket sslyze belum terpasang."""


def aktif() -> bool:
    return os.environ.get("SSLYZE_ENABLE", "true").strip().lower() not in ("0", "false", "no")


def _port_default() -> int:
    try:
        return int(os.environ.get("SSLYZE_PORT", "443"))
    except ValueError:
        return 443


def _timeout() -> float:
    try:
        return float(os.environ.get("SSLYZE_TIMEOUT", "10"))
    except ValueError:
        return 10.0


def tersedia() -> bool:
    """True bila modul sslyze bisa diimpor."""
    try:
        import sslyze  # noqa: F401
    except Exception:
        return False
    return True


def host_port(url: str) -> tuple[str, int]:
    """Ekstrak (hostname, port) dari URL. Port: eksplisit → skema https(443)/http(80) → SSLYZE_PORT."""
    b = urlsplit(url)
    host = (b.hostname or "").lower()
    if b.port:
        return host, b.port
    if b.scheme == "https":
        return host, 443
    if b.scheme == "http":
        return host, _port_default()
    return host, _port_default()


# --------------------------------------------------------------------------- ekstraksi

def _issuer_fields(cert: Any) -> tuple[str, str]:
    """(organisasi, common_name) penerbit sertifikat dari objek cryptography x509."""
    org = cn = ""
    try:
        from cryptography.x509.oid import NameOID

        o = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        if o:
            org = str(o[0].value)
        c = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if c:
            cn = str(c[0].value)
    except Exception:
        pass
    return org, cn


def _subject_cn(cert: Any) -> str:
    try:
        from cryptography.x509.oid import NameOID

        c = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if c:
            return str(c[0].value)
    except Exception:
        pass
    return ""


def _san(cert: Any) -> list[str]:
    """Daftar DNS Subject Alternative Name dari objek cryptography x509."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID

        ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        return [str(n) for n in ext.value.get_values_for_type(x509.DNSName)]
    except Exception:
        return []


def _kunci_tanda(cert: Any) -> dict[str, Any]:
    """Tipe & ukuran kunci publik + algoritma tanda tangan sertifikat (dari cryptography x509)."""
    out: dict[str, Any] = {"tipe_kunci": None, "ukuran_kunci": None, "kurva": None, "algoritma_tanda_tangan": None}
    try:
        from cryptography.hazmat.primitives.asymmetric import ec, rsa, ed25519, ed448

        pub = cert.public_key()
        if isinstance(pub, rsa.RSAPublicKey):
            out["tipe_kunci"], out["ukuran_kunci"] = "RSA", pub.key_size
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            out["tipe_kunci"], out["ukuran_kunci"], out["kurva"] = "EC", pub.curve.key_size, pub.curve.name
        elif isinstance(pub, ed25519.Ed25519PublicKey):
            out["tipe_kunci"], out["ukuran_kunci"] = "Ed25519", 256
        elif isinstance(pub, ed448.Ed448PublicKey):
            out["tipe_kunci"], out["ukuran_kunci"] = "Ed448", 448
        else:
            out["tipe_kunci"] = type(pub).__name__
    except Exception:
        pass
    try:
        alg = getattr(cert, "signature_hash_algorithm", None)
        if alg is not None and getattr(alg, "name", None):
            out["algoritma_tanda_tangan"] = str(alg.name)
        else:
            oid = getattr(cert, "signature_algorithm_oid", None)
            out["algoritma_tanda_tangan"] = getattr(oid, "_name", None) or (str(oid) if oid else None)
    except Exception:
        pass
    return out


def _cocok_satu(host: str, pola: str) -> bool:
    """Cocokkan host dengan satu entri sertifikat (dukung wildcard leftmost RFC 6125)."""
    host = host.lower().strip(".")
    pola = pola.lower().strip(".")
    if not host or not pola:
        return False
    if pola.startswith("*."):
        # Wildcard hanya pada label paling kiri & cocok TEPAT satu label.
        sisa = pola[2:]
        bagian = host.split(".", 1)
        return len(bagian) == 2 and bagian[1] == sisa and "." not in bagian[0] and bool(bagian[0])
    return host == pola


def cocok_host(host: str, san: list[str], cn: str) -> bool | None:
    """True/False kecocokan nama host terhadap SAN (CN hanya cadangan bila SAN kosong).

    None bila tak ada nama yang bisa dinilai (ambigu → bisa ditie-break AI).
    """
    kandidat = list(san) if san else ([cn] if cn else [])
    if not kandidat:
        return None
    return any(_cocok_satu(host, p) for p in kandidat)


def _tanggal(cert: Any, akhir: bool) -> Optional[Any]:
    """not_valid_after/before sebagai datetime aware UTC (cryptography lama & baru)."""
    try:
        return getattr(cert, "not_valid_after_utc" if akhir else "not_valid_before_utc")
    except Exception:
        pass
    try:
        from datetime import timezone

        dt = getattr(cert, "not_valid_after" if akhir else "not_valid_before")
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _proto_didukung(attempt: Any) -> tuple[Optional[bool], list[str]]:
    """(didukung?, nama_cipher_diterima). didukung None bila attempt tak selesai."""
    try:
        from sslyze import ScanCommandAttemptStatusEnum
    except Exception:
        return None, []
    if attempt is None or getattr(attempt, "status", None) != ScanCommandAttemptStatusEnum.COMPLETED:
        return None, []
    res = getattr(attempt, "result", None)
    diterima = list(getattr(res, "accepted_cipher_suites", None) or [])
    nama = []
    for a in diterima:
        cs = getattr(a, "cipher_suite", None)
        n = getattr(cs, "name", None) or getattr(cs, "openssl_name", None)
        if n:
            nama.append(str(n))
    return (len(diterima) > 0), nama


def _ekstrak_sertifikat(attempt: Any, hostname: str = "") -> dict[str, Any]:
    """Ringkasan deployment sertifikat pertama → dict (lihat skema di `pindai`)."""
    out: dict[str, Any] = {"tersedia": False}
    try:
        from sslyze import ScanCommandAttemptStatusEnum
    except Exception:
        return out
    if attempt is None or getattr(attempt, "status", None) != ScanCommandAttemptStatusEnum.COMPLETED:
        out["galat"] = getattr(attempt, "error_reason", None) if attempt is not None else "tak dijalankan"
        return out
    res = getattr(attempt, "result", None)
    deployments = list(getattr(res, "certificate_deployments", None) or [])
    if not deployments:
        return out
    dep = deployments[0]
    rantai = list(getattr(dep, "received_certificate_chain", None) or [])
    if not rantai:
        return out
    leaf = rantai[0]
    org, cn = _issuer_fields(leaf)
    san = _san(leaf)
    t_akhir = _tanggal(leaf, akhir=True)
    t_awal = _tanggal(leaf, akhir=False)

    kedaluwarsa = None
    hari_tersisa = None
    try:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if t_akhir is not None:
            kedaluwarsa = now > t_akhir
            hari_tersisa = int((t_akhir - now).total_seconds() // 86400)
    except Exception:
        pass

    # Validasi rantai terhadap tiap trust store bawaan sslyze.
    trust: dict[str, bool] = {}
    for pvr in list(getattr(dep, "path_validation_results", None) or []):
        ts = getattr(pvr, "trust_store", None)
        nama = str(getattr(ts, "name", "") or "").strip()
        if not nama:
            continue
        sukses = getattr(pvr, "was_validation_successful", None)
        if sukses is None:
            sukses = getattr(pvr, "verified_certificate_chain", None) is not None
        trust[nama] = bool(sukses)

    # host_cocok dihitung sendiri: sslyze 6.x tak lagi mengekspos boolean kecocokan hostname.
    # None (SAN & CN kosong) = ambigu → bisa ditie-break AI.
    host_cocok = cocok_host(hostname, san, _subject_cn(leaf)) if hostname else None

    out.update(
        tersedia=True,
        subjek_cn=_subject_cn(leaf),
        san=san,
        penerbit_o=org,
        penerbit_cn=cn,
        tidak_sebelum=t_awal.isoformat() if t_awal is not None else None,
        tidak_sesudah=t_akhir.isoformat() if t_akhir is not None else None,
        kedaluwarsa=kedaluwarsa,
        hari_tersisa=hari_tersisa,
        host_cocok=(None if host_cocok is None else bool(host_cocok)),
        urutan_rantai_valid=getattr(dep, "received_chain_has_valid_order", None),
        panjang_rantai=len(rantai),
        trust=trust,
        **_kunci_tanda(leaf),
    )
    return out


# --------------------------------------------------------------------------- scan

def _scan(hostname: str, port: int) -> dict[str, Any]:
    """Jalankan sslyze sekali untuk (host, port) → dict ternormalisasi. Tak pernah melempar."""
    hasil: dict[str, Any] = {"ok": False, "galat": None, "hostname": hostname, "port": port}
    if not hostname:
        hasil["galat"] = "hostname kosong"
        return hasil
    try:
        from sslyze import (
            Scanner,
            ScanCommand,
            ServerNetworkLocation,
            ServerScanRequest,
            ServerScanStatusEnum,
        )
    except Exception as e:
        hasil["galat"] = f"sslyze tak tersedia: {type(e).__name__}"
        return hasil

    perintah = {
        ScanCommand.SSL_2_0_CIPHER_SUITES,
        ScanCommand.SSL_3_0_CIPHER_SUITES,
        ScanCommand.TLS_1_0_CIPHER_SUITES,
        ScanCommand.TLS_1_1_CIPHER_SUITES,
        ScanCommand.TLS_1_2_CIPHER_SUITES,
        ScanCommand.TLS_1_3_CIPHER_SUITES,
        ScanCommand.CERTIFICATE_INFO,
    }
    try:
        lokasi = ServerNetworkLocation(hostname=hostname, port=port)
        req_kwargs: dict[str, Any] = {"server_location": lokasi, "scan_commands": perintah}
        try:
            from sslyze import ServerNetworkConfiguration

            req_kwargs["network_configuration"] = ServerNetworkConfiguration(
                tls_server_name_indication=hostname, network_timeout=int(_timeout())
            )
        except Exception:
            pass
        permintaan = ServerScanRequest(**req_kwargs)
    except Exception as e:
        hasil["galat"] = f"gagal menyiapkan scan: {type(e).__name__}: {e}"
        return hasil

    try:
        pemindai = Scanner()
        pemindai.queue_scans([permintaan])
        hasil_scan = None
        for r in pemindai.get_results():
            hasil_scan = r
            break
    except Exception as e:
        hasil["galat"] = f"sslyze gagal memindai: {type(e).__name__}: {e}"
        return hasil

    if hasil_scan is None:
        hasil["galat"] = "tak ada hasil scan"
        return hasil

    if getattr(hasil_scan, "scan_status", None) == ServerScanStatusEnum.ERROR_NO_CONNECTIVITY:
        jejak = getattr(hasil_scan, "connectivity_error_trace", None)
        hasil["galat"] = f"tak dapat menjabat TLS di {hostname}:{port}" + (f" ({jejak})" if jejak else "")
        return hasil

    sr = getattr(hasil_scan, "scan_result", None)
    if sr is None:
        hasil["galat"] = "hasil scan kosong"
        return hasil

    # Protokol & cipher.
    peta_proto = {
        "SSL 2.0": getattr(sr, "ssl_2_0_cipher_suites", None),
        "SSL 3.0": getattr(sr, "ssl_3_0_cipher_suites", None),
        "TLS 1.0": getattr(sr, "tls_1_0_cipher_suites", None),
        "TLS 1.1": getattr(sr, "tls_1_1_cipher_suites", None),
        "TLS 1.2": getattr(sr, "tls_1_2_cipher_suites", None),
        "TLS 1.3": getattr(sr, "tls_1_3_cipher_suites", None),
    }
    protokol: dict[str, Optional[bool]] = {}
    cipher_per_proto: dict[str, list[str]] = {}
    for nama, attempt in peta_proto.items():
        didukung, ciphers = _proto_didukung(attempt)
        protokol[nama] = didukung
        if ciphers:
            cipher_per_proto[nama] = ciphers

    # Cipher lemah & forward secrecy (hanya protokol yang masih relevan: TLS 1.2/1.3 + legasi bila aktif).
    cipher_lemah: list[dict[str, str]] = []
    for nama, ciphers in cipher_per_proto.items():
        for c in ciphers:
            if _CIPHER_LEMAH.search(c):
                cipher_lemah.append({"protokol": nama, "cipher": c})
    fs = bool(protokol.get("TLS 1.3")) or any(_FS.search(c) for c in cipher_per_proto.get("TLS 1.2", []))

    hasil.update(
        ok=True,
        protokol=protokol,
        cipher_per_protokol=cipher_per_proto,
        cipher_lemah=cipher_lemah,
        forward_secrecy=fs,
        sertifikat=_ekstrak_sertifikat(getattr(sr, "certificate_info", None), hostname),
    )
    return hasil


def pindai(url_atau_host: str, port: Optional[int] = None) -> dict[str, Any]:
    """Scan ternormalisasi untuk target (URL atau hostname), di-cache per (host, port).

    Skema dict (ok=True):
        protokol: {"SSL 2.0": bool|None, ..., "TLS 1.3": bool|None}  (None = tak terverifikasi)
        cipher_per_protokol: {proto: [nama_cipher]}
        cipher_lemah: [{protokol, cipher}]
        forward_secrecy: bool
        sertifikat: {tersedia, subjek_cn, penerbit_o, penerbit_cn, tidak_sebelum, tidak_sesudah,
                     kedaluwarsa, hari_tersisa, host_cocok, panjang_rantai, trust: {nama: bool}}
    ok=False → {galat}.
    """
    if "://" in url_atau_host or "/" in url_atau_host:
        host, p = host_port(url_atau_host)
    else:
        host, p = url_atau_host.lower(), (port or _port_default())
    if port:
        p = port
    kunci = (host, p)
    with _kunci:
        if kunci in _cache:
            return _cache[kunci]
    hasil = _scan(host, p)
    with _kunci:
        _cache[kunci] = hasil
    return hasil


def _bersihkan_cache() -> None:
    """Hanya untuk pengujian."""
    with _kunci:
        _cache.clear()
