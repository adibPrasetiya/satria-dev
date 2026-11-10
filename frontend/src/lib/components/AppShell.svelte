<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { page } from '$app/state';
	import { preloadCode } from '$app/navigation';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { USE_MOCK } from '#lib/api/client.js';
	import type { Peran } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { cn } from '#lib/utils.js';
	import LogoSatria from './LogoSatria.svelte';
	import MenuAkun from './MenuAkun.svelte';
	import IndikatorWorker from './IndikatorWorker.svelte';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import AppWindow from '@lucide/svelte/icons/app-window';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import Users from '@lucide/svelte/icons/users';
	import Building from '@lucide/svelte/icons/building-2';
	import Menu from '@lucide/svelte/icons/menu';
	import X from '@lucide/svelte/icons/x';
	import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
	import PanelLeftOpen from '@lucide/svelte/icons/panel-left-open';

	let { children }: { children: Snippet } = $props();

	// Halaman operasi scan memakai kanvas penuh (seluruh area selain header & sidebar) di lg+.
	const layarPenuh = $derived(page.route.id === '/scan/[scanId]');
	// Dasbor diawali peta selebar area konten (tanpa padding/batas lebar); halaman mengatur wadahnya sendiri.
	const tanpaBingkai = $derived(page.route.id === '/dashboard');
	// Halaman daftar bertabel memakai seluruh lebar area konten (tanpa batas max-w).
	const lebarPenuh = $derived(page.route.id === '/aplikasi' || page.route.id === '/admin/pengguna');

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
				// Registrasi aplikasi dibuka dari tombol di halaman Aplikasi (bukan menu sidebar).
				{ href: '/aplikasi', label: 'Aplikasi', ikon: AppWindow, peran: SEMUA },
				{ href: '/katalog', label: 'Katalog Kontrol', ikon: BookOpen, peran: SEMUA }
			]
		},
		{
			grup: 'Administrasi',
			item: [
				{ href: '/admin/pengguna', label: 'Pengguna', ikon: Users, peran: ['admin'] },
				{ href: '/admin/satuan', label: 'Satuan Kerja', ikon: Building, peran: ['admin'] }
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

<div class="flex min-h-svh bg-background">
	<aside
		class={cn(
			'no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-card text-foreground transition-[transform,width] duration-200 lg:translate-x-0',
			terbuka ? 'translate-x-0 shadow-2xl' : '-translate-x-full',
			ciut && 'lg:w-[72px]'
		)}
	>
		<!-- Identitas -->
		<div
			class={cn('flex h-16 shrink-0 items-center gap-3 px-5', ciut && 'lg:justify-center lg:px-0')}
		>
			<a href="/dashboard" aria-label="SATRIA — dasbor" class="flex items-center">
				<LogoSatria tema="ikut" class={cn('[--logo-h:2.25rem]', ciut && 'lg:hidden')} />
				{#if ciut}
					<img
						src="/satria-lambang.png"
						alt=""
						width="94"
						height="138"
						class="hidden h-9 w-auto lg:block"
					/>
				{/if}
			</a>
			<Button
				variant="ghost"
				size="icon-sm"
				class="ml-auto text-muted-foreground lg:hidden"
				onclick={() => (terbuka = false)}
				aria-label="Tutup menu"
			>
				<X />
			</Button>
		</div>

		<nav aria-label="Menu utama" class="flex-1 overflow-x-hidden overflow-y-auto px-3 py-4">
			{#each nav as g, gi (g.grup)}
				<div class={cn(gi > 0 && 'mt-6')}>
					<p
						class={cn(
							'mb-1.5 px-3 text-[11px] font-semibold tracking-[0.06em] text-muted-foreground uppercase',
							ciut && 'lg:sr-only'
						)}
					>
						{g.grup}
					</p>
					{#if ciut && gi > 0}
						<div class="mx-auto mb-2 hidden h-px w-6 bg-border lg:block" aria-hidden="true"></div>
					{/if}
					<ul class="grid gap-0.5">
						{#each g.item as i (i.href)}
							{@const sini = aktif(i.href)}
							<li>
								<a
									href={i.href}
									title={ciut ? i.label : undefined}
									aria-current={sini ? 'page' : undefined}
									class={cn(
										'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
										sini
											? 'bg-gold/12 font-semibold text-foreground'
											: 'font-medium text-muted-foreground hover:bg-muted hover:text-foreground',
										ciut && 'lg:justify-center lg:px-0'
									)}
								>
									<i.ikon
										class={cn(
											'size-[18px] shrink-0',
											sini ? 'text-gold' : 'text-muted-foreground group-hover:text-foreground'
										)}
									/>
									<span class={cn('truncate', ciut && 'lg:sr-only')}>{i.label}</span>
								</a>
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		</nav>

		<!-- Status worker pengujian di kaki sidebar. -->
		<div class={cn('shrink-0 border-t border-border p-3', ciut && 'lg:px-2')}>
			<IndikatorWorker {ciut} />
		</div>
	</aside>

	{#if terbuka}
		<button
			class="fixed inset-0 z-30 bg-black/50 lg:hidden"
			aria-label="Tutup menu"
			onclick={() => (terbuka = false)}
		></button>
	{/if}

	<div
		class={cn(
			'flex min-w-0 flex-1 flex-col transition-[padding] duration-200',
			ciut ? 'lg:pl-[72px]' : 'lg:pl-64',
			layarPenuh && 'lg:h-svh'
		)}
	>
		<!-- Bilah atas -->
		<header
			class="no-print sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-border bg-background/85 px-4 backdrop-blur sm:px-6 lg:px-8"
		>
			<Button
				variant="ghost"
				size="icon-sm"
				class="hidden text-muted-foreground lg:inline-flex"
				onclick={alihCiut}
				aria-label={ciut ? 'Lebarkan menu' : 'Ciutkan menu'}
				title={ciut ? 'Lebarkan menu' : 'Ciutkan menu'}
			>
				{#if ciut}<PanelLeftOpen />{:else}<PanelLeftClose />{/if}
			</Button>
			<Button
				variant="ghost"
				size="icon-sm"
				class="text-muted-foreground lg:hidden"
				onclick={() => (terbuka = true)}
				aria-label="Buka menu"
			>
				<Menu />
			</Button>
			<a href="/dashboard" class="lg:hidden" aria-label="SATRIA — dasbor">
				<LogoSatria tema="ikut" class="[--logo-h:1.75rem]" />
			</a>
			<div class="ml-auto flex items-center gap-2">
				<MenuAkun />
			</div>
		</header>
		{#if USE_MOCK}
			<div
				class="no-print border-b border-warning/30 bg-warning/10 px-4 py-1.5 text-center text-xs font-medium text-warning-foreground"
			>
				Mode latihan — data tiruan disimpan di browser, belum terhubung ke backend
			</div>
		{/if}
		<main
			class={cn(
				'w-full flex-1',
				layarPenuh
					? 'relative min-h-0 px-4 py-4 lg:overflow-hidden lg:p-0'
					: tanpaBingkai
						? ''
						: lebarPenuh
							? 'px-4 py-6 sm:px-6 lg:px-8'
							: 'mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8'
			)}
		>
			{@render children()}
		</main>
		<footer
			class={cn(
				'no-print border-t border-border px-4 py-4 text-center text-xs text-muted-foreground',
				layarPenuh && 'lg:hidden',
				// Dasbor = peta satu layar; footer di bawahnya hanya menambah gulir.
				tanpaBingkai && 'hidden'
			)}
		>
			SATRIA · Hasil asesmen bersifat terbatas, untuk kalangan sendiri
		</footer>
	</div>
</div>
