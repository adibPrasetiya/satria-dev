<script lang="ts">
	// Penanda langkah form bertahap: bulatan bernomor yang terhubung garis, label di bawahnya.
	// Membentang selebar konten — bulatan pertama rata kiri, terakhir rata kanan, garis mengisi sisanya.
	// Langkah yang sudah dilewati bisa diklik untuk kembali; langkah di depan terkunci.
	import { cn } from '#lib/utils.js';
	import Check from '@lucide/svelte/icons/check';

	let {
		langkah,
		label,
		onpilih,
		tema = 'gelap',
		bebas = false,
		ariaLabel = 'Langkah pendaftaran'
	}: {
		/** Indeks langkah aktif (mulai 0). */
		langkah: number;
		label: readonly string[];
		onpilih: (i: number) => void;
		/** gelap = halaman publik (login/daftar); terang = di dalam aplikasi (mengikuti tema terang/gelap). */
		tema?: 'gelap' | 'terang';
		/** true = semua langkah bisa diklik (mis. mengubah data yang sudah lengkap). */
		bebas?: boolean;
		ariaLabel?: string;
	} = $props();

	const gelap = $derived(tema === 'gelap');
</script>

<ol class="flex w-full items-start" aria-label={ariaLabel}>
	{#each label as l, i (l)}
		{@const selesai = i < langkah}
		{@const aktif = i === langkah}
		{@const pertama = i === 0}
		{@const terakhir = i === label.length - 1}
		<li class="relative shrink-0">
			<button
				type="button"
				disabled={!selesai && !(bebas && !aktif)}
				onclick={() => onpilih(i)}
				aria-current={aktif ? 'step' : undefined}
				aria-label="Langkah {i + 1}: {l}{selesai ? ' (selesai)' : ''}"
				class="group/langkah flex size-[30px] disabled:cursor-default"
			>
				<span
					class={cn(
						'grid size-[30px] place-items-center rounded-full border text-[13px] font-semibold transition-all duration-300',
						aktif &&
							'border-gold bg-gold text-gold-foreground shadow-[0_0_0_4px_rgb(150_175_95/0.18),0_0_18px_rgb(150_175_95/0.35)]',
						selesai && 'border-gold/70 bg-gold/15 text-gold group-hover/langkah:bg-gold/25',
						!aktif &&
							!selesai &&
							(gelap
								? 'border-white/15 bg-white/[0.04] text-white/45'
								: 'border-border bg-muted text-muted-foreground'),
						!aktif && !selesai && bebas && 'group-hover/langkah:border-gold/60'
					)}
				>
					{#if selesai}<Check class="size-3.5" />{:else}{i + 1}{/if}
				</span>
			</button>
			<!-- Label di bawah bulatan: tengah, kecuali ujung kiri/kanan agar tak melewati tepi konten. -->
			<span
				aria-hidden="true"
				class={cn(
					'absolute top-[40px] text-[11.5px] whitespace-nowrap transition-colors',
					pertama ? 'left-0' : terakhir ? 'right-0' : 'left-1/2 -translate-x-1/2',
					gelap
						? aktif
							? 'font-medium text-white'
							: selesai
								? 'text-white/70'
								: 'text-white/45'
						: aktif
							? 'font-medium text-foreground'
							: 'text-muted-foreground'
				)}
			>
				{l}
			</span>
		</li>
		{#if !terakhir}
			<!-- Garis penghubung: mengisi ruang antar-bulatan. -->
			<li
				aria-hidden="true"
				class={cn('relative mx-2 mt-[15px] h-px flex-1 overflow-hidden', gelap ? 'bg-white/12' : 'bg-border')}
			>
				<span
					class={cn(
						'absolute inset-y-0 left-0 bg-gold transition-[width] duration-500 ease-out',
						selesai ? 'w-full' : aktif ? 'w-1/2' : 'w-0'
					)}
				></span>
			</li>
		{/if}
	{/each}
</ol>
<!-- Ruang untuk label yang diposisikan absolut di bawah bulatan. -->
<div class="h-7" aria-hidden="true"></div>
