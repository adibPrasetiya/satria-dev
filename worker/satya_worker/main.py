"""Entri worker AUTH-1.3.

Mode LOOP (bawaan) — tersambung ke backend:
  python -m satya_worker.main
      Poll POST {BACKEND_URL}/internal/tasks/claim; untuk tiap task jalankan check
      lalu kirim hasil ke /internal/tasks/{id}/result. Berhenti rapi saat Ctrl+C.
      Butuh env: BACKEND_URL, WORKER_TOKEN (opsional: WORKER_ID, WORKER_ENGINES, POLL_INTERVAL,
      HEARTBEAT_INTERVAL). Thread heartbeat melapor status/tahap ke backend, memperpanjang lease
      task, dan menerima sinyal batal (lihat koordinasi.py).

Mode CONTEXT — uji lokal tanpa backend:
  python -m satya_worker.main --context ctx.json [--post]
      Baca ScanContext + daftar metode dari JSON, jalankan, cetak HasilMetode.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from . import keterjangkauan, koordinasi
from .backend_client import BackendClient
from .discovery import temukan
from .models import HasilMetode, MetodeSpec, ScanContext
from .runner import jalankan_metode


def muat_env() -> None:
    """Muat worker/.env (bila ada) ke os.environ. Baris 'KEY=VALUE'; '#' = komentar.
    Tidak menimpa variabel yang sudah diset di shell (shell menang)."""
    berkas = Path(__file__).resolve().parent.parent / ".env"
    try:
        isi = berkas.read_text(encoding="utf-8")
    except OSError:
        return  # .env tidak ada; pakai env shell saja
    for baris in isi.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, nilai = baris.partition("=")
        kunci = kunci.strip()
        nilai = nilai.strip().strip('"').strip("'")
        if kunci and kunci not in os.environ:
            os.environ[kunci] = nilai


def muat_context(path: str) -> tuple[ScanContext, list[MetodeSpec]]:
    with open(path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    ctx = ScanContext.from_dict(raw)
    metode = [MetodeSpec.from_dict(m) for m in raw.get("metode", [])]
    return ctx, metode


# --------------------------------------------------------------------------- loop


def proses_satu(backend: BackendClient, engines: list[str], detak: Optional["koordinasi.Detak"] = None) -> bool:
    """Klaim & proses satu task. Return True bila ada task diproses, False bila antrean kosong."""
    tugas = backend.claim(engines)
    if tugas is None:
        return False
    task_id = tugas["task_id"]
    ctx = ScanContext.from_dict(tugas["context"])
    metode = MetodeSpec.from_dict(tugas["metode"])
    koordinasi.STATUS.mulai_task(task_id, metode.id)
    if detak is not None:
        detak.segera()  # registry & lease langsung diperbarui
    _cetak(task_id, f"▶ {metode.id} ({metode.engine}) → {ctx.base_url}")
    pengawas: Optional[keterjangkauan.Pengawas] = None
    fase = _fase(metode)
    host = keterjangkauan.host_port(ctx.base_url)[0]
    try:
        # Preflight: target tak terjangkau (mis. IP worker diblokir) → akhiri task segera dengan
        # alasan jelas, alih-alih membiarkan tiap alat menunggu timeout-nya sendiri.
        koordinasi.set_tahap("cek keterjangkauan target")
        pf = keterjangkauan.preflight(ctx.base_url)
        if not pf.ok:
            _akhiri_tak_terjangkau(backend, task_id, metode, pf.alasan, lapisan=pf.lapisan or "tcp", awal=True, host=host)
            return True
        lapor = _lapor_thread(backend, task_id)
        if pf.waf:
            # Terjangkau, tetapi halaman utama sudah berupa penolakan WAF/rate-limit sejak awal.
            alasan = (f"Sejak awal {fase}, target membalas worker dengan {pf.waf}. Kemungkinan IP worker "
                      "dibatasi/diblokir WAF — hasil bisa tidak lengkap atau tidak mewakili aplikasi.")
            lapor("peringatan", alasan, keterjangkauan.peristiwa_terblokir(
                fase=fase, lapisan="http", alasan=alasan, fatal=False, awal=True, host=host, status=pf.status))
        pengawas = keterjangkauan.Pengawas(ctx.base_url, fase=fase, status_dasar=pf.status, lapor=lapor)
        pengawas.start()
        if metode.engine == "discovery":
            return proses_penemuan(backend, task_id, ctx, metode)
        return _proses_metode(backend, task_id, ctx, metode)
    finally:
        if pengawas is not None:
            pengawas.hentikan()
        koordinasi.STATUS.selesai_task()


def _fase(metode: MetodeSpec) -> str:
    return "recon" if metode.engine == "discovery" else "pengujian"


def _cetak(task_id: str, pesan: str) -> None:
    """Baris progres ke stderr (log PM2) dengan cap waktu — agar operator bisa melihat posisi task."""
    print(f"{datetime.now():%H:%M:%S} [task {task_id}] {pesan}", file=sys.stderr, flush=True)


def _lapor_thread(backend: BackendClient, task_id: str) -> Any:
    """Callback log yang aman dipanggil dari thread lain (pengawas): klien HTTP sendiri per panggilan
    (httpx.Client tak dibagi antar-thread). Dipanggil sangat jarang (≤1× per task)."""

    def lapor(level: str, pesan: str, data: Optional[dict[str, Any]] = None) -> None:
        _cetak(task_id, f"{level.upper()}: {pesan}")
        try:
            with backend.salin() as b:
                b.kirim_log(task_id, level, pesan, data)
        except Exception:
            pass

    return lapor


def _akhiri_tak_terjangkau(backend: BackendClient, task_id: str, metode: MetodeSpec, alasan: str,
                           *, lapisan: str = "tcp", awal: bool = False, host: str = "") -> None:
    """Laporkan task sebagai tidak dapat diverifikasi karena target tak terjangkau dari worker.

    Selain log `galat`, dipancarkan peristiwa `terblokir` (fatal) agar UI menampilkan keterangan
    blokir yang menonjol (bukan sekadar satu baris di antara log)."""
    fase = _fase(metode)
    nama = "Recon" if fase == "recon" else "Pengujian"
    pembuka = (f"{nama} tidak dijalankan: target tidak terjangkau dari worker" if awal
               else f"{nama} dihentikan: target berhenti merespons worker")
    alasan = alasan.rstrip(".") + "."
    ringkasan = f"{pembuka} — {alasan} {keterjangkauan.saran_whitelist()}"
    try:
        backend.kirim_log(task_id, "galat", ringkasan, keterjangkauan.peristiwa_terblokir(
            fase=fase, lapisan="dns" if "DNS" in alasan else lapisan, alasan=alasan,
            fatal=True, awal=awal, host=host))
    except Exception:
        pass
    backend.kirim_hasil(task_id, {"metode_id": metode.id, "status": "tidak_dapat_diverifikasi", "ringkasan": ringkasan, "bukti": []})
    _cetak(task_id, f"[TIDAK_DAPAT_DIVERIFIKASI] {metode.id}  {ringkasan}")


def _proses_metode(backend: BackendClient, task_id: str, ctx: ScanContext, metode: MetodeSpec) -> bool:
    """Jalankan satu metode uji (engine custom/zap/playwright) lalu kirim hasilnya."""

    def log_ke_ui(level: str, pesan: str, data: Optional[dict[str, Any]] = None) -> None:
        # `data` = peristiwa uji terstruktur untuk animasi pengujian (lihat peristiwa_uji.py).
        backend.kirim_log(task_id, level, pesan, data)

    def unggah_gambar(gambar_png: bytes) -> Optional[str]:
        return backend.unggah_gambar(ctx.scan_id, gambar_png)

    try:
        koordinasi.periksa_batal()
        # Baris "▶ metode" kini dipancarkan runner sebagai peristiwa uji `mulai`.
        hasil = jalankan_metode(ctx, metode, log=log_ke_ui, unggah=unggah_gambar)
        backend.kirim_hasil(task_id, hasil.to_dict())
        print(f"[{hasil.status.upper():24}] {metode.id}  {hasil.ringkasan}", file=sys.stderr)
    except koordinasi.TargetTakTerjangkau as e:
        _akhiri_tak_terjangkau(backend, task_id, metode, e.alasan, host=keterjangkauan.host_port(ctx.base_url)[0])
    except koordinasi.Dibatalkan:
        backend.kirim_hasil(task_id, {"metode_id": metode.id, "status": "tidak_dapat_diverifikasi", "ringkasan": "Dihentikan: pengujian dibatalkan.", "bukti": []})
    except Exception as e:  # jangan sampai satu task menjatuhkan worker
        print(f"Galat memproses {metode.id}: {type(e).__name__}: {e}", file=sys.stderr)
        backend.kirim_hasil(
            task_id,
            {
                "metode_id": metode.id,
                "status": "tidak_dapat_diverifikasi",
                "ringkasan": f"Galat worker: {type(e).__name__}",
                "bukti": [],
            },
        )
    return True


def proses_penemuan(backend: BackendClient, task_id: str, ctx: ScanContext, metode: MetodeSpec) -> bool:
    """Fase penemuan (engine discovery): crawl base_url, kirim hasil ke backend
    (yang menyemai task pengujian), lalu tandai task penemuan selesai."""
    def log_ke_ui(level: str, pesan: str, data: Optional[dict[str, Any]] = None) -> None:
        # `data` = peristiwa terstruktur untuk visualisasi penemuan (lihat peristiwa.py).
        backend.kirim_log(task_id, level, pesan, data)
        # Tahap & peringatan juga ke log PM2 agar progres recon terlihat dari server.
        if (data or {}).get("jenis") == "tahap" or level in ("peringatan", "galat"):
            _cetak(task_id, f"{'' if level == 'info' else level.upper() + ': '}{pesan}")

    try:
        penemuan = temukan(ctx.base_url, openapi_url=ctx.openapi_url or None, ctx=ctx, log=log_ke_ui)
        data = backend.kirim_penemuan(ctx.scan_id, penemuan)
        disemai = data.get("disemai", 0)
        rk = penemuan["ringkasan"]
        titik = ", ".join(rk["titik_ditemukan"]) or "tidak ada"
        auth = " (terautentikasi)" if rk.get("terautentikasi") else ""
        ringkasan = (
            f"Penemuan selesai{auth}: {rk['jumlah_halaman']} halaman, "
            f"{rk.get('jumlah_endpoint_unik', 0)} endpoint unik, {len(rk.get('flows', []))} alur bisnis, "
            f"titik uji terdeteksi [{titik}], {disemai} metode disemai."
        )
        hasil = HasilMetode(metode_id=metode.id, status="lulus", ringkasan=ringkasan)
    except koordinasi.TargetTakTerjangkau as e:
        _akhiri_tak_terjangkau(backend, task_id, metode, e.alasan, host=keterjangkauan.host_port(ctx.base_url)[0])
        return True
    except koordinasi.Dibatalkan:
        backend.kirim_log(task_id, "peringatan", "Penemuan dihentikan: pengujian dibatalkan pengguna.")
        hasil = HasilMetode(metode_id=metode.id, status="tidak_dapat_diverifikasi", ringkasan="Penemuan dihentikan karena pengujian dibatalkan.")
    except Exception as e:  # penemuan gagal → task selesai dengan catatan
        hasil = HasilMetode(
            metode_id=metode.id,
            status="tidak_dapat_diverifikasi",
            ringkasan=f"Fase penemuan gagal: {type(e).__name__}: {e}",
        )
    backend.kirim_hasil(task_id, hasil.to_dict())
    print(f"[{hasil.status.upper():24}] {metode.id}  {hasil.ringkasan}", file=sys.stderr)
    return True


def jalankan_loop() -> int:
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:3000/api/v1")
    token = os.environ.get("WORKER_TOKEN", "")
    worker_id = os.environ.get("WORKER_ID", f"worker-{os.getpid()}")
    engines = [e.strip() for e in os.environ.get("WORKER_ENGINES", "custom,discovery,zap").split(",") if e.strip()]
    poll = float(os.environ.get("POLL_INTERVAL", "2"))

    if not token:
        print("WORKER_TOKEN wajib diisi untuk mode loop.", file=sys.stderr)
        return 1

    berhenti = {"minta": False}

    def _stop(*_: object) -> None:
        berhenti["minta"] = True
        print("\nBerhenti setelah task berjalan selesai…", file=sys.stderr)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(f"Worker {worker_id} siap (engines={engines}) → {backend_url}", file=sys.stderr)
    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "10"))
    # Heartbeat memakai klien HTTP terpisah (thread sendiri).
    with BackendClient(backend_url, token, worker_id=worker_id) as backend,             BackendClient(backend_url, token, worker_id=worker_id) as klien_detak:
        detak = koordinasi.Detak(klien_detak, engines, interval=interval)
        detak.start()
        while not berhenti["minta"]:
            try:
                ada = proses_satu(backend, engines, detak)
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                print(f"Gagal berkomunikasi dengan backend: {e}; coba lagi dalam {poll}s", file=sys.stderr)
                time.sleep(poll)
                continue
            if not ada:
                time.sleep(poll)  # antrean kosong
        detak.hentikan()
        backend.berhenti()
    return 0


# --------------------------------------------------------------------------- context


def jalankan_context(path: str, post: bool) -> int:
    ctx, metode_list = muat_context(path)
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:3000/api/v1")
    token = os.environ.get("WORKER_TOKEN", "")

    keluar: list[dict[str, Any]] = []
    for metode in metode_list:
        hasil = jalankan_metode(ctx, metode)
        d = hasil.to_dict()
        keluar.append(d)
        print(f"[{hasil.status.upper():24}] {metode.id}  {hasil.ringkasan}", file=sys.stderr)
        if post:
            if not token:
                print("WORKER_TOKEN kosong; lewati pengiriman.", file=sys.stderr)
            else:
                # Mode context tak punya task_id; hanya untuk uji manual terhadap backend lama.
                print("Mode --post tidak didukung tanpa task_id; gunakan mode loop.", file=sys.stderr)

    json.dump(keluar, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    muat_env()  # isi env dari worker/.env bila ada (tidak menimpa env shell)
    p = argparse.ArgumentParser(description="Worker pengujian SATYA — AUTH-1.3")
    p.add_argument("--context", help="Uji lokal: berkas JSON ScanContext + metode (tanpa backend)")
    p.add_argument("--post", action="store_true", help="(mode context) — tidak dipakai lagi")
    args = p.parse_args(argv)

    if args.context:
        return jalankan_context(args.context, args.post)
    return jalankan_loop()


if __name__ == "__main__":
    raise SystemExit(main())
