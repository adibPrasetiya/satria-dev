<script lang="ts">
	// Jendela dokumen Syarat & Ketentuan pengujian. Pengguna menggulir dokumen hingga akhir, mencentang
	// persetujuan, lalu menekan "Setujui & Tutup". Sebelum disetujui jendela tidak dapat ditutup dengan
	// Esc / klik di luar / tombol silang; jalan keluar lain hanya membatalkan pengujian.
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { BERLAKU_SK, KODE_SK, VERSI_SK, dokumenSK } from '#lib/pengujian/syarat-ketentuan.js';

	let {
		open = $bindable(false),
		blackbox,
		target,
		namaAplikasi,
		sudahSetuju,
		onsetuju,
		onbatal
	}: {
		open?: boolean;
		blackbox: boolean;
		target: string;
		namaAplikasi: string;
		/** Sudah disetujui sebelumnya → dokumen hanya dibaca ulang, bisa ditutup bebas. */
		sudahSetuju: boolean;
		onsetuju: () => void;
		onbatal: () => void;
	} = $props();

	const pasal = $derived(dokumenSK(blackbox));
	const pendekatan = $derived(blackbox ? 'Black Box' : 'Grey Box');

	let isi = $state<HTMLDivElement | null>(null);
	let sampaiAkhir = $state(false);
	let centang = $state(false);

	$effect(() => {
		if (!open) return;
		centang = sudahSetuju;
		sampaiAkhir = sudahSetuju;
		queueMicrotask(() => {
			isi?.scrollTo({ top: 0 });
			gulir();
		});
	});

	function gulir() {
		if (!isi) return;
		if (isi.scrollHeight - isi.clientHeight - isi.scrollTop < 24) sampaiAkhir = true;
	}

	function setuju() {
		if (!centang) return;
		open = false;
		onsetuju();
	}

	const bebas = $derived(sudahSetuju);
</script>

<Dialog.Root
	bind:open={
		() => open,
		(v) => {
			// Hanya boleh tertutup tanpa persetujuan bila dokumen sudah pernah disetujui.
			if (v || bebas) open = v;
		}
	}
>
	<Dialog.Content
		showCloseButton={bebas}
		escapeKeydownBehavior={bebas ? 'close' : 'ignore'}
		interactOutsideBehavior={bebas ? 'close' : 'ignore'}
		class="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden border bg-card p-0 text-card-foreground shadow-2xl sm:max-w-[min(760px,calc(100%-2rem))]"
	>
		<Dialog.Header class="border-b px-6 py-5 text-left sm:px-8">
			<p class="font-mono text-[10px] tracking-wider text-muted-foreground uppercase">{KODE_SK} · Versi {VERSI_SK}</p>
			<Dialog.Title class="mt-1 font-heading text-lg tracking-wide uppercase sm:text-xl">Syarat & Ketentuan Operasi Pengujian</Dialog.Title>
			<Dialog.Description class="mt-1 text-xs text-muted-foreground">
				{namaAplikasi} · <span class="font-mono">{target}</span> · {pendekatan} · berlaku sejak {BERLAKU_SK}
			</Dialog.Description>
		</Dialog.Header>

		<div bind:this={isi} onscroll={gulir} class="min-h-0 flex-1 overflow-y-auto px-6 py-6 sm:px-8">
			<p class="text-sm leading-relaxed text-muted-foreground">
				Dokumen ini mengatur pelaksanaan operasi pengujian keamanan melalui SATRIA. Dengan menyetujui dokumen ini, Pengguna
				terikat pada seluruh ketentuan di bawah selama pengujian berlangsung.
			</p>

			<ol class="mt-7 space-y-7">
				{#each pasal as p, i (p.judul)}
					<li>
						<h3 class="text-sm font-semibold">
							<span class="mr-2 font-mono text-xs font-normal text-muted-foreground">{i + 1}.</span>{p.judul}
						</h3>
						{#if p.pengantar}<p class="mt-2 text-sm text-muted-foreground">{p.pengantar}</p>{/if}
						<ol class="mt-2 space-y-1.5">
							{#each p.butir as b, j (j)}
								<li class="grid grid-cols-[1.75rem_1fr] text-sm leading-relaxed text-foreground/90">
									<span class="font-mono text-xs leading-6 text-muted-foreground">{i + 1}.{j + 1}</span>
									<span>{b}</span>
								</li>
							{/each}
						</ol>
					</li>
				{/each}
			</ol>
		</div>

		<div class="border-t px-6 py-4 sm:px-8">
			<label class="flex items-start gap-3 text-sm {sampaiAkhir ? 'cursor-pointer' : 'cursor-not-allowed text-muted-foreground'}">
				<Checkbox bind:checked={centang} disabled={!sampaiAkhir} class="mt-0.5" />
				<span>
					Saya telah membaca dan menyetujui Syarat & Ketentuan ini, serta menyatakan berwenang menguji aplikasi tersebut.
					{#if !sampaiAkhir}<span class="mt-0.5 block text-xs">Baca dokumen hingga akhir untuk menyetujui.</span>{/if}
				</span>
			</label>
			<div class="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
				{#if bebas}
					<span></span>
				{:else}
					<button type="button" onclick={onbatal} class="text-xs text-muted-foreground hover:text-foreground">Tidak setuju, batalkan pengujian</button>
				{/if}
				<Button onclick={setuju} disabled={!centang} class="bg-gold text-gold-foreground hover:bg-gold/85">Setujui & Tutup</Button>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>
