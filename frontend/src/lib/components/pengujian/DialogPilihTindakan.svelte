<script lang="ts">
	// Modal 1 — setelah membuka aset: lihat riwayat pengujian atau lakukan pengujian baru.
	import DialogPilihanTaktis, { type OpsiTaktis } from './DialogPilihanTaktis.svelte';
	import History from '@lucide/svelte/icons/history';
	import FlaskConical from '@lucide/svelte/icons/flask-conical';

	let {
		open = $bindable(false),
		onlihatRiwayat,
		onpengujian
	}: {
		open?: boolean;
		onlihatRiwayat: () => void;
		onpengujian: () => void;
	} = $props();

	type Tindakan = 'riwayat' | 'pengujian';
	const OPSI: OpsiTaktis<Tindakan>[] = [
		{
			id: 'riwayat',
			judul: 'Riwayat Pengujian',
			keterangan: 'Lihat hasil & laporan pengujian sebelumnya.',
			gambar: '/login/prajurit.webp',
			posisiGambar: '18% center',
			Ikon: History
		},
		{
			id: 'pengujian',
			judul: 'Lakukan Pengujian',
			keterangan: 'Mulai operasi pengujian keamanan baru.',
			gambar: '/login/prajurit-daftar.webp',
			posisiGambar: '62% center',
			Ikon: FlaskConical
		}
	];
</script>

<DialogPilihanTaktis
	bind:open
	judul="Operasi Pengujian"
	deskripsi="Pilih tindakan untuk aset ini."
	opsi={OPSI}
	onpilih={(t) => (t === 'riwayat' ? onlihatRiwayat() : onpengujian())}
/>
