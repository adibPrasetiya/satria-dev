<script lang="ts" module>
	export type Pendekatan = 'greybox' | 'blackbox';
</script>

<script lang="ts">
	// Modal 2 — pilih metode pengujian. Keduanya memakai alur otomatis (eksploratif) yang sama:
	// Grey Box meminta akun uji (kredensial), Black Box tanpa akun maupun informasi internal.
	import DialogPilihanTaktis, { type OpsiTaktis } from './DialogPilihanTaktis.svelte';
	import Code from '@lucide/svelte/icons/code';
	import Box from '@lucide/svelte/icons/box';

	let {
		open = $bindable(false),
		onpilih
	}: {
		open?: boolean;
		onpilih: (pendekatan: Pendekatan) => void;
	} = $props();

	const OPSI: OpsiTaktis<Pendekatan>[] = [
		{
			id: 'greybox',
			judul: 'Grey Box',
			keterangan:
				'Pengujian dengan akses terbatas terhadap informasi internal (mis. dokumentasi, akun terbatas, atau sumber daya tertentu).',
			gambar: '/pengujian/greybox.webp',
			Ikon: Code
		},
		{
			id: 'blackbox',
			judul: 'Black Box',
			keterangan: 'Pengujian tanpa pengetahuan internal tentang struktur, konfigurasi, atau mekanisme sistem.',
			gambar: '/pengujian/blackbox.webp',
			Ikon: Box
		}
	];
</script>

<DialogPilihanTaktis
	bind:open
	judul="Metode Pengujian"
	deskripsi="Pilih bagaimana pengujian dijalankan."
	opsi={OPSI}
	{onpilih}
/>
