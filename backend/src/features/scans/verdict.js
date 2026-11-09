// Putusan kelaikan sebuah scan dari hasil metodenya. Cermin `nilaiKelaikan` di
// frontend/src/lib/catalog.ts — ubah keduanya bersamaan bila aturan berubah.
// Murni (tanpa I/O) agar mudah diuji.

/** Aturan putusan kelaikan; ubah di sini bila kebijakan instansi berbeda. */
export const ATURAN_PUTUSAN = {
  /** Kontrol gagal dengan severity ini membuat aplikasi Tidak Laik. */
  severityPenggagal: ['kritis', 'tinggi'],
  /** Skor minimum agar dapat dinyatakan Laik. */
  skorMinimumLaik: 100,
};

/** Status akhir metode; belum selesai/tidak ada hasil = belum dapat diverifikasi. */
function statusAkhir(status) {
  if (!status || status === 'antre' || status === 'berjalan') return 'tidak_dapat_diverifikasi';
  return status;
}

/**
 * Status kontrol dari hasil metodenya sesuai aturan agregasi.
 * @param {{ aggregation: string, methods: { code: string, severity: string }[] }} kontrol
 * @param {Map<string, string>} hasil kode metode → status hasil
 */
export function statusKontrol(kontrol, hasil) {
  // Metode bertingkat severity "info" hanya informasi dan tidak memengaruhi status.
  const status = kontrol.methods
    .filter((m) => m.severity !== 'info')
    .map((m) => statusAkhir(hasil.get(m.code)))
    .filter((s) => s !== 'tidak_berlaku');

  if (status.length === 0) return 'tidak_berlaku';
  if (kontrol.aggregation === 'minimal_satu') {
    if (status.includes('lulus')) return 'lulus';
    if (status.includes('tidak_dapat_diverifikasi')) return 'tidak_dapat_diverifikasi';
    return 'gagal';
  }
  if (status.includes('gagal')) return 'gagal';
  if (status.includes('tidak_dapat_diverifikasi')) return 'tidak_dapat_diverifikasi';
  return 'lulus';
}

/**
 * Jumlah temuan (metode berstatus GAGAL) per severity metode, seperti ringkasan di halaman laporan.
 * Metode ber-severity info dan task tanpa severity (mis. fase penemuan) tidak dihitung.
 * @param {{ status: string, severity: string | null }[]} hasil
 */
export function hitungTemuan(hasil) {
  const n = { kritis: 0, tinggi: 0, sedang: 0, rendah: 0 };
  for (const h of hasil) if (h.status === 'gagal' && h.severity in n) n[h.severity] += 1;
  return n;
}

/**
 * @param {{ severity: string, aggregation: string, methods: { code: string, severity: string }[] }[]} kontrol
 *   kontrol aktif katalog beserta metode aktifnya
 * @param {Map<string, string>} hasil kode metode → status hasil scan
 * @returns {{ putusan: 'laik'|'laik_bersyarat'|'tidak_laik', skor: number }}
 */
export function nilaiKelaikan(kontrol, hasil) {
  const n = { lulus: 0, gagal: 0, tidak_berlaku: 0, tidak_dapat_diverifikasi: 0 };
  let gagalKritisTinggi = 0;
  for (const k of kontrol) {
    const s = statusKontrol(k, hasil);
    n[s] += 1;
    if (s === 'gagal' && ATURAN_PUTUSAN.severityPenggagal.includes(k.severity)) gagalKritisTinggi += 1;
  }
  const teruji = n.lulus + n.gagal;
  const skor = teruji ? Math.round((n.lulus / teruji) * 100) : 0;

  let putusan = 'laik';
  if (gagalKritisTinggi > 0) putusan = 'tidak_laik';
  else if (n.gagal > 0 || n.tidak_dapat_diverifikasi > 0 || skor < ATURAN_PUTUSAN.skorMinimumLaik) putusan = 'laik_bersyarat';
  return { putusan, skor };
}
