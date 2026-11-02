<script lang="ts">
	// Tambah / ubah butir kontrol katalog (khusus admin). Kode kontrol = <FUNGSI>-<nomor referensi>, tetap setelah dibuat.
	import { api } from '#lib/api/client.js';
	import { GalatApi } from '#lib/api/http.js';
	import type { Fungsi, Kontrol, KontrolBaru } from '#lib/types.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import Field from './Field.svelte';
	import NativeSelect from './NativeSelect.svelte';
	import EditorParameter from './EditorParameter.svelte';
	import { toast } from 'svelte-sonner';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let {
		open = $bindable(false),
		fungsi,
		kontrol,
		onselesai
	}: {
		open?: boolean;
		/** Fungsi induk (wajib untuk tambah; untuk ubah hanya ditampilkan). */
		fungsi: Fungsi | null;
		/** Kontrol yang diubah; kosong = tambah baru. */
		kontrol?: Kontrol | null;
		onselesai: () => void;
	} = $props();

	type Kolom = 'nomor_referensi' | 'uraian' | 'verifiabilitas' | 'severity_default' | 'agregasi' | 'referensi_pendukung' | 'parameter';

	let f = $state({
		nomor_referensi: '',
		uraian: '',
		verifiabilitas: 'otomatis' as KontrolBaru['verifiabilitas'],
		severity_default: 'sedang' as KontrolBaru['severity_default'],
		agregasi: 'semua_lulus' as KontrolBaru['agregasi'],
		referensi: '',
		aktif: true
	});
	let galat = $state<Partial<Record<Kolom, string>>>({});
	let parameter = $state<Record<string, unknown> | null>(null);
	let parameterValid = $state(true);
	let menyimpan = $state(false);

	// Isi ulang form setiap kali dibuka.
	$effect(() => {
		if (!open) return;
		f = {
			nomor_referensi: kontrol?.nomor_referensi ?? '',
			uraian: kontrol?.uraian ?? '',
			verifiabilitas: kontrol?.verifiabilitas ?? 'otomatis',
			severity_default: kontrol?.severity_default ?? 'sedang',
			agregasi: kontrol?.agregasi ?? 'semua_lulus',
			referensi: (kontrol?.referensi_pendukung ?? []).join(', '),
			aktif: kontrol?.aktif ?? true
		};
		galat = {};
	});

	async function simpan(e: SubmitEvent) {
		e.preventDefault();
		const data: KontrolBaru = {
			nomor_referensi: f.nomor_referensi.trim(),
			uraian: f.uraian.trim(),
			verifiabilitas: f.verifiabilitas,
			severity_default: f.severity_default,
			agregasi: f.agregasi,
			referensi_pendukung: [...new Set(f.referensi.split(',').map((s) => s.trim()).filter(Boolean))],
			parameter
		};
		galat = {};
		if (!kontrol && !/^\d+(\.\d+)*$/.test(data.nomor_referensi)) galat.nomor_referensi = 'Nomor berupa angka bertitik, mis. 1.10';
		if (data.uraian.length < 5) galat.uraian = 'Uraian minimal 5 karakter';
		if (Object.keys(galat).length || !parameterValid) return;

		menyimpan = true;
		try {
			if (kontrol) {
				const { nomor_referensi: _, ...ubah } = data;
				await api.ubahKontrol(kontrol.id, { ...ubah, aktif: f.aktif });
				toast.success(`Kontrol ${kontrol.id} diperbarui`);
			} else {
				const k = await api.tambahKontrol(fungsi!.id, data);
				toast.success(`Kontrol ${k.id} ditambahkan`);
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

	const OPSI_VERIFIABILITAS = [
		{ value: 'otomatis', label: 'Otomatis' },
		{ value: 'sebagian', label: 'Sebagian' },
		{ value: 'manual', label: 'Manual' }
	];
	const OPSI_SEVERITY = ['kritis', 'tinggi', 'sedang', 'rendah', 'info'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }));
	const OPSI_AGREGASI = [
		{ value: 'semua_lulus', label: 'Semua metode harus lulus' },
		{ value: 'minimal_satu', label: 'Minimal satu metode lulus' }
	];
</script>

{#snippet pesan(k: Kolom)}
	{#if galat[k]}<p class="text-xs text-critical">{galat[k]}</p>{/if}
{/snippet}

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90svh] overflow-y-auto sm:max-w-xl">
		<form class="grid gap-4" onsubmit={simpan} novalidate>
			<Dialog.Header>
				<Dialog.Title>{kontrol ? `Ubah kontrol ${kontrol.id}` : 'Tambah kontrol'}</Dialog.Title>
				{#if fungsi}<Dialog.Description>Fungsi keamanan {fungsi.nomor}. {fungsi.nama}</Dialog.Description>{/if}
			</Dialog.Header>

			{#if !kontrol}
				<Field label="Nomor referensi" id="k-nomor" wajib bantuan="Kode kontrol menjadi {fungsi?.id}-{f.nomor_referensi || 'nomor'} dan tidak bisa diubah.">
					<Input id="k-nomor" bind:value={f.nomor_referensi} placeholder="mis. {fungsi?.nomor}.10" aria-invalid={!!galat.nomor_referensi} />
					{@render pesan('nomor_referensi')}
				</Field>
			{/if}
			<Field label="Uraian kontrol" id="k-uraian" wajib>
				<Textarea id="k-uraian" bind:value={f.uraian} rows={3} maxlength={2000} aria-invalid={!!galat.uraian} />
				{@render pesan('uraian')}
			</Field>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Verifiabilitas" id="k-verif" bantuan="Seberapa jauh kontrol bisa dibuktikan dari luar.">
					<NativeSelect id="k-verif" class="h-9" bind:value={f.verifiabilitas} opsi={OPSI_VERIFIABILITAS} />
				</Field>
				<Field label="Severity bawaan" id="k-sev" bantuan="Dipakai metode yang tidak menetapkan severity sendiri.">
					<NativeSelect id="k-sev" class="h-9" bind:value={f.severity_default} opsi={OPSI_SEVERITY} />
				</Field>
			</div>
			<Field label="Aturan kelulusan" id="k-agregasi">
				<NativeSelect id="k-agregasi" class="h-9" bind:value={f.agregasi} opsi={OPSI_AGREGASI} />
			</Field>
			<Field label="Referensi pendukung" id="k-ref" bantuan="Pisahkan dengan koma, mis. OWASP ASVS V2.1, CWE-521">
				<Input id="k-ref" class="h-9" bind:value={f.referensi} />
				{@render pesan('referensi_pendukung')}
			</Field>
			{#key kontrol?.id ?? 'baru'}
				<EditorParameter awal={kontrol?.parameter} bind:nilai={parameter} bind:valid={parameterValid} galatServer={galat.parameter} />
			{/key}
			{#if kontrol}
				<div class="flex items-start justify-between gap-4 rounded-lg border p-3">
					<div>
						<label for="k-aktif" class="text-sm font-medium">Aktif</label>
						<p class="text-xs text-muted-foreground">Kontrol nonaktif tidak dipakai di pengujian baru; hasil lama tetap terbaca.</p>
					</div>
					<Switch id="k-aktif" bind:checked={f.aktif} />
				</div>
			{/if}

			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" disabled={menyimpan}>
					{#if menyimpan}<LoaderCircle class="animate-spin" />{/if}{kontrol ? 'Simpan' : 'Tambah kontrol'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
