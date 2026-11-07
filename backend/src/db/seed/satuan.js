// Data awal hierarki satuan untuk `npm run satuan:seed` (lihat src/cli/seedSatuan.js).
//
// NAMA SATUAN FIKTIF (tidak merujuk satuan nyata) — untuk pengembangan, demo, & uji peta dasbor.
// Lokasi memakai kota nyata (perkiraan pusat kota) agar peta sebaran terisi wajar.
//
// Semua jenis satuan terwakili:
//   MABES     Mabes Nusantara → Mabes Matra Darat / Laut / Udara
//   BALAKPUS  Pusat Siber Nusantara, Pusat Data dan Informasi Nusantara
//   KOTAMA    15 Kodam (Alfa … Oscar), Komando Armada Samudra, Komando Udara Dirgantara
//   KOREM     Korem <Kodam>-<n>/<kota>           (pangkalan laut ikut setingkat Korem)
//   KODIM     Kodim <Kodam>-<nn>/<kota>          (pangkalan udara ikut setingkat Kodim)
//   KORAMIL   Koramil <Kodim>-01/<kota>          (satu per Kodam, di Kodim pertamanya)
//   SATUAN    Batalyon Siber, laboratorium/tim, serta satuan contoh dari migrasi 0001
//
// Satuan contoh lama (Laboratorium Siber, Satuan Contoh A/B/C, dst.) ikut ditempatkan di pohon & diberi
// lokasi agar aplikasi yang sudah terdaftar di sana langsung terpetakan.
//
// Format kota: [nama kota, provinsi (kode BPS), lat, lng].

/** @typedef {{ nama: string, jenis: string, kota: [string, string, number, number], anak?: Satuan[] }} Satuan */

const kota = (nama, prov, lat, lng) => [nama, prov, lat, lng];
/** Titik sedikit bergeser dari pusat kota (satuan berbeda di kota yang sama tidak bertumpuk). */
const geser = ([nama, prov, lat, lng], d = 0.04) => [nama, prov, Number((lat + d).toFixed(4)), Number((lng + d).toFixed(4))];
const dua = (n) => String(n).padStart(2, '0');

const JAKTIM = kota('Kota Jakarta Timur', '31', -6.225, 106.9004);
const JAKPUS = kota('Kota Jakarta Pusat', '31', -6.1805, 106.8284);
const JAKUT = kota('Kota Jakarta Utara', '31', -6.1384, 106.8636);
const JAKSEL = kota('Kota Jakarta Selatan', '31', -6.2615, 106.8106);
const BOGOR = kota('Kota Bogor', '32', -6.5971, 106.806);

// [kode, sebutan, kota markas, satuan bawahan [jenis, kota, prov, lat, lng], satuan contoh lama di Kodam ini]
const KODAM = [
  ['Alfa', 'Rajawali', kota('Kota Banda Aceh', '11', 5.55, 95.32), [
    ['KOREM', 'Lhokseumawe', '11', 5.18, 97.15], ['KODIM', 'Meulaboh', '11', 4.14, 96.13],
    ['KODIM', 'Takengon', '11', 4.63, 96.84], ['KODIM', 'Langsa', '11', 4.47, 97.97],
  ]],
  ['Bravo', 'Bentala', kota('Kota Medan', '12', 3.59, 98.67), [
    ['KOREM', 'Pematangsiantar', '12', 2.96, 99.06], ['KOREM', 'Pekanbaru', '14', 0.51, 101.45],
    ['KOREM', 'Padang', '13', -0.95, 100.35], ['KODIM', 'Padang Sidempuan', '12', 1.38, 99.27],
    ['KODIM', 'Bukittinggi', '13', -0.3, 100.37], ['KODIM', 'Batam', '21', 1.08, 104.03],
    ['KODIM', 'Dumai', '14', 1.67, 101.45], ['KODIM', 'Sibolga', '12', 1.74, 98.78],
  ]],
  ['Charlie', 'Cakrawala', kota('Kota Palembang', '16', -2.98, 104.75), [
    ['KOREM', 'Jambi', '15', -1.61, 103.61], ['KOREM', 'Bengkulu', '17', -3.8, 102.26],
    ['KOREM', 'Bandar Lampung', '18', -5.43, 105.26], ['KODIM', 'Pangkalpinang', '19', -2.13, 106.11],
    ['KODIM', 'Lubuklinggau', '16', -3.29, 102.86], ['KODIM', 'Metro', '18', -5.11, 105.31],
    ['KODIM', 'Baturaja', '16', -4.13, 104.17],
  ]],
  ['Delta', 'Nusa Indah', JAKPUS, [
    ['KOREM', 'Serang', '36', -6.12, 106.15], ['KODIM', 'Tangerang', '36', -6.18, 106.63],
    ['KODIM', 'Bekasi', '32', -6.24, 106.99], ['KODIM', 'Depok', '32', -6.4, 106.82],
  ]],
  ['Echo', 'Kencana', kota('Kota Bandung', '32', -6.91, 107.61), [
    ['KOREM', 'Bogor', '32', -6.6, 106.8], ['KOREM', 'Cirebon', '32', -6.73, 108.55],
    ['KOREM', 'Tasikmalaya', '32', -7.33, 108.22], ['KODIM', 'Sukabumi', '32', -6.92, 106.93],
    ['KODIM', 'Garut', '32', -7.21, 107.9], ['KODIM', 'Purwakarta', '32', -6.55, 107.44],
  ]],
  ['Foxtrot', 'Bayu Seta', kota('Kota Semarang', '33', -6.99, 110.42), [
    ['KOREM', 'Yogyakarta', '34', -7.8, 110.36], ['KOREM', 'Surakarta', '33', -7.57, 110.82],
    ['KOREM', 'Purwokerto', '33', -7.42, 109.23], ['KODIM', 'Magelang', '33', -7.47, 110.22],
    ['KODIM', 'Pekalongan', '33', -6.89, 109.67], ['KODIM', 'Tegal', '33', -6.87, 109.14],
  ], [
    ['Satuan Contoh A', kota('Kota Semarang', '33', -6.9932, 110.4203)],
    ['Satuan Contoh B', kota('Kota Surakarta', '33', -7.5755, 110.8243)],
  ]],
  ['Golf', 'Arga Dipa', kota('Kota Surabaya', '35', -7.25, 112.75), [
    ['KOREM', 'Malang', '35', -7.98, 112.63], ['KOREM', 'Madiun', '35', -7.63, 111.52],
    ['KODIM', 'Kediri', '35', -7.82, 112.01], ['KODIM', 'Jember', '35', -8.17, 113.7],
    ['KODIM', 'Banyuwangi', '35', -8.22, 114.37], ['KODIM', 'Pamekasan', '35', -7.16, 113.48],
  ]],
  ['Hotel', 'Lembayung', kota('Kota Denpasar', '51', -8.65, 115.22), [
    ['KOREM', 'Mataram', '52', -8.58, 116.12], ['KOREM', 'Kupang', '53', -10.18, 123.6],
    ['KODIM', 'Bima', '52', -8.46, 118.73], ['KODIM', 'Ende', '53', -8.84, 121.66],
    ['KODIM', 'Atambua', '53', -9.11, 124.89], ['KODIM', 'Singaraja', '51', -8.11, 115.09],
  ]],
  ['India', 'Candra Kirana', kota('Kota Pontianak', '61', -0.03, 109.33), [
    ['KOREM', 'Palangka Raya', '62', -2.21, 113.92], ['KODIM', 'Singkawang', '61', 0.91, 108.98],
    ['KODIM', 'Ketapang', '61', -1.85, 109.98], ['KODIM', 'Sintang', '61', 0.07, 111.5],
    ['KODIM', 'Sampit', '62', -2.53, 112.95], ['KODIM', 'Putussibau', '61', 0.84, 112.93],
  ]],
  ['Juliet', 'Tirta Wening', kota('Kota Balikpapan', '64', -1.24, 116.85), [
    ['KOREM', 'Samarinda', '64', -0.5, 117.15], ['KOREM', 'Banjarmasin', '63', -3.32, 114.59],
    ['KOREM', 'Tarakan', '65', 3.3, 117.63], ['KODIM', 'Bontang', '64', 0.13, 117.5],
    ['KODIM', 'Tanjung Selor', '65', 2.84, 117.37], ['KODIM', 'Kotabaru', '63', -3.24, 116.21],
  ], [['Satuan Contoh C', kota('Kota Balikpapan', '64', -1.2379, 116.8529)]]],
  ['Kilo', 'Gema Nusa', kota('Kota Manado', '71', 1.47, 124.84), [
    ['KOREM', 'Gorontalo', '75', 0.54, 123.06], ['KOREM', 'Palu', '72', -0.9, 119.87],
    ['KODIM', 'Bitung', '71', 1.44, 125.19], ['KODIM', 'Luwuk', '72', -0.95, 122.79],
    ['KODIM', 'Tolitoli', '72', 1.04, 120.82],
  ]],
  ['Lima', 'Wira Bhumi', kota('Kota Makassar', '73', -5.14, 119.42), [
    ['KOREM', 'Kendari', '74', -3.97, 122.51], ['KOREM', 'Parepare', '73', -4.01, 119.62],
    ['KODIM', 'Mamuju', '76', -2.68, 118.89], ['KODIM', 'Palopo', '73', -3.0, 120.2],
    ['KODIM', 'Bau-Bau', '74', -5.47, 122.6], ['KODIM', 'Bone', '73', -4.54, 120.33],
  ]],
  ['Mike', 'Sangkala', kota('Kota Ambon', '81', -3.7, 128.18), [
    ['KOREM', 'Ternate', '82', 0.79, 127.38], ['KODIM', 'Tual', '81', -5.64, 132.75],
    ['KODIM', 'Masohi', '81', -3.3, 128.96], ['KODIM', 'Saumlaki', '81', -7.98, 131.3],
    ['KODIM', 'Tobelo', '82', 1.73, 128.0],
  ]],
  ['November', 'Nara Bhakti', kota('Kabupaten Manokwari', '92', -0.86, 134.06), [
    ['KOREM', 'Sorong', '96', -0.88, 131.26], ['KODIM', 'Fakfak', '92', -2.93, 132.3],
    ['KODIM', 'Kaimana', '92', -3.65, 133.75], ['KODIM', 'Teluk Bintuni', '92', -2.1, 133.53],
  ]],
  ['Oscar', 'Bhumi Cendana', kota('Kota Jayapura', '91', -2.53, 140.72), [
    ['KOREM', 'Merauke', '93', -8.49, 140.4], ['KOREM', 'Timika', '94', -4.55, 136.89],
    ['KODIM', 'Wamena', '95', -4.1, 138.95], ['KODIM', 'Nabire', '94', -3.37, 135.5],
    ['KODIM', 'Biak', '91', -1.18, 136.08], ['KODIM', 'Sarmi', '91', -1.86, 138.74],
  ]],
];

/** Kodam beserta Korem, Kodim, satu Koramil, Batalyon Siber, dan satuan contoh lama di wilayahnya. */
function kodam([kode, sebutan, markas, bawahan, contoh = []]) {
  let korem = 0;
  let kodim = 0;
  const anak = bawahan.map(([jenis, namaKota, prov, lat, lng]) => {
    const lokasi = kota(namaKota, prov, lat, lng);
    if (jenis === 'KOREM') return { nama: `Korem ${kode}-${(korem += 1)}/${namaKota}`, jenis, kota: lokasi };
    const nomor = `${kode}-${dua((kodim += 1))}`;
    return {
      nama: `Kodim ${nomor}/${namaKota}`,
      jenis,
      kota: lokasi,
      // Satu Koramil (Kodim pertama tiap Kodam) sebagai perwakilan tingkat terbawah.
      ...(kodim === 1 && { anak: [{ nama: `Koramil ${nomor}-01/${namaKota}`, jenis: 'KORAMIL', kota: geser(lokasi) }] }),
    };
  });
  anak.push({ nama: `Batalyon Siber ${kode}`, jenis: 'SATUAN', kota: geser(markas, -0.03) });
  for (const [nama, lokasi] of contoh) anak.push({ nama, jenis: 'SATUAN', kota: lokasi });
  return { nama: `Kodam ${kode}/${sebutan}`, jenis: 'KOTAMA', kota: markas, anak };
}

/** @type {Satuan[]} */
export const SEED_SATUAN = [
  {
    nama: 'Mabes Nusantara',
    jenis: 'MABES',
    kota: JAKTIM,
    anak: [
      { nama: 'Mabes Matra Darat', jenis: 'MABES', kota: JAKPUS, anak: KODAM.map(kodam) },
      {
        nama: 'Mabes Matra Laut',
        jenis: 'MABES',
        kota: JAKUT,
        anak: [
          {
            nama: 'Komando Armada Samudra',
            jenis: 'KOTAMA',
            kota: kota('Kota Surabaya', '35', -7.2, 112.73),
            anak: [
              { nama: 'Pangkalan Laut Samudra-1/Ambon', jenis: 'KOREM', kota: kota('Kota Ambon', '81', -3.66, 128.15) },
              { nama: 'Pangkalan Laut Samudra-2/Batam', jenis: 'KOREM', kota: kota('Kota Batam', '21', 1.13, 104.05) },
            ],
          },
        ],
      },
      {
        nama: 'Mabes Matra Udara',
        jenis: 'MABES',
        kota: geser(JAKTIM, -0.04),
        anak: [
          {
            nama: 'Komando Udara Dirgantara',
            jenis: 'KOTAMA',
            kota: kota('Kota Makassar', '73', -5.08, 119.55),
            anak: [
              { nama: 'Pangkalan Udara Dirgantara-1/Biak', jenis: 'KODIM', kota: kota('Kabupaten Biak Numfor', '91', -1.19, 136.11) },
              { nama: 'Pangkalan Udara Dirgantara-2/Pekanbaru', jenis: 'KODIM', kota: kota('Kota Pekanbaru', '14', 0.46, 101.44) },
            ],
          },
        ],
      },
      {
        nama: 'Pusat Siber Nusantara',
        jenis: 'BALAKPUS',
        kota: JAKSEL,
        anak: [
          { nama: 'Laboratorium Siber', jenis: 'SATUAN', kota: geser(JAKSEL, 0.02) },
          { nama: 'Tim Asesor Keamanan Siber', jenis: 'SATUAN', kota: geser(JAKSEL, -0.02) },
        ],
      },
      {
        nama: 'Pusat Data dan Informasi Nusantara',
        jenis: 'BALAKPUS',
        kota: BOGOR,
        anak: [{ nama: 'Pengelola Platform', jenis: 'SATUAN', kota: geser(BOGOR, 0.02) }],
      },
    ],
  },
];
