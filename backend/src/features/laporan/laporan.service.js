import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { scansRepository } from '../scans/scans.repository.js';
import { scansService } from '../scans/scans.service.js';
import { muatProvider } from './laporan.ai.js';
import { bangunPrompt, susunKonteks } from './laporan.konteks.js';
import { laporanRepository } from './laporan.repository.js';

const PRIORITAS = ['segera', 'tinggi', 'sedang', 'rendah'];
const teks = (v, maks = 2000) => (typeof v === 'string' ? v.trim().slice(0, maks) : '');

/** Rapikan & validasi keluaran AI: hanya rekomendasi untuk temuan yang ada, field terbatas. */
export function rapikanKeluaran(keluaran, idTemuan) {
  const ids = new Set(idTemuan);
  const sudah = new Set();
  const rekomendasi = [];
  for (const r of Array.isArray(keluaran?.rekomendasi) ? keluaran.rekomendasi : []) {
    const id = teks(r?.metode_id, 80);
    if (!ids.has(id) || sudah.has(id)) continue;
    sudah.add(id);
    rekomendasi.push({
      metode_id: id,
      judul: teks(r.judul, 160) || 'Perbaiki temuan',
      prioritas: PRIORITAS.includes(r.prioritas) ? r.prioritas : 'sedang',
      penjelasan: teks(r.penjelasan, 1200),
      langkah: (Array.isArray(r.langkah) ? r.langkah : []).map((l) => teks(l, 400)).filter(Boolean).slice(0, 8),
      verifikasi: teks(r.verifikasi, 600),
    });
  }
  return {
    ringkasan_eksekutif: teks(keluaran?.ringkasan_eksekutif, 6000),
    rekomendasi,
    rekomendasi_umum: (Array.isArray(keluaran?.rekomendasi_umum) ? keluaran.rekomendasi_umum : [])
      .map((x) => teks(x, 600))
      .filter(Boolean)
      .slice(0, 8),
  };
}

/**
 * Penyusun laporan AI. Laporan riwayat TERAKHIR (scan selesai terakhir aplikasi) disimpan di backend;
 * laporan riwayat lain selalu di-generate ulang dan tidak disimpan.
 */
export function createLaporanService({
  scans = scansService,
  scanRepo = scansRepository,
  apps = applicationsRepository,
  repository = laporanRepository,
  provider = () => muatProvider(),
  auditor = audit,
  sekarang = () => new Date(),
} = {}) {
  return {
    async generate(actor, scanId) {
      // Otorisasi (404 bila di luar cakupan) sekaligus DTO yang akan dikembalikan.
      const dto = await scans.get(actor, scanId);
      const scan = await scanRepo.findScanById(Number(scanId));
      if (scan.status === 'berjalan' || scan.status === 'antre') {
        throw AppError.badRequest('Laporan baru dapat dibuat setelah pengujian selesai');
      }
      const ai = provider();
      if (!ai) {
        throw new AppError(503, 'Layanan AI penyusun laporan belum dikonfigurasi', undefined, 'AI_TIDAK_AKTIF');
      }

      const [aplikasi, metode, acuan, akunUji, terakhir] = await Promise.all([
        apps.findById(scan.applicationId),
        repository.metodeScan(scan.id),
        repository.acuan(),
        repository.akunUji(scan.applicationId),
        repository.scanSelesaiTerakhir(scan.applicationId),
      ]);
      const konteks = susunKonteks({ aplikasi, scan, metode, akunUji, acuan });

      let keluaran;
      try {
        keluaran = await ai.tanyaJson(bangunPrompt(konteks));
      } catch (error) {
        throw new AppError(502, `AI gagal menyusun laporan: ${error.message}`, undefined, 'AI_GAGAL');
      }

      const disimpan = scan.status === 'selesai' && terakhir === Number(scan.id);
      const analisis = {
        ...rapikanKeluaran(keluaran, konteks.temuan.map((t) => t.metode_id)),
        provider: ai.nama,
        model: ai.model,
        dibuat_pada: sekarang().toISOString(),
        disamarkan: true,
      };
      if (disimpan) await repository.simpan(scan.applicationId, scan.id, analisis);
      auditor('laporan.generate', { scanId: String(scan.id), provider: ai.nama, disimpan });
      return { ...dto, ai: { ...analisis, disimpan } };
    },
  };
}

export const laporanService = createLaporanService();
