<script lang="ts">
	// Modal 1 — setelah membuka aset: lihat riwayat pengujian atau lakukan pengujian baru.
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import History from '@lucide/svelte/icons/history';
	import FlaskConical from '@lucide/svelte/icons/flask-conical';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		open = $bindable(false),
		onlihatRiwayat,
		onpengujian
	}: {
		open?: boolean;
		onlihatRiwayat: () => void;
		onpengujian: () => void;
	} = $props();

	function pilih(fn: () => void) {
		open = false;
		fn();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="sm:max-w-lg">
		<Dialog.Header>
			<Dialog.Title>Operasi Pengujian</Dialog.Title>
			<Dialog.Description>Pilih tindakan untuk aset ini.</Dialog.Description>
		</Dialog.Header>
		<div class="grid gap-3 sm:grid-cols-2">
			<button
				type="button"
				onclick={() => pilih(onlihatRiwayat)}
				class="sudut-taktis group flex flex-col gap-2 rounded-lg border bg-card p-4 text-left transition hover:border-gold/70 hover:bg-gold/5"
			>
				<div class="flex items-center justify-between">
					<History class="size-5 text-gold" />
					<ChevronRight class="size-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-gold" />
				</div>
				<p class="font-heading text-sm tracking-wide uppercase">Riwayat Pengujian</p>
				<p class="text-xs text-muted-foreground">Lihat hasil & laporan pengujian sebelumnya.</p>
			</button>
			<button
				type="button"
				onclick={() => pilih(onpengujian)}
				class="sudut-taktis group flex flex-col gap-2 rounded-lg border bg-card p-4 text-left transition hover:border-gold/70 hover:bg-gold/5"
			>
				<div class="flex items-center justify-between">
					<FlaskConical class="size-5 text-gold" />
					<ChevronRight class="size-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-gold" />
				</div>
				<p class="font-heading text-sm tracking-wide uppercase">Lakukan Pengujian</p>
				<p class="text-xs text-muted-foreground">Mulai operasi pengujian keamanan baru.</p>
			</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
