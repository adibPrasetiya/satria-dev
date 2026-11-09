// Dokumen Syarat & Ketentuan Operasi Pengujian Keamanan (dibaca di modal sebelum pengujian dimulai).
// Isi menyesuaikan pendekatan: bagian akun uji hanya untuk Grey Box.

export const VERSI_SK = '1.0';
export const BERLAKU_SK = '9 November 2026';
export const KODE_SK = 'SATRIA/SK-UJI/01';

export interface PasalSK {
	judul: string;
	/** Paragraf pembuka (opsional). */
	pengantar?: string;
	butir: string[];
}

/** Ringkasan dampak yang ditampilkan di halaman (bukan pengganti dokumen). */
export interface DampakSK {
	fase: string;
	aktivitas: string;
	dampak: string;
	tingkat: 'rendah' | 'sedang' | 'tinggi';
}

export function dampakPengujian(blackbox: boolean): DampakSK[] {
	const d: DampakSK[] = [
		{
			fase: 'Recon & Discovery',
			aktivitas: 'Penelusuran halaman, render SPA, penyadapan lalu lintas, pembacaan spesifikasi OpenAPI.',
			dampak: 'Hanya membaca; permintaan selain GET dibatalkan sebelum terkirim.',
			tingkat: 'rendah'
		},
		{
			fase: 'Pengujian kontrol',
			aktivitas: 'Lalu lintas uji sesuai metode katalog BSSN (header, TLS, input, sesi, batas laju).',
			dampak: 'Dapat membuat data uji (mis. registrasi/percobaan) dan memicu alarm WAF/IDS.',
			tingkat: 'sedang'
		}
	];
	if (!blackbox)
		d.push({
			fase: 'Uji akun (opsional)',
			aktivitas: 'Uji kebijakan kata sandi dan penguncian akun pada akun uji.',
			dampak: 'Kata sandi akun uji dapat berubah; akun uji dapat terkunci sementara.',
			tingkat: 'tinggi'
		});
	return d;
}

export function dokumenSK(blackbox: boolean): PasalSK[] {
	const pendekatan = blackbox ? 'Black Box' : 'Grey Box';
	const pasal: PasalSK[] = [
		{
			judul: 'Ketentuan Umum',
			pengantar: 'Dalam dokumen ini yang dimaksud dengan:',
			butir: [
				'SATRIA adalah sistem pengujian keamanan aplikasi web yang menjalankan metode uji berdasarkan katalog kontrol keamanan BSSN.',
				'Pengguna adalah personel yang memulai operasi pengujian melalui akun SATRIA miliknya.',
				'Target adalah aplikasi yang terdaftar di SATRIA beserta URL dasar yang tercatat pada berkas aplikasi.',
				`Pengujian ${pendekatan} adalah pengujian ${blackbox ? 'dari sudut pandang pihak luar, tanpa akun maupun informasi internal' : 'menggunakan akun uji dengan hak akses terbatas yang disediakan Pengguna'}.`,
				'Temuan adalah metode uji yang berstatus Failed; Out of Scope adalah metode yang tidak dapat diuji secara otomatis dengan pendekatan yang dipilih.'
			]
		},
		{
			judul: 'Kewenangan & Otorisasi',
			butir: [
				'Pengguna menyatakan memiliki kewenangan yang sah untuk menguji Target, baik sebagai pemilik aset maupun atas penugasan tertulis dari pimpinan satuan pemilik aset.',
				'Pengguna menjamin bahwa pengelola infrastruktur Target (penyedia hosting, pusat data, atau unit TI terkait) telah diberitahu atau tidak berkeberatan atas pengujian.',
				'Pengujian tanpa kewenangan dapat melanggar ketentuan peraturan perundang-undangan, termasuk UU Informasi dan Transaksi Elektronik. Segala akibat dari pengujian tanpa kewenangan menjadi tanggung jawab Pengguna.'
			]
		},
		{
			judul: 'Lingkup Pengujian',
			butir: [
				'Pengujian dibatasi pada URL dasar Target dan sumber daya di host yang sama yang ditemukan selama fase Recon & Discovery.',
				'Layanan pihak ketiga (CDN, penyedia identitas eksternal, API mitra) yang dirujuk Target tidak termasuk dalam lingkup dan tidak diuji secara aktif.',
				'Metode uji yang memerlukan penilaian manusia, atau tidak didukung oleh pendekatan yang dipilih, dinyatakan Out of Scope dan tidak ikut dalam perhitungan skor.',
				'Pengujian tidak mencakup uji beban, uji ketahanan terhadap serangan penolakan layanan (DoS), rekayasa sosial, maupun pengujian fisik.'
			]
		},
		{
			judul: 'Aktivitas & Dampak terhadap Target',
			butir: [
				'Fase Recon & Discovery bersifat membaca: menelusuri halaman, merender aplikasi SPA, menyadap lalu lintas, dan membaca spesifikasi OpenAPI. Permintaan selain GET yang muncul pada fase ini dibatalkan sebelum terkirim.',
				'Fase pengujian mengirim lalu lintas uji ke Target, termasuk muatan uji validasi input, uji batas laju (puluhan permintaan beruntun), serta pemindaian otomatis (OWASP ZAP, Nuclei, SSLyze).',
				'Pengujian dapat membuat data uji pada Target, misalnya akun hasil uji registrasi atau entri percobaan, yang perlu dibersihkan oleh pengelola Target setelah pengujian.',
				'Lalu lintas uji dapat memicu peringatan pada WAF, IDS/IPS, atau sistem pemantauan, serta tercatat pada log aplikasi Target.',
				'SATRIA tidak melakukan eksploitasi lanjutan, tidak mengambil data di luar yang diperlukan sebagai bukti, dan tidak dengan sengaja menghapus data Target.'
			]
		}
	];

	if (!blackbox)
		pasal.push({
			judul: 'Akun Uji',
			butir: [
				'Pengguna wajib menyediakan sekurang-kurangnya dua akun uji yang dibuat khusus untuk SATRIA, dengan hak akses pengguna biasa (bukan administrator).',
				'Akun uji tidak boleh milik orang sebenarnya dan tidak boleh berisi data pribadi atau data operasional yang sesungguhnya.',
				'Mesin uji akan masuk, keluar, dan membuat sesi berulang kali menggunakan akun uji; sesi aktif pada akun tersebut dapat berakhir.',
				'Bila uji berisiko diizinkan, uji kebijakan kata sandi dapat mengganti kata sandi akun uji dan uji penguncian dapat mengunci akun uji untuk sementara waktu.',
				'Kredensial akun uji disimpan di server SATRIA, hanya digunakan oleh mesin uji, dan dapat diganti oleh Pengguna pada pengujian berikutnya.'
			]
		});

	pasal.push(
		{
			judul: 'Kewajiban Pengguna',
			butir: [
				'Mengutamakan pengujian pada lingkungan pengembangan atau staging. Pengujian pada lingkungan produksi dilakukan di luar jam sibuk dan setelah berkoordinasi dengan pengelola Target.',
				'Memastikan cadangan (backup) data Target tersedia sebelum pengujian dimulai.',
				'Memberitahu tim pemantau keamanan (SOC) atau administrator Target agar peringatan yang timbul tidak ditangani sebagai insiden.',
				'Memantau jalannya pengujian dan menghentikannya melalui tombol Hentikan bila Target menunjukkan gangguan.',
				'Menindaklanjuti temuan dengan pemilik aset dan melakukan pengujian ulang setelah perbaikan.'
			]
		},
		{
			judul: 'Kerahasiaan Hasil',
			butir: [
				'Hasil pengujian, bukti permintaan/respons, dan laporan merupakan informasi terbatas sesuai klasifikasi data Target, dan hanya dapat diakses oleh pemilik aset serta administrator SATRIA.',
				'Pengguna dilarang menyebarkan hasil pengujian di luar keperluan perbaikan dan pelaporan kedinasan.',
				'Analisis dan rekomendasi berbantuan AI hanya menerima ringkasan hasil pengujian tanpa kredensial, token sesi, maupun data sensitif Target.'
			]
		},
		{
			judul: 'Batasan Hasil',
			butir: [
				'Hasil pengujian otomatis dapat mengandung positif palsu maupun negatif palsu; temuan perlu diverifikasi sebelum ditindaklanjuti.',
				'Status Pass pada suatu metode tidak menjamin bahwa Target bebas dari kerentanan pada aspek tersebut.',
				'Skor dan putusan kelaikan SATRIA merupakan alat bantu penilaian dan tidak menggantikan audit keamanan atau sertifikasi resmi.'
			]
		},
		{
			judul: 'Penghentian & Pencatatan',
			butir: [
				'Pengguna dapat menghentikan pengujian kapan saja; metode yang belum dijalankan tidak akan dieksekusi.',
				'Administrator SATRIA berwenang membatalkan pengujian yang dinilai mengganggu layanan atau berada di luar kewenangan Pengguna.',
				'Persetujuan atas dokumen ini, identitas Pengguna, waktu, dan seluruh aktivitas pengujian dicatat sebagai bagian dari riwayat pengujian.'
			]
		}
	);
	return pasal;
}
