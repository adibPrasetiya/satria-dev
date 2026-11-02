<script lang="ts">
	// Editor parameter katalog (objek bebas bentuk yang dibaca pemeriksa pengujian).
	// Mode formulir untuk nilai sederhana (angka, teks, ya/tidak, daftar); mode JSON untuk struktur bertingkat.
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import NativeSelect from './NativeSelect.svelte';
	import { cn } from '#lib/utils.js';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';

	let {
		awal,
		nilai = $bindable(null),
		valid = $bindable(true),
		galatServer = null
	}: {
		/** Parameter tersimpan; dibaca sekali saat editor dibuat. */
		awal?: Record<string, unknown>;
		/** Hasil yang akan dikirim: null bila kosong. */
		nilai?: Record<string, unknown> | null;
		valid?: boolean;
		galatServer?: string | null;
	} = $props();

	type Jenis = 'angka' | 'teks' | 'boolean' | 'daftar';
	interface Baris {
		id: number;
		kunci: string;
		jenis: Jenis;
		isi: string;
	}

	const KUNCI = /^[a-z][a-z0-9_]{0,59}$/;
	const ANGKA = /^-?\d+(\.\d+)?$/;

	const sederhana = (v: unknown) =>
		['number', 'string', 'boolean'].includes(typeof v) ||
		(Array.isArray(v) && v.every((x) => typeof x === 'string' || typeof x === 'number'));
	const bisaFormulir = (o: Record<string, unknown>) => Object.values(o).every(sederhana);

	let urut = 0;
	function keBaris(o: Record<string, unknown>): Baris[] {
		return Object.entries(o).map(([kunci, v]) => ({
			id: urut++,
			kunci,
			jenis: Array.isArray(v) ? 'daftar' : typeof v === 'number' ? 'angka' : typeof v === 'boolean' ? 'boolean' : 'teks',
			isi: Array.isArray(v) ? v.join(', ') : String(v)
		}));
	}

	// Salinan awal sengaja diambil sekali: editor menyunting draf.
	// svelte-ignore state_referenced_locally
	const mula = awal ?? {};
	let mode = $state<'formulir' | 'json'>(bisaFormulir(mula) ? 'formulir' : 'json');
	let baris = $state<Baris[]>(keBaris(mula));
	let teksJson = $state(JSON.stringify(mula, null, 2));

	function dariFormulir(): { obj: Record<string, unknown>; galat: Record<number, string> } {
		const obj: Record<string, unknown> = {};
		const galat: Record<number, string> = {};
		for (const b of baris) {
			const k = b.kunci.trim();
			if (!KUNCI.test(k)) galat[b.id] = 'Nama: huruf kecil/angka/garis bawah, diawali huruf';
			else if (k in obj) galat[b.id] = 'Nama parameter ganda';
			else if (b.jenis === 'angka' && !ANGKA.test(b.isi.trim())) galat[b.id] = 'Nilai harus angka';
			if (galat[b.id]) continue;
			obj[k] =
				b.jenis === 'angka'
					? Number(b.isi.trim())
					: b.jenis === 'boolean'
						? b.isi === 'true'
						: b.jenis === 'daftar'
							? b.isi.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (ANGKA.test(s) ? Number(s) : s))
							: b.isi.trim();
		}
		return { obj, galat };
	}

	function dariJson(): { obj: Record<string, unknown> | null; galat: string | null } {
		if (!teksJson.trim()) return { obj: {}, galat: null };
		try {
			const v = JSON.parse(teksJson);
			if (!v || typeof v !== 'object' || Array.isArray(v)) return { obj: null, galat: 'Parameter harus berupa objek JSON { … }' };
			const salah = Object.keys(v).find((k) => !KUNCI.test(k));
			if (salah) return { obj: null, galat: `Nama "${salah}" tidak valid: huruf kecil/angka/garis bawah, diawali huruf` };
			return { obj: v, galat: null };
		} catch (e) {
			return { obj: null, galat: `JSON tidak valid: ${(e as Error).message}` };
		}
	}

	const hasilFormulir = $derived(mode === 'formulir' ? dariFormulir() : null);
	const hasilJson = $derived(mode === 'json' ? dariJson() : null);
	const jsonBisaFormulir = $derived(mode === 'json' && !!hasilJson?.obj && bisaFormulir(hasilJson.obj));

	$effect(() => {
		const obj = mode === 'formulir' ? hasilFormulir!.obj : hasilJson!.obj;
		valid = mode === 'formulir' ? !Object.keys(hasilFormulir!.galat).length : !hasilJson!.galat;
		nilai = obj && Object.keys(obj).length ? obj : null;
	});

	function keJson() {
		teksJson = JSON.stringify(dariFormulir().obj, null, 2);
		mode = 'json';
	}
	function keFormulir() {
		if (!jsonBisaFormulir) return;
		baris = keBaris(hasilJson!.obj!);
		mode = 'formulir';
	}
	function tambah() {
		baris.push({ id: urut++, kunci: '', jenis: 'angka', isi: '' });
	}

	const OPSI_JENIS = [
		{ value: 'angka', label: 'Angka' },
		{ value: 'teks', label: 'Teks' },
		{ value: 'boolean', label: 'Ya / tidak' },
		{ value: 'daftar', label: 'Daftar' }
	];
</script>

<div class="grid gap-2 rounded-lg border p-3">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<p class="text-sm font-medium">Parameter <span class="font-normal text-muted-foreground">(opsional)</span></p>
			<p class="text-xs text-muted-foreground">Nilai yang dibaca pemeriksa, mis. batas percobaan atau panjang minimum.</p>
		</div>
		<div class="inline-flex rounded-md border p-0.5 text-xs" role="tablist" aria-label="Mode editor parameter">
			<button
				type="button"
				role="tab"
				aria-selected={mode === 'formulir'}
				disabled={mode === 'json' && !jsonBisaFormulir}
				title={mode === 'json' && !jsonBisaFormulir ? 'Parameter bertingkat hanya bisa diedit sebagai JSON' : undefined}
				class={cn('rounded px-2.5 py-1 transition-colors disabled:cursor-not-allowed disabled:opacity-40', mode === 'formulir' ? 'bg-gold text-gold-foreground' : 'hover:bg-muted')}
				onclick={keFormulir}
			>
				Formulir
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={mode === 'json'}
				class={cn('rounded px-2.5 py-1 font-mono transition-colors', mode === 'json' ? 'bg-gold text-gold-foreground' : 'hover:bg-muted')}
				onclick={() => mode === 'formulir' && keJson()}
			>
				JSON
			</button>
		</div>
	</div>

	{#if mode === 'formulir'}
		{#each baris as b, i (b.id)}
			{@const galat = hasilFormulir?.galat[b.id]}
			<div class="grid gap-1">
				<div class="grid grid-cols-[1fr_auto] gap-2 sm:grid-cols-[minmax(0,1fr)_120px_minmax(0,1.3fr)_auto]">
					<Input class="h-9 font-mono text-xs" placeholder="nama_parameter" bind:value={b.kunci} aria-label="Nama parameter {i + 1}" spellcheck={false} aria-invalid={!!galat} />
					<NativeSelect class="h-9 max-sm:order-3" bind:value={b.jenis} opsi={OPSI_JENIS} aria-label="Jenis parameter {i + 1}"
						onchange={() => b.jenis === 'boolean' && !['true', 'false'].includes(b.isi) && (b.isi = 'true')} />
					{#if b.jenis === 'boolean'}
						<NativeSelect class="h-9 max-sm:order-4" bind:value={b.isi} opsi={[{ value: 'true', label: 'Ya' }, { value: 'false', label: 'Tidak' }]} aria-label="Nilai parameter {i + 1}" />
					{:else}
						<Input
							class="h-9 max-sm:order-4"
							inputmode={b.jenis === 'angka' ? 'decimal' : undefined}
							placeholder={b.jenis === 'daftar' ? 'pisahkan dengan koma' : b.jenis === 'angka' ? '0' : 'nilai'}
							bind:value={b.isi}
							aria-label="Nilai parameter {i + 1}"
						/>
					{/if}
					<Button type="button" variant="ghost" size="icon-sm" class="self-center text-muted-foreground hover:text-critical max-sm:order-2"
						onclick={() => baris.splice(i, 1)} aria-label="Hapus parameter {b.kunci || i + 1}">
						<Trash2 />
					</Button>
				</div>
				{#if galat}<p class="flex items-center gap-1 text-xs text-critical"><CircleAlert class="size-3" />{galat}</p>{/if}
			</div>
		{:else}
			<p class="text-xs text-muted-foreground italic">Belum ada parameter.</p>
		{/each}
		<Button type="button" variant="ghost" size="sm" class="justify-self-start text-gold" onclick={tambah}>
			<Plus /> Tambah parameter
		</Button>
	{:else}
		<!-- Tinggi dibatasi agar daftar panjang (mis. daftar PSrE) digulir di dalam kotak, bukan memanjangkan dialog. -->
		<Textarea bind:value={teksJson} rows={8} spellcheck={false} class="max-h-72 overflow-y-auto font-mono text-xs" aria-label="Parameter (JSON)" aria-invalid={!!hasilJson?.galat} />
		{#if hasilJson?.galat}
			<p class="flex items-center gap-1 text-xs text-critical"><CircleAlert class="size-3" />{hasilJson.galat}</p>
		{:else if !jsonBisaFormulir}
			<p class="text-xs text-muted-foreground">Parameter bertingkat (objek/daftar objek) hanya bisa diedit sebagai JSON.</p>
		{/if}
	{/if}

	{#if galatServer}<p class="flex items-center gap-1 text-xs text-critical"><CircleAlert class="size-3" />{galatServer}</p>{/if}
</div>
