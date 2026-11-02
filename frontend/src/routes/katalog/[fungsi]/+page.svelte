<script lang="ts">
	// Kriteria (kontrol) satu fungsi keamanan: daftar di kiri, detail kriteria terpilih di kanan.
	// Kedua panel mengisi tinggi layar dan digulir sendiri-sendiri; pilihan disimpan di URL (?k=KODE).
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { fade } from 'svelte/transition';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import type { Katalog, KetersediaanWorker, Kontrol, Metode } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import SeverityBadge from '#lib/components/SeverityBadge.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import DialogKontrol from '#lib/components/DialogKontrol.svelte';
	import DialogMetode from '#lib/components/DialogMetode.svelte';
	import KartuMetode from '#lib/components/KartuMetode.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Search from '@lucide/svelte/icons/search';
	import Pencil from '@lucide/svelte/icons/pencil';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import Plus from '@lucide/svelte/icons/plus';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import MousePointerClick from '@lucide/svelte/icons/mouse-pointer-click';

	let katalog = $state<Katalog | null>(null);
	let galatMuat = $state<string | null>(null);

	async function muat() {
		try {
			katalog = await api.getKatalog();
			galatMuat = null;
		} catch (e) {
			galatMuat = (e as Error).message;
		}
	}
	$effect(() => {
		muat();
	});

	const admin = $derived(auth.punya('admin'));
	const fungsi = $derived(katalog?.fungsi_keamanan.find((f) => f.id === page.params.fungsi) ?? null);
	const aktif = (x: { aktif?: boolean }) => x.aktif !== false;
	const namaTitikUji = $derived(new Map((katalog?.titik_uji ?? []).map((t) => [t.id, t.nama])));
	const kapital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

	let cari = $state('');
	/** Aktif = hanya yang dipakai di pengujian; semua = termasuk yang dinonaktifkan (khusus admin). */
	let tampil = $state<'aktif' | 'semua'>('aktif');
	const lihatSemua = $derived(admin && tampil === 'semua');

	// --- Daftar kriteria (kiri)
	const daftar = $derived(
		(fungsi?.kontrol ?? []).filter((k) => {
			if (!lihatSemua && !aktif(k)) return false;
			const q = cari.trim().toLowerCase();
			if (!q) return true;
			return [k.id, k.nomor_referensi, k.uraian, ...k.metode_pengujian.flatMap((m) => [m.id, m.nama, m.check_id])].some((s) =>
				s.toLowerCase().includes(q)
			);
		})
	);
	const jumlahKriteria = $derived((fungsi?.kontrol ?? []).filter(aktif).length);
	const jumlahMetode = $derived((fungsi?.kontrol ?? []).filter(aktif).reduce((n, k) => n + k.metode_pengujian.filter(aktif).length, 0));

	// --- Kriteria terpilih (kanan): dari URL; bila tidak ada/tersaring pakai yang pertama.
	let kodeDipilih = $state<string | null>(page.url.searchParams.get('k'));
	const dipilih = $derived(daftar.find((k) => k.id === kodeDipilih) ?? daftar[0] ?? null);
	const metodeDipilih = $derived((dipilih?.metode_pengujian ?? []).filter((m) => lihatSemua || aktif(m)));

	// Ketersediaan worker per check_id (sementara data contoh dari mock; lihat api.getKetersediaanWorker).
	let worker = $state<KetersediaanWorker>({});
	// Registri worker belum ada di backend, jadi status worker selalu berupa data contoh.
	const workerContoh = true;
	$effect(() => {
		api.getKetersediaanWorker().then((w) => (worker = w)).catch(() => (worker = {}));
	});
	const kesiapan = $derived(
		metodeDipilih.reduce(
			(n, m) => {
				if (m.engine === 'manual') n.asesor++;
				else if ((worker[m.check_id]?.siap ?? 0) > 0) n.siap++;
				else n.tanpaWorker++;
				return n;
			},
			{ siap: 0, asesor: 0, tanpaWorker: 0 }
		)
	);

	let panel = $state<HTMLElement>();
	function pilih(kode: string) {
		kodeDipilih = kode;
		const url = new URL(page.url.href);
		url.searchParams.set('k', kode);
		replaceState(url, {});
		panel?.scrollTo({ top: 0 });
		// Layar sempit: panel detail ada di bawah daftar.
		if (panel && matchMedia('(max-width: 1023px)').matches) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	const nomorMetode = (m: Metode) => m.id.match(/-(T\d+)$/)?.[1] ?? m.id;
	const tampilNilai = (v: unknown) =>
		Array.isArray(v) && v.every((x) => typeof x !== 'object') ? v.join(', ') : typeof v === 'object' ? 'struktur bertingkat' : String(v);

	// --- Dialog penyuntingan (admin)
	let dialogKontrol = $state(false);
	let kontrolDialog = $state<Kontrol | null>(null);
	let dialogMetode = $state(false);
	let metodeDialog = $state<Metode | null>(null);

	function bukaKontrol(k: Kontrol | null = null) {
		kontrolDialog = k;
		dialogKontrol = true;
	}
	function bukaMetode(m: Metode | null = null) {
		kontrolDialog = dipilih;
		metodeDialog = m;
		dialogMetode = true;
	}
	async function alihAktifMetode(m: Metode) {
		try {
			await api.ubahMetode(m.id, { aktif: !aktif(m) });
			toast.success(`Metode ${m.id} ${aktif(m) ? 'dinonaktifkan' : 'diaktifkan kembali'}`);
			await muat();
		} catch (e) {
			toast.error((e as Error).message);
		}
	}

	const LABEL_PEMBUKTIAN = {
		otomatis: 'Otomatis oleh sistem',
		sebagian: 'Sebagian otomatis, sebagian asesor',
		manual: 'Diperiksa asesor'
	};
</script>

<svelte:head><title>{fungsi?.nama ?? 'Katalog'} — Katalog Kontrol — SATYA</title></svelte:head>

{#snippet properti(label: string, isi: import('svelte').Snippet)}
	<div class="min-w-0">
		<p class="label-stensil text-[10px] text-muted-foreground">{label}</p>
		<div class="mt-1 text-sm">{@render isi()}</div>
	</div>
{/snippet}

{#if galatMuat}
	<Kosong judul="Katalog gagal dimuat" pesan={galatMuat}><Button variant="outline" onclick={muat}>Coba lagi</Button></Kosong>
{:else if !katalog}
	<Memuat />
{:else if !fungsi}
	<Kosong judul="Fungsi keamanan tidak ditemukan" pesan="Kode {page.params.fungsi} tidak ada di katalog.">
		<Button href="/katalog" variant="outline">Kembali ke katalog</Button>
	</Kosong>
{:else}
	<!-- Kepala ringkas agar kedua panel muat di layar. -->
	<div class="mb-4 flex flex-wrap items-end justify-between gap-3">
		<div>
			<a href="/katalog" class="mb-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Katalog kontrol
			</a>
			<h1 class="flex items-center gap-3">
				<span class="font-stencil text-3xl leading-none text-gold">{String(fungsi.nomor).padStart(2, '0')}</span>
				<span class="h-7 w-px bg-gold/50" aria-hidden="true"></span>
				<span class="font-heading text-2xl font-semibold tracking-[0.04em] uppercase">{fungsi.nama}</span>
			</h1>
		</div>
		<p class="font-heading text-xs tracking-[0.14em] text-muted-foreground uppercase">
			<b class="font-stencil text-base text-foreground">{jumlahKriteria}</b> kriteria ·
			<b class="font-stencil text-base text-foreground">{jumlahMetode}</b> metode uji
		</p>
	</div>

	<div class="grid gap-4 lg:h-[calc(100svh-15rem)] lg:min-h-[480px] lg:grid-cols-[minmax(260px,340px)_1fr]">
		<!-- ===================== Kiri: daftar kriteria ===================== -->
		<aside class="sudut-taktis flex min-h-0 flex-col rounded-lg border bg-card max-lg:max-h-[60svh]" aria-label="Daftar kriteria keamanan">
			<div class="grid gap-2 border-b p-3">
				<div class="relative">
					<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
					<Input bind:value={cari} placeholder="Cari kriteria…" class="h-9 pl-8" />
				</div>
				{#if admin}
					<div class="flex items-center justify-between gap-2">
						<div class="inline-flex rounded-md border p-0.5 text-xs" role="radiogroup" aria-label="Tampilkan">
							{#each [{ v: 'aktif', l: 'Aktif' }, { v: 'semua', l: 'Semua' }] as o (o.v)}
								<button
									type="button"
									role="radio"
									aria-checked={tampil === o.v}
									class={cn('rounded px-3 py-1 transition-colors', tampil === o.v ? 'bg-gold text-gold-foreground' : 'text-muted-foreground hover:bg-muted')}
									onclick={() => (tampil = o.v as typeof tampil)}
								>
									{o.l}
								</button>
							{/each}
						</div>
						<Button size="sm" variant="ghost" class="h-8 text-gold" onclick={() => bukaKontrol()}><Plus /> Kriteria</Button>
					</div>
				{/if}
			</div>

			<ul class="min-h-0 flex-1 overflow-y-auto p-1.5">
				{#each daftar as k (k.id)}
					{@const terpilih = dipilih?.id === k.id}
					<li>
						<button
							type="button"
							onclick={() => pilih(k.id)}
							aria-current={terpilih ? 'true' : undefined}
							class={cn(
								'relative flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition-colors',
								terpilih ? 'bg-gold/12' : 'hover:bg-muted/60'
							)}
						>
							{#if terpilih}<span class="absolute inset-y-1.5 left-0 w-1 rounded-r bg-gold"></span>{/if}
							<span
								class={cn(
									'grid h-6 min-w-9 shrink-0 place-items-center rounded-sm border px-1 font-mono text-[11px] font-semibold',
									terpilih ? 'border-gold/60 text-gold' : 'text-muted-foreground'
								)}
							>
								{k.nomor_referensi}
							</span>
							<span class="min-w-0 flex-1">
								<span class={cn('line-clamp-2 text-sm leading-snug', terpilih && 'font-medium')}>{kapital(k.uraian)}</span>
								<span class="mt-0.5 block text-[11px] text-muted-foreground">
									{k.metode_pengujian.filter(aktif).length} metode uji{#if !aktif(k)}<span class="ml-1 font-semibold text-critical/80">· nonaktif</span>{/if}
								</span>
							</span>
						</button>
					</li>
				{:else}
					<li class="px-3 py-8 text-center text-sm text-muted-foreground">Tidak ada kriteria yang cocok.</li>
				{/each}
			</ul>
		</aside>

		<!-- ===================== Kanan: detail kriteria terpilih ===================== -->
		<section bind:this={panel} class="sudut-taktis min-h-0 scroll-mt-24 overflow-x-hidden overflow-y-auto rounded-lg border bg-card" aria-live="polite">
			{#if !dipilih}
				<div class="grid h-full place-items-center p-10 text-center text-sm text-muted-foreground">
					<div><MousePointerClick class="mx-auto mb-2 size-6" />Pilih kriteria di sebelah kiri untuk melihat detailnya.</div>
				</div>
			{:else}
				{#key dipilih.id}
					<div in:fade={{ duration: 150 }}>
						<!-- Kepala kriteria -->
						<div class="border-b p-5 sm:p-6">
							<div class="flex items-start gap-3">
								<div class="min-w-0 flex-1">
									<p class="label-stensil text-[10px]">
										Kriteria {dipilih.nomor_referensi}
										<span class="ml-1 font-mono tracking-normal text-muted-foreground normal-case">{dipilih.id}</span>
									</p>
									<h2 class="mt-1 text-xl leading-snug font-semibold">{kapital(dipilih.uraian)}</h2>
								</div>
								{#if !aktif(dipilih)}
									<span class="inline-flex shrink-0 items-center gap-1 rounded-sm border border-critical/40 bg-critical/10 px-2 py-0.5 text-xs font-medium text-critical">
										<EyeOff class="size-3" /> Nonaktif
									</span>
								{/if}
								{#if admin}
									<Button variant="outline" size="sm" class="shrink-0" onclick={() => bukaKontrol(dipilih)}><Pencil /> Ubah</Button>
								{/if}
							</div>

							<div class="mt-5 grid gap-4 sm:grid-cols-3">
								{#snippet sev()}<SeverityBadge severity={dipilih!.severity_default} />{/snippet}
								{#snippet bukti()}{LABEL_PEMBUKTIAN[dipilih!.verifiabilitas]}{/snippet}
								{#snippet syarat()}{dipilih!.agregasi === 'minimal_satu' ? 'Minimal satu metode lulus' : 'Semua metode harus lulus'}{/snippet}
								{@render properti('Tingkat risiko', sev)}
								{@render properti('Pembuktian', bukti)}
								{@render properti('Syarat lulus', syarat)}
							</div>

							{#if dipilih.referensi_pendukung?.length || dipilih.parameter}
								<div class="mt-4 grid gap-4 sm:grid-cols-3">
									{#if dipilih.referensi_pendukung?.length}
										{#snippet referensi()}
											<div class="flex flex-wrap gap-1">
												{#each dipilih!.referensi_pendukung ?? [] as r (r)}<span class="rounded bg-muted px-1.5 py-0.5 text-xs">{r}</span>{/each}
											</div>
										{/snippet}
										{@render properti('Referensi', referensi)}
									{/if}
									{#if dipilih.parameter}
										{#snippet param()}
											<dl class="grid gap-0.5 text-xs">
												{#each Object.entries(dipilih!.parameter ?? {}) as [k, v] (k)}
													<div class="flex gap-2"><dt class="font-mono text-muted-foreground">{k}</dt><dd class="min-w-0 break-words font-medium">{tampilNilai(v)}</dd></div>
												{/each}
											</dl>
										{/snippet}
										<div class="sm:col-span-2">{@render properti('Parameter', param)}</div>
									{/if}
								</div>
							{/if}
						</div>

						<!-- Metode pengujian -->
						<div class="p-5 sm:p-6">
							<div class="mb-4 flex flex-wrap items-end justify-between gap-2">
								<div>
									<h3 class="font-heading text-sm font-semibold tracking-[0.12em] uppercase">Metode pengujian · {metodeDipilih.length}</h3>
									<p class="text-xs text-muted-foreground">
										Langkah yang dijalankan untuk membuktikan kriteria ini.
										{#if metodeDipilih.length}
											<span class="ml-1 whitespace-nowrap">
												<b class={kesiapan.siap ? 'text-success' : 'text-muted-foreground'}>{kesiapan.siap} siap dijalankan</b>{#if kesiapan.asesor}{' · '}{kesiapan.asesor} oleh asesor{/if}{#if kesiapan.tanpaWorker}{' · '}<b class="text-critical">{kesiapan.tanpaWorker} belum ada worker</b>{/if}
											</span>
										{/if}
									</p>
								</div>
								{#if admin}
									<Button size="sm" variant="outline" onclick={() => bukaMetode()}><Plus /> Tambah metode</Button>
								{/if}
							</div>

							<ol class="grid gap-3">
								{#each metodeDipilih as m (m.id)}
									<li>
										<KartuMetode
											metode={m}
											bagianAplikasi={namaTitikUji.get(m.titik_uji) ?? m.titik_uji}
											worker={worker[m.check_id]}
											dataContoh={workerContoh}
											{admin}
											onubah={() => bukaMetode(m)}
											onalihaktif={() => alihAktifMetode(m)}
										/>
									</li>
								{:else}
									<li class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">Belum ada metode pengujian untuk kriteria ini.</li>
								{/each}
							</ol>
						</div>
					</div>
				{/key}
			{/if}
		</section>
	</div>

	{#if admin}
		<DialogKontrol bind:open={dialogKontrol} {fungsi} kontrol={kontrolDialog} onselesai={muat} />
		<DialogMetode bind:open={dialogMetode} kontrol={kontrolDialog} metode={metodeDialog} titikUji={katalog.titik_uji} onselesai={muat} />
	{/if}
{/if}
