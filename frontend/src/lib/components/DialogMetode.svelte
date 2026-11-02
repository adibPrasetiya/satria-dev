<script lang="ts">
	// Tambah / ubah metode pengujian katalog (khusus admin). Kode metode = <KONTROL>-Tnn, dibuat backend.
	import { api } from '#lib/api/client.js';
	import { GalatApi } from '#lib/api/http.js';
	import { LABEL_ENGINE, LABEL_JENIS } from '#lib/catalog.js';
	import type { JenisBukti, Kontrol, Metode, MetodeBaru, TitikUji } from '#lib/types.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import Field from './Field.svelte';
	import NativeSelect from './NativeSelect.svelte';
	import EditorParameter from './EditorParameter.svelte';
	import { toast } from 'svelte-sonner';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let {
		open = $bindable(false),
		kontrol,
		metode,
		titikUji,
		onselesai
	}: {
		open?: boolean;
		/** Kontrol induk (wajib untuk tambah). */
		kontrol: Kontrol | null;
		/** Metode yang diubah; kosong = tambah baru. */
		metode?: Metode | null;
		titikUji: TitikUji[];
		onselesai: () => void;
	} = $props();

	type Kolom = keyof MetodeBaru;

	const kosong = (): MetodeBaru & { aktif: boolean } => ({
		nama: '',
		titik_uji: titikUji[0]?.id ?? '',
		check_id: '',
		jenis: 'otomatis',
		engine: 'custom',
		profil: 'aman',
		butuh_autentikasi: false,
		bukti: ['request_response'],
		kriteria_lulus: '',
		efek_samping: '',
		severity: kontrol?.severity_default ?? 'sedang',
		aktif: true
	});
	let f = $state(kosong());
	let galat = $state<Partial<Record<Kolom, string>>>({});
	let parameter = $state<Record<string, unknown> | null>(null);
	let parameterValid = $state(true);
	let menyimpan = $state(false);

	$effect(() => {
		if (!open) return;
		f = metode
			? {
					nama: metode.nama,
					titik_uji: metode.titik_uji,
					check_id: metode.check_id,
					jenis: metode.jenis,
					engine: metode.engine,
					profil: metode.profil,
					butuh_autentikasi: metode.butuh_autentikasi,
					bukti: [...metode.bukti],
					kriteria_lulus: metode.kriteria_lulus,
					efek_samping: metode.efek_samping ?? '',
					severity: metode.severity,
					aktif: metode.aktif ?? true
				}
			: kosong();
		galat = {};
	});

	function alihBukti(b: JenisBukti, pilih: boolean) {
		f.bukti = pilih ? [...new Set([...f.bukti, b])] : f.bukti.filter((x) => x !== b);
	}

	async function simpan(e: SubmitEvent) {
		e.preventDefault();
		galat = {};
		if (f.nama.trim().length < 3) galat.nama = 'Nama metode minimal 3 karakter';
		if (!/^[a-z0-9_.-]+$/.test(f.check_id.trim())) galat.check_id = 'Huruf kecil, angka, titik, garis bawah; mis. auth.login_required';
		if (f.kriteria_lulus.trim().length < 3) galat.kriteria_lulus = 'Kriteria lulus wajib diisi';
		if (!f.bukti.length) galat.bukti = 'Pilih minimal satu jenis bukti';
		if (Object.keys(galat).length || !parameterValid) return;

		const { aktif, ...isi } = f;
		const data: MetodeBaru = {
			...isi,
			nama: isi.nama.trim(),
			check_id: isi.check_id.trim(),
			kriteria_lulus: isi.kriteria_lulus.trim(),
			efek_samping: isi.efek_samping.trim(),
			parameter
		};
		menyimpan = true;
		try {
			if (metode) {
				await api.ubahMetode(metode.id, { ...data, aktif });
				toast.success(`Metode ${metode.id} diperbarui`);
			} else {
				const m = await api.tambahMetode(kontrol!.id, data);
				toast.success(`Metode ${m.id} ditambahkan`);
			}
			open = false;
			onselesai();
		} catch (err) {
			const daftar = err instanceof GalatApi ? (err.errors ?? []) : [];
			for (const g of daftar) galat[g.field as Kolom] = g.message;
			if (!daftar.length) toast.error((err as Error).message);
		} finally {
			menyimpan = false;
		}
	}

	const opsi = (label: Record<string, string>) => Object.entries(label).map(([value, l]) => ({ value, label: l }));
	const OPSI_SEVERITY = ['kritis', 'tinggi', 'sedang', 'rendah', 'info'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }));
	const BUKTI: { value: JenisBukti; label: string }[] = [
		{ value: 'request_response', label: 'Request/response' },
		{ value: 'screenshot', label: 'Tangkapan layar' },
		{ value: 'dokumen', label: 'Dokumen' }
	];
</script>

{#snippet pesan(k: Kolom)}
	{#if galat[k]}<p class="text-xs text-critical">{galat[k]}</p>{/if}
{/snippet}

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
		<form class="grid gap-4" onsubmit={simpan} novalidate>
			<Dialog.Header>
				<Dialog.Title>{metode ? `Ubah metode ${metode.id}` : 'Tambah metode pengujian'}</Dialog.Title>
				{#if kontrol}<Dialog.Description>Kontrol {kontrol.id} — {kontrol.uraian}</Dialog.Description>{/if}
			</Dialog.Header>

			<Field label="Nama metode" id="m-nama" wajib>
				<Input id="m-nama" class="h-9" bind:value={f.nama} maxlength={255} aria-invalid={!!galat.nama} />
				{@render pesan('nama')}
			</Field>
			<Field label="Kriteria lulus" id="m-kriteria" wajib bantuan="Kondisi yang harus terpenuhi agar metode dinyatakan lulus.">
				<Textarea id="m-kriteria" bind:value={f.kriteria_lulus} rows={2} maxlength={2000} aria-invalid={!!galat.kriteria_lulus} />
				{@render pesan('kriteria_lulus')}
			</Field>

			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Titik uji" id="m-titik">
					<NativeSelect id="m-titik" class="h-9" bind:value={f.titik_uji} opsi={titikUji.map((t) => ({ value: t.id, label: t.nama }))} />
					{@render pesan('titik_uji')}
				</Field>
				<Field label="Check ID" id="m-check" wajib bantuan="Pengenal pemeriksa otomatis.">
					<Input id="m-check" class="h-9 font-mono" bind:value={f.check_id} maxlength={120} aria-invalid={!!galat.check_id} placeholder="auth.login_required" spellcheck={false} />
					{@render pesan('check_id')}
				</Field>
				<Field label="Jenis" id="m-jenis">
					<NativeSelect id="m-jenis" class="h-9" bind:value={f.jenis} opsi={opsi(LABEL_JENIS)} />
				</Field>
				<Field label="Mesin pengujian" id="m-engine">
					<NativeSelect id="m-engine" class="h-9" bind:value={f.engine} opsi={opsi(LABEL_ENGINE)} />
				</Field>
				<Field label="Profil" id="m-profil" bantuan="Intrusif hanya dijalankan pada target berizin.">
					<NativeSelect id="m-profil" class="h-9" bind:value={f.profil} opsi={[{ value: 'aman', label: 'Aman' }, { value: 'intrusif', label: 'Intrusif' }]} />
				</Field>
				<Field label="Severity" id="m-sev">
					<NativeSelect id="m-sev" class="h-9" bind:value={f.severity} opsi={OPSI_SEVERITY} />
				</Field>
			</div>

			<fieldset class="grid gap-2">
				<legend class="mb-1 text-sm font-medium">Jenis bukti</legend>
				<div class="flex flex-wrap gap-x-5 gap-y-2">
					{#each BUKTI as b (b.value)}
						<label class="flex items-center gap-2 text-sm">
							<Checkbox checked={f.bukti.includes(b.value)} onCheckedChange={(v) => alihBukti(b.value, v === true)} />
							{b.label}
						</label>
					{/each}
				</div>
				{@render pesan('bukti')}
			</fieldset>

			<div class="flex items-start justify-between gap-4 rounded-lg border p-3">
				<div>
					<label for="m-auth" class="text-sm font-medium">Butuh akun uji (login)</label>
					<p class="text-xs text-muted-foreground">Metode dilewati bila aplikasi belum menyediakan akun uji.</p>
				</div>
				<Switch id="m-auth" bind:checked={f.butuh_autentikasi} />
			</div>

			<Field label="Efek samping (opsional)" id="m-efek" bantuan="Dampak terhadap aplikasi yang diuji, mis. membuat akun uji.">
				<Textarea id="m-efek" bind:value={f.efek_samping} rows={2} maxlength={2000} />
			</Field>

			{#key metode?.id ?? 'baru'}
				<EditorParameter awal={metode?.parameter} bind:nilai={parameter} bind:valid={parameterValid} galatServer={galat.parameter} />
			{/key}

			{#if metode}
				<div class="flex items-start justify-between gap-4 rounded-lg border p-3">
					<div>
						<label for="m-aktif" class="text-sm font-medium">Aktif</label>
						<p class="text-xs text-muted-foreground">Metode nonaktif tidak dijalankan di pengujian baru.</p>
					</div>
					<Switch id="m-aktif" bind:checked={f.aktif} />
				</div>
			{/if}

			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" disabled={menyimpan}>
					{#if menyimpan}<LoaderCircle class="animate-spin" />{/if}{metode ? 'Simpan' : 'Tambah metode'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
