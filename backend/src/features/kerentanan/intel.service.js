// Orkestrator sinkron intel kerentanan: NVD (per produk inventaris + inkremental) → KEV → OSV → pencocokan
// → EPSS → pencocokan ulang (prioritas) → notifikasi. Dipakai CLI `cve:sync` (PM2 terjadwal) dan tombol admin.
import { env } from '../../config/env.js';
import { errorMessage } from '../../utils/errorMessage.js';
import { logger } from '../../utils/logger.js';
import { cpeTerkait } from '../komponen/komponen.parser.js';
import { dariNvd, dariOsv } from './intel.normalisasi.js';
import { intelRepository } from './intel.repository.js';
import * as sumberBawaan from './intel.sumber.js';
import { kerentananService } from './kerentanan.service.js';

const KUNCI_GLOBAL = 'sinkron:global';
const HARI = 24 * 60 * 60 * 1000;

export function createIntelService({ repository = intelRepository, sumber = sumberBawaan, pencocok = kerentananService } = {}) {
  const log = (pesan, data) => logger.info(`[intel CVE] ${pesan}`, data);

  /** Jalankan langkah; galat dicatat di status kunci tersebut tanpa menghentikan langkah lain. */
  async function langkah(kunci, fn) {
    try {
      const hasil = await fn();
      return { kunci, ok: true, ...hasil };
    } catch (error) {
      const pesan = errorMessage(error);
      logger.warn(`[intel CVE] ${kunci} gagal: ${pesan}`);
      await repository.catatStatus(kunci, { status: 'gagal', pesan }).catch(() => {});
      return { kunci, ok: false, pesan };
    }
  }

  /** Semua pasangan CPE (beserta kerabat kamus) dari produk inventaris. */
  async function pasanganInventaris() {
    const peta = new Map();
    for (const { vendor, produk } of await repository.produkInventaris()) {
      const { bagian, pasangan } = cpeTerkait(vendor, produk);
      for (const [v, p] of pasangan) peta.set(`${v}:${p}`, { bagian, vendor: v, produk: p });
    }
    return [...peta.values()];
  }

  /** Backfill NVD untuk produk yang belum pernah disinkron (riwayat lengkap per produk). */
  async function backfillProduk(pasangan) {
    let produk = 0;
    let jumlah = 0;
    for (const { bagian, vendor, produk: nama } of pasangan) {
      const kunci = `nvd:produk:${vendor}:${nama}`;
      if ((await repository.status(kunci))?.status === 'berhasil') continue;
      const r = await langkah(kunci, async () => {
        let n = 0;
        for await (const halaman of sumber.nvdPerProduk(bagian, vendor, nama)) {
          const rows = halaman.map(dariNvd).filter(Boolean);
          await repository.simpanNvd(rows);
          n += rows.length;
        }
        await repository.catatStatus(kunci, { status: 'berhasil', kursor: new Date(), pesan: `${n} CVE` });
        return { jumlah: n };
      });
      produk += 1;
      jumlah += r.jumlah ?? 0;
      await sumber.jedaAntarPermintaanNvd();
    }
    if (produk) log(`backfill ${produk} produk baru: ${jumlah} CVE`);
    return { produk, jumlah };
  }

  /**
   * Perubahan NVD sejak kursor (jendela ≤ 120 hari). Hanya CVE yang menyentuh produk inventaris — atau yang
   * sudah ada di tabel lokal — yang disimpan, agar basis data tetap kecil.
   */
  async function inkremental(pasangan) {
    const kunci = 'nvd:inkremental';
    const st = await repository.status(kunci);
    const sekarang = new Date();
    // Pertama kali: riwayat sudah dicakup backfill per produk → mulai dari sekarang.
    if (!st?.kursor) {
      await repository.catatStatus(kunci, { status: 'berhasil', kursor: sekarang, pesan: 'kursor awal' });
      return { jumlah: 0 };
    }
    const relevan = new Set(pasangan.map((p) => `${p.vendor}:${p.produk}`));
    let dari = new Date(st.kursor.getTime() - 60 * 60 * 1000); // tumpang 1 jam agar tak ada yang terlewat
    let jumlah = 0;
    while (dari < sekarang) {
      const sampai = new Date(Math.min(sekarang.getTime(), dari.getTime() + (sumber.NVD_MAKS_HARI - 1) * HARI));
      for await (const halaman of sumber.nvdBerubah(dari, sampai)) {
        const rows = halaman.map(dariNvd).filter(Boolean);
        const ada = await repository.idCveAda(rows.map((r) => r.cve.id));
        const simpan = rows.filter((r) => ada.has(r.cve.id) || r.cpe.some((c) => relevan.has(`${c.vendor}:${c.produk}`)));
        await repository.simpanNvd(simpan);
        jumlah += simpan.length;
      }
      await repository.catatStatus(kunci, { status: 'berhasil', kursor: sampai, pesan: `${jumlah} CVE diperbarui` });
      dari = sampai;
      await sumber.jedaAntarPermintaanNvd();
    }
    log(`inkremental: ${jumlah} CVE relevan berubah`);
    return { jumlah };
  }

  async function kev({ paksa }) {
    const st = await repository.status('kev');
    if (!paksa && st?.status === 'berhasil' && Date.now() - new Date(st.updatedAt).getTime() < 20 * 60 * 60 * 1000) {
      return { dilewati: true };
    }
    const entri = await sumber.ambilKev();
    const n = await repository.terapkanKev(entri);
    await repository.catatStatus('kev', { status: 'berhasil', kursor: new Date(), pesan: `${entri.length} entri katalog, ${n} relevan` });
    log(`KEV: ${n} CVE lokal dieksploitasi aktif`);
    return { jumlah: n };
  }

  /** OSV untuk paket berversi di inventaris (diperbarui per paket@versi tiap ±24 jam). */
  async function osv({ paksa }) {
    if (!env.cve.osvEnabled) return { dilewati: true };
    const purls = [];
    for (const purl of await repository.paketInventaris()) {
      const st = await repository.status(`osv:${purl}`);
      const segar = st?.status === 'berhasil' && Date.now() - new Date(st.updatedAt).getTime() < 20 * 60 * 60 * 1000;
      if (paksa || !segar) purls.push(purl);
    }
    if (!purls.length) return { jumlah: 0 };
    const hasil = await sumber.osvQueryBatch(purls);
    let jumlah = 0;
    for (let i = 0; i < purls.length; i++) {
      const purl = purls[i];
      const at = purl.lastIndexOf('@');
      const [dasar, versi] = [purl.slice(0, at), decodeURIComponent(purl.slice(at + 1))];
      await repository.resetPaket(dasar, versi);
      for (const id of hasil[i] ?? []) {
        const c = dariOsv(await sumber.osvVuln(id));
        if (!c) continue;
        await repository.simpanOsv(c, dasar, versi);
        jumlah += 1;
      }
      await repository.catatStatus(`osv:${purl}`, { status: 'berhasil', kursor: new Date(), pesan: `${(hasil[i] ?? []).length} advisory` });
    }
    log(`OSV: ${purls.length} paket diperiksa, ${jumlah} advisory`);
    return { jumlah };
  }

  async function epss({ semua }) {
    const ids = await repository.idUntukEpss({ semua });
    if (!ids.length) return { jumlah: 0 };
    const data = await sumber.ambilEpss(ids);
    await repository.terapkanEpss(data);
    await repository.catatStatus('epss', { status: 'berhasil', kursor: new Date(), pesan: `${data.length} skor` });
    return { jumlah: data.length };
  }

  return {
    /**
     * Sinkron lengkap. `ringan`: hanya backfill produk baru, OSV yang basi, EPSS yang kosong, dan pencocokan
     * (dipakai setelah komponen aset berubah). Mengembalikan null bila sinkron lain sedang berjalan.
     */
    async sinkron({ ringan = false, paksa = false } = {}) {
      if (!env.cve.syncEnabled) return { dinonaktifkan: true };
      if (!(await repository.ambilKunci(KUNCI_GLOBAL))) return null;
      const mulai = Date.now();
      const langkahLangkah = [];
      try {
        const pasangan = await pasanganInventaris();
        langkahLangkah.push(await langkah('nvd:backfill', () => backfillProduk(pasangan)));
        if (!ringan) langkahLangkah.push(await langkah('nvd:inkremental', () => inkremental(pasangan)));
        langkahLangkah.push(await langkah('kev', () => kev({ paksa: paksa && !ringan })));
        langkahLangkah.push(await langkah('osv', () => osv({ paksa })));
        langkahLangkah.push(await langkah('epss', () => epss({ semua: !ringan })));
        const cocok = await langkah('pencocokan', () => pencocok.cocokkanSemua());
        langkahLangkah.push(cocok);
        langkahLangkah.push(await langkah('notifikasi', async () => ({ jumlah: await pencocok.notifikasi() })));
        const gagal = langkahLangkah.filter((l) => !l.ok);
        const ringkas = `${gagal.length ? `${gagal.length} langkah gagal (${gagal.map((g) => g.kunci).join(', ')}); ` : ''}${
          cocok.kecocokanBaru ?? 0
        } kecocokan baru · ${Math.round((Date.now() - mulai) / 1000)} dtk`;
        await repository.catatStatus(KUNCI_GLOBAL, { status: gagal.length ? 'gagal' : 'berhasil', kursor: new Date(), pesan: ringkas });
        log(`selesai: ${ringkas}`);
        return { langkah: langkahLangkah, ringkasan: ringkas };
      } catch (error) {
        await repository.catatStatus(KUNCI_GLOBAL, { status: 'gagal', pesan: errorMessage(error) });
        throw error;
      }
    },

    /** Status sinkron untuk UI admin. */
    async status() {
      const rows = await repository.semuaStatus();
      const ambil = (k) => rows.find((r) => r.kunci === k) ?? null;
      const ringkas = (r) => (r ? { status: r.status, pesan: r.pesan, kursor: r.kursor, diperbarui: r.updatedAt } : null);
      return {
        aktif: env.cve.syncEnabled,
        kunci_nvd: Boolean(env.cve.nvdApiKey),
        osv: env.cve.osvEnabled,
        global: ringkas(ambil(KUNCI_GLOBAL)),
        nvd: ringkas(ambil('nvd:inkremental')),
        kev: ringkas(ambil('kev')),
        epss: ringkas(ambil('epss')),
        produk: rows
          .filter((r) => r.kunci.startsWith('nvd:produk:'))
          .map((r) => ({ produk: r.kunci.slice('nvd:produk:'.length), ...ringkas(r) })),
      };
    },
  };
}

export const intelService = createIntelService();

