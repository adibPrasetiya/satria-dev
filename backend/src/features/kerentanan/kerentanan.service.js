import { env } from '../../config/env.js';
import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { emailKerentanan } from '../../utils/emailTemplate.js';
import { logger } from '../../utils/logger.js';
import { sendMail } from '../../utils/mailer.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { pilihEfektif } from '../komponen/komponen.efektif.js';
import { cpeTerkait } from '../komponen/komponen.parser.js';
import { kerentananRepository } from './kerentanan.repository.js';
import { evaluasiKomponen, hitungPrioritas, layakTanpaVersi, tingkatPrioritas } from './pencocokan.js';

const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';
const angka = (v) => (v === null || v === undefined ? null : Number(v));
const jsonArr = (v) => (Array.isArray(v) ? v : typeof v === 'string' ? JSON.parse(v || '[]') : []);

const toDto = (r) => ({
  id: String(r.id),
  aplikasi: { id: String(r.applicationId), nama: r.aplikasi, satuan: r.satuan, lingkungan: r.environment },
  komponen: { vendor: r.vendor, produk: r.produk, nama: r.namaKomponen, versi: r.versi, sumber: r.sumberKomponen },
  cve: {
    id: r.cveId,
    ringkasan: r.ringkasan,
    dipublikasi_pada: r.dipublikasiPada,
    diubah_pada: r.diubahPada,
    cvss: angka(r.cvssSkor),
    cvss_vektor: r.cvssVektor,
    severitas: r.severitas,
    cwe: jsonArr(r.cwe),
    referensi: jsonArr(r.referensi),
    status_analisis: r.statusAnalisis,
    kev: Boolean(r.kev),
    kev_ditambahkan: r.kevDitambahkan,
    kev_tenggat: r.kevTenggat,
    kev_ransomware: Boolean(r.kevRansomware),
    epss: angka(r.epss),
    epss_persentil: angka(r.epssPersentil),
    sumber: r.sumberCve,
    tautan: r.cveId.startsWith('CVE-') ? `https://nvd.nist.gov/vuln/detail/${r.cveId}` : `https://osv.dev/vulnerability/${r.cveId}`,
  },
  status: r.status,
  alasan: r.alasan,
  prioritas: r.prioritas,
  tingkat: tingkatPrioritas(r.prioritas, Boolean(r.kev)),
  catatan: r.catatan,
  ditangani_oleh: r.ditanganiNama ?? null,
  ditangani_pada: r.ditanganiPada,
  pertama_ditemukan: r.pertamaDitemukan,
  terakhir_dievaluasi: r.terakhirDievaluasi,
});

export function createKerentananService({
  repository = kerentananRepository,
  aplikasi = applicationsRepository,
  auditor = audit,
  kirimEmail = sendMail,
} = {}) {
  async function findVisible(actor, id) {
    const app = await aplikasi.findById(Number(id));
    if (!app || (!seesAll(actor) && String(app.unitId) !== actor.satuan_id)) throw AppError.notFound('Aplikasi tidak ditemukan');
    return app;
  }

  /** Cocokkan komponen sekumpulan aplikasi ke CVE lokal → simpan hasil. Mengembalikan jumlah kecocokan baru. */
  async function cocokkan(applicationIds) {
    const semua = pilihEfektif(await repository.komponenAplikasi(applicationIds)).filter((k) => k.dipakai);
    const perAplikasi = new Map(applicationIds.map((id) => [id, []]));
    for (const k of semua) perAplikasi.get(k.applicationId)?.push(k);

    // Data CVE dimuat sekali untuk semua produk/paket yang terlibat.
    const pasangan = new Map();
    for (const k of semua) for (const p of cpeTerkait(k.vendor, k.produk).pasangan) pasangan.set(p.join(':'), p);
    const purlBerversi = [...new Set(semua.filter((k) => k.purl?.includes('@')).map((k) => k.purl))];
    const [cpeRows, paketRows] = await Promise.all([repository.cpeUntukPasangan([...pasangan.values()]), repository.paketUntuk(purlBerversi)]);

    const cpePerPasangan = new Map();
    for (const r of cpeRows) {
      const kunci = `${r.vendor}:${r.produk}`;
      cpePerPasangan.set(kunci, [...(cpePerPasangan.get(kunci) ?? []), r]);
    }
    const paketPerPurl = new Map();
    for (const r of paketRows) {
      const kunci = `${r.purl}@${r.versi}`;
      paketPerPurl.set(kunci, [...(paketPerPurl.get(kunci) ?? []), r]);
    }

    let baru = 0;
    const waktu = new Date();
    for (const [applicationId, komponen] of perAplikasi) {
      const hasil = [];
      for (const k of komponen) {
        const rows = cpeTerkait(k.vendor, k.produk).pasangan.flatMap((p) => cpePerPasangan.get(p.join(':')) ?? []);
        const evaluasi = evaluasiKomponen(k, rows, paketPerPurl.get(k.purl) ?? []);
        for (const [cveId, e] of evaluasi) hasil.push({ k, cveId, ...e });
      }
      const info = await repository.infoCve([...new Set(hasil.map((h) => h.cveId))]);
      const app = komponen[0] ?? {};
      const relevan = hasil.filter((h) => h.k.versi || layakTanpaVersi(info.get(h.cveId), waktu));
      const baris = relevan.map(({ k, cveId, status, alasan }) => ({
        cveId,
        vendor: k.vendor,
        produk: k.produk,
        namaKomponen: k.nama,
        versi: k.versi,
        sumberKomponen: k.sumber,
        status,
        alasan,
        prioritas: hitungPrioritas(info.get(cveId) ?? {}, status, app),
      }));
      const lama = await repository.kunciHasil(applicationId);
      baru += baris.filter((b) => !lama.has(`${b.cveId}|${b.produk}`)).length;
      await repository.simpanHasil(applicationId, baris, waktu);
    }
    return { aplikasi: perAplikasi.size, kecocokanBaru: baru };
  }

  return {
    cocokkanAplikasi: (applicationId) => cocokkan([Number(applicationId)]),

    async cocokkanSemua() {
      const ids = await repository.idAplikasiAktif();
      return ids.length ? cocokkan(ids) : { aplikasi: 0, kecocokanBaru: 0 };
    },

    /** Daftar kecocokan lintas aset (pemilik: aset satuannya saja). */
    async list(actor, { page, limit, aplikasi_id, status, kev, severitas, search, sort }) {
      const filters = {
        unitId: seesAll(actor) ? undefined : Number(actor.satuan_id),
        applicationId: aplikasi_id ? Number(aplikasi_id) : undefined,
        status: status ? status.split(',') : undefined,
        kev,
        severitas,
        search,
      };
      if (filters.applicationId) await findVisible(actor, filters.applicationId);
      const [{ rows, total }, ringkasan] = await Promise.all([
        repository.list({ ...filters, offset: (page - 1) * limit, limit, sort }),
        repository.ringkasan({ unitId: filters.unitId, applicationId: filters.applicationId }),
      ]);
      return { items: rows.map(toDto), meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)), ringkasan } };
    },

    async ringkasan(actor) {
      return repository.ringkasan({ unitId: seesAll(actor) ? undefined : Number(actor.satuan_id) });
    },

    /** Tandai ditangani/dikecualikan (wajib catatan) atau kembalikan ke evaluasi otomatis ('buka'). */
    async ubahStatus(actor, id, { status, catatan }) {
      const row = await repository.findById(Number(id));
      if (!row || (!seesAll(actor) && String(row.unitId) !== actor.satuan_id)) throw AppError.notFound('Kerentanan tidak ditemukan');
      // 'buka' = serahkan lagi ke pencocokan otomatis; status sementara 'kemungkinan' sampai evaluasi berikutnya.
      const baru = status === 'buka' ? 'kemungkinan' : status;
      await repository.ubahStatus(row.id, { status: baru, catatan: status === 'buka' ? null : catatan, oleh: Number(actor.id) });
      auditor('kerentanan.status', { id: row.id, aplikasiId: row.applicationId, cve: row.cveId, dari: row.status, ke: baru, oleh: actor.id });
      if (status === 'buka') await cocokkan([row.applicationId]);
      return toDto(await repository.findById(row.id));
    },

    /** Email ke pemilik aset untuk kecocokan mendesak yang belum diberitahukan (dikelompokkan per aplikasi). */
    async notifikasi() {
      if (!env.cve.notifEmail) return 0;
      const rows = await repository.untukNotifikasi();
      const perAplikasi = new Map();
      for (const r of rows) perAplikasi.set(r.applicationId, [...(perAplikasi.get(r.applicationId) ?? []), r]);
      let terkirim = 0;
      for (const [applicationId, temuan] of perAplikasi) {
        const { email, pemilik, aplikasi: nama } = temuan[0];
        try {
          const surat = emailKerentanan({
            nama: pemilik,
            aplikasi: nama,
            temuan: temuan.slice(0, 15).map((t) => ({ ...t, kev: Boolean(t.kev) })),
            tautan: `${env.appUrl}/kerentanan?aplikasi=${applicationId}`,
            appUrl: env.appUrl,
          });
          await kirimEmail({ to: email, ...surat });
          await repository.tandaiDiberitahu(temuan.map((t) => t.id));
          terkirim += 1;
        } catch (error) {
          logger.warn('Email peringatan kerentanan gagal dikirim', { aplikasiId: applicationId, error: error.message });
        }
      }
      return terkirim;
    },
  };
}

export const kerentananService = createKerentananService();
