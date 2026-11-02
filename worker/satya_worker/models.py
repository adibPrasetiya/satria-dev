"""Model data worker — dipetakan satu-ke-satu dengan tipe frontend.

Lihat `frontend/src/lib/types.ts`:
  - Status          -> StatusHasil di sini
  - Bukti           -> Bukti
  - HasilMetode     -> HasilMetode
Metode & konteks scan dikirim backend sebagai JSON; di sini hanya subset
yang dibutuhkan kontrol AUTH-1.3.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# frontend: type Status = 'lulus' | 'gagal' | 'tidak_berlaku' | 'tidak_dapat_diverifikasi'
StatusHasil = Literal["lulus", "gagal", "tidak_berlaku", "tidak_dapat_diverifikasi"]
JenisBukti = Literal["request_response", "screenshot", "dokumen"]


@dataclass
class Bukti:
    """frontend: interface Bukti."""

    jenis: JenisBukti
    judul: str
    isi: Optional[str] = None
    nama_file: Optional[str] = None
    waktu: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jenis": self.jenis, "judul": self.judul}
        if self.isi is not None:
            d["isi"] = self.isi
        if self.nama_file is not None:
            d["nama_file"] = self.nama_file
        if self.waktu is not None:
            d["waktu"] = self.waktu
        return d


@dataclass
class HasilMetode:
    """frontend: interface HasilMetode. Dikirim ke backend lewat /internal/.../results."""

    metode_id: str
    status: StatusHasil
    ringkasan: str = ""
    detail: str = ""
    bukti: list[Bukti] = field(default_factory=list)
    menunggu_tinjauan: bool = False
    durasi_ms: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "metode_id": self.metode_id,
            "status": self.status,
            "bukti": [b.to_dict() for b in self.bukti],
        }
        if self.ringkasan:
            d["ringkasan"] = self.ringkasan
        if self.detail:
            d["detail"] = self.detail
        if self.menunggu_tinjauan:
            d["menunggu_tinjauan"] = True
        if self.durasi_ms is not None:
            d["durasi_ms"] = self.durasi_ms
        return d


@dataclass
class TitikUji:
    """Pemetaan titik uji -> URL nyata pada aplikasi (frontend: PemetaanTitikUji)."""

    tersedia: bool
    url: str
    metode_http: str = "POST"
    catatan: Optional[str] = None


@dataclass
class FormTitikUji:
    """Template form untuk mengirim request ke suatu titik uji.

    Tidak ada di frontend; disusun backend dari onboarding aset agar worker
    tahu nama-nama field dan bagaimana mengenali keberhasilan.
    """

    # Field valid selain kata sandi (mis. nama/nrp/satuan_id/email untuk registrasi SATYA).
    field_dasar: dict[str, Any] = field(default_factory=dict)
    # Nama field kata sandi yang divariasikan uji.
    field_sandi: str = "password"
    # Field yang harus unik tiap percobaan agar penolakan bukan karena duplikasi (mis. email, nrp).
    field_unik: list[str] = field(default_factory=list)
    # Tipe body: json | form.
    tipe_body: Literal["json", "form"] = "json"
    # Status HTTP yang berarti "diterima" (akun kemungkinan terbuat).
    status_sukses: list[int] = field(default_factory=lambda: [200, 201, 202])
    # --- Form login (titik 'login') ---
    field_username: str = "email"
    field_password: str = "password"
    penanda_berhasil: str = ""
    penanda_gagal: str = ""
    # --- Form ubah kata sandi (titik 'ubah_password') ---
    field_lama: str = "current_password"
    field_baru: str = "new_password"
    # --- Form reset / lupa sandi (titik 'reset_password') ---
    field_identitas: str = "email"
    email: str = ""
    # --- Skema field (dari OpenAPI) untuk menyusun payload VALID: nama → {type, format, enum,
    # minLength, maxLength, minimum, pattern, example, required}. Lihat atribusi_sandi.payload_valid.
    skema_field: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Field konfirmasi sandi (diisi sama dengan sandi) & field token reset (titik reset_password_konfirmasi).
    field_konfirmasi: str = ""
    field_token: str = ""


@dataclass
class MetodeSpec:
    """Satu metode_pengujian dari katalog (subset yang dipakai AUTH-1.3)."""

    id: str
    check_id: str
    titik_uji: str
    nama: str = ""
    kriteria_lulus: str = ""
    butuh_autentikasi: bool = False
    profil: Literal["aman", "intrusif"] = "aman"
    engine: str = "custom"
    # parameter gabungan kontrol+metode: panjang_minimum, wajib: [...]
    parameter: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MetodeSpec":
        return cls(
            id=d["id"],
            check_id=d["check_id"],
            titik_uji=d["titik_uji"],
            nama=d.get("nama", ""),
            kriteria_lulus=d.get("kriteria_lulus", ""),
            butuh_autentikasi=bool(d.get("butuh_autentikasi", False)),
            profil=d.get("profil", "aman"),
            engine=d.get("engine", "custom"),
            parameter=dict(d.get("parameter", {})),
        )


@dataclass
class AkunUji:
    kunci: str
    username: str
    password: Optional[str] = None
    terisi: bool = False
    # Secret TOTP (base32) untuk MFA; bila ada, worker membangkitkan kode OTP sendiri.
    totp_secret: Optional[str] = None
    # Parameter TOTP dari URI otpauth (QR); default RFC 6238 umum.
    totp_digits: int = 6
    totp_period: int = 30
    totp_algoritma: str = "SHA1"


@dataclass
class Intrusif:
    """Izin & jendela uji berisiko (mis. penguncian akun)."""

    izinkan_penguncian: bool = False
    jendela_mulai: str = ""
    jendela_selesai: str = ""


@dataclass
class ScanContext:
    """Konteks satu scan yang diberikan backend ke worker.

    Dibentuk dari aset aplikasi (`GET /internal/scans/:id/context`): URL dasar,
    pemetaan titik uji, akun uji (kata sandi hanya di memori, tak dicatat), dan
    template form per titik uji.
    """

    scan_id: str
    aplikasi_id: str
    base_url: str
    # Hint URL spesifikasi OpenAPI untuk fase penemuan (opsional; bila kosong, worker mencari otomatis).
    openapi_url: str = ""
    titik_uji: dict[str, TitikUji] = field(default_factory=dict)
    form: dict[str, FormTitikUji] = field(default_factory=dict)
    akun_uji: list[AkunUji] = field(default_factory=list)
    intrusif: Intrusif = field(default_factory=Intrusif)
    # Inventaris & kandidat uji hasil discovery (diisi backend dari scan_targets.discovery).
    # Check hilir membacanya via `endpoints` / `kandidat_untuk(kode_fungsi)`.
    endpoints: list[dict[str, Any]] = field(default_factory=list)
    flows: list[dict[str, Any]] = field(default_factory=list)
    kandidat_uji: Optional[dict[str, Any]] = None
    # Kanal log langkah demi langkah ke UI (diisi runner saat eksekusi; tak diserialisasi).
    # Check memanggil `ctx.catat("info", "...")` untuk menarasikan prosesnya ke terminal.
    _log: Optional[Any] = field(default=None, compare=False, repr=False)
    # Metode yang sedang dijalankan (diisi runner) — dipakai peristiwa uji otomatis.
    _metode_aktif: str = field(default="", compare=False, repr=False)

    def catat(self, level: str, pesan: str) -> None:
        """Kirim satu baris log proses ke UI (best-effort; aman bila kanal tak ada)."""
        if self._log:
            try:
                self._log(level, pesan)
            except Exception:
                pass  # logging tak boleh menjatuhkan check

    def langkah(self, langkah: str, label: str, **detail: Any) -> None:
        """Peristiwa uji terstruktur: satu langkah check (siapkan_payload, periksa_skema, …)
        untuk animasi graf di UI. `detail` hanya metadata aman (lihat peristiwa_uji.payload_aman)."""
        if self._log:
            from . import peristiwa_uji as pu

            pu.pancar(self._log, self._metode_aktif, "langkah", f"  {label}", langkah=langkah, label=label[:200], detail=detail)

    def rekam_request(self, info: dict[str, Any]) -> None:
        """Hook `KlienScan` → peristiwa uji `request` (metode, URL, skema, status; tanpa nilai body)."""
        if self._log:
            from . import peristiwa_uji as pu

            status = info.get("status")
            akhir = f"HTTP {status}" if status is not None else f"gagal ({info.get('galat', '?')})"
            pu.pancar(self._log, self._metode_aktif, "request",
                      f"  → {info['metode_http']} {info['url']} · {akhir} ({info['durasi_ms']} ms)", **info)

    def url_titik(self, titik: str) -> Optional[str]:
        t = self.titik_uji.get(titik)
        if t is None or not t.tersedia or not t.url:
            return None
        return t.url

    def endpoint_titik(self, titik: str) -> Optional[dict[str, Any]]:
        """Endpoint inventaris discovery yang sama (metode + host + path) dengan titik uji."""
        from urllib.parse import urlsplit

        t = self.titik_uji.get(titik)
        if t is None or not t.url:
            return None
        sasaran = urlsplit(t.url)
        kunci = (t.metode_http.upper(), sasaran.netloc.lower(), sasaran.path.rstrip("/"))
        for ep in self.endpoints:
            u = urlsplit(str(ep.get("url") or ""))
            if (str(ep.get("metode_http") or "GET").upper(), u.netloc.lower(), u.path.rstrip("/")) == kunci:
                return ep
        return None

    def form_untuk(self, titik: str) -> Optional["FormTitikUji"]:
        """Template form titik uji. Bila belum dikonfigurasi (mis. hasil penemuan lama tanpa `forms`),
        disusun dari field body endpoint inventaris yang sama dengan titik uji."""
        f = self.form.get(titik)
        if f is not None and (titik != "registrasi" or f.field_dasar or f.skema_field):
            return f
        ep = self.endpoint_titik(titik)
        if not ep:
            return f
        from .discovery import templat_dari_field

        t = templat_dari_field(titik, list(ep.get("request_fields") or []), str(ep.get("content_type") or ""))
        if not t:
            return f
        bidang = FormTitikUji.__dataclass_fields__
        return FormTitikUji(**{k: v for k, v in t.items() if k in bidang})

    def akun(self, kunci: str) -> Optional[AkunUji]:
        """Akun uji berdasarkan kunci ('akun_uji_1'/'utama', 'penguncian'/'akun_uji_2')."""
        for a in self.akun_uji:
            if a.kunci == kunci and a.terisi:
                return a
        return None

    def kandidat_untuk(self, kode_fungsi: str) -> list[dict[str, Any]]:
        """Endpoint kandidat uji untuk suatu fungsi keamanan (mis. 'INPV', 'ACCS').

        Membaca `kandidat_uji.per_endpoint` hasil discovery; kosong bila belum ada.
        """
        if not self.kandidat_uji:
            return []
        kode = (kode_fungsi or "").upper()
        return [e for e in self.kandidat_uji.get("per_endpoint", []) if kode in (e.get("kategori") or [])]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScanContext":
        titik = {
            k: TitikUji(
                tersedia=bool(v.get("tersedia", False)),
                url=v.get("url", ""),
                metode_http=v.get("metode_http", "POST"),
                catatan=v.get("catatan"),
            )
            for k, v in (d.get("titik_uji") or {}).items()
        }
        form = {
            k: FormTitikUji(
                field_dasar=dict(v.get("field_dasar", {})),
                field_sandi=v.get("field_sandi", "password"),
                field_unik=list(v.get("field_unik", [])),
                tipe_body=v.get("tipe_body", "json"),
                status_sukses=list(v.get("status_sukses", [200, 201, 202])),
                field_username=v.get("field_username", "email"),
                field_password=v.get("field_password", "password"),
                penanda_berhasil=v.get("penanda_berhasil", ""),
                penanda_gagal=v.get("penanda_gagal", ""),
                field_lama=v.get("field_lama", "current_password"),
                field_baru=v.get("field_baru", "new_password"),
                field_identitas=v.get("field_identitas", "email"),
                email=v.get("email", ""),
                skema_field=dict(v.get("skema_field") or {}),
                field_konfirmasi=v.get("field_konfirmasi", "") or "",
                field_token=v.get("field_token", "") or "",
            )
            for k, v in (d.get("form") or {}).items()
        }
        akun = [
            AkunUji(
                kunci=a.get("kunci", ""),
                username=a.get("username", ""),
                password=a.get("password"),
                terisi=bool(a.get("terisi", False)),
                totp_secret=a.get("totp_secret") or None,
                totp_digits=int(a.get("totp_digits") or 6),
                totp_period=int(a.get("totp_period") or 30),
                totp_algoritma=str(a.get("totp_algoritma") or "SHA1").upper(),
            )
            for a in (d.get("akun_uji") or [])
        ]
        it = d.get("intrusif") or {}
        intrusif = Intrusif(
            izinkan_penguncian=bool(it.get("izinkan_penguncian", False)),
            jendela_mulai=it.get("jendela_mulai", ""),
            jendela_selesai=it.get("jendela_selesai", ""),
        )
        return cls(
            scan_id=d.get("scan_id", ""),
            aplikasi_id=d.get("aplikasi_id", ""),
            base_url=d.get("base_url", ""),
            openapi_url=d.get("openapi_url", ""),
            titik_uji=titik,
            form=form,
            akun_uji=akun,
            intrusif=intrusif,
            endpoints=list(d.get("endpoints") or []),
            flows=list(d.get("flows") or []),
            kandidat_uji=d.get("kandidat_uji") or None,
        )


class Pewaktu:
    """Pengukur durasi metode (ms)."""

    def __enter__(self) -> "Pewaktu":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.durasi_ms = int((time.perf_counter() - self._t0) * 1000)
