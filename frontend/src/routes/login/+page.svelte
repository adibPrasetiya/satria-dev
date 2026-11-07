<script lang="ts">
	import { goto, preloadCode } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { galatEmail as cekEmail } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import AuthShell from '#lib/components/AuthShell.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import TombolLihatSandi from '#lib/components/TombolLihatSandi.svelte';
	import { cn } from '#lib/utils.js';
	import Mail from '@lucide/svelte/icons/mail';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Check from '@lucide/svelte/icons/check';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let email = $state('');
	let password = $state('');
	let lihatSandi = $state(false);
	let capsLock = $state(false);
	let tahap = $state<'diam' | 'memuat' | 'berhasil'>('diam');
	let galatServer = $state<string | null>(null);
	let goyang = $state(false);
	let disentuh = $state({ email: false, password: false });

	let refEmail = $state<HTMLInputElement | null>(null);
	let refSandi = $state<HTMLInputElement | null>(null);

	const galatEmail = $derived(cekEmail(email));
	const galatSandi = $derived(!password ? 'Kata sandi wajib diisi.' : null);
	const siap = $derived(!galatEmail && !galatSandi);
	const reduksiGerak = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

	// Fokus otomatis ke email hanya di perangkat berpenunjuk (tidak memunculkan keyboard ponsel).
	$effect(() => {
		if (refEmail && matchMedia('(pointer: fine)').matches) refEmail.focus();
	});

	function cekCaps(e: KeyboardEvent) {
		capsLock = e.getModifierState?.('CapsLock') ?? false;
	}

	function enterEmail(e: KeyboardEvent) {
		if (e.key === 'Enter' && !galatEmail && !password) {
			e.preventDefault();
			disentuh.email = true;
			refSandi?.focus();
		}
	}

	async function masuk(e: SubmitEvent) {
		e.preventDefault();
		if (tahap !== 'diam') return;
		galatServer = null;
		if (!siap) {
			disentuh = { email: true, password: true };
			(galatEmail ? refEmail : refSandi)?.focus();
			return;
		}
		tahap = 'memuat';
		// Kode dasbor dimuat bersamaan dengan verifikasi kata sandi, bukan setelahnya.
		preloadCode('/dashboard').catch(() => {});
		try {
			const pengguna = await api.login(email.trim(), password);
			tahap = 'berhasil';
			// Tampilkan status "Akses diberikan" sebentar sebelum berpindah halaman.
			if (!reduksiGerak()) await new Promise((r) => setTimeout(r, 350));
			auth.masuk(pengguna);
			goto('/dashboard');
		} catch (err) {
			tahap = 'diam';
			galatServer = (err as Error).message;
			password = '';
			disentuh.password = false;
			refSandi?.focus();
			if (!reduksiGerak()) {
				goyang = true;
				setTimeout(() => (goyang = false), 350);
			}
		}
	}
</script>

<svelte:head><title>Masuk — SATRIA</title></svelte:head>

<AuthShell judul="Masuk" {goyang}>
	<form class="grid gap-4" onsubmit={masuk} novalidate>
		<FieldAuth
			id="email"
			label="Email dinas"
			ikon={Mail}
			type="email"
			inputmode="email"
			autocomplete="username"
			spellcheck={false}
			placeholder="nama@satuan.mil.id"
			bind:value={email}
			bind:ref={refEmail}
			galat={disentuh.email ? galatEmail : null}
			onblur={() => (disentuh.email ||= !!email)}
			oninput={() => (galatServer = null)}
			onkeydown={enterEmail}
		>
			{#snippet kanan()}
				{#if !galatEmail}
					<Check class="absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-[#9fe08a]" aria-hidden="true" />
				{/if}
			{/snippet}
		</FieldAuth>

		<FieldAuth
			id="password"
			label="Kata sandi"
			ikon={KeyRound}
			type={lihatSandi ? 'text' : 'password'}
			autocomplete="current-password"
			placeholder="••••••••"
			bind:value={password}
			bind:ref={refSandi}
			galat={disentuh.password ? galatSandi : null}
			onblur={() => (disentuh.password ||= !!password)}
			oninput={() => (galatServer = null)}
			onkeydown={cekCaps}
			onkeyup={cekCaps}
		>
			{#snippet aksiLabel()}
				<a href="/lupa-sandi" class="text-xs font-medium text-gold hover:underline">Lupa kata sandi?</a>
			{/snippet}
			{#snippet kanan()}
				<TombolLihatSandi bind:lihat={lihatSandi} />
			{/snippet}
			{#snippet bawah()}
				{#if capsLock}
					<p class="flex items-center gap-1.5 rounded-sm bg-gold/15 px-1.5 py-0.5 text-gold">
						<TriangleAlert class="size-3.5" />Caps Lock aktif
					</p>
				{/if}
			{/snippet}
		</FieldAuth>

		{#if galatServer}
			<p
				class="flex items-center gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200"
				role="alert"
			>
				<CircleAlert class="size-4 shrink-0" />{galatServer}
			</p>
		{/if}

		<Button
			type="submit"
			aria-disabled={tahap !== 'diam'}
			class={cn(
				'group/masuk mt-2 h-10 font-heading text-[15px] tracking-[0.12em] uppercase transition-all',
				tahap === 'berhasil'
					? 'bg-success text-white hover:bg-success'
					: siap
						? 'bg-gold text-gold-foreground shadow-[0_0_24px_rgb(150_175_95/0.28)] hover:bg-gold/90'
						: 'bg-gold/55 text-gold-foreground/80 hover:bg-gold/65'
			)}
		>
			{#if tahap === 'memuat'}
				<LoaderCircle class="animate-spin" /> Memverifikasi…
			{:else if tahap === 'berhasil'}
				<Check /> Akses diberikan
			{:else}
				Masuk <ArrowRight class="transition-transform group-hover/masuk:translate-x-0.5" />
			{/if}
		</Button>
	</form>

	<p class="mt-5 text-center text-sm text-white/60">
		Belum punya akun? <a href="/daftar" class="font-medium text-gold hover:underline">Daftar</a>
	</p>
</AuthShell>
