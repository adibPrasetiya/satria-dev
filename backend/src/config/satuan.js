// Referensi satuan kerja TNI: jenis (tingkatan) satuan dan wilayah provinsi.
// Sama dengan `JENIS_SATUAN` & `PROVINSI` di frontend (src/lib/satuan.ts) — ubah keduanya bersamaan.

/** Jenis satuan; urutan kira-kira dari puncak hierarki ke bawah. */
export const JENIS_SATUAN = [
  'MABES', // Markas Besar: Mabes TNI, Mabesad, Mabesal, Mabesau
  'KOTAMA', // Komando Utama: Kodam, Kostrad, Kopassus, Koarmada, Koopsud, Kogabwilhan, …
  'BALAKPUS', // Badan Pelaksana Pusat: Pusinfolahta, Bais, Satsiber, Puspom, …
  'KOREM', // Komando Resor Militer / setingkat (Lantamal, Lanud tipe A)
  'KODIM', // Komando Distrik Militer / setingkat (Lanal, Lanud)
  'KORAMIL', // Komando Rayon Militer / setingkat
  'SATUAN', // Satuan/satker lain: batalyon, detasemen, dinas, staf, laboratorium, …
];

/** Kedalaman maksimum pohon satuan (Mabes → … → Koramil → sub-satuan) agar tidak tak terhingga. */
export const MAKS_KEDALAMAN_SATUAN = 8;

/** 38 provinsi; kode = kode wilayah Kemendagri/BPS (2 digit), dipakai peta sebaran di dasbor. */
export const PROVINSI = [
  ['11', 'Aceh'],
  ['12', 'Sumatera Utara'],
  ['13', 'Sumatera Barat'],
  ['14', 'Riau'],
  ['15', 'Jambi'],
  ['16', 'Sumatera Selatan'],
  ['17', 'Bengkulu'],
  ['18', 'Lampung'],
  ['19', 'Kepulauan Bangka Belitung'],
  ['21', 'Kepulauan Riau'],
  ['31', 'DKI Jakarta'],
  ['32', 'Jawa Barat'],
  ['33', 'Jawa Tengah'],
  ['34', 'DI Yogyakarta'],
  ['35', 'Jawa Timur'],
  ['36', 'Banten'],
  ['51', 'Bali'],
  ['52', 'Nusa Tenggara Barat'],
  ['53', 'Nusa Tenggara Timur'],
  ['61', 'Kalimantan Barat'],
  ['62', 'Kalimantan Tengah'],
  ['63', 'Kalimantan Selatan'],
  ['64', 'Kalimantan Timur'],
  ['65', 'Kalimantan Utara'],
  ['71', 'Sulawesi Utara'],
  ['72', 'Sulawesi Tengah'],
  ['73', 'Sulawesi Selatan'],
  ['74', 'Sulawesi Tenggara'],
  ['75', 'Gorontalo'],
  ['76', 'Sulawesi Barat'],
  ['81', 'Maluku'],
  ['82', 'Maluku Utara'],
  ['91', 'Papua'],
  ['92', 'Papua Barat'],
  ['93', 'Papua Selatan'],
  ['94', 'Papua Tengah'],
  ['95', 'Papua Pegunungan'],
  ['96', 'Papua Barat Daya'],
].map(([kode, nama]) => ({ kode, nama }));

export const KODE_PROVINSI = PROVINSI.map((p) => p.kode);
export const namaProvinsi = (kode) => PROVINSI.find((p) => p.kode === kode)?.nama ?? null;

/** Batas kotak wilayah Indonesia (dengan sedikit kelonggaran) untuk menolak koordinat yang tertukar/salah. */
export const BATAS_KOORDINAT = { latMin: -11.5, latMax: 6.5, lngMin: 94.5, lngMax: 141.5 };
