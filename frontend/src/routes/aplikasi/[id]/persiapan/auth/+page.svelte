<script lang="ts">
	// Daftar bagian persiapan Autentikasi sebagai kartu, masing-masing dengan status keterpenuhan data.
	// Pengisian dilakukan di halaman fokus per bagian (klik kartu).
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import type { Aplikasi, Katalog, PersiapanAuth } from '#lib/types.js';
	import { persiapanAuthKosong, kesiapanMetodeAuth } from '#lib/persiapan/auth.js';
	import { BAGIAN_AUTH, statusBagian, type StatusBagian } from '#lib/persiapan/bagian.js';
	import type { StatusKesiapan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleDashed from '@lucide/svelte/icons/circle-dashed';
	import ListChecks from '@lucide/svelte/icons/list-checks';
	import Info from '@lucide/svelte/icons/info';

	const id = $derived(page.params.id!);

	let app = $state<Aplikasi | null>(null);
	let katalog = $state<Katalog | null>(null);
	let p = $state<PersiapanAuth | null>(null);
	let galat = $state<string | null>(null);

	$effect(() => {
		const aid = id;
		Promise.all([api.getAplikasi(aid), api.getKatalog(), api.getPersiapanAuth(aid)])
			.then(([a, k, simpanan]) => {
				app = a;
				katalog = k;
				p = simpanan ? { ...persiapanAuthKosong(), ...simpanan } : persiapanAuthKosong();
			})
			.catch((e) => (galat = (e as Error).message));
	});

	const fungsiAuth = $derived(katalog?.fungsi_keamanan.find((f) => f.id === 'AUTH') ?? null);

	// Ringkasan kesiapan metode (ringkas): hitung status tiap metode aktif.
	const aktif = (x: { aktif?: boolean }) => x.aktif !== false;
	const hitung = $derived.by(() => {
		const acc: Record<StatusKesiapan, number> = { siap: 0, perlu_data: 0, dilewati: 0, asesor: 0 };
		if (!fungsiAuth || !p) return acc;
		for (const k of fungsiAuth.kontrol.filter(aktif))
			for (const m of k.metode_pengujian.filter(aktif)) acc[kesiapanMetodeAuth(p, m).status]++;
		return acc;
	});
	const RINGKAS: { key: StatusKesiapan; label: string; dot: string; teks: string }[] = [
		{ key: 'siap', label: 'Siap', dot: 'bg-success', teks: 'text-success' },
		{ key: 'perlu_data', label: 'Perlu data', dot: 'bg-warning', teks: 'text-warning-foreground' },
		{ key: 'dilewati', label: 'Dilewati', dot: 'bg-muted-foreground/60', teks: 'text-muted-foreground' },
		{ key: 'asesor', label: 'Asesor', dot: 'bg-info', teks: 'text-info' }
	];

	// Nilai kebijakan dari katalog (hanya-baca) sebagai konteks.
	const LABEL_WAJIB: Record<string, string> = { huruf_besar: 'huruf besar', huruf_kecil: 'huruf kecil', angka: 'angka', simbol: 'simbol' };
	const kontrol = (kode: string) => fungsiAuth?.kontrol.find((k) => k.id === kode);
	const kebijakan = $derived({
		panjang: kontrol('AUTH-1.3')?.parameter?.panjang_minimum as number | undefined,
		wajib: kontrol('AUTH-1.3')?.parameter?.wajib as string[] | undefined,
		batas: kontrol('AUTH-1.4')?.parameter?.batas_percobaan as number | undefined
	});

	const GAYA: Record<StatusBagian, { label: string; kelas: string; opsional?: boolean }> = {
		lengkap: { label: 'Lengkap', kelas: 'bg-success/12 text-success' },
		belum: { label: 'Belum lengkap', kelas: 'bg-muted text-muted-foreground' },
		opsional: { label: 'Opsional', kelas: 'border border-dashed text-muted-foreground', opsional: true }
	};
</script>

<svelte:head><title>Persiapan Autentikasi — {app?.nama ?? 'Aplikasi'} — SATRIA</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app || !katalog || !p || !fungsiAuth}
	<Memuat />
{:else}
	<div class="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
		<div class="min-w-0">
			<a href="/aplikasi/{app.id}/persiapan" class="mb-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Fungsi keamanan
			</a>
			<p class="label-stensil text-[10px]">Isi data pengujian</p>
			<h1 class="font-heading text-2xl font-semibold tracking-[0.04em] uppercase">01 · Autentikasi</h1>
			<p class="mt-1 max-w-2xl text-sm text-muted-foreground">
				Pilih satu bagian untuk diisi. Setiap bagian hanya menampilkan field yang relevan.
			</p>
		</div>
		<!-- Ringkasan kesiapan metode (ringkas): hanya angka per status. -->
		<div class="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border bg-card/60 px-3 py-1.5 text-xs">
			<span class="label-stensil text-[10px] text-muted-foreground">Kesiapan</span>
			{#each RINGKAS as s (s.key)}
				<span class="inline-flex items-center gap-1.5" title={s.label}>
					<span class={cn('size-2 rounded-full', s.dot)}></span>
					<b class={cn('font-stencil leading-none', s.teks)}>{hitung[s.key]}</b>
					<span class="text-muted-foreground">{s.label}</span>
				</span>
			{/each}
		</div>
	</div>

	<!-- Konteks kebijakan (hanya-baca). -->
	<div class="mb-4 flex items-start gap-3 rounded-lg border border-info/30 bg-info/5 px-4 py-3 text-sm">
		<Info class="mt-0.5 size-4 shrink-0 text-info" />
		<p>
			Kebijakan yang diuji (dari katalog): kata sandi minimal <b>{kebijakan.panjang ?? '—'} karakter</b>
			{#if kebijakan.wajib?.length}dengan <b>{kebijakan.wajib.map((w) => LABEL_WAJIB[w] ?? w).join(', ')}</b>{/if};
			akun terkunci setelah <b>{kebijakan.batas ?? '—'} kali</b> salah memasukkan kata sandi.
		</p>
	</div>

	<div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
		{#each BAGIAN_AUTH as b (b.id)}
			{@const s = statusBagian(p, b.id)}
			{@const g = GAYA[s]}
			<a
				href="/aplikasi/{app.id}/persiapan/auth/{b.id}"
				class="sudut-taktis group flex flex-col rounded-lg border bg-card p-4 transition hover:border-gold/60 hover:bg-gold/5"
			>
				<div class="flex items-start gap-3">
					<span class="grid size-9 shrink-0 place-items-center rounded-sm bg-olive-dark font-stencil text-gold">{b.nomor}</span>
					<div class="min-w-0 flex-1">
						<h2 class="flex flex-wrap items-center gap-2 font-heading text-sm font-semibold tracking-[0.06em] uppercase">
							{b.judul}
							{#if b.wajib}<span class="rounded-sm bg-critical/12 px-1.5 py-0.5 font-sans text-[10px] font-medium tracking-normal text-critical normal-case">Wajib</span>{/if}
						</h2>
						<p class="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{b.ket}</p>
					</div>
				</div>
				<div class="mt-3 flex items-center justify-between gap-2">
					<span class={cn('inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium', g.kelas)}>
						{#if s === 'lengkap'}<CircleCheck class="size-3.5" />{:else if s === 'belum'}<CircleDashed class="size-3.5" />{/if}
						{g.label}
					</span>
					<span class="flex items-center gap-2 text-xs text-muted-foreground">
						{#if b.metode.length}<span class="inline-flex items-center gap-1"><ListChecks class="size-3.5" /> {b.metode.length} uji</span>{/if}
						<ChevronRight class="size-4 text-gold transition-transform group-hover:translate-x-0.5" />
					</span>
				</div>
			</a>
		{/each}
	</div>
{/if}
