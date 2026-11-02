<script lang="ts">
	// Registrasi aset aplikasi: data dasar saja. Persiapan pengujian (kepemilikan, titik uji, akun uji,
	// izin intrusif) dilakukan terpisah saat akan menguji.
	import { goto } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import FormAset from '#lib/components/FormAset.svelte';
	import { toast } from 'svelte-sonner';

	async function simpan(data: Parameters<typeof api.buatAplikasi>[0]) {
		const app = await api.buatAplikasi(data);
		toast.success(`Aplikasi "${app.nama}" terdaftar`);
		goto(`/aplikasi/${app.id}`);
	}
</script>

<svelte:head><title>Registrasi Aplikasi — SATYA</title></svelte:head>

<PageHeader
	label="Aset Aplikasi"
	judul="Registrasi Aplikasi"
	deskripsi="Daftarkan informasi dasar aplikasi. Persiapan pengujian dilakukan terpisah saat aplikasi akan diuji."
/>

<FormAset labelSimpan="Daftarkan aplikasi" batalHref="/aplikasi" onsimpan={simpan} />
