import { logger } from '../../utils/logger.js';
import { hitungTemuan, nilaiKelaikan } from './verdict.js';
import { verdictRepository } from './verdict.repository.js';

/** Kelompokkan baris (kontrol × metode) menjadi kontrol beserta daftar metodenya. */
function kelompokkanKontrol(rows) {
  const perKontrol = new Map();
  for (const r of rows) {
    const k = perKontrol.get(r.controlCode) ?? { severity: r.controlSeverity, aggregation: r.aggregation, methods: [] };
    if (r.methodCode) k.methods.push({ code: r.methodCode, severity: r.methodSeverity });
    perKontrol.set(r.controlCode, k);
  }
  return [...perKontrol.values()];
}

/**
 * Menghitung & menyimpan ringkasan penilaian per scan selesai (putusan, skor, jumlah temuan per
 * severity) di tabel scans, dipakai daftar aplikasi untuk filter & urut di DB.
 */
export function createVerdictService({ repository = verdictRepository, log = logger } = {}) {
  async function nilaiBanyak(scanIds) {
    if (!scanIds.length) return 0;
    const [kontrol, hasil] = await Promise.all([repository.controls(), repository.taskResults(scanIds)]);
    const katalog = kelompokkanKontrol(kontrol);
    const perScan = new Map(scanIds.map((id) => [Number(id), []]));
    for (const h of hasil) perScan.get(Number(h.scanId))?.push(h);
    for (const [scanId, baris] of perScan) {
      const { putusan, skor } = nilaiKelaikan(katalog, new Map(baris.map((h) => [h.methodCode, h.status])));
      await repository.saveSummary(scanId, { verdict: putusan, score: skor, temuan: hitungTemuan(baris) });
    }
    return perScan.size;
  }

  return {
    /** Hitung ringkasan satu scan (dipanggil saat scan selesai). */
    nilaiScan: (scanId) => nilaiBanyak([scanId]),

    /**
     * Isi ringkasan scan selesai yang belum punya (data lama sebelum kolom ada, atau perhitungan sempat
     * gagal). Dipanggil sebelum daftar aplikasi dimuat; bila semua sudah terisi hanya satu query kosong.
     */
    async lengkapiYangKosong(batas = 200) {
      try {
        return await nilaiBanyak(await repository.finishedWithoutVerdict(batas));
      } catch (error) {
        log.warn('Gagal melengkapi putusan scan', { error: error.message });
        return 0;
      }
    },
  };
}

export const verdictService = createVerdictService();
