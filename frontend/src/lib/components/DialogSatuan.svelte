<script lang="ts">
	// Form satuan kerja bertahap (pola sama dengan pendaftaran akun): Identitas → Induk → Lokasi → Tinjau.
	// Tambah: maju per langkah, tiap langkah divalidasi sebelum lanjut, simpan di langkah terakhir.
	// Ubah: data sudah lengkap, jadi semua langkah bisa dibuka langsung dan "Simpan" tersedia di tiap langkah.
	import { tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { api } from '#lib/api/client.js';
	import {
		BATAS_KOORDINAT,
		JENIS_SATUAN,
		labelJenis,
		namaProvinsi,
		PROVINSI
	} from '#lib/data/satuan.js';
	import type { SatuanAdmin, SatuanInput } from '#lib/types.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import Field from '#lib/components/Field.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import ComboboxAuth from '#lib/components/ComboboxAuth.svelte';
	import StepperAuth from '#lib/components/StepperAuth.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Building from '@lucide/svelte/icons/building-2';
	import Network from '@lucide/svelte/icons/network';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import House from '@lucide/svelte/icons/house';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		open = $bindable(false),
		target,
		indukAwal,
		onsimpan
	}: {
		open?: boolean;
		/** Satuan yang diubah; null = tambah baru. */
		target: SatuanAdmin | null;
		/** Saat menambah: induk bawaan (satuan yang sedang dibuka di daftar). */
		indukAwal: SatuanAdmin | null;
		onsimpan: () => unknown;
	} = $props();

	type Form = {
		nama: string;
		jenis: SatuanInput['jenis'];
		induk_id: string | null;
		aktif: boolean;
		alamat: string;
		kota: string;
		provinsi_kode: string;
		latitude: string;
		longitude: string;
	};
	type Kolom = keyof Form;

	const LANGKAH = [
		{
			label: 'Identitas',
			kolom: ['nama', 'jenis'],
			ikon: Building,
			judul: 'Identitas Satuan',
			sub: 'Nama resmi dan jenis/tingkatan satuan'
		},
		{
			label: 'Induk',
			kolom: ['induk_id'],
			ikon: Network,
			judul: 'Kedudukan dalam Hierarki',
			sub: 'Satuan atasan langsung; kosongkan bila satuan teratas'
		},
		{
			label: 'Lokasi',
			kolom: ['alamat', 'kota', 'provinsi_kode', 'latitude', 'longitude'],
			ikon: MapPin,
			judul: 'Alamat & Lokasi',
			sub: 'Dipakai peta sebaran sistem informasi per daerah di dasbor'
		},
		{
			label: 'Tinjau',
			kolom: ['aktif'],
			ikon: ClipboardCheck,
			judul: 'Tinjau & Simpan',
			sub: 'Periksa kembali data sebelum disimpan'
		}
	] as const satisfies readonly { label: string; kolom: readonly Kolom[]; ikon: unknown; judul: string; sub: string }[];
	const TERAKHIR = LANGKAH.length - 1;

	let f = $state<Form>(formAwal());
	let namaInduk = $state('');
	let jalurInduk = $state('');
	let langkah = $state(0);
	/** 1 = maju (isi baru masuk dari kanan), -1 = mundur. */
	let arah = $state(1);
	let disentuh = $state<Partial<Record<Kolom, boolean>>>({});
	let galatServer = $state<string | null>(null);
	let menyimpan = $state(false);
	// Provinsi & jalur tiap opsi induk yang muncul di combobox (untuk isi otomatis & ringkasan).
	const infoOpsi = new Map<string, { provinsi: string | null; jalur: string }>();

	const ubah = $derived(!!target);

	function formAwal(): Form {
		const s = target;
		if (s)
			return {
				nama: s.nama,
				jenis: s.jenis,
				induk_id: s.induk_id,
				aktif: s.aktif,
				alamat: s.alamat ?? '',
				kota: s.kota ?? '',
				provinsi_kode: s.provinsi_kode ?? '',
				latitude: s.latitude?.toString() ?? '',
				longitude: s.longitude?.toString() ?? ''
			};
		return {
			nama: '',
			jenis: 'SATUAN',
			induk_id: indukAwal?.id ?? null,
			aktif: true,
			alamat: '',
			kota: '',
			provinsi_kode: indukAwal?.provinsi_kode ?? '',
			latitude: '',
			longitude: ''
		};
	}

	// Setiap kali dialog dibuka: isi ulang dari target/induk dan mulai dari langkah pertama.
	$effect(() => {
		if (!open) return;
		f = formAwal();
		const leluhurInduk = target
			? target.leluhur
			: indukAwal
				? [...indukAwal.leluhur, { id: indukAwal.id, nama: indukAwal.nama }]
				: [];
		namaInduk = leluhurInduk.at(-1)?.nama ?? '';
		jalurInduk = leluhurInduk.map((l) => l.nama).join(' › ');
		langkah = 0;
		arah = 1;
		disentuh = {};
		galatServer = null;
		void tick().then(() => document.getElementById('nama-satuan')?.focus());
	});

	const angka = (v: string) => (v.trim() === '' ? null : Number(v));
	const B = BATAS_KOORDINAT;

	const galat = $derived.by(() => {
		const g: Partial<Record<Kolom, string>> = {};
		if (f.nama.trim().replace(/\s+/g, ' ').length < 2) g.nama = 'Nama satuan minimal 2 karakter.';
		const lat = angka(f.latitude);
		const lng = angka(f.longitude);
		if (lat !== null && (!Number.isFinite(lat) || lat < B.latMin || lat > B.latMax))
			g.latitude = `Latitude harus antara ${B.latMin} dan ${B.latMax}.`;
		if (lng !== null && (!Number.isFinite(lng) || lng < B.lngMin || lng > B.lngMax))
			g.longitude = `Longitude harus antara ${B.lngMin} dan ${B.lngMax}.`;
		if (!g.latitude && !g.longitude && (lat === null) !== (lng === null))
			g[lat === null ? 'latitude' : 'longitude'] = 'Isi berpasangan dengan kolom satunya.';
		return g;
	});
	const tampil = (k: Kolom) => (disentuh[k] ? galat[k] : undefined);

	/** Langkah pertama yang masih salah (untuk lompat ke sana saat menyimpan dari langkah lain). */
	const langkahSalah = $derived(LANGKAH.findIndex((l) => l.kolom.some((k) => galat[k as Kolom])));

	async function pindah(ke: number) {
		arah = ke > langkah ? 1 : -1;
		langkah = ke;
		galatServer = null;
		await tick();
		const pertama = LANGKAH[ke].kolom[0].split('_')[0];
		document.getElementById(`${pertama}-satuan`)?.focus();
	}

	function tandai(i: number) {
		for (const k of LANGKAH[i].kolom) disentuh[k as Kolom] = true;
	}

	function data(): SatuanInput {
		const teks = (v: string) => v.trim().replace(/\s+/g, ' ') || null;
		return {
			nama: f.nama.trim().replace(/\s+/g, ' '),
			jenis: f.jenis,
			induk_id: f.induk_id || null,
			aktif: f.aktif,
			alamat: teks(f.alamat),
			kota: teks(f.kota),
			provinsi_kode: f.provinsi_kode || null,
			latitude: angka(f.latitude),
			longitude: angka(f.longitude)
		};
	}

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		if (menyimpan) return;
		galatServer = null;
		const simpanSekarang = ubah || langkah === TERAKHIR;

		if (!simpanSekarang) {
			tandai(langkah);
			if (LANGKAH[langkah].kolom.some((k) => galat[k as Kolom])) return;
			return pindah(langkah + 1);
		}
		if (langkahSalah >= 0) {
			tandai(langkahSalah);
			if (langkahSalah !== langkah) await pindah(langkahSalah);
			return;
		}

		menyimpan = true;
		const d = data();
		try {
			if (target) {
				const t = target;
				// Kirim hanya yang berubah.
				const berubah = Object.fromEntries(
					Object.entries(d).filter(([k, v]) => v !== t[k as keyof SatuanInput])
				) as Partial<SatuanInput>;
				if (Object.keys(berubah).length) {
					await api.ubahSatuan(t.id, berubah);
					toast.success(`Satuan "${d.nama}" diperbarui`);
				}
			} else {
				await api.tambahSatuan(d);
				toast.success(`Satuan "${d.nama}" ditambahkan${d.aktif ? '' : ' (nonaktif)'}`);
			}
			open = false;
			await onsimpan();
		} catch (err) {
			galatServer = (err as Error).message;
		} finally {
			menyimpan = false;
		}
	}

	const cariInduk = async (kata: string) => {
		const { items } = await api.listSatuanAdmin({ search: kata.trim(), limit: 25 });
		return (
			items
				// Satuan yang diubah dan sub-satuannya tidak boleh menjadi induknya sendiri.
				.filter((s) => s.id !== target?.id && !s.leluhur.some((l) => l.id === target?.id))
				.map((s) => {
					infoOpsi.set(s.id, {
						provinsi: s.provinsi_kode,
						jalur: [s.jalur, s.nama].filter(Boolean).join(' › ')
					});
					return {
						value: s.id,
						label: s.nama,
						keterangan: [labelJenis(s.jenis), s.jalur].filter(Boolean).join(' · ')
					};
				})
		);
	};

	// Tempel "lat, lng" (format salinan aplikasi peta) ke kolom latitude: dipecah ke dua kolom.
	function tempelKoordinat(e: ClipboardEvent) {
		const m = (e.clipboardData?.getData('text') ?? '').match(
			/^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/
		);
		if (!m) return;
		e.preventDefault();
		f.latitude = m[1];
		f.longitude = m[2];
		disentuh.latitude = disentuh.longitude = true;
	}

	const reduksiGerak = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
	const durasi = (ms: number) => (reduksiGerak() ? 0 : ms);

	const sekarang = $derived(LANGKAH[langkah]);
	const opsiJenis = JENIS_SATUAN.map((j) => ({ value: j.kode, label: j.label }));
	const opsiProvinsi = PROVINSI.map((p) => ({ value: p.kode, label: p.nama }));
	const ringkasLokasi = $derived(
		[f.alamat.trim(), f.kota.trim(), namaProvinsi(f.provinsi_kode)].filter(Boolean).join(', ')
	);
</script>

{#snippet pesanGalat(k: Kolom)}
	{#if tampil(k)}
		<p class="flex items-center gap-1.5 text-xs text-critical" role="alert">
			<CircleAlert class="size-3.5" />{tampil(k)}
		</p>
	{/if}
{/snippet}

{#snippet baris(label: string, nilai: string, ke: number)}
	<div class="flex items-start justify-between gap-4 py-2.5">
		<dt class="w-32 shrink-0 text-xs text-muted-foreground">{label}</dt>
		<dd class="min-w-0 flex-1 text-sm break-words">{nilai}</dd>
		<button
			type="button"
			class="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
			onclick={() => pindah(ke)}
		>
			Ubah
		</button>
	</div>
{/snippet}

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90vh] overflow-y-auto sm:max-w-xl">
		<Dialog.Header>
			<Dialog.Title>{ubah ? `Ubah ${target?.nama}` : 'Tambah satuan'}</Dialog.Title>
			{#if target && (target.jumlah_pengguna || target.jumlah_sub || target.jumlah_aplikasi)}
				<Dialog.Description>
					Dipakai {target.jumlah_pengguna} akun dan {target.jumlah_aplikasi} aplikasi, membawahi {target.jumlah_sub}
					sub-satuan.
				</Dialog.Description>
			{/if}
		</Dialog.Header>

		<div class="pt-2">
			<StepperAuth
				{langkah}
				label={LANGKAH.map((l) => l.label)}
				onpilih={pindah}
				tema="terang"
				bebas={ubah}
				ariaLabel="Langkah pengisian satuan"
			/>
		</div>

		<form class="grid gap-6" onsubmit={kirim} novalidate>
			<!-- Isi langkah bergeser horizontal; lama & baru ditumpuk di sel grid yang sama selama transisi. -->
			<div class="-mx-1 grid overflow-x-clip px-1">
				{#key langkah}
					<div
						class="grid gap-5 [grid-area:1/1]"
						in:fly={{ x: 36 * arah, duration: durasi(280), delay: durasi(110), easing: cubicOut }}
						out:fly={{ x: -36 * arah, duration: durasi(110) }}
					>
						<div class="flex items-center gap-3">
							<span
								class="grid size-10 shrink-0 place-items-center rounded-full bg-gold/12 text-gold"
							>
								<sekarang.ikon class="size-5" />
							</span>
							<div class="min-w-0">
								<h3 class="font-heading text-lg leading-tight font-semibold">{sekarang.judul}</h3>
								<p class="text-sm text-muted-foreground">{sekarang.sub}</p>
							</div>
						</div>

						{#if langkah === 0}
							<Field label="Nama satuan" id="nama-satuan" wajib>
								<Input
									id="nama-satuan"
									bind:value={f.nama}
									onblur={() => (disentuh.nama = true)}
									maxlength={120}
									aria-invalid={!!tampil('nama')}
									placeholder="mis. Kodim 0501/Jakarta Pusat"
								/>
								{@render pesanGalat('nama')}
							</Field>
							<div class="grid gap-2">
								<span class="text-sm font-medium"
									>Jenis satuan<span class="text-critical">*</span></span
								>
								<div class="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Jenis satuan">
									{#each JENIS_SATUAN as j, i (j.kode)}
										<label
											class={cn(
												'flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5 transition-colors hover:bg-muted/60',
												f.jenis === j.kode && 'border-gold/70 bg-gold/8',
												i === JENIS_SATUAN.length - 1 && 'sm:col-span-2'
											)}
										>
											<input
												type="radio"
												name="jenis"
												id={i === 0 ? 'jenis-satuan' : undefined}
												value={j.kode}
												bind:group={f.jenis}
												class="mt-0.5 accent-gold"
											/>
											<span class="grid gap-0.5">
												<span class="text-sm font-medium">{j.label}</span>
												<span class="text-xs leading-snug text-muted-foreground"
													>{j.keterangan}</span
												>
											</span>
										</label>
									{/each}
								</div>
							</div>
						{:else if langkah === 1}
							<ComboboxAuth
								id="induk-satuan"
								label="Satuan induk"
								ikon={Network}
								tema="terang"
								cari={cariInduk}
								placeholder="Ketik nama satuan induk…"
								bind:value={() => f.induk_id ?? '', (v) => (f.induk_id = v || null)}
								bind:terpilih={namaInduk}
								onpilih={(o) => {
									const info = infoOpsi.get(o.value);
									jalurInduk = info?.jalur ?? o.label;
									// Sub-satuan biasanya berada di provinsi yang sama dengan induknya.
									if (!f.provinsi_kode) f.provinsi_kode = info?.provinsi ?? '';
								}}
							/>
							<div class="rounded-lg border bg-muted/40 p-3 text-sm">
								<p class="mb-1.5 text-xs text-muted-foreground">Kedudukan satuan ini</p>
								<p class="flex flex-wrap items-center gap-1">
									<House class="size-3.5 text-muted-foreground" />
									{#if f.induk_id}
										{#each (jalurInduk || namaInduk).split(' › ') as n, i (i)}
											<span class="text-muted-foreground">{n}</span>
											<ChevronRight class="size-3.5 text-muted-foreground" />
										{/each}
									{/if}
									<b>{f.nama.trim() || 'Satuan baru'}</b>
								</p>
								<p class="mt-2 text-xs text-muted-foreground">
									{#if f.induk_id}
										<button
											type="button"
											class="underline underline-offset-2 hover:text-foreground"
											onclick={() => ((f.induk_id = null), (namaInduk = ''), (jalurInduk = ''))}
										>
											Jadikan satuan teratas
										</button>
									{:else}
										Tanpa induk = satuan teratas, mis. Mabes TNI.
									{/if}
								</p>
							</div>
						{:else if langkah === 2}
							<Field label="Alamat" id="alamat-satuan">
								<Input
									id="alamat-satuan"
									bind:value={f.alamat}
									maxlength={255}
									placeholder="Nama jalan, nomor, kelurahan/kecamatan"
								/>
							</Field>
							<div class="grid gap-4 sm:grid-cols-2">
								<Field label="Kabupaten / kota" id="kota-satuan">
									<Input
										id="kota-satuan"
										bind:value={f.kota}
										maxlength={100}
										placeholder="mis. Kota Jakarta Pusat"
									/>
								</Field>
								<Field
									label="Provinsi"
									id="provinsi-satuan"
									info="Dipakai untuk mewarnai peta sebaran per provinsi di dasbor."
								>
									<NativeSelect
										id="provinsi-satuan"
										class="h-9"
										bind:value={f.provinsi_kode}
										opsi={[{ value: '', label: '— Belum diisi —' }, ...opsiProvinsi]}
									/>
								</Field>
							</div>
							<div class="grid gap-4 sm:grid-cols-2">
								<Field
									label="Latitude"
									id="latitude-satuan"
									info={'Opsional, untuk titik di peta. Tempel "lat, lng" dari aplikasi peta di kolom ini: otomatis dipecah ke dua kolom.'}
								>
									<Input
										id="latitude-satuan"
										inputmode="decimal"
										bind:value={f.latitude}
										onpaste={tempelKoordinat}
										onblur={() => (disentuh.latitude = true)}
										aria-invalid={!!tampil('latitude')}
										placeholder="mis. -6.175392"
									/>
									{@render pesanGalat('latitude')}
								</Field>
								<Field label="Longitude" id="longitude-satuan">
									<Input
										id="longitude-satuan"
										inputmode="decimal"
										bind:value={f.longitude}
										onblur={() => (disentuh.longitude = true)}
										aria-invalid={!!tampil('longitude')}
										placeholder="mis. 106.827153"
									/>
									{@render pesanGalat('longitude')}
								</Field>
							</div>
							<p class="-mt-2 text-xs text-muted-foreground">
								Semua kolom lokasi boleh dilengkapi nanti.
							</p>
						{:else}
							<dl class="divide-y rounded-lg border px-3">
								{@render baris('Nama', f.nama.trim() || '—', 0)}
								{@render baris('Jenis', labelJenis(f.jenis), 0)}
								{@render baris(
									'Induk',
									f.induk_id ? jalurInduk || namaInduk : 'Tanpa induk (satuan teratas)',
									1
								)}
								{@render baris('Lokasi', ringkasLokasi || 'Belum diisi', 2)}
								{@render baris(
									'Koordinat',
									f.latitude && f.longitude ? `${f.latitude}, ${f.longitude}` : 'Belum diisi',
									2
								)}
							</dl>
							<div class="flex items-start justify-between gap-4 rounded-lg border p-3">
								<div class="grid gap-0.5">
									<label for="aktif-satuan" class="text-sm font-medium">Aktif</label>
									<p class="text-xs text-muted-foreground">
										{#if f.aktif}
											Dapat dipilih saat pendaftaran akun dan aplikasi.
										{:else}
											Tidak muncul di pilihan pendaftaran{target?.jumlah_pengguna
												? `; ${target.jumlah_pengguna} akun yang sudah memakainya tetap sah`
												: ''}.
										{/if}
									</p>
								</div>
								<Switch id="aktif-satuan" bind:checked={f.aktif} />
							</div>
						{/if}
					</div>
				{/key}
			</div>

			{#if galatServer}
				<p
					class="flex items-center gap-2 rounded-md bg-critical/10 px-3 py-2 text-sm text-critical"
					role="alert"
				>
					<CircleAlert class="size-4 shrink-0" />{galatServer}
				</p>
			{/if}

			<div class="flex items-center justify-between gap-2 border-t pt-4">
				{#if langkah > 0}
					<Button type="button" variant="ghost" onclick={() => pindah(langkah - 1)}
						><ArrowLeft /> Kembali</Button
					>
				{:else}
					<Button type="button" variant="ghost" onclick={() => (open = false)}>Batal</Button>
				{/if}
				<div class="flex gap-2">
					{#if ubah && langkah < TERAKHIR}
						<Button
							type="button"
							variant="outline"
							onclick={() => (
								tandai(langkah),
								!LANGKAH[langkah].kolom.some((k) => galat[k as Kolom]) && pindah(langkah + 1)
							)}
						>
							Berikutnya <ArrowRight />
						</Button>
					{/if}
					<Button type="submit" disabled={menyimpan}>
						{#if menyimpan}
							<LoaderCircle class="animate-spin" /> Menyimpan…
						{:else if ubah}
							Simpan
						{:else if langkah === TERAKHIR}
							Tambah satuan
						{:else}
							Lanjut <ArrowRight />
						{/if}
					</Button>
				</div>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
