<script lang="ts">
	// Form data dasar aset aplikasi (registrasi & ubah). Persiapan pengujian tidak diisi di sini.
	import { api } from '#lib/api/client.js';
	import { GalatApi } from '#lib/api/http.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import type { Aplikasi, AsetBaru, KlasifikasiData, Lingkungan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import Field from './Field.svelte';
	import NativeSelect from './NativeSelect.svelte';
	import ComboboxAuth from './ComboboxAuth.svelte';
	import Building from '@lucide/svelte/icons/building-2';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Lock from '@lucide/svelte/icons/lock';

	let {
		awal,
		labelSimpan = 'Simpan',
		batalHref,
		onsimpan
	}: {
		/** Data aset yang diubah; kosong = registrasi baru. */
		awal?: Aplikasi;
		labelSimpan?: string;
		batalHref: string;
		/** Simpan ke API; lempar galat agar ditampilkan di form. */
		onsimpan: (data: AsetBaru) => Promise<void>;
	} = $props();

	type Kolom = 'nama' | 'deskripsi' | 'url_dasar' | 'satuan_id' | 'pic_nama' | 'pic_kontak' | 'lingkungan' | 'klasifikasi_data';

	const admin = $derived(auth.punya('admin'));

	// Salinan awal sengaja diambil sekali: form menyunting draf, bukan data asli.
	// svelte-ignore state_referenced_locally
	let f = $state({
		nama: awal?.nama ?? '',
		deskripsi: awal?.deskripsi ?? '',
		url_dasar: awal?.url_dasar ?? '',
		satuan_id: awal?.satuan_id ?? auth.pengguna?.satuan_id ?? '',
		pic_nama: awal?.pic_nama ?? '',
		pic_kontak: awal?.pic_kontak ?? '',
		lingkungan: (awal?.lingkungan ?? '') as Lingkungan | '',
		klasifikasi_data: (awal?.klasifikasi_data ?? '') as KlasifikasiData | '',
		teknologi: { frontend: '', backend: '', database: '', server: '', ...awal?.teknologi }
	});
	// svelte-ignore state_referenced_locally
	let namaSatuan = $state(awal?.satuan ?? auth.pengguna?.satuan ?? '');
	let disentuh = $state<Partial<Record<Kolom, boolean>>>({});
	let galatServer = $state<Partial<Record<Kolom, string>>>({});
	let galatUmum = $state<string | null>(null);
	let menyimpan = $state(false);

	const rapikan = (s: string) => s.trim().replace(/\s+/g, ' ');
	const urlValid = (u: string) => /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(u.trim());

	const galat = $derived<Record<Kolom, string | null>>({
		nama: rapikan(f.nama).length < 3 ? 'Nama aplikasi minimal 3 karakter.' : null,
		deskripsi: f.deskripsi.length > 2000 ? 'Deskripsi maksimal 2000 karakter.' : null,
		url_dasar: !urlValid(f.url_dasar) ? 'URL dasar harus diawali http:// atau https://.' : null,
		satuan_id: admin && !f.satuan_id ? 'Pilih satuan pemilik aplikasi.' : null,
		pic_nama: rapikan(f.pic_nama).length < 3 ? 'Nama PIC minimal 3 karakter.' : null,
		pic_kontak: rapikan(f.pic_kontak).length < 3 ? 'Kontak PIC wajib diisi.' : null,
		lingkungan: !f.lingkungan ? 'Pilih lingkungan aplikasi.' : null,
		klasifikasi_data: !f.klasifikasi_data ? 'Pilih klasifikasi data.' : null
	});
	const tampil = (k: Kolom) => galatServer[k] ?? (disentuh[k] ? galat[k] : null);
	const sentuh = (k: Kolom) => () => (disentuh[k] = true);
	const ubah = (k: Kolom) => () => delete galatServer[k];

	// Nama field API → kolom form (galat validasi dari backend).
	const KOLOM_API: Record<string, Kolom> = { satuan_id: 'satuan_id' };

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		galatUmum = null;
		const salah = (Object.keys(galat) as Kolom[]).filter((k) => galat[k]);
		if (salah.length) {
			for (const k of Object.keys(galat) as Kolom[]) disentuh[k] = true;
			document.getElementById(`aset-${salah[0]}`)?.focus();
			return;
		}
		menyimpan = true;
		try {
			await onsimpan({
				nama: rapikan(f.nama),
				deskripsi: f.deskripsi.trim(),
				url_dasar: f.url_dasar.trim().replace(/\/+$/, ''),
				pic_nama: rapikan(f.pic_nama),
				pic_kontak: rapikan(f.pic_kontak),
				lingkungan: f.lingkungan as Lingkungan,
				klasifikasi_data: f.klasifikasi_data as KlasifikasiData,
				teknologi: {
					frontend: f.teknologi.frontend.trim(),
					backend: f.teknologi.backend.trim(),
					database: f.teknologi.database.trim(),
					server: f.teknologi.server.trim()
				},
				...(admin ? { satuan_id: f.satuan_id } : {})
			});
		} catch (err) {
			const daftar = err instanceof GalatApi ? (err.errors ?? []) : [];
			for (const g of daftar) {
				const k = (KOLOM_API[g.field] ?? g.field) as Kolom;
				if (k in galat) galatServer[k] = g.message;
			}
			if (!daftar.length) galatUmum = (err as Error).message;
			const pertama = daftar[0]?.field;
			if (pertama) document.getElementById(`aset-${KOLOM_API[pertama] ?? pertama}`)?.focus();
		} finally {
			menyimpan = false;
		}
	}

	const cariSatuan = async (kata: string) =>
		(await api.cariSatuan(kata)).map((s) => ({ value: s.id, label: s.nama, keterangan: s.jalur || undefined }));

	const OPSI_LINGKUNGAN = [
		{ value: '', label: 'Pilih lingkungan…' },
		{ value: 'produksi', label: 'Produksi' },
		{ value: 'staging', label: 'Staging' },
		{ value: 'pengembangan', label: 'Pengembangan' }
	];
	const OPSI_KLASIFIKASI = [
		{ value: '', label: 'Pilih klasifikasi…' },
		{ value: 'biasa', label: 'Biasa' },
		{ value: 'terbatas', label: 'Terbatas' },
		{ value: 'rahasia', label: 'Rahasia' }
	];
	const TEKNOLOGI = [
		{ k: 'frontend', label: 'Frontend', contoh: 'mis. React, Laravel Blade' },
		{ k: 'backend', label: 'Backend', contoh: 'mis. Laravel 10, Spring Boot' },
		{ k: 'database', label: 'Basis data', contoh: 'mis. MySQL 8, PostgreSQL' },
		{ k: 'server', label: 'Server', contoh: 'mis. Nginx di Ubuntu 22.04' }
	] as const;

</script>

{#snippet pesan(k: Kolom)}
	{#if tampil(k)}
		<p class="flex items-center gap-1 text-xs text-critical"><CircleAlert class="size-3.5" />{tampil(k)}</p>
	{/if}
{/snippet}

{#snippet bagian(nomor: string, judul: string, ket: string)}
	<div class="mb-4 flex items-baseline gap-3 border-b pb-3">
		<span class="font-stencil text-lg text-gold">{nomor}</span>
		<div>
			<h2 class="font-heading text-sm font-semibold tracking-[0.12em] uppercase">{judul}</h2>
			<p class="text-xs text-muted-foreground">{ket}</p>
		</div>
	</div>
{/snippet}

<form class="grid max-w-4xl gap-6" onsubmit={kirim} novalidate>
	<section class="sudut-taktis rounded-lg border bg-card p-5 sm:p-6">
		{@render bagian('01', 'Identitas aplikasi', 'Nama, fungsi, dan alamat aplikasi yang akan dinilai.')}
		<div class="grid gap-4">
			<Field label="Nama aplikasi" id="aset-nama" wajib>
				<Input class="h-9" id="aset-nama" bind:value={f.nama} maxlength={150} aria-invalid={!!tampil('nama')}
					onblur={sentuh('nama')} oninput={ubah('nama')} placeholder="mis. Sistem Informasi Personel" />
				{@render pesan('nama')}
			</Field>
			<Field label="URL dasar" id="aset-url_dasar" wajib bantuan="Alamat utama aplikasi. Satu URL hanya bisa didaftarkan sekali.">
				<Input class="h-9" id="aset-url_dasar" type="url" inputmode="url" bind:value={f.url_dasar} maxlength={255}
					aria-invalid={!!tampil('url_dasar')} onblur={sentuh('url_dasar')} oninput={ubah('url_dasar')}
					placeholder="https://aplikasi.satuan.mil.id" spellcheck={false} />
				{@render pesan('url_dasar')}
			</Field>
			<Field label="Deskripsi" id="aset-deskripsi" bantuan="Fungsi utama dan pengguna aplikasi (opsional).">
				<Textarea id="aset-deskripsi" bind:value={f.deskripsi} rows={3} maxlength={2000} oninput={ubah('deskripsi')} />
				{@render pesan('deskripsi')}
			</Field>
		</div>
	</section>

	<section class="sudut-taktis rounded-lg border bg-card p-5 sm:p-6">
		{@render bagian('02', 'Penanggung jawab', 'Satuan pemilik dan personel yang dapat dihubungi.')}
		<div class="grid items-start gap-4 sm:grid-cols-2">
			<div class="sm:col-span-2">
				{#if admin}
					<ComboboxAuth id="aset-satuan_id" label="Satuan pemilik" ikon={Building} tema="terang" cari={cariSatuan}
						placeholder="Ketik nama satuan…" bind:value={f.satuan_id} bind:terpilih={namaSatuan}
						galat={tampil('satuan_id')} onpilih={() => delete galatServer.satuan_id} />
				{:else}
					<Field label="Satuan pemilik" id="aset-satuan" bantuan="Aset didaftarkan atas nama satuan Anda.">
						<div id="aset-satuan" class="flex h-9 items-center gap-2 rounded-lg border bg-muted/50 px-3 text-sm">
							<Building class="size-4 text-muted-foreground" />
							<span class="flex-1 truncate">{namaSatuan}</span>
							<Lock class="size-3.5 text-muted-foreground" aria-label="Tidak dapat diubah" />
						</div>
					</Field>
				{/if}
			</div>
			<Field label="Nama PIC" id="aset-pic_nama" wajib>
				<Input class="h-9" id="aset-pic_nama" bind:value={f.pic_nama} maxlength={100} aria-invalid={!!tampil('pic_nama')}
					onblur={sentuh('pic_nama')} oninput={ubah('pic_nama')} placeholder="Pangkat & nama lengkap" />
				{@render pesan('pic_nama')}
			</Field>
			<Field label="Kontak PIC" id="aset-pic_kontak" wajib>
				<Input class="h-9" id="aset-pic_kontak" bind:value={f.pic_kontak} maxlength={100} aria-invalid={!!tampil('pic_kontak')}
					onblur={sentuh('pic_kontak')} oninput={ubah('pic_kontak')} placeholder="Email dinas / nomor telepon" />
				{@render pesan('pic_kontak')}
			</Field>
		</div>
	</section>

	<section class="sudut-taktis rounded-lg border bg-card p-5 sm:p-6">
		{@render bagian('03', 'Lingkungan & teknologi', 'Konteks operasional untuk menentukan cakupan penilaian.')}
		<div class="grid items-start gap-4 sm:grid-cols-2">
			<Field label="Lingkungan" id="aset-lingkungan" wajib>
				<NativeSelect id="aset-lingkungan" bind:value={f.lingkungan} opsi={OPSI_LINGKUNGAN} class="h-9"
					aria-invalid={!!tampil('lingkungan')} onchange={sentuh('lingkungan')} />
				{@render pesan('lingkungan')}
			</Field>
			<Field label="Klasifikasi data" id="aset-klasifikasi_data" wajib bantuan="Tingkat kerahasiaan data yang diolah aplikasi.">
				<NativeSelect id="aset-klasifikasi_data" bind:value={f.klasifikasi_data} opsi={OPSI_KLASIFIKASI} class="h-9"
					aria-invalid={!!tampil('klasifikasi_data')} onchange={sentuh('klasifikasi_data')} />
				{@render pesan('klasifikasi_data')}
			</Field>
			<div class="mt-2 border-t pt-4 sm:col-span-2">
				<p class="text-sm font-medium">Teknologi <span class="font-normal text-muted-foreground">(opsional)</span></p>
				<p class="text-xs text-muted-foreground">Membantu asesor menentukan metode uji yang relevan.</p>
			</div>
			{#each TEKNOLOGI as t (t.k)}
				<Field label={t.label} id="aset-tek-{t.k}">
					<Input class="h-9" id="aset-tek-{t.k}" bind:value={f.teknologi[t.k]} maxlength={100} placeholder={t.contoh} />
				</Field>
			{/each}
		</div>
	</section>

	{#if galatUmum}
		<p class="flex items-center gap-2 rounded-md border border-critical/40 bg-critical/10 px-3 py-2.5 text-sm text-critical" role="alert">
			<CircleAlert class="size-4 shrink-0" />{galatUmum}
		</p>
	{/if}

	<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
		<Button variant="outline" href={batalHref}>Batal</Button>
		<Button type="submit" disabled={menyimpan} class="bg-gold text-gold-foreground hover:bg-gold/85">
			{#if menyimpan}<LoaderCircle class="animate-spin" /> Menyimpan…{:else}{labelSimpan}{/if}
		</Button>
	</div>
</form>
