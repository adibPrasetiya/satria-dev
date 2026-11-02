<script lang="ts">
	import { katalog, jumlahMetodePerTitik, TITIK_UJI_TETAP } from '#lib/catalog.js';
	import type { PemetaanTitikUji } from '#lib/types.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import NativeSelect from './NativeSelect.svelte';
	import { cn } from '#lib/utils.js';

	let {
		titik = $bindable(),
		urlDasar
	}: { titik: Record<string, PemetaanTitikUji>; urlDasar: string } = $props();

	const daftar = katalog.titik_uji.filter((t) => !TITIK_UJI_TETAP.includes(t.id));
	const HTTP = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => ({ value: m, label: m }));

	const CONTOH: Record<string, string> = {
		registrasi: '/register',
		login: '/login',
		reset_password: '/password/reset',
		ubah_password: '/akun/password',
		logout: '/logout',
		area_terautentikasi: '/dashboard',
		admin: '/admin',
		form_input: '/cari?q=',
		unggah_file: '/dokumen/unggah',
		unduh_file: '/dokumen/unduh/1',
		api: '/api/v1'
	};
</script>

<div class="divide-y overflow-hidden rounded-lg border bg-card">
	{#each daftar as t (t.id)}
		{@const p = titik[t.id]}
		<div class={cn('grid gap-3 p-3 sm:grid-cols-[minmax(0,240px)_1fr] sm:items-center', !p.tersedia && 'bg-muted/40')}>
			<label class="flex cursor-pointer items-start gap-3">
				<Switch bind:checked={titik[t.id].tersedia} class="mt-0.5" />
				<span class="min-w-0">
					<span class="block text-sm font-medium">{t.nama}</span>
					<span class="font-heading text-[10px] tracking-[0.15em] text-muted-foreground uppercase">
						{jumlahMetodePerTitik[t.id] ?? 0} metode uji
					</span>
				</span>
			</label>
			{#if p.tersedia}
				<div class="flex gap-2">
					<NativeSelect bind:value={titik[t.id].metode_http} opsi={HTTP} class="w-24 shrink-0" aria-label="Metode HTTP" />
					<div class="flex min-w-0 flex-1 items-center rounded-lg border border-input focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
						<span class="hidden max-w-48 truncate border-r bg-muted/60 px-2 py-1.5 text-xs text-muted-foreground sm:block">
							{urlDasar || 'https://…'}
						</span>
						<Input
							bind:value={titik[t.id].url}
							placeholder={CONTOH[t.id] ?? '/'}
							class="h-8 border-0 focus-visible:ring-0"
							aria-label="Path {t.nama}"
						/>
					</div>
				</div>
			{:else}
				<p class="text-xs text-muted-foreground italic">
					Tidak tersedia — metode terkait dinyatakan <span class="font-medium">Tidak Berlaku</span>.
				</p>
			{/if}
		</div>
	{/each}
</div>
