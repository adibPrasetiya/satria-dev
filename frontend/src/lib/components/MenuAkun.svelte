<script lang="ts">
	// Tombol akun di kanan atas header + dropdown (Profil, Ganti Password, Keluar) bergaya loreng.
	import { goto } from '$app/navigation';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import { auth, inisialNama, LABEL_PERAN } from '#lib/stores/auth.svelte.js';
	import { USE_MOCK } from '#lib/api/client.js';
	import { resetMock } from '#lib/api/mock/index.js';
	import DialogGantiSandi from './DialogGantiSandi.svelte';
	import { cn } from '#lib/utils.js';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import UserRound from '@lucide/svelte/icons/user-round';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import LogOut from '@lucide/svelte/icons/log-out';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';

	let buka = $state(false);
	let gantiSandi = $state(false);

	const p = $derived(auth.pengguna);
	const inisial = $derived(inisialNama(p?.nama));

	function keluar() {
		auth.keluar();
		goto('/login');
	}

	function resetDemo() {
		resetMock();
		location.reload();
	}

	// Gaya item: garis emas di kiri saat disorot, seperti menu sidebar.
	const ITEM =
		'relative gap-3 rounded-sm px-3 py-2.5 font-heading text-[13px] tracking-[0.06em] text-white/85 uppercase focus:bg-white/8 focus:text-white before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-r before:bg-gold before:opacity-0 focus:before:opacity-100 [&_svg]:text-gold/80';
</script>

<DropdownMenu.Root bind:open={buka}>
	<DropdownMenu.Trigger
		class={cn(
			'group flex items-center gap-2.5 rounded-sm p-1 pr-2 transition-colors hover:bg-black/30 focus-visible:ring-2 focus-visible:ring-gold/60 focus-visible:outline-none',
			buka && 'bg-black/30'
		)}
		aria-label="Akun"
	>
		<span
			class={cn(
				'grid size-10 shrink-0 place-items-center rounded-sm border bg-black/45 font-heading text-sm font-semibold tracking-wider text-gold shadow-[inset_0_0_0_1px_rgb(0_0_0/0.4)] transition-colors',
				buka ? 'border-gold' : 'border-gold/55 group-hover:border-gold'
			)}
		>
			{inisial}
		</span>
		<span class="hidden min-w-0 text-left leading-tight md:block">
			<span class="block max-w-44 truncate text-sm font-medium text-white">{p?.nama}</span>
			<span class="block font-heading text-[10px] tracking-[0.18em] text-gold/90 uppercase">
				{p && LABEL_PERAN[p.peran]}
			</span>
		</span>
		<ChevronDown class={cn('size-4 text-white/60 transition-transform', buka && 'rotate-180')} />
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		align="end"
		sideOffset={10}
		class="w-72 overflow-hidden rounded-none border-gold/35 bg-[#10150e] p-0 text-white shadow-[0_24px_60px_rgb(0_0_0/0.6)]"
	>
		<!-- Kepala: identitas di atas latar loreng. -->
		<div class="bg-loreng sudut-taktis flex items-center gap-3 border-b border-gold/30 px-4 py-4">
			<span class="grid size-12 shrink-0 place-items-center rounded-sm border border-gold/70 bg-black/45 font-heading text-base font-semibold tracking-wider text-gold">
				{inisial}
			</span>
			<div class="min-w-0 leading-tight">
				<p class="truncate font-medium text-white">{p?.nama}</p>
				<p class="mt-0.5 font-heading text-[10px] tracking-[0.18em] text-gold uppercase">{p && LABEL_PERAN[p.peran]}</p>
				<p class="mt-1 truncate text-xs text-white/65">{p?.email}</p>
				<p class="truncate text-xs text-white/50">{p?.satuan}</p>
			</div>
		</div>

		<div class="grid gap-0.5 p-1.5">
			<DropdownMenu.Item class={ITEM} onSelect={() => goto('/akun/profil')}>
				<UserRound /> Profil
			</DropdownMenu.Item>
			<DropdownMenu.Item class={ITEM} onSelect={() => (gantiSandi = true)}>
				<KeyRound /> Ganti Password
			</DropdownMenu.Item>
			{#if USE_MOCK}
				<DropdownMenu.Item class={ITEM} onSelect={resetDemo}>
					<RotateCcw /> Reset data demo
				</DropdownMenu.Item>
			{/if}
			<DropdownMenu.Separator class="mx-1.5 my-1 bg-white/10" />
			<DropdownMenu.Item
				class={cn(ITEM, 'text-red-300 before:bg-red-400 focus:bg-red-500/10 focus:text-red-200 [&_svg]:text-red-300')}
				onSelect={keluar}
			>
				<LogOut /> Keluar
			</DropdownMenu.Item>
		</div>
	</DropdownMenu.Content>
</DropdownMenu.Root>

<DialogGantiSandi bind:open={gantiSandi} />
