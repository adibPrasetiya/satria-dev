<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { page } from '$app/state';
	import { preloadCode } from '$app/navigation';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { USE_MOCK } from '#lib/api/client.js';
	import type { Peran } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { cn } from '#lib/utils.js';
	import Lambang from './Lambang.svelte';
	import MenuAkun from './MenuAkun.svelte';
	import IndikatorWorker from './IndikatorWorker.svelte';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import AppWindow from '@lucide/svelte/icons/app-window';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import Users from '@lucide/svelte/icons/users';
	import Building from '@lucide/svelte/icons/building-2';
	import Bot from '@lucide/svelte/icons/bot';
	import Menu from '@lucide/svelte/icons/menu';
	import X from '@lucide/svelte/icons/x';
	import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
	import PanelLeftOpen from '@lucide/svelte/icons/panel-left-open';

	let { children }: { children: Snippet } = $props();

	// Halaman operasi scan memakai kanvas penuh (seluruh area selain header & sidebar) di lg+.
	const layarPenuh = $derived(page.route.id === '/scan/[scanId]');

	interface ItemNav {
		href: Parameters<typeof preloadCode>[0];
		label: string;
		ikon: Component;
		peran: Peran[];
	}

	const SEMUA: Peran[] = ['pemilik', 'asesor', 'admin'];
	const NAV: { grup: string; item: ItemNav[] }[] = [
		{
			grup: 'Umum',
			item: [
				{ href: '/dashboard', label: 'Dasbor', ikon: LayoutDashboard, peran: SEMUA },
				{ href: '/aplikasi', label: 'Aplikasi', ikon: AppWindow, peran: SEMUA },
				{ href: '/aplikasi/baru', label: 'Registrasi Aplikasi', ikon: CirclePlus, peran: ['pemilik', 'admin'] },
				{ href: '/katalog', label: 'Katalog Kontrol', ikon: BookOpen, peran: SEMUA }
			]
		},
		{
			grup: 'Asesmen',
			item: [
				{ href: '/asesor/antrian', label: 'Antrian Tinjauan', ikon: ClipboardCheck, peran: ['asesor', 'admin'] }
			]
		},
		{
			grup: 'Administrasi',
			item: [
				{ href: '/admin/pengguna', label: 'Pengguna', ikon: Users, peran: ['admin'] },
				{ href: '/admin/satuan', label: 'Satuan Kerja', ikon: Building, peran: ['admin'] },
				{ href: '/admin/ai', label: 'Pengaturan AI', ikon: Bot, peran: ['admin'] }
			]
		}
	];

	const nav = $derived(
		NAV.map((g) => ({ ...g, item: g.item.filter((i) => auth.punya(...i.peran)) })).filter(
			(g) => g.item.length
		)
	);

	// Muat kode semua menu yang boleh diakses saat browser senggang, agar pindah halaman tidak menunggu
	// unduh modul. Berjalan sekali per daftar menu (berubah hanya bila peran berubah).
	$effect(() => {
		const href = nav.flatMap((g) => g.item.map((i) => i.href));
		const muat = () => href.forEach((h) => preloadCode(h).catch(() => {}));
		if ('requestIdleCallback' in window) {
			const id = requestIdleCallback(muat, { timeout: 2000 });
			return () => cancelIdleCallback(id);
		}
		const id = setTimeout(muat, 300);
		return () => clearTimeout(id);
	});

	let terbuka = $state(false);

	// Sidebar desktop bisa diciutkan jadi deret ikon; pilihan diingat per browser.
	const KUNCI_CIUT = 'satya-sidebar-ciut';
	let ciut = $state(
		(() => {
			try {
				return localStorage.getItem(KUNCI_CIUT) === '1';
			} catch {
				return false;
			}
		})()
	);
	function alihCiut() {
		ciut = !ciut;
		try {
			localStorage.setItem(KUNCI_CIUT, ciut ? '1' : '0');
		} catch {
			// localStorage tidak tersedia; pilihan hanya berlaku di sesi ini.
		}
	}

	function aktif(href: string) {
		const p = page.url.pathname;
		if (href === '/aplikasi')
			return p === '/aplikasi' || (p.startsWith('/aplikasi/') && !p.startsWith('/aplikasi/baru'));
		return p === href || p.startsWith(href + '/');
	}

	// Tutup menu ponsel saat berpindah halaman.
	$effect(() => {
		void page.url.pathname;
		terbuka = false;
	});
</script>

<div class="flex min-h-svh">
	<aside
		class={cn(
			'bg-loreng no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col text-sidebar-foreground shadow-xl transition-[transform,width] duration-200 lg:translate-x-0',
			terbuka ? 'translate-x-0' : '-translate-x-full',
			ciut && 'lg:w-16'
		)}
	>
		<!-- Identitas -->
		<div class={cn('flex h-19 shrink-0 items-center gap-3 border-b border-sidebar-border px-4', ciut && 'lg:justify-center lg:px-0')}>
			<Lambang class="size-11 shrink-0 drop-shadow" />
			<div class={cn('min-w-0 leading-tight', ciut && 'lg:hidden')}>
				<p class="font-stencil text-2xl tracking-[0.12em] text-gold">SATYA</p>
				<p class="font-heading text-[10px] tracking-[0.18em] text-sidebar-foreground/80 uppercase">
					Kelaikan Keamanan Aplikasi
				</p>
			</div>
			<Button
				variant="ghost"
				size="icon-sm"
				class="ml-auto text-sidebar-foreground hover:bg-white/10 hover:text-white lg:hidden"
				onclick={() => (terbuka = false)}
				aria-label="Tutup menu"
			>
				<X />
			</Button>
		</div>

		<nav class={cn('flex-1 overflow-x-hidden overflow-y-auto px-3 py-2', ciut && 'lg:px-2')}>
			{#each nav as g (g.grup)}
				<p
					class={cn(
						'flex items-center gap-2 px-2 pt-4 pb-1.5 font-heading text-[10px] font-medium tracking-[0.22em] text-gold/90 uppercase',
						ciut && 'lg:justify-center lg:px-0'
					)}
				>
					<span class={cn('h-px w-3 bg-gold/70', ciut && 'lg:w-6')}></span><span class={cn(ciut && 'lg:hidden')}>{g.grup}</span>
				</p>
				{#each g.item as i (i.href)}
					<a
						href={i.href}
						title={ciut ? i.label : undefined}
						class={cn(
							'group relative flex items-center gap-2.5 rounded-sm px-3 py-2 font-heading text-[13px] tracking-[0.06em] uppercase transition-colors hover:bg-white/10',
							aktif(i.href) && 'bg-black/35 text-white',
							ciut && 'lg:justify-center lg:px-0'
						)}
					>
						{#if aktif(i.href)}
							<span class="absolute inset-y-1 left-0 w-1 rounded-r bg-gold"></span>
						{/if}
						<i.ikon
							class={cn(
								'size-4',
								aktif(i.href) ? 'text-gold' : 'text-sidebar-foreground/70 group-hover:text-white'
							)}
						/>
						<span class={cn('truncate', ciut && 'lg:sr-only')}>{i.label}</span>
					</a>
				{/each}
			{/each}
		</nav>

	</aside>

	{#if terbuka}
		<button
			class="fixed inset-0 z-30 bg-black/50 lg:hidden"
			aria-label="Tutup menu"
			onclick={() => (terbuka = false)}
		></button>
	{/if}

	<div class={cn('flex min-w-0 flex-1 flex-col transition-[padding] duration-200', ciut ? 'lg:pl-16' : 'lg:pl-64', layarPenuh && 'lg:h-svh')}>
		<!-- Bilah komando atas -->
		<header
			class="bg-loreng no-print sticky top-0 z-20 flex h-19 items-center gap-3 border-b-2 border-gold/70 px-4 text-sidebar-foreground"
		>
			<Button
				variant="ghost"
				size="icon-sm"
				class="hidden text-sidebar-foreground hover:bg-white/10 hover:text-white lg:inline-flex"
				onclick={alihCiut}
				aria-label={ciut ? 'Lebarkan menu' : 'Ciutkan menu'}
				title={ciut ? 'Lebarkan menu' : 'Ciutkan menu'}
			>
				{#if ciut}<PanelLeftOpen />{:else}<PanelLeftClose />{/if}
			</Button>
			<Button
				variant="ghost"
				size="icon-sm"
				class="text-sidebar-foreground hover:bg-white/10 hover:text-white lg:hidden"
				onclick={() => (terbuka = true)}
				aria-label="Buka menu"
			>
				<Menu />
			</Button>
			<span class="font-stencil tracking-[0.12em] text-gold lg:hidden">SATYA</span>
			<div class="ml-auto flex items-center gap-3">
				<IndikatorWorker />
				<MenuAkun />
			</div>
		</header>
		{#if USE_MOCK}
			<div
				class="no-print border-b border-warning/30 bg-warning/10 px-4 py-1 text-center font-heading text-[11px] tracking-[0.12em] text-warning-foreground uppercase"
			>
				Mode latihan — data tiruan disimpan di browser, belum terhubung ke backend
			</div>
		{/if}
		<main class={cn('w-full flex-1', layarPenuh ? 'relative min-h-0 px-4 py-4 lg:overflow-hidden lg:p-0' : 'mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8')}>
			{@render children()}
		</main>
		<footer
			class={cn('no-print border-t px-4 py-3 text-center font-heading text-[10px] tracking-[0.2em] text-muted-foreground uppercase', layarPenuh && 'lg:hidden')}
		>
			SATYA · Hasil asesmen bersifat terbatas — untuk kalangan sendiri
		</footer>
	</div>
</div>
