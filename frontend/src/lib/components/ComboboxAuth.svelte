<script lang="ts">
	// Pilihan dari daftar besar di halaman publik (mis. ribuan satuan): pengguna mengetik, hasil dicari ke
	// server (dibatasi), lalu dipilih dari daftar pendek. Tampilan sama dengan FieldAuth.
	// Pola ARIA combobox: panah atas/bawah memilih, Enter menetapkan, Esc menutup.
	import type { Component, Snippet } from 'svelte';
	import { Label } from '#lib/components/ui/label/index.js';
	import { cn } from '#lib/utils.js';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import Check from '@lucide/svelte/icons/check';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Search from '@lucide/svelte/icons/search';

	type Opsi = { value: string; label: string };

	let {
		id,
		label,
		ikon: Ikon,
		cari,
		placeholder = 'Ketik untuk mencari…',
		value = $bindable(''),
		terpilih = $bindable(''),
		ref = $bindable(null),
		galat = null,
		bawah,
		onpilih,
		tema = 'gelap'
	}: {
		id: string;
		label: string;
		ikon: Component<{ class?: string }>;
		/** Cari opsi yang cocok dengan kata kunci (kosong = beberapa opsi teratas). */
		cari: (kata: string) => Promise<Opsi[]>;
		placeholder?: string;
		/** Nilai (id) opsi terpilih; kosong bila belum memilih. */
		value?: string;
		/** Label opsi terpilih (untuk ringkasan & isi kolom). */
		terpilih?: string;
		ref?: HTMLInputElement | null;
		galat?: string | null;
		bawah?: Snippet;
		onpilih?: (o: Opsi) => void;
		/** gelap = halaman publik (login/daftar); terang = form di dalam aplikasi (mengikuti tema). */
		tema?: 'gelap' | 'terang';
	} = $props();

	let kata = $state(terpilih);
	let buka = $state(false);
	let hasil = $state<Opsi[]>([]);
	let aktif = $state(-1);
	let memuat = $state(false);
	let gagal = $state(false);
	let urutan = 0;
	let tunda: ReturnType<typeof setTimeout> | undefined;

	const idDaftar = $derived(`${id}-daftar`);
	const gelap = $derived(tema === 'gelap');

	async function jalankanCari(q: string) {
		const ke = ++urutan;
		memuat = true;
		gagal = false;
		try {
			const r = await cari(q);
			if (ke !== urutan) return; // jawaban lama tiba belakangan: abaikan
			hasil = r;
			aktif = r.length ? 0 : -1;
		} catch {
			if (ke === urutan) gagal = true;
		} finally {
			if (ke === urutan) memuat = false;
		}
	}

	function ketik() {
		// Mengubah teks membatalkan pilihan sebelumnya sampai pengguna memilih lagi.
		if (kata !== terpilih) {
			value = '';
			terpilih = '';
		}
		buka = true;
		clearTimeout(tunda);
		tunda = setTimeout(() => jalankanCari(kata), 250);
	}

	function bukaDaftar() {
		buka = true;
		if (!hasil.length && !memuat) jalankanCari(value ? '' : kata);
	}

	function pilih(o: Opsi) {
		value = o.value;
		terpilih = o.label;
		kata = o.label;
		buka = false;
		onpilih?.(o);
	}

	function tombol(e: KeyboardEvent) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			if (!buka) return bukaDaftar();
			if (!hasil.length) return;
			aktif = (aktif + (e.key === 'ArrowDown' ? 1 : -1) + hasil.length) % hasil.length;
			document.getElementById(`${id}-opsi-${aktif}`)?.scrollIntoView({ block: 'nearest' });
		} else if (e.key === 'Enter' && buka && hasil[aktif]) {
			// Enter memilih opsi, bukan mengirim form.
			e.preventDefault();
			pilih(hasil[aktif]);
		} else if (e.key === 'Escape' && buka) {
			e.preventDefault();
			buka = false;
		}
	}

	// Tandai bagian nama yang cocok dengan kata kunci.
	function potong(teks: string): [string, string, string] {
		const q = kata.trim().toLowerCase();
		const i = q && !value ? teks.toLowerCase().indexOf(q) : -1;
		return i < 0 ? [teks, '', ''] : [teks.slice(0, i), teks.slice(i, i + q.length), teks.slice(i + q.length)];
	}
</script>

<div class="grid gap-1.5">
	<Label for={id} class={gelap ? 'text-sm font-medium text-white/85' : ''}>{label}</Label>
	<div class="group relative">
		<Ikon
			class={cn(
				'pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 transition group-focus-within:text-gold',
				gelap ? 'text-white/40' : 'text-muted-foreground'
			)}
		/>
		<input
			{id}
			bind:this={ref}
			bind:value={kata}
			role="combobox"
			autocomplete="off"
			spellcheck={false}
			aria-expanded={buka}
			aria-controls={idDaftar}
			aria-autocomplete="list"
			aria-activedescendant={buka && aktif >= 0 ? `${id}-opsi-${aktif}` : undefined}
			aria-invalid={!!galat}
			aria-describedby="{id}-pesan"
			{placeholder}
			oninput={ketik}
			onfocus={bukaDaftar}
			onclick={bukaDaftar}
			onblur={() => (buka = false)}
			onkeydown={tombol}
			class={cn(
				'w-full min-w-0 rounded-lg border py-1 pr-10 pl-10 outline-none transition-colors focus-visible:ring-3 aria-invalid:ring-3',
				gelap
					? 'h-10 border-white/12 bg-black/40 text-[15px] text-white placeholder:text-white/30 focus-visible:border-gold/70 focus-visible:ring-gold/20 aria-invalid:border-red-400/70 aria-invalid:ring-red-400/15'
					: 'h-9 border-input bg-transparent text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:bg-input/30'
			)}
		/>
		<span class="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2">
			{#if memuat}
				<LoaderCircle class={cn('size-4 animate-spin', gelap ? 'text-white/40' : 'text-muted-foreground')} />
			{:else if value}
				<Check class={cn('size-4', gelap ? 'text-[#9fe08a]' : 'text-success')} aria-label="Terpilih" />
			{:else}
				<Search class={cn('size-4', gelap ? 'text-white/30' : 'text-muted-foreground')} />
			{/if}
		</span>

		{#if buka}
			<!-- mousedown dicegah agar input tidak kehilangan fokus sebelum klik opsi diproses. -->
			<ul
				id={idDaftar}
				role="listbox"
				aria-label={label}
				class={cn(
					'absolute inset-x-0 top-full z-30 mt-1 max-h-60 overflow-y-auto rounded-lg border py-1',
					gelap
						? 'border-white/12 bg-[#121614] text-white/80 shadow-[0_16px_40px_rgb(0_0_0/0.6)]'
						: 'bg-popover text-popover-foreground shadow-lg'
				)}
				onmousedown={(e) => e.preventDefault()}
			>
				{#if gagal}
					<li class="px-3 py-2 text-sm text-red-300">
						Gagal memuat daftar.
						<button type="button" class="font-medium text-gold hover:underline" onclick={() => jalankanCari(kata)}>Coba lagi</button>
					</li>
				{:else if !hasil.length}
					<li class={cn('px-3 py-2 text-sm', gelap ? 'text-white/45' : 'text-muted-foreground')}>{memuat ? 'Mencari…' : 'Tidak ada yang cocok.'}</li>
				{:else}
					{#each hasil as o, i (o.value)}
						{@const [awal, cocok, akhir] = potong(o.label)}
						<!-- Keyboard ditangani input (pola combobox: panah + Enter); opsi cukup bisa diklik. -->
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<li
							id="{id}-opsi-{i}"
							role="option"
							aria-selected={o.value === value}
							class={cn(
								'flex cursor-pointer items-center gap-2 px-3 py-2 text-sm',
								i === aktif && (gelap ? 'bg-gold/15 text-white' : 'bg-accent text-accent-foreground'),
								o.value === value && 'text-gold'
							)}
							onmousemove={() => (aktif = i)}
							onclick={() => pilih(o)}
						>
							<span class="min-w-0 flex-1 break-words">{awal}<b class="font-semibold text-gold">{cocok}</b>{akhir}</span>
							{#if o.value === value}<Check class="size-3.5 shrink-0" />{/if}
						</li>
					{/each}
				{/if}
			</ul>
		{/if}
	</div>
	<div id="{id}-pesan" aria-live="polite" class="flex flex-wrap items-center gap-2 text-xs empty:hidden">
		{#if galat}
			<p class="flex items-center gap-1.5 text-red-300"><CircleAlert class="size-3.5" />{galat}</p>
		{/if}
		{@render bawah?.()}
	</div>
</div>
