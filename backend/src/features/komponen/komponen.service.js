import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { dariTeknologi, uraiTeks } from './komponen.parser.js';
import { komponenRepository } from './komponen.repository.js';

// Urutan kepercayaan antarsumber untuk produk yang sama. 'manual' selalu menang; di luar itu
// baris yang memiliki versi didahulukan (bukti recon berversi lebih berguna dari isian tanpa versi).
const PERINGKAT_SUMBER = ['manual', 'formulir', 'nuclei', 'banner', 'bundle_js', 'tls'];

const kunciProduk = (k) => `${k.vendor ?? ''}|${k.produk}`;

/** Tandai satu baris "dipakai" per produk — baris inilah yang nanti dicocokkan ke CVE. */
export function pilihEfektif(rows) {
  const terbaik = new Map();
  const skor = (k) => [k.sumber === 'manual' ? 0 : 1, k.versi ? 0 : 1, PERINGKAT_SUMBER.indexOf(k.sumber)];
  const lebihBaik = (a, b) => {
    const [x, y] = [skor(a), skor(b)];
    for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i];
    return false;
  };
  for (const r of rows) {
    const kunci = kunciProduk(r);
    if (!terbaik.has(kunci) || lebihBaik(r, terbaik.get(kunci))) terbaik.set(kunci, r);
  }
  const dipakai = new Set([...terbaik.values()].map((r) => r.id));
  return rows.map((r) => ({ ...r, dipakai: dipakai.has(r.id) }));
}

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

const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

export function createKomponenService({ repository = komponenRepository, aplikasi = applicationsRepository, auditor = audit } = {}) {
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
      return daftar(app.id);
    },

    /** Sinkron field teknologi aset → komponen bersumber 'formulir' (dipanggil saat aset dibuat/diubah). */
    async sinkronFormulir(applicationId, teknologi) {
      const items = dariTeknologi(teknologi);
      await repository.gantiSumber(applicationId, 'formulir', items);
      return items.length;
    },
  };
}

export const komponenService = createKomponenService();
