<script lang="ts">
	// Halaman fokus: mengisi satu bagian persiapan Autentikasi. Hanya field bagian ini yang tampil.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import type { Aplikasi, Katalog, PersiapanAuth } from '#lib/types.js';
	import { persiapanAuthKosong } from '#lib/persiapan/auth.js';
	import { META_BAGIAN, adalahBagian, alamatSalah, type IdBagian } from '#lib/persiapan/bagian.js';
	import { petakanKeScanTarget } from '#lib/persiapan/target.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import Login from '#lib/components/persiapan/bagian/Login.svelte';
	import Registrasi from '#lib/components/persiapan/bagian/Registrasi.svelte';
	import Reset from '#lib/components/persiapan/bagian/Reset.svelte';
	import Ubah from '#lib/components/persiapan/bagian/Ubah.svelte';
	import AkunUji from '#lib/components/persiapan/bagian/AkunUji.svelte';
	import Pengaman from '#lib/components/persiapan/bagian/Pengaman.svelte';
	import Izin from '#lib/components/persiapan/bagian/Izin.svelte';
	import Dokumen from '#lib/components/persiapan/bagian/Dokumen.svelte';
	import { toast } from 'svelte-sonner';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import Save from '@lucide/svelte/icons/save';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ListChecks from '@lucide/svelte/icons/list-checks';

	const id = $derived(page.params.id!);
	const bagian = $derived(page.params.bagian as string);
	const valid = $derived(adalahBagian(bagian));
	const meta = $derived(valid ? META_BAGIAN[bagian as IdBagian] : null);

	let app = $state<Aplikasi | null>(null);
	let katalog = $state<Katalog | null>(null);
	let p = $state<PersiapanAuth | null>(null);
	let galat = $state<string | null>(null);
	let menyimpan = $state(false);

	$effect(() => {
		if (!valid) return;
		const aid = id;
		Promise.all([api.getAplikasi(aid), api.getKatalog(), api.getPersiapanAuth(aid)])
			.then(([a, k, simpanan]) => {
				app = a;
				katalog = k;
				p = simpanan ? { ...persiapanAuthKosong(), ...simpanan } : persiapanAuthKosong();
			})
			.catch((e) => (galat = (e as Error).message));
	});

	const bisaUbah = $derived(auth.punya('pemilik', 'admin'));
	const fungsiAuth = $derived(katalog?.fungsi_keamanan.find((f) => f.id === 'AUTH') ?? null);

	// Kode metode ringkas + nama dari katalog, untuk lencana "n metode uji".
	const metode = $derived(
		(meta?.metode ?? []).map((k) => ({
			kode: k,
			nama: fungsiAuth?.kontrol.flatMap((c) => c.metode_pengujian).find((m) => m.id === `AUTH-${k}`)?.nama ?? ''
		}))
	);

	// Pertanyaan "Ada / Tidak ada" untuk bagian registrasi/reset/ubah (menggerbang isian).
	const tersediaBagian = $derived(
		bagian === 'registrasi'
			? (p?.registrasi.tersedia ?? null)
			: bagian === 'reset'
				? (p?.reset.tersedia ?? null)
				: bagian === 'ubah'
					? (p?.ubah_password.tersedia ?? null)
					: null
	);
	function setTersedia(v: boolean) {
		if (!p) return;
		if (bagian === 'registrasi') p.registrasi.tersedia = v;
		else if (bagian === 'reset') p.reset.tersedia = v;
		else if (bagian === 'ubah') p.ubah_password.tersedia = v;
	}

	// Alamat yang perlu divalidasi per bagian.
	const alamatBagian = $derived.by(() => {
		if (!p) return [] as string[];
		switch (bagian) {
			case 'login':
				return [p.login.jalur_halaman, p.login.jalur_aksi, p.login.jalur_terbatas];
			case 'registrasi':
				return [p.registrasi.jalur_halaman, p.registrasi.jalur_aksi];
			case 'reset':
				return [p.reset.jalur_halaman, p.reset.jalur_aksi];
			case 'ubah':
				return [p.ubah_password.jalur_halaman, p.ubah_password.jalur_aksi];
			default:
				return [];
		}
	});
	const adaAlamatSalah = $derived(alamatBagian.some(alamatSalah));

	async function simpan() {
		if (!p) return;
		if (adaAlamatSalah) {
			toast.error('Periksa kembali alamat yang ditandai merah (harus lengkap, diawali https://).');
			return;
		}
		menyimpan = true;
		try {
			// Snapshot penuh (masih memuat kata sandi akun uji) untuk dipetakan ke scan_targets,
			// karena respons simpanPersiapanAuth menyamarkan kata sandi.
			const penuh = $state.snapshot(p) as PersiapanAuth;
			const hasil = await api.simpanPersiapanAuth(id, penuh);
			p = { ...persiapanAuthKosong(), ...hasil };
			toast.success(`Bagian "${meta?.judul}" tersimpan`);
			// Kirim data yang dibutuhkan mesin uji ke scan_targets backend (best-effort:
			// kegagalan sinkronisasi tidak membatalkan simpan persiapan).
			try {
				await api.simpanTargetUji(id, petakanKeScanTarget(penuh));
			} catch (e) {
				toast.warning(`Tersimpan, tetapi gagal mengirim ke mesin uji: ${(e as Error).message}`);
			}
			await goto(`/aplikasi/${id}/persiapan/auth`);
		} catch (e) {
			toast.error((e as Error).message);
		} finally {
			menyimpan = false;
		}
	}
</script>

<svelte:head><title>{meta?.judul ?? 'Bagian'} — Persiapan — SATRIA</title></svelte:head>

{#if !valid}
	<Kosong judul="Bagian tidak dikenal" pesan="Bagian persiapan yang Anda tuju tidak ada.">
		<Button href="/aplikasi/{id}/persiapan/auth" variant="outline">Kembali ke daftar</Button>
	</Kosong>
{:else if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app || !katalog || !p || !meta}
	<Memuat />
{:else}
	<div class="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
		<div class="min-w-0">
			<a href="/aplikasi/{app.id}/persiapan/auth" class="mb-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Daftar bagian
			</a>
			<p class="label-stensil text-[10px]">Autentikasi · bagian {meta.nomor} dari 8</p>
			<h1 class="flex flex-wrap items-center gap-2.5 font-heading text-2xl font-semibold tracking-[0.04em] uppercase">
				{meta.judul}
				{#if meta.wajib}<span class="rounded-sm bg-critical/12 px-1.5 py-0.5 font-sans text-[10px] font-medium tracking-normal text-critical normal-case">Wajib</span>{/if}
			</h1>
			<p class="mt-1 max-w-2xl text-sm text-muted-foreground">{meta.ket}</p>
		</div>
		<!-- Metode yang memakai isian bagian ini: cukup jumlahnya; daftar muncul saat disorot. -->
		{#if metode.length}
			<Tooltip.Root>
				<Tooltip.Trigger
					type="button"
					class="mt-1 inline-flex shrink-0 items-center gap-1 rounded-sm border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:border-gold/50 hover:text-foreground"
				>
					<ListChecks class="size-3.5" /> {metode.length} metode uji
				</Tooltip.Trigger>
				<Tooltip.Content class="max-w-80">
					<div class="grid gap-1 py-0.5">
						<p class="text-[11px] font-semibold">Isian bagian ini dipakai oleh:</p>
						<ul class="grid gap-1 text-[11px]">
							{#each metode as m (m.kode)}
								<li class="grid grid-cols-[52px_1fr] gap-1.5"><span class="font-mono opacity-70">{m.kode}</span><span>{m.nama}</span></li>
							{/each}
						</ul>
					</div>
				</Tooltip.Content>
			</Tooltip.Root>
		{/if}
	</div>

	<fieldset class="grid min-w-0 max-w-3xl gap-5" disabled={!bisaUbah}>
		{#if meta.pertanyaan}
			<div class="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-4 py-3">
				<p class="text-sm font-medium">{meta.pertanyaan}</p>
				<div class="inline-flex rounded-md border p-0.5 text-sm" role="radiogroup" aria-label={meta.pertanyaan}>
					{#each [{ v: true, l: 'Ada' }, { v: false, l: 'Tidak ada' }] as o (o.l)}
						<button
							type="button"
							role="radio"
							aria-checked={tersediaBagian === o.v}
							class={cn(
								'rounded px-3 py-1 transition-colors',
								tersediaBagian === o.v ? (o.v ? 'bg-gold text-gold-foreground' : 'bg-muted-foreground/80 text-background') : 'text-muted-foreground hover:bg-muted'
							)}
							onclick={() => setTersedia(o.v)}
						>
							{o.l}
						</button>
					{/each}
				</div>
			</div>
		{/if}

		{#if !meta.pertanyaan || tersediaBagian === true}
			{#if bagian === 'login'}
				<Login bind:p app={app} />
			{:else if bagian === 'registrasi'}
				<Registrasi bind:p app={app} />
			{:else if bagian === 'reset'}
				<Reset bind:p app={app} />
			{:else if bagian === 'ubah'}
				<Ubah bind:p app={app} />
			{:else if bagian === 'akun'}
				<AkunUji bind:p />
			{:else if bagian === 'pengaman'}
				<Pengaman bind:p />
			{:else if bagian === 'izin'}
				<Izin bind:p />
			{:else if bagian === 'dokumen'}
				<Dokumen bind:p />
			{/if}
		{:else if tersediaBagian === false}
			<p class="text-sm text-muted-foreground">Metode di bagian ini akan <b>dilewati</b> karena fitur tidak ada di aplikasi.</p>
		{:else}
			<p class="text-sm text-muted-foreground">Pilih <b>Ada</b> atau <b>Tidak ada</b> terlebih dahulu.</p>
		{/if}

		{#if bisaUbah}
			<div class="mt-1 flex justify-end gap-2 border-t pt-4">
				<Button variant="outline" href="/aplikasi/{app.id}/persiapan/auth">Kembali</Button>
				<Button onclick={simpan} disabled={menyimpan} class="bg-gold text-gold-foreground hover:bg-gold/85">
					{#if menyimpan}<LoaderCircle class="animate-spin" /> Menyimpan…{:else}<Save /> Simpan bagian{/if}
				</Button>
			</div>
		{/if}
	</fieldset>
{/if}
