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
	import { parameterStandar, secretValid } from '#lib/totp.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import StepperAuth from '#lib/components/StepperAuth.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { toast } from 'svelte-sonner';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import UsersRound from '@lucide/svelte/icons/users-round';
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Lock from '@lucide/svelte/icons/lock';
	import Check from '@lucide/svelte/icons/check';
	import Radar from '@lucide/svelte/icons/radar';
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
	import DialogAkunUji, { type AkunForm } from '#lib/components/pengujian/DialogAkunUji.svelte';
	import { barisMetode, daftarTemuan, WARNA_SEVERITY } from '#lib/operasi/ringkas.js';
	import type { Scan, Severity } from '#lib/types.js';
	import FileText from '@lucide/svelte/icons/file-text';
	import BadgeCheck from '@lucide/svelte/icons/badge-check';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import DialogSyaratKetentuan from '#lib/components/pengujian/DialogSyaratKetentuan.svelte';
	import { KODE_SK, VERSI_SK, dampakPengujian, dokumenSK } from '#lib/pengujian/syarat-ketentuan.js';

	const id = $derived(page.params.id!);
	// Pendekatan dari modal Metode Pengujian: grey box (akun uji terbatas) | black box (tanpa akun/akses internal).
	const blackbox = $derived(page.url.searchParams.get('pendekatan') === 'blackbox');
	const NAMA_PENDEKATAN = $derived(blackbox ? 'Black Box' : 'Grey Box');

	let app = $state<Aplikasi | null>(null);
	let galat = $state<string | null>(null);
	let langkah = $state(0);
	let memulai = $state(false);
	// Koordinasi worker: status dipoll; scan aktif aplikasi ini (satu pengujian aktif per aplikasi).
	$effect(() => storeWorker.pakai());
	let scanAktifId = $state<string | null>(null);
	const sw = $derived(storeWorker.status);

	// Akun uji baru dibuat satu per satu lewat dialog (sudah tervalidasi saat disimpan).
	let akun = $state<AkunForm[]>([]);
	let dialogAkun = $state(false);
	let indeksUbah = $state<number | null>(null);
	let setujuPemindaian = $state(false);
	let izinkanBerisiko = $state(false);
	// Persetujuan S&K hanya diberikan lewat jendela dokumen (dibaca hingga akhir + dicentang).
	let dialogSK = $state(false);
	let waktuSetuju = $state<Date | null>(null);

	// Uji ulang: akun & hasil penemuan dari pengujian sebelumnya (scan_targets).
	let tersimpan = $state<TargetTersimpan | null>(null);
	let sumberAkun = $state<'tersimpan' | 'baru'>('baru');
	let sumberPenemuan = $state<'terakhir' | 'ulang'>('ulang');
	const akunTersimpan = $derived(tersimpan?.akun.filter((a) => a.ada_sandi) ?? []);
	const adaAkunTersimpan = $derived(akunTersimpan.length >= 2);
	const discovery = $derived(tersimpan?.discovery ?? null);

	type Langkah = 'akun' | 'penemuan' | 'review' | 'sk';
	// Alur sama untuk kedua metode; black box hanya tanpa langkah akun. Hasil penemuan tersimpan
	// ditawarkan ke black box hanya bila penemuan itu dijalankan tanpa login.
	const penemuanBisaDipakai = $derived(!!discovery && (!blackbox || !discovery.terautentikasi));
	const LANGKAH = $derived<Langkah[]>([
		...(blackbox ? [] : (['akun'] as Langkah[])),
		...(penemuanBisaDipakai ? (['penemuan'] as Langkah[]) : []),
		'review',
		'sk'
	]);
	const JUDUL: Record<Langkah, string> = { akun: 'Akun Uji', penemuan: 'Recon & Discovery', review: 'Review', sk: 'Syarat & Ketentuan' };
	const LABEL = $derived(LANGKAH.map((l) => JUDUL[l]));
	const kini = $derived(LANGKAH[langkah]);

	const akunTerisi = $derived(akun.filter((a) => a.username.trim() && a.password.trim()));
	const pakaiAkunTersimpan = $derived(adaAkunTersimpan && sumberAkun === 'tersimpan');
	const akunValid = $derived(blackbox || pakaiAkunTersimpan || akunTerisi.length >= 2);
	const pakaiPenemuanTerakhir = $derived(penemuanBisaDipakai && sumberPenemuan === 'terakhir');

	// Pengujian dilakukan asesor/admin; pemilik hanya melihat hasil.
	const bisaUji = $derived(!!app && auth.bisaMenguji);
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

	function gantiAkun() {
		sumberAkun = 'baru';
	}
	function bukaBuatAkun() {
		if (akun.length >= 10) return;
		indeksUbah = null;
		dialogAkun = true;
	}
	function bukaUbahAkun(i: number) {
		indeksUbah = i;
		dialogAkun = true;
	}
	function simpanAkun(a: AkunForm) {
		if (indeksUbah === null) akun.push(a);
		else akun[indeksUbah] = a;
	}
	function hapusAkun(i: number) {
		akun.splice(i, 1);
	}

	// Ringkasan recon terakhir: temuan & pendekatan dari scan sumber recon.
	let scanRecon = $state<Scan | null>(null);
	$effect(() => {
		const sid = discovery?.scan_id;
		if (!sid) return;
		api.getScan(sid).then((x) => (scanRecon = x)).catch(() => (scanRecon = null));
	});
	const temuanRecon = $derived(scanRecon ? daftarTemuan(barisMetode(scanRecon)) : discovery?.scan_id ? null : []);
	const sebaranRecon = $derived.by(() => {
		const n = new Map<Severity, number>();
		for (const t of temuanRecon ?? []) n.set(t.severity, (n.get(t.severity) ?? 0) + 1);
		return [...n.entries()];
	});
	const metodeRecon = $derived(
		scanRecon ? (scanRecon.pendekatan === 'blackbox' ? 'Black Box' : 'Grey Box') : discovery?.terautentikasi ? 'Grey Box' : null
	);

	function lanjut() {
		if (kini === 'akun' && !akunValid) {
			toast.error('Buat minimal 2 akun uji.');
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
	const engineAwal = $derived(pakaiPenemuanTerakhir ? 'custom' : 'discovery');
	const tanpaWorker = $derived(!!sw && !sw.engines.includes(engineAwal));
	const workerSibuk = $derived(!!sw && !tanpaWorker && (sw.siaga === 0 || sw.scan_baru.scan_di_depan > 0));

	// Masuk langkah S&K tanpa persetujuan → jendela dokumen langsung dibuka.
	$effect(() => {
		if (kini === 'sk' && !setujuPemindaian) dialogSK = true;
	});
	const dampak = $derived(dampakPengujian(blackbox));
	const jumlahPasal = $derived(dokumenSK(blackbox).length);
	const WARNA_TINGKAT = {
		rendah: 'border-success/50 bg-success/10 text-success',
		sedang: 'border-warning/50 bg-warning/10 text-warning-foreground',
		tinggi: 'border-critical/50 bg-critical/10 text-critical'
	} as const;

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
				pendekatan: blackbox ? 'blackbox' : 'greybox',
				persetujuan: true,
				...(blackbox || pakaiAkunTersimpan ? {} : { accounts: { daftar } }),
				options: { izinkan_penguncian: !blackbox && izinkanBerisiko },
				pakai_discovery: pakaiPenemuanTerakhir,
				persetujuan_sk: VERSI_SK
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

<svelte:head><title>Pengujian {NAMA_PENDEKATAN} — {app?.nama ?? 'Aplikasi'}</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app}
	<Memuat />
{:else if !bisaUji}
	<Kosong judul="Tidak berwenang" pesan="Hanya asesor atau administrator yang dapat melakukan pengujian.">
		<Button href="/aplikasi" variant="outline">Kembali ke daftar aplikasi</Button>
	</Kosong>
{:else}
	<PageHeader
		label="Operasi Pengujian · {NAMA_PENDEKATAN}"
		judul={app.nama}
		deskripsi="{app.url_dasar} · {blackbox
			? 'tanpa akun uji maupun informasi internal'
			: 'dengan akun uji terbatas'} · penemuan otomatis"
	>
		{#snippet atas()}
			<a href="/aplikasi" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Daftar aplikasi
			</a>
		{/snippet}
	</PageHeader>

	<!-- Stepper di panel loreng gelap -->
	<div class="bg-loreng sudut-taktis mb-6 rounded-lg p-4">
		<StepperAuth {langkah} label={LABEL} onpilih={(i) => (langkah = i)} />
	</div>

	<div class="mx-auto max-w-3xl">
		{#if kini === 'akun'}
			<!-- Langkah: Akun uji (grey box) -->
			<section class="sudut-taktis overflow-hidden rounded-lg border bg-card">
				<header class="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-5 py-3.5">
					<div class="flex items-center gap-2.5">
						<UsersRound class="size-5 text-gold" />
						<div>
							<p class="font-heading text-sm tracking-wide uppercase">Akun Uji</p>
							<p class="text-[11px] text-muted-foreground">Minimal 2 akun khusus SATRIA dengan hak akses pengguna biasa</p>
						</div>
					</div>
					{#if adaAkunTersimpan}
						<div class="inline-flex rounded-md border p-0.5 text-xs" role="tablist" aria-label="Sumber akun uji">
							<button
								type="button"
								role="tab"
								aria-selected={sumberAkun === 'tersimpan'}
								onclick={() => (sumberAkun = 'tersimpan')}
								class="rounded px-3 py-1.5 transition {sumberAkun === 'tersimpan' ? 'bg-gold text-gold-foreground' : 'text-muted-foreground hover:text-foreground'}"
							>
								Akun tersimpan
							</button>
							<button
								type="button"
								role="tab"
								aria-selected={sumberAkun === 'baru'}
								onclick={gantiAkun}
								class="rounded px-3 py-1.5 transition {sumberAkun === 'baru' ? 'bg-gold text-gold-foreground' : 'text-muted-foreground hover:text-foreground'}"
							>
								Akun baru
							</button>
						</div>
					{:else if akun.length}
						<Button size="sm" onclick={bukaBuatAkun} disabled={akun.length >= 10} class="bg-gold text-gold-foreground hover:bg-gold/85">
							<UserPlus /> Buat akun
						</Button>
					{/if}
				</header>

				{#if pakaiAkunTersimpan}
					<!-- Uji ulang: daftar akun dari pengujian sebelumnya -->
					<div class="px-5 py-4">
						<table class="w-full text-left text-sm">
							<thead class="text-[11px] text-muted-foreground uppercase">
								<tr class="border-b">
									<th class="w-10 py-2 font-medium tracking-wide">#</th>
									<th class="py-2 font-medium tracking-wide">Akun</th>
									<th class="hidden py-2 font-medium tracking-wide sm:table-cell">Kata sandi</th>
									<th class="py-2 font-medium tracking-wide">MFA</th>
									<th class="py-2 text-right font-medium tracking-wide">Status</th>
								</tr>
							</thead>
							<tbody class="divide-y">
								{#each akunTersimpan as a, i (i)}
									<tr>
										<td class="py-2.5 font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, '0')}</td>
										<td class="py-2.5">
											<p class="font-medium">{a.username}</p>
											<p class="text-[11px] text-muted-foreground">{i === 0 ? 'Akun utama' : 'Akun pembanding'}</p>
										</td>
										<td class="hidden py-2.5 font-mono text-xs text-muted-foreground sm:table-cell">••••••••</td>
										<td class="py-2.5 text-xs">
											{#if a.ada_totp}<span class="inline-flex items-center gap-1 text-success"><ShieldCheck class="size-3.5" /> TOTP</span>{:else}<span class="text-muted-foreground">—</span>{/if}
										</td>
										<td class="py-2.5 text-right">
											<span class="rounded-sm border border-success/50 bg-success/10 px-1.5 py-px font-heading text-[10px] tracking-wide text-success uppercase">Siap</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
						<p class="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
							<Lock class="size-3" /> Kredensial dari pengujian sebelumnya. Kata sandi & seed TOTP tidak pernah ditampilkan kembali.
						</p>
					</div>
				{:else if !akun.length}
					<!-- Belum ada akun -->
					<div class="flex flex-col items-center px-6 py-10 text-center">
						<span class="flex size-14 items-center justify-center rounded-full border border-dashed border-gold/50 bg-gold/5">
							<UserPlus class="size-6 text-gold" />
						</span>
						<p class="mt-4 font-heading tracking-wide uppercase">Belum ada akun uji</p>
						<p class="mt-1 max-w-md text-sm text-muted-foreground">
							Grey box menguji aplikasi dari dalam sesi login. Siapkan dua akun atau lebih: akun utama untuk menelusuri aplikasi,
							akun pembanding untuk menguji akses lintas akun.
						</p>
						<ul class="mt-5 grid gap-2 text-left text-xs text-muted-foreground sm:grid-cols-3">
							<li class="flex items-start gap-1.5 rounded-md border p-2.5"><Check class="mt-px size-3.5 shrink-0 text-gold" /> Dibuat khusus untuk SATRIA</li>
							<li class="flex items-start gap-1.5 rounded-md border p-2.5"><Check class="mt-px size-3.5 shrink-0 text-gold" /> Hak akses pengguna biasa</li>
							<li class="flex items-start gap-1.5 rounded-md border p-2.5"><Check class="mt-px size-3.5 shrink-0 text-gold" /> Tanpa data pribadi asli</li>
						</ul>
						<Button onclick={bukaBuatAkun} class="mt-6 bg-gold text-gold-foreground hover:bg-gold/85"><UserPlus /> Buat akun uji</Button>
					</div>
				{:else}
					<!-- Daftar akun baru -->
					<div class="px-5 py-4">
						<table class="w-full text-left text-sm">
							<thead class="text-[11px] text-muted-foreground uppercase">
								<tr class="border-b">
									<th class="w-10 py-2 font-medium tracking-wide">#</th>
									<th class="py-2 font-medium tracking-wide">Akun</th>
									<th class="hidden py-2 font-medium tracking-wide sm:table-cell">Kata sandi</th>
									<th class="py-2 font-medium tracking-wide">MFA</th>
									<th class="py-2 text-right font-medium tracking-wide">Aksi</th>
								</tr>
							</thead>
							<tbody class="divide-y">
								{#each akun as a, i (i)}
									<tr>
										<td class="py-2.5 font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, '0')}</td>
										<td class="py-2.5">
											<p class="font-medium break-all">{a.username}</p>
											<p class="text-[11px] text-muted-foreground">{i === 0 ? 'Akun utama' : 'Akun pembanding'}</p>
										</td>
										<td class="hidden py-2.5 font-mono text-xs text-muted-foreground sm:table-cell">••••••••</td>
										<td class="py-2.5 text-xs">
											{#if a.totp_secret.trim()}
												<span class="inline-flex items-center gap-1 text-success"><ShieldCheck class="size-3.5" /> TOTP</span>
												{#if !parameterStandar({ digits: a.totp_digits, period: a.totp_period, algoritma: a.totp_algoritma })}
													<span class="block text-[10px] text-muted-foreground">{a.totp_digits} digit · {a.totp_period} dtk · {a.totp_algoritma}</span>
												{/if}
											{:else}<span class="text-muted-foreground">—</span>{/if}
										</td>
										<td class="py-2.5 text-right whitespace-nowrap">
											<button type="button" onclick={() => bukaUbahAkun(i)} class="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Ubah akun {i + 1}">
												<Pencil class="size-3.5" />
											</button>
											<button type="button" onclick={() => hapusAkun(i)} class="rounded p-1.5 text-muted-foreground hover:bg-critical/10 hover:text-critical" aria-label="Hapus akun {i + 1}">
												<Trash2 class="size-3.5" />
											</button>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
						<div class="mt-3 flex flex-wrap items-center justify-between gap-2">
							<p class="text-xs {akun.length >= 2 ? 'text-success' : 'text-warning-foreground'}">
								{akun.length >= 2 ? `${akun.length} akun siap dipakai` : `Tambahkan ${2 - akun.length} akun lagi (minimal 2)`}
							</p>
							{#if adaAkunTersimpan}
								<Button size="sm" variant="outline" onclick={bukaBuatAkun} disabled={akun.length >= 10}><UserPlus /> Buat akun</Button>
							{/if}
						</div>
					</div>
				{/if}

				<footer class="flex items-start gap-2 border-t bg-muted/20 px-5 py-3 text-[11px] text-muted-foreground">
					<TriangleAlert class="mt-px size-3.5 shrink-0 text-warning-foreground" />
					<p>Kata sandi akun uji dapat diganti oleh mesin uji saat menguji fitur ubah kata sandi. Jangan gunakan akun milik personel sebenarnya.</p>
				</footer>
			</section>

			<DialogAkunUji
				bind:open={dialogAkun}
				awal={indeksUbah === null ? null : akun[indeksUbah]}
				nomor={indeksUbah === null ? akun.length + 1 : indeksUbah + 1}
				usernameLain={akun.filter((_, i) => i !== indeksUbah).map((a) => a.username)}
				onsimpan={simpanAkun}
			/>
		{:else if kini === 'penemuan' && discovery}
			<!-- Langkah (uji ulang): hasil Recon & Discovery terakhir -->
			<section class="sudut-taktis overflow-hidden rounded-lg border bg-card">
				<header class="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-5 py-3.5">
					<div class="flex items-center gap-2.5">
						<Radar class="size-5 text-gold" />
						<div>
							<p class="font-heading text-sm tracking-wide uppercase">Hasil Recon Terakhir</p>
							<p class="text-[11px] text-muted-foreground">
								{#if discovery.waktu}{relatif(discovery.waktu)} · {tanggal(discovery.waktu)}{:else}Waktu tidak diketahui{/if}
								{#if discovery.scan_id}· <a href="/scan/{discovery.scan_id}" class="underline-offset-2 hover:text-foreground hover:underline">pengujian #{discovery.scan_id}</a>{/if}
							</p>
						</div>
					</div>
				</header>

				<div class="grid divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
					<div class="px-5 py-4">
						<p class="label-stensil text-[10px] text-muted-foreground">Aset ditemukan</p>
						<p class="mt-1 font-heading text-3xl tabular-nums">{discovery.jumlah_endpoint_unik + discovery.jumlah_halaman}</p>
						<p class="text-[11px] text-muted-foreground">{discovery.jumlah_endpoint_unik} endpoint · {discovery.jumlah_halaman} halaman</p>
					</div>
					<div class="px-5 py-4">
						<p class="label-stensil text-[10px] text-muted-foreground">Kerentanan ditemukan</p>
						{#if temuanRecon === null}
							<div class="mt-2 h-8 w-12 animate-pulse rounded bg-muted"></div>
						{:else}
							<p class="mt-1 font-heading text-3xl tabular-nums {temuanRecon.length ? 'text-critical' : ''}">{temuanRecon.length}</p>
							<div class="mt-0.5 flex flex-wrap gap-x-2.5 text-[11px] text-muted-foreground">
								{#each sebaranRecon as [sev, n] (sev)}
									<span class="inline-flex items-center gap-1"><span class="size-1.5 rounded-full" style="background: {WARNA_SEVERITY[sev]}"></span>{n} {sev}</span>
								{:else}
									<span>Tidak ada temuan</span>
								{/each}
							</div>
						{/if}
					</div>
					<div class="px-5 py-4">
						<p class="label-stensil text-[10px] text-muted-foreground">Metode sebelumnya</p>
						<p class="mt-1 font-heading text-2xl tracking-wide uppercase">{metodeRecon ?? '—'}</p>
						<p class="text-[11px] text-muted-foreground">{discovery.terautentikasi ? 'Penelusuran dengan login' : 'Penelusuran tanpa login'}</p>
					</div>
				</div>

				<div class="grid gap-3 border-t px-5 py-4 sm:grid-cols-2">
					{@render pilihan(sumberPenemuan === 'terakhir', () => (sumberPenemuan = 'terakhir'), ClockCheck, 'Gunakan hasil ini', 'Lewati recon; langsung ke fase pengujian.')}
					{@render pilihan(sumberPenemuan === 'ulang', () => (sumberPenemuan = 'ulang'), RefreshCw, 'Discovery ulang', 'Petakan ulang aplikasi bila ada perubahan.')}
				</div>
			</section>
		{:else if kini === 'review'}
			<!-- Review -->
			<div class="sudut-taktis rounded-lg border bg-card p-5">
				<p class="label-stensil text-muted-foreground">Ringkasan</p>
				<dl class="mt-3 grid gap-2 text-sm sm:grid-cols-2">
					<div><dt class="text-muted-foreground">Target</dt><dd class="font-mono break-all">{app.url_dasar}</dd></div>
					<div><dt class="text-muted-foreground">Metode</dt><dd>{NAMA_PENDEKATAN} · eksploratif (penemuan otomatis)</dd></div>
					<div>
						<dt class="text-muted-foreground">Penemuan</dt>
						<dd>{pakaiPenemuanTerakhir && discovery ? `Pakai hasil terakhir (${relatif(discovery.waktu ?? undefined)})` : 'Jalankan penemuan baru'}</dd>
					</div>
					<div><dt class="text-muted-foreground">Sumber akun</dt><dd>{blackbox ? 'Tanpa akun uji' : pakaiAkunTersimpan ? 'Akun tersimpan' : 'Akun baru'}</dd></div>
				</dl>
				{#if blackbox}
					<div class="mt-5 flex items-start gap-2 rounded-md border border-info/40 bg-info/5 px-3 py-2 text-xs text-muted-foreground">
						<TriangleAlert class="mt-0.5 size-3.5 shrink-0 text-info" />
						<p>
							Black box menguji aplikasi seperti penyerang dari luar: tanpa login dan tanpa informasi internal.
							Metode yang memerlukan login dinyatakan <strong class="text-foreground">Out of Scope</strong> dan tidak ikut
							dinilai. Untuk menguji fungsi setelah login, gunakan Grey Box.
						</p>
					</div>
				{:else if pakaiAkunTersimpan}
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
			<!-- Langkah terakhir: Syarat & Ketentuan -->
			<section class="sudut-taktis overflow-hidden rounded-lg border bg-card">
				<header class="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-5 py-3.5">
					<div class="flex items-center gap-2.5">
						<ShieldCheck class="size-5 text-gold" />
						<div>
							<p class="font-heading text-sm tracking-wide uppercase">Syarat & Ketentuan</p>
							<p class="text-[11px] text-muted-foreground">Persetujuan wajib sebelum operasi pengujian dimulai</p>
						</div>
					</div>
					<span
						class="inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-heading text-[10px] tracking-wide uppercase {setujuPemindaian
							? 'border-success/50 bg-success/10 text-success'
							: 'border-warning/50 bg-warning/10 text-warning-foreground'}"
					>
						{#if setujuPemindaian}<BadgeCheck class="size-3" /> Disetujui{:else}<TriangleAlert class="size-3" /> Belum disetujui{/if}
					</span>
				</header>

				<!-- Dokumen -->
				<div class="flex flex-col gap-4 border-b px-5 py-4 sm:flex-row sm:items-center">
					<span class="flex size-11 shrink-0 items-center justify-center rounded-md border bg-muted/40">
						<FileText class="size-5 text-muted-foreground" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-sm font-medium">Syarat & Ketentuan Operasi Pengujian</p>
						<p class="mt-0.5 font-mono text-[11px] text-muted-foreground">{KODE_SK} · Versi {VERSI_SK} · {jumlahPasal} pasal</p>
						{#if setujuPemindaian && waktuSetuju}
							<p class="mt-1 text-xs text-success">
								Disetujui oleh {auth.pengguna?.nama ?? 'Anda'} · {waktuSetuju.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' })}
							</p>
						{/if}
					</div>
					<Button
						variant={setujuPemindaian ? 'outline' : 'default'}
						class={setujuPemindaian ? '' : 'bg-gold text-gold-foreground hover:bg-gold/85'}
						onclick={() => (dialogSK = true)}
					>
						<BookOpen />
						{setujuPemindaian ? 'Baca ulang' : 'Baca & setujui'}
					</Button>
				</div>

				<!-- Ringkasan dampak -->
				<div class="px-5 py-4">
					<p class="label-stensil text-[10px] text-muted-foreground">Ringkasan dampak terhadap target</p>
					<div class="mt-2.5 overflow-hidden rounded-md border">
						<table class="w-full text-left text-sm">
							<thead class="bg-muted/40 text-[11px] text-muted-foreground uppercase">
								<tr>
									<th class="px-3 py-2 font-medium tracking-wide">Fase</th>
									<th class="hidden px-3 py-2 font-medium tracking-wide md:table-cell">Aktivitas</th>
									<th class="px-3 py-2 font-medium tracking-wide">Dampak</th>
									<th class="px-3 py-2 text-right font-medium tracking-wide">Risiko</th>
								</tr>
							</thead>
							<tbody class="divide-y">
								{#each dampak as d (d.fase)}
									<tr class="align-top">
										<td class="px-3 py-2.5 font-medium whitespace-nowrap">{d.fase}</td>
										<td class="hidden px-3 py-2.5 text-xs text-muted-foreground md:table-cell">{d.aktivitas}</td>
										<td class="px-3 py-2.5 text-xs">{d.dampak}</td>
										<td class="px-3 py-2.5 text-right">
											<span class="rounded-sm border px-1.5 py-px font-heading text-[10px] tracking-wide uppercase {WARNA_TINGKAT[d.tingkat]}">{d.tingkat}</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>

				{#if !blackbox}
					<!-- Opsi uji berisiko -->
					<div class="border-t px-5 py-4">
						<p class="label-stensil text-[10px] text-muted-foreground">Opsi pengujian</p>
						<label
							class="mt-2.5 flex cursor-pointer items-start justify-between gap-4 rounded-md border p-3 transition hover:border-gold/50 {izinkanBerisiko
								? 'border-critical/50 bg-critical/5'
								: ''}"
						>
							<span>
								<span class="flex items-center gap-2 text-sm font-medium">
									Uji berisiko pada akun uji
									<span class="rounded-sm border px-1.5 py-px font-heading text-[10px] tracking-wide uppercase {WARNA_TINGKAT.tinggi}">tinggi</span>
								</span>
								<span class="mt-1 block text-xs text-muted-foreground">
									Mengizinkan uji penguncian akun dan ubah kata sandi. Akun uji dapat terkunci sementara dan kata sandinya dapat berubah.
									Bila tidak diizinkan, metode tersebut tidak dijalankan.
								</span>
							</span>
							<Switch bind:checked={izinkanBerisiko} class="mt-0.5 shrink-0" />
						</label>
					</div>
				{/if}
			</section>

			<DialogSyaratKetentuan
				bind:open={dialogSK}
				{blackbox}
				target={app.url_dasar}
				namaAplikasi={app.nama}
				sudahSetuju={setujuPemindaian}
				onsetuju={() => {
					if (!setujuPemindaian) waktuSetuju = new Date();
					setujuPemindaian = true;
				}}
				onbatal={() => goto('/aplikasi')}
			/>
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
				<p class="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
					<span class="relative flex size-2"><span class="absolute inline-flex size-full animate-ping rounded-full bg-[#9fe08a] opacity-60"></span><span class="relative inline-flex size-2 rounded-full bg-[#9fe08a]"></span></span>
					Worker siaga — pengujian langsung dikerjakan setelah dimulai.
				</p>
			{/if}
		{/if}

		<!-- Navigasi -->
		<div class="mt-6 flex items-center justify-between gap-3 border-t pt-4">
			<Button variant="outline" onclick={kembali} disabled={langkah === 0}><ChevronLeft /> Kembali</Button>
			{#if kini === 'sk' && !setujuPemindaian}
				<p class="hidden text-xs text-muted-foreground sm:block">Setujui Syarat & Ketentuan untuk memulai pengujian.</p>
			{/if}
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
