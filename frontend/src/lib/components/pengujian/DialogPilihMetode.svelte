<script lang="ts">
	// Modal 2 — pilih metode pengujian: otomatis (eksploratif) atau manual (segera).
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import ScanSearch from '@lucide/svelte/icons/scan-search';
	import Hand from '@lucide/svelte/icons/hand';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		open = $bindable(false),
		onotomatis
	}: {
		open?: boolean;
		onotomatis: () => void;
	} = $props();

	function pilihOtomatis() {
		open = false;
		onotomatis();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="sm:max-w-lg">
		<Dialog.Header>
			<Dialog.Title>Metode Pengujian</Dialog.Title>
			<Dialog.Description>Pilih bagaimana pengujian dijalankan.</Dialog.Description>
		</Dialog.Header>
		<div class="grid gap-3 sm:grid-cols-2">
			<button
				type="button"
				onclick={pilihOtomatis}
				class="sudut-taktis group flex flex-col gap-2 rounded-lg border bg-card p-4 text-left transition hover:border-gold/70 hover:bg-gold/5"
			>
				<div class="flex items-center justify-between">
					<ScanSearch class="size-5 text-gold" />
					<ChevronRight class="size-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-gold" />
				</div>
				<p class="font-heading text-sm tracking-wide uppercase">Metode Otomatis</p>
				<p class="text-xs text-muted-foreground">Mesin menemukan titik uji dari URL lalu menguji otomatis (eksploratif).</p>
			</button>
			<div
				aria-disabled="true"
				class="relative flex cursor-not-allowed flex-col gap-2 rounded-lg border border-dashed bg-muted/30 p-4 text-left opacity-80"
			>
				<div class="flex items-center justify-between">
					<Hand class="size-5 text-muted-foreground" />
					<span class="rounded-sm border border-warning/50 bg-warning/10 px-1.5 py-px font-heading text-[10px] tracking-wide text-warning-foreground uppercase">Segera</span>
				</div>
				<p class="font-heading text-sm tracking-wide text-muted-foreground uppercase">Metode Manual</p>
				<p class="text-xs text-muted-foreground">Pengisian titik uji & metode secara manual. Belum tersedia.</p>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>
