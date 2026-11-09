<script lang="ts">
	// Pemilih riwayat pengujian (header halaman operasi): tombol bergaya pil berisi pengujian yang
	// sedang dibuka; menu berisi seluruh pengujian aplikasi (terbaru dulu) dengan status & penanda
	// pengujian aktif. Memilih item → buka halaman operasi pengujian itu.
	import { goto } from '$app/navigation';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import { durasi } from '#lib/format.js';
	import type { Scan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import History from '@lucide/svelte/icons/history';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import Check from '@lucide/svelte/icons/check';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let { scan, riwayat }: { scan: Scan; riwayat: Scan[] } = $props();

	let buka = $state(false);
	const daftar = $derived(riwayat.length ? riwayat : [scan]);

	const STATUS: Record<Scan['status'], { label: string; kelas: string }> = {
		antre: { label: 'antre', kelas: 'bg-[#f5c451]/15 text-[#f5c451]' },
		berjalan: { label: 'berjalan', kelas: 'bg-[#7fe9d8]/15 text-[#7fe9d8]' },
		selesai: { label: 'selesai', kelas: 'bg-[#4ade80]/15 text-[#4ade80]' },
		dibatalkan: { label: 'dihentikan', kelas: 'bg-[#ff7b6b]/15 text-[#ff7b6b]' }
	};
	const waktu = (iso: string) =>
		new Date(iso).toLocaleString('id-ID', {
			day: 'numeric',
			month: 'short',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	const pendekatan = (s: Scan) => (s.pendekatan === 'blackbox' ? 'Black Box' : 'Grey Box');
</script>

<DropdownMenu.Root bind:open={buka}>
	<DropdownMenu.Trigger
		class={cn(
			'group inline-flex h-10 max-w-full items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.03] pr-3 pl-3.5 text-[13.5px] text-white/90 transition outline-none hover:border-white/20 hover:bg-white/[0.06] focus-visible:border-[#4ade80]/60',
			buka && 'border-[#4ade80]/50 bg-white/[0.06]'
		)}
		aria-label="Riwayat pengujian"
	>
		<History class="size-4 shrink-0 text-white/60" />
		<span class="truncate">
			<span class="font-semibold">#{scan.id}</span>
			<span class="mx-1.5 text-white/40">·</span>{waktu(scan.dimulai_pada)}
			<span class="mx-1.5 text-white/40">·</span><span class="text-white/70"
				>{STATUS[scan.status].label}</span
			>
		</span>
		<ChevronDown
			class={cn('size-4 shrink-0 text-white/60 transition-transform', buka && 'rotate-180')}
		/>
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		align="end"
		sideOffset={6}
		class="dark w-[min(24rem,calc(100vw-2rem))] rounded-xl border border-white/10 bg-[#111714] p-1.5 text-white shadow-[0_20px_50px_rgb(0_0_0/0.55)] ring-0"
	>
		<p class="px-2.5 pt-1.5 pb-2 text-[11px] font-medium tracking-wider text-white/45 uppercase">
			Riwayat pengujian · {daftar.length}
		</p>
		<div class="max-h-80 overflow-y-auto">
			{#each daftar as r (r.id)}
				{@const kini = r.id === scan.id}
				<DropdownMenu.Item
					onSelect={() => !kini && goto(`/scan/${r.id}`)}
					class={cn(
						'flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 outline-none data-highlighted:bg-white/[0.06]',
						kini && 'bg-[#4ade80]/[0.08]'
					)}
				>
					<span class="grid size-5 shrink-0 place-items-center">
						{#if kini}
							<Check class="size-4 text-[#4ade80]" />
						{:else if r.status === 'berjalan'}
							<LoaderCircle class="size-3.5 animate-spin text-[#7fe9d8]" />
						{:else}
							<span class="size-1.5 rounded-full bg-white/25"></span>
						{/if}
					</span>
					<span class="min-w-0 flex-1">
						<span class="block truncate text-[13px] text-white/90">
							<span class="font-semibold">#{r.id}</span> · {waktu(r.dimulai_pada)}
						</span>
						<span class="block truncate text-[11.5px] text-white/45">
							{pendekatan(r)} · {r.mode === 'eksploratif' ? 'eksploratif' : 'terarah'} · {durasi(
								r.dimulai_pada,
								r.selesai_pada
							)}
						</span>
					</span>
					<span
						class={cn(
							'shrink-0 rounded-md px-1.5 py-0.5 text-[10.5px] font-medium',
							STATUS[r.status].kelas
						)}
					>
						{STATUS[r.status].label}
					</span>
				</DropdownMenu.Item>
			{/each}
		</div>
	</DropdownMenu.Content>
</DropdownMenu.Root>
