<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import type { Aplikasi } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import FormAset from '#lib/components/FormAset.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { toast } from 'svelte-sonner';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';

	const id = $derived(page.params.id!);
	let app = $state<Aplikasi | null>(null);
	let galat = $state<string | null>(null);

	$effect(() => {
		const aid = id;
		app = null;
		galat = null;
		api.getAplikasi(aid).then(
			(a) => (app = a),
			(e) => (galat = (e as Error).message)
		);
	});

	async function simpan(data: Parameters<typeof api.ubahAplikasi>[1]) {
		await api.ubahAplikasi(id, data);
		toast.success('Data aplikasi diperbarui');
		goto(`/aplikasi/${id}`);
	}
</script>

<svelte:head><title>Ubah Aplikasi — SATYA</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app}
	<Memuat baris={2} />
{:else}
	<PageHeader label="Aset Aplikasi" judul="Ubah {app.nama}">
		{#snippet atas()}
			<a href="/aplikasi/{app!.id}" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Kembali ke berkas aplikasi
			</a>
		{/snippet}
	</PageHeader>
	{#key app.id}
		<FormAset awal={app} batalHref="/aplikasi/{app.id}" onsimpan={simpan} />
	{/key}
{/if}
