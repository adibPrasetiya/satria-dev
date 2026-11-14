import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { pilihEfektif } from './komponen.efektif.js';
import { peristiwaKomponen } from './komponen.events.js';
import { dariTeknologi, gabungUnik, uraiTeks } from './komponen.parser.js';
import { komponenRepository } from './komponen.repository.js';

const toDto = (k) => ({
  id: String(k.id),
  kategori: k.kategori,
  vendor: k.vendor,
  produk: k.produk,
  nama: k.nama,
  versi: k.versi,
  cpe: k.cpe,
  purl: k.purl,
  sumber: k.sumber,
  keyakinan: k.keyakinan,
  bukti: k.bukti,
  scan_id: k.scanId ? String(k.scanId) : null,
  terakhir_terlihat: k.terakhirTerlihat,
  dikenali: Boolean(k.vendor || k.purl),
  dipakai: Boolean(k.dipakai),
});

const TINGKAT = ['rendah', 'sedang', 'tinggi'];
const tingkatTerendah = (a, b) => TINGKAT[Math.min(TINGKAT.indexOf(a), TINGKAT.indexOf(b))];

const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

export { pilihEfektif };

export function createKomponenService({
  repository = komponenRepository,
  aplikasi = applicationsRepository,
  auditor = audit,
  peristiwa = peristiwaKomponen,
} = {}) {
  const berubah = (applicationId) => peristiwa.emit('berubah', applicationId);

  /** Sama dengan applications.service: aset di luar cakupan dijawab 404. */
  async function findVisible(actor, id) {
    const app = await aplikasi.findById(Number(id));
    if (!app || (!seesAll(actor) && String(app.unitId) !== actor.satuan_id)) {
      throw AppError.notFound('Aplikasi tidak ditemukan');
    }
    return app;
  }

  const bisaDiubah = (app) => {
    if (app.archivedAt) throw AppError.conflict('Aplikasi ini diarsipkan. Pulihkan dari daftar arsip lebih dulu.');
  };

  async function daftar(applicationId) {
    const items = pilihEfektif(await repository.listByApplication(applicationId)).map(toDto);
    const dipakai = items.filter((k) => k.dipakai);
    return {
      items,
      ringkasan: {
        produk: dipakai.length,
        dikenali: dipakai.filter((k) => k.dikenali).length,
        berversi: dipakai.filter((k) => k.versi).length,
      },
    };
  }

  return {
    async list(actor, applicationId) {
      const app = await findVisible(actor, applicationId);
      return daftar(app.id);
    },

    /**
     * Koreksi/tambahan manual dari teks ("nginx 1.18.0"). Komponen manual untuk produk yang sama ditimpa,
     * dan selalu mengalahkan isian formulir maupun hasil recon.
     */
    async tambahManual(actor, applicationId, { kategori, teks }) {
      const app = await findVisible(actor, applicationId);
      bisaDiubah(app);
      const [item] = uraiTeks(teks, kategori);
      if (!item) {
        throw AppError.badRequest('Data yang dikirim tidak valid', [
          { field: 'teks', message: 'Nama komponen tidak dikenali, contoh: "nginx 1.18.0"' },
        ]);
      }
      const row = await repository.upsert(app.id, 'manual', { ...item, kategori, keyakinan: 'tinggi', bukti: teks });
      auditor('komponen.manual', { aplikasiId: app.id, komponenId: row?.id, produk: item.produk, versi: item.versi });
      berubah(app.id);
      return daftar(app.id);
    },

    /** Hanya komponen manual yang dapat dihapus; sumber lain dibentuk ulang dari formulir/recon. */
    async hapus(actor, applicationId, komponenId) {
      const app = await findVisible(actor, applicationId);
      bisaDiubah(app);
      const row = await repository.findById(Number(komponenId));
      if (!row || row.applicationId !== app.id) throw AppError.notFound('Komponen tidak ditemukan');
      if (row.sumber !== 'manual') {
        throw AppError.conflict(
          'Komponen dari formulir atau hasil recon tidak dapat dihapus langsung. Ubah field teknologi aset, atau tambahkan koreksi manual.',
        );
      }
      await repository.hapus(row.id);
      auditor('komponen.hapus', { aplikasiId: app.id, komponenId: row.id, produk: row.produk });
      berubah(app.id);
      return daftar(app.id);
    },

    /** Sinkron field teknologi aset → komponen bersumber 'formulir' (dipanggil saat aset dibuat/diubah). */
    async sinkronFormulir(applicationId, teknologi) {
      const items = dariTeknologi(teknologi);
      await repository.gantiSumber(applicationId, 'formulir', items);
      berubah(applicationId);
      return items.length;
    },

    /**
     * Komponen hasil recon worker: item {sumber, kategori, teks, keyakinan, bukti} diurai dengan parser yang sama,
     * lalu tiap sumber yang dilaporkan diganti utuh (banner lama yang tak terlihat lagi ikut hilang).
     */
    async simpanRecon(applicationId, scanId, laporan) {
      const perSumber = new Map();
      for (const l of laporan) {
        const items = uraiTeks(l.teks, l.kategori ?? 'lainnya').map((it) => ({
          ...it,
          keyakinan: tingkatTerendah(it.keyakinan, l.keyakinan ?? 'sedang'),
          bukti: (l.bukti || l.teks).slice(0, 255),
        }));
        perSumber.set(l.sumber, [...(perSumber.get(l.sumber) ?? []), ...items]);
      }
      let total = 0;
      for (const [sumber, items] of perSumber) {
        const unik = gabungUnik(items);
        await repository.gantiSumber(applicationId, sumber, unik, { scanId });
        total += unik.length;
      }
      if (perSumber.size) berubah(applicationId);
      return total;
    },
  };
}

export const komponenService = createKomponenService();
