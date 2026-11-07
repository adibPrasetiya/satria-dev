<script lang="ts">
	// Wizard jalur otomatis (eksploratif): isi ≥2 akun uji → review → S&K → mulai.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import type { Aplikasi } from '#lib/types.js';
	import type { TargetTersimpan } from '#lib/api/types.js';
	import { relatif, tanggal } from '#lib/format.js';
	import { totpUntukKirim, type AkunTarget } from '#lib/persiapan/target.js';
	import { parameterStandar, secretValid, type AlgoritmaTotp } from '#lib/totp.js';
	import InputTotp from '#lib/components/InputTotp.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import Field from '#lib/components/Field.svelte';
	import StepperAuth from '#lib/components/StepperAuth.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { toast } from 'svelte-sonner';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import ScanSearch from '@lucide/svelte/icons/scan-search';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Server from '@lucide/svelte/icons/server';
	import ListOrdered from '@lucide/svelte/icons/list-ordered';
	import { GalatApi } from '#lib/api/http.js';
	import { storeWorker, teksPerkiraan } from '#lib/stores/worker.svelte.js';
	import ClockCheck from '@lucide/svelte/icons/clock-check';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import UserPen from '@lucide/svelte/icons/user-pen';

	const id = $derived(page.params.id!);

	let app = $state<Aplikasi | null>(null);
	let galat = $state<string | null>(null);
	let langkah = $state(0);
	let memulai = $state(false);
	// Koordinasi worker: status dipoll; scan aktif aplikasi ini (satu pengujian aktif per aplikasi).
	$effect(() => storeWorker.pakai());
	let scanAktifId = $state<string | null>(null);
	const sw = $derived(storeWorker.status);

	type AkunForm = {
		username: string;
		password: string;
		totp_secret: string;
		totp_digits: number;
		totp_period: number;
		totp_algoritma: AlgoritmaTotp;
	};
	const akunKosong = (): AkunForm => ({
		username: '',
		password: '',
		totp_secret: '',
		totp_digits: 6,
		totp_period: 30,
		totp_algoritma: 'SHA1'
	});
	let akun = $state<AkunForm[]>([akunKosong(), akunKosong()]);
	let setujuPemindaian = $state(false);
	let izinkanBerisiko = $state(false);

	// Uji ulang: akun & hasil penemuan dari pengujian sebelumnya (scan_targets).
	let tersimpan = $state<TargetTersimpan | null>(null);
	let sumberAkun = $state<'tersimpan' | 'baru'>('baru');
	let sumberPenemuan = $state<'terakhir' | 'ulang'>('ulang');
	const akunTersimpan = $derived(tersimpan?.akun.filter((a) => a.ada_sandi) ?? []);
	const adaAkunTersimpan = $derived(akunTersimpan.length >= 2);
	const discovery = $derived(tersimpan?.discovery ?? null);

	type Langkah = 'akun' | 'penemuan' | 'review' | 'sk';
	const LANGKAH = $derived<Langkah[]>(discovery ? ['akun', 'penemuan', 'review', 'sk'] : ['akun', 'review', 'sk']);
	const JUDUL: Record<Langkah, string> = { akun: 'Akun Uji', penemuan: 'Recon & Discovery', review: 'Review', sk: 'Syarat & Ketentuan' };
	const LABEL = $derived(LANGKAH.map((l) => JUDUL[l]));
	const kini = $derived(LANGKAH[langkah]);

	const akunTerisi = $derived(akun.filter((a) => a.username.trim() && a.password.trim()));
	const pakaiAkunTersimpan = $derived(adaAkunTersimpan && sumberAkun === 'tersimpan');
	const akunValid = $derived(pakaiAkunTersimpan || akunTerisi.length >= 2);

	const bisaUbah = $derived(
		!!app &&
			(auth.punya('admin') ||
				(auth.punya('pemilik') &&
					(app.satuan_id ? app.satuan_id === auth.pengguna?.satuan_id : app.pemilik_id === auth.pengguna?.id)))
	);
	$effect(() => {
		const aid = id;
		api.listScan(aid)
			.then((xs) => (scanAktifId = xs.find((x) => x.status === 'berjalan')?.id ?? null))
			.catch(() => {});
		Promise.all([api.getAplikasi(aid), api.getTargetUji(aid).catch(() => null)])
			.then(([a, t]) => {
				tersimpan = t;
				if (t && t.akun.filter((x) => x.ada_sandi).length >= 2) sumberAkun = 'tersimpan';
				if (t?.discovery) sumberPenemuan = 'terakhir';
				app = a;
			})
			.catch((e) => (galat = e.message));
	});

	/** Ganti akun: form diisi username tersimpan (sandi tetap harus diketik ulang). */
	function gantiAkun() {
		sumberAkun = 'baru';
		if (akun.every((a) => !a.username.trim()) && akunTersimpan.length) {
			akun = akunTersimpan.map((a) => ({ ...akunKosong(), username: a.username }));
		}
	}

	function tambahAkun() {
		if (akun.length < 10) akun.push(akunKosong());
	}
	function hapusAkun(i: number) {
		if (akun.length > 2) akun.splice(i, 1);
	}

	function lanjut() {
		if (kini === 'akun' && !akunValid) {
			toast.error('Isi minimal 2 akun uji (username + kata sandi).');
			return;
		}
		if (kini === 'akun' && !pakaiAkunTersimpan && akun.some((a) => a.totp_secret.trim() && !secretValid(a.totp_secret))) {
			toast.error('Ada seed TOTP yang tidak valid. Perbaiki atau kosongkan.');
			return;
		}
		langkah = Math.min(langkah + 1, LABEL.length - 1);
	}
	function kembali() {
		langkah = Math.max(langkah - 1, 0);
	}

	// Engine tahap pertama: penemuan ulang → 'discovery'; pakai hasil penemuan terakhir → 'custom'.
	const engineAwal = $derived(!!discovery && sumberPenemuan === 'terakhir' ? 'custom' : 'discovery');
	const tanpaWorker = $derived(!!sw && !sw.engines.includes(engineAwal));
	const workerSibuk = $derived(!!sw && !tanpaWorker && (sw.siaga === 0 || sw.scan_baru.scan_di_depan > 0));

	async function mulai() {
		if (!app || !akunValid || !setujuPemindaian || tanpaWorker || scanAktifId) return;
		memulai = true;
		try {
			// Akun tersimpan: tidak dikirim — backend mempertahankan kredensial yang ada.
			const daftar: AkunTarget[] = akunTerisi.map((a) => ({
				username: a.username.trim(),
				password: a.password,
				...totpUntukKirim(a)
			}));
			const s = await api.mulaiScan(app.id, {
				mode: 'eksploratif',
				persetujuan: true,
				...(pakaiAkunTersimpan ? {} : { accounts: { daftar } }),
				options: { izinkan_penguncian: izinkanBerisiko },
				pakai_discovery: !!discovery && sumberPenemuan === 'terakhir'
			});
			await goto(`/scan/${s.id}`);
		} catch (e) {
			if (e instanceof GalatApi && e.code === 'SCAN_AKTIF') scanAktifId = String(e.detail?.scan_id ?? '') || null;
			if (e instanceof GalatApi && e.code === 'WORKER_TIDAK_AKTIF') void storeWorker.segarkan();
			toast.error((e as Error).message);
			memulai = false;
		}
	}
</script>

{#snippet pilihan(aktif: boolean, onpilih: () => void, Ikon: typeof ClockCheck, judul: string, keterangan: string)}
	<button
		type="button"
		onclick={onpilih}
		aria-pressed={aktif}
		class="sudut-taktis flex flex-col gap-1.5 rounded-lg border p-3 text-left transition {aktif ? 'border-gold bg-gold/10' : 'bg-card hover:border-gold/60 hover:bg-gold/5'}"
	>
		<span class="flex items-center gap-2">
			<Ikon class="size-4 {aktif ? 'text-gold' : 'text-muted-foreground'}" />
			<span class="font-heading text-sm tracking-wide uppercase">{judul}</span>
		</span>
		<span class="text-xs text-muted-foreground">{keterangan}</span>
	</button>
{/snippet}

<svelte:head><title>Pengujian Otomatis — {app?.nama ?? 'Aplikasi'}</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app}
	<Memuat />
{:else if !bisaUbah}
	<Kosong judul="Tidak berwenang" pesan="Hanya pemilik aset atau admin yang dapat memulai pengujian.">
		<Button href="/aplikasi/{app.id}" variant="outline">Kembali ke aset</Button>
	</Kosong>
{:else}
	<PageHeader label="Operasi Pengujian · Otomatis" judul={app.nama} deskripsi="{app.url_dasar} · mode eksploratif (penemuan otomatis)">
		{#snippet atas()}
			<a href="/aplikasi/{app!.id}" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Berkas aplikasi
			</a>
		{/snippet}
	</PageHeader>

	<!-- Stepper di panel loreng gelap -->
	<div class="bg-loreng sudut-taktis mb-6 rounded-lg p-4">
		<StepperAuth {langkah} label={LABEL} onpilih={(i) => (langkah = i)} />
	</div>

	<div class="mx-auto max-w-3xl">
		{#if kini === 'akun'}
			<!-- Langkah 1: Akun uji -->
			<div class="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 px-3 py-2 text-xs text-warning-foreground">
				<TriangleAlert class="mt-0.5 size-3.5 shrink-0" />
				<p>Gunakan akun yang dibuat khusus untuk SATRIA dengan hak akses biasa. Kata sandi akun ini bisa diganti oleh mesin uji saat menguji fitur ubah kata sandi.</p>
			</div>

			{#if adaAkunTersimpan}
				<!-- Uji ulang: tawarkan kredensial dari pengujian sebelumnya -->
				<div class="sudut-taktis mt-4 rounded-lg border bg-card p-4">
					<p class="label-stensil text-[10px] text-muted-foreground">Akun uji tersimpan ({akunTersimpan.length})</p>
					<ul class="mt-2 divide-y rounded-md border">
						{#each akunTersimpan as a, i (i)}
							<li class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
								<span class="inline-flex items-center gap-2"><KeyRound class="size-3.5 text-gold" /><span class="font-medium">{a.username}</span></span>
								<span class="flex items-center gap-3 text-xs text-muted-foreground"><span>sandi ••••••</span><span>TOTP {a.ada_totp ? '✓' : '—'}</span></span>
							</li>
						{/each}
					</ul>
					<div class="mt-3 grid gap-3 sm:grid-cols-2">
						{@render pilihan(sumberAkun === 'tersimpan', () => (sumberAkun = 'tersimpan'), ClockCheck, 'Gunakan akun tersimpan', 'Pakai kredensial dari pengujian sebelumnya.')}
						{@render pilihan(sumberAkun === 'baru', gantiAkun, UserPen, 'Ganti akun', 'Isi kredensial baru (menggantikan yang tersimpan).')}
					</div>
				</div>
			{/if}

			{#if !pakaiAkunTersimpan}
			<div class="mt-4 grid gap-4">
				{#each akun as a, i (i)}
					<div class="sudut-taktis rounded-lg border bg-card p-4">
						<div class="mb-3 flex items-center justify-between">
							<p class="label-stensil text-[10px]">Akun uji {i + 1}{i === 0 ? ' (utama)' : ''}</p>
							{#if akun.length > 2}
								<button type="button" onclick={() => hapusAkun(i)} class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-critical">
									<Trash2 class="size-3.5" /> Hapus
								</button>
							{/if}
						</div>
						<div class="grid gap-4 sm:grid-cols-2">
							<Field label="Username / email" id="akun-{i}-user" wajib>
								<Input id="akun-{i}-user" class="h-9" autocomplete="off" bind:value={a.username} />
							</Field>
							<Field label="Kata sandi" id="akun-{i}-pass" wajib>
								<Input id="akun-{i}-pass" class="h-9" type="password" autocomplete="new-password" bind:value={a.password} />
							</Field>
							<div class="sm:col-span-2">
								<InputTotp
									id="akun-{i}-totp"
									bind:secret={a.totp_secret}
									bind:digits={a.totp_digits}
									bind:period={a.totp_period}
									bind:algoritma={a.totp_algoritma}
								/>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<div class="mt-3 flex items-center justify-between">
				<Button variant="outline" size="sm" onclick={tambahAkun} disabled={akun.length >= 10}><Plus /> Tambah akun</Button>
				<p class="text-xs text-muted-foreground">{akunTerisi.length} akun terisi · minimal 2</p>
			</div>
			{/if}
		{:else if kini === 'penemuan' && discovery}
			<!-- Langkah 2 (uji ulang): hasil penemuan terakhir -->
			<div class="sudut-taktis rounded-lg border bg-card p-5">
				<div class="flex items-start justify-between gap-3">
					<div>
						<p class="label-stensil text-muted-foreground">Hasil penemuan terakhir</p>
						<p class="mt-1 text-xs text-muted-foreground">
							{#if discovery.waktu}{tanggal(discovery.waktu)} · {relatif(discovery.waktu)}{:else}Waktu tidak diketahui{/if}
							{#if discovery.scan_id}· <a href="/scan/{discovery.scan_id}" class="underline hover:text-foreground">pengujian #{discovery.scan_id}</a>{/if}
						</p>
					</div>
					<span class="rounded-sm border px-1.5 py-px font-heading text-[10px] tracking-wide uppercase {discovery.terautentikasi ? 'border-success/50 bg-success/10 text-success' : 'border-warning/50 bg-warning/10 text-warning-foreground'}">
						{discovery.terautentikasi ? 'Terautentikasi' : 'Anonim'}
					</span>
				</div>
				<dl class="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
					<div class="rounded-md border p-2"><dt class="text-[11px] text-muted-foreground">Endpoint unik</dt><dd class="font-heading text-lg">{discovery.jumlah_endpoint_unik}</dd></div>
					<div class="rounded-md border p-2"><dt class="text-[11px] text-muted-foreground">Halaman</dt><dd class="font-heading text-lg">{discovery.jumlah_halaman}</dd></div>
					<div class="rounded-md border p-2"><dt class="text-[11px] text-muted-foreground">Alur bisnis</dt><dd class="font-heading text-lg">{discovery.jumlah_alur}</dd></div>
					<div class="rounded-md border p-2"><dt class="text-[11px] text-muted-foreground">Titik uji</dt><dd class="font-heading text-lg">{discovery.titik_ditemukan.length}</dd></div>
				</dl>
				{#if discovery.titik_ditemukan.length}
					<p class="mt-3 text-xs text-muted-foreground">Titik uji: <span class="text-foreground">{discovery.titik_ditemukan.join(', ')}</span></p>
				{/if}
				{#if discovery.openapi}
					<p class="mt-1 text-xs text-muted-foreground">OpenAPI: <span class="text-foreground">{discovery.openapi.judul || '—'}</span> ({discovery.openapi.jumlah_endpoint} endpoint)</p>
				{/if}
				{#if Object.keys(discovery.kandidat).length}
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each Object.entries(discovery.kandidat) as [k, n] (k)}
							<span class="rounded-sm border px-1.5 py-px font-mono text-[11px]">{k} <span class="text-muted-foreground">{n}</span></span>
						{/each}
					</div>
				{/if}
				{#if discovery.contoh_endpoint.length}
					<ul class="mt-3 max-h-56 overflow-y-auto rounded-md border font-mono text-xs">
						{#each discovery.contoh_endpoint as e, i (i)}
							<li class="flex gap-3 border-b px-3 py-1.5 last:border-b-0">
								<span class="w-14 shrink-0 text-gold">{e.metode_http}</span>
								<span class="break-all">{e.path}</span>
								{#if e.butuh_autentikasi}<KeyRound class="ml-auto size-3 shrink-0 text-muted-foreground" />{/if}
							</li>
						{/each}
					</ul>
					{#if discovery.jumlah_endpoint_unik > discovery.contoh_endpoint.length}
						<p class="mt-1 text-[11px] text-muted-foreground">… dan {discovery.jumlah_endpoint_unik - discovery.contoh_endpoint.length} endpoint lain.</p>
					{/if}
				{/if}
				<div class="mt-4 grid gap-3 sm:grid-cols-2">
					{@render pilihan(sumberPenemuan === 'terakhir', () => (sumberPenemuan = 'terakhir'), ClockCheck, 'Gunakan hasil ini', 'Lewati penemuan; langsung ke fase pengujian.')}
					{@render pilihan(sumberPenemuan === 'ulang', () => (sumberPenemuan = 'ulang'), RefreshCw, 'Discovery ulang', 'Petakan ulang permukaan aplikasi (bila ada perubahan).')}
				</div>
			</div>
		{:else if kini === 'review'}
			<!-- Review -->
			<div class="sudut-taktis rounded-lg border bg-card p-5">
				<p class="label-stensil text-muted-foreground">Ringkasan</p>
				<dl class="mt-3 grid gap-2 text-sm sm:grid-cols-2">
					<div><dt class="text-muted-foreground">Target</dt><dd class="font-mono break-all">{app.url_dasar}</dd></div>
					<div><dt class="text-muted-foreground">Mode</dt><dd>Eksploratif (penemuan otomatis)</dd></div>
					<div>
						<dt class="text-muted-foreground">Penemuan</dt>
						<dd>{discovery && sumberPenemuan === 'terakhir' ? `Pakai hasil terakhir (${relatif(discovery.waktu ?? undefined)})` : 'Jalankan penemuan baru'}</dd>
					</div>
					<div><dt class="text-muted-foreground">Sumber akun</dt><dd>{pakaiAkunTersimpan ? 'Akun tersimpan' : 'Akun baru'}</dd></div>
				</dl>
				{#if pakaiAkunTersimpan}
					<p class="label-stensil mt-5 text-muted-foreground">Akun uji ({akunTersimpan.length})</p>
					<ul class="mt-2 divide-y rounded-md border">
						{#each akunTersimpan as a, i (i)}
							<li class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
								<span class="inline-flex items-center gap-2"><KeyRound class="size-3.5 text-gold" /><span class="font-medium">{a.username}</span></span>
								<span class="flex items-center gap-3 text-xs text-muted-foreground"><span>sandi ••••••</span><span>TOTP {a.ada_totp ? '✓' : '—'}</span></span>
							</li>
						{/each}
					</ul>
				{:else}
				<p class="label-stensil mt-5 text-muted-foreground">Akun uji ({akunTerisi.length})</p>
				<ul class="mt-2 divide-y rounded-md border">
					{#each akunTerisi as a, i (i)}
						<li class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
							<span class="inline-flex items-center gap-2"><KeyRound class="size-3.5 text-gold" /><span class="font-medium">{a.username}</span></span>
							<span class="flex items-center gap-3 text-xs text-muted-foreground">
								<span>sandi ••••••</span>
								<span>
									TOTP {a.totp_secret.trim() ? '✓' : '—'}{#if a.totp_secret.trim() && !parameterStandar({ digits: a.totp_digits, period: a.totp_period, algoritma: a.totp_algoritma })}
										({a.totp_digits} digit/{a.totp_period} dtk/{a.totp_algoritma}){/if}
								</span>
							</span>
						</li>
					{/each}
				</ul>
				{/if}
			</div>
		{:else}
			<!-- Langkah 3: Syarat & Ketentuan -->
			<div class="sudut-taktis rounded-lg border bg-card p-5">
				<div class="flex items-center gap-2"><ShieldCheck class="size-5 text-gold" /><p class="font-heading tracking-wide uppercase">Syarat & Ketentuan</p></div>
				<p class="mt-2 text-sm text-muted-foreground">Efek yang dapat terjadi pada aplikasi selama pengujian:</p>
				<ul class="mt-3 space-y-2 text-sm">
					<li class="flex gap-2"><span class="text-gold">•</span> Fase <strong>penemuan</strong> hanya membaca (GET, render SPA, sadap lalu lintas) — tidak mengubah data.</li>
					<li class="flex gap-2"><span class="text-gold">•</span> Fase <strong>pengujian</strong> mengirim lalu lintas uji ke target dan dapat <strong>membuat data</strong> (mis. registrasi/percobaan).</li>
					<li class="flex gap-2"><span class="text-gold">•</span> Uji kebijakan sandi dapat <strong>mengubah kata sandi akun uji</strong>; uji penguncian dapat <strong>mengunci akun uji sementara</strong>.</li>
					<li class="flex gap-2"><span class="text-gold">•</span> Gunakan hanya akun & lingkungan yang Anda berwenang menguji.</li>
				</ul>

				<label class="mt-4 flex items-start gap-2 rounded-md border border-warning/50 bg-warning/10 p-3 text-sm">
					<Checkbox bind:checked={setujuPemindaian} class="mt-0.5" />
					<span class="flex items-start gap-1.5">
						<TriangleAlert class="mt-0.5 size-4 shrink-0 text-warning-foreground" />
						<span>Saya berwenang menguji aplikasi ini dan menyetujui <strong>pemindaian aktif</strong> terhadap target.</span>
					</span>
				</label>
				<label class="mt-2 flex items-start gap-2 rounded-md border p-3 text-sm">
					<Checkbox bind:checked={izinkanBerisiko} class="mt-0.5" />
					<span>Izinkan uji <strong>berisiko</strong> (penguncian akun / ubah kata sandi) pada akun uji.</span>
				</label>
			</div>
		{/if}

		<!-- Status worker & antrean (langkah terakhir) -->
		{#if langkah === LABEL.length - 1}
			{#if scanAktifId}
				<div class="mt-4 flex items-start gap-2 rounded-md border border-warning/50 bg-warning/10 p-3 text-sm">
					<TriangleAlert class="mt-0.5 size-4 shrink-0 text-warning-foreground" />
					<span>Aplikasi ini masih memiliki pengujian yang berjalan/mengantre. Satu aplikasi hanya boleh punya satu pengujian aktif.
						<a href="/scan/{scanAktifId}" class="font-medium text-gold underline">Lihat pengujian yang berjalan</a></span>
				</div>
			{:else if !sw}
				<p class="mt-4 flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle class="size-4 animate-spin" /> Memeriksa ketersediaan worker…</p>
			{:else if tanpaWorker}
				<div class="mt-4 flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm">
					<Server class="mt-0.5 size-4 shrink-0 text-destructive" />
					<span><strong>Tidak ada worker pengujian yang aktif</strong>{sw.aktif ? ` untuk engine "${engineAwal}"` : ''}. Pengujian tidak dapat dimulai sampai worker dinyalakan
						(<code class="rounded bg-black/30 px-1">python -m satya_worker.main</code> di folder <code class="rounded bg-black/30 px-1">worker</code>). Status diperiksa ulang tiap 10 detik.</span>
				</div>
			{:else if workerSibuk}
				<div class="mt-4 flex items-start gap-2 rounded-md border border-gold/50 bg-gold/10 p-3 text-sm">
					<ListOrdered class="mt-0.5 size-4 shrink-0 text-gold" />
					<span>Worker sedang menjalankan pengujian lain. Pengujian Anda akan <strong>masuk antrean ke-{sw.scan_baru.posisi}</strong>
						(perkiraan mulai {teksPerkiraan(sw.scan_baru.perkiraan_tunggu_detik)}). Anda dapat menutup halaman; pengujian berjalan otomatis saat gilirannya tiba.</span>
				</div>
			{:else}
				<p class="mt-4 flex items-center gap-2 text-sm text-muted-foreground"><span class="size-2 rounded-full bg-[#9fe08a]"></span> Worker siaga — pengujian langsung dikerjakan.</p>
			{/if}
		{/if}

		<!-- Navigasi -->
		<div class="mt-6 flex items-center justify-between">
			<Button variant="outline" onclick={kembali} disabled={langkah === 0}><ChevronLeft /> Kembali</Button>
			{#if langkah < LABEL.length - 1}
				<Button onclick={lanjut} class="bg-gold text-gold-foreground hover:bg-gold/85">Lanjut <ChevronRight /></Button>
			{:else}
				<Button onclick={mulai} disabled={memulai || !akunValid || !setujuPemindaian || tanpaWorker || !!scanAktifId || !sw} class="bg-gold text-gold-foreground hover:bg-gold/85">
					{#if memulai}<LoaderCircle class="animate-spin" /> Memulai…{:else if workerSibuk}<ListOrdered /> Masuk antrean{:else}<ScanSearch /> Mulai Pengujian{/if}
				</Button>
			{/if}
		</div>
	</div>
{/if}
