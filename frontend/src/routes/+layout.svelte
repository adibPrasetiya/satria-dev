<script lang="ts">
	import './layout.css';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from '#lib/components/ui/sonner/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
	import AppShell from '#lib/components/AppShell.svelte';
	import PanggungAuth from '#lib/components/PanggungAuth.svelte';
	import { auth, PERAN_PENDAFTAR, PERAN_PENGUJI } from '#lib/stores/auth.svelte.js';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import type { Peran } from '#lib/types.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// Batas akses per pola route (backend tetap menegakkan hal yang sama lewat requireRole).
	const AKSES: [RegExp, Peran[]][] = [
		[/^\/admin(\/|$)/, ['admin']],
		// Mendaftarkan & mengubah aplikasi: pemilik/admin.
		[/^\/aplikasi\/baru(\/|$)/, PERAN_PENDAFTAR],
		[/^\/aplikasi\/[^/]+\/ubah(\/|$)/, PERAN_PENDAFTAR],
		// Menyiapkan & menjalankan pengujian: asesor/admin.
		[/^\/aplikasi\/[^/]+\/(pengujian|persiapan)(\/|$)/, PERAN_PENGUJI]
	];

	// Halaman publik (tanpa sesi): login, pendaftaran akun, dan lupa kata sandi.
	const PUBLIK = ['/login', '/daftar', '/lupa-sandi', '/reset-sandi'];
	const diLogin = $derived(PUBLIK.some((p) => page.url.pathname.startsWith(p)));
	const diizinkan = $derived(
		AKSES.every(([pola, peran]) => !pola.test(page.url.pathname) || auth.punya(...peran))
	);

	$effect(() => {
		if (!auth.pengguna && !diLogin) goto('/login');
		else if (auth.pengguna && diLogin) goto('/dashboard');
	});
</script>

<svelte:head>
	<!-- Ikon dari lambang SATRIA (dibangun: node scripts/build-favicon.mjs). -->
	<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
	<link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png" />
	<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
	<title>SATRIA — Asesmen Kelaikan Keamanan Aplikasi</title>
</svelte:head>

<ModeWatcher />
<Toaster position="top-right" duration={4000} />

<Tooltip.Provider>
	{#if diLogin}
		<PanggungAuth>{@render children()}</PanggungAuth>
	{:else if auth.pengguna}
		<AppShell>
			{#if diizinkan}
				{@render children()}
			{:else}
				<div class="rounded-xl border border-dashed p-10 text-center">
					<p class="font-medium">Akses ditolak</p>
					<p class="mt-1 text-sm text-muted-foreground">
						Peran Anda tidak memiliki akses ke halaman ini.
					</p>
				</div>
			{/if}
		</AppShell>
	{/if}
</Tooltip.Provider>
