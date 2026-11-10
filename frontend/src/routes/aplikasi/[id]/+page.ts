// Halaman "Berkas Aplikasi" (/aplikasi/:id) sudah dihapus — fungsinya pindah ke daftar aplikasi
// (menu aksi per baris: riwayat, persiapan uji, ubah data, arsip) dan halaman operasi pengujian.
// Tautan lama (bookmark/riwayat browser) diarahkan ke daftar aplikasi.
import { redirect } from '@sveltejs/kit';

export const load = () => {
	redirect(308, '/aplikasi');
};
