<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { galatEmail as cekEmail } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import LayarAuthPenuh from '#lib/components/LayarAuthPenuh.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import Mail from '@lucide/svelte/icons/mail';
	import MailCheck from '@lucide/svelte/icons/mail-check';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	let email = $state('');
	let disentuh = $state(false);
	let memuat = $state(false);
	let terkirim = $state(false);
	let goyang = $state(false);
	let galatServer = $state<string | null>(null);
	let refEmail = $state<HTMLInputElement | null>(null);

	const galat = $derived(cekEmail(email));

	$effect(() => {
		if (refEmail && matchMedia('(pointer: fine)').matches) refEmail.focus();
	});

	function getar() {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		goyang = true;
		setTimeout(() => (goyang = false), 350);
	}

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		if (memuat) return;
		galatServer = null;
		if (galat) {
			disentuh = true;
			refEmail?.focus();
			getar();
			return;
		}
		memuat = true;
		try {
			// Respons selalu sama, terdaftar atau tidak (cegah enumerasi akun).
			await api.lupaSandi(email.trim());
			terkirim = true;
		} catch (err) {
			galatServer = (err as Error).message;
			getar();
		} finally {
			memuat = false;
		}
	}
</script>

<svelte:head><title>Lupa kata sandi — SATRIA</title></svelte:head>

{#if terkirim}
	<LayarAuthPenuh label="Tautan atur ulang terkirim">
		<div class="flex flex-col items-center gap-4 text-center">
			<span class="grid size-16 place-items-center rounded-full border border-gold/40 bg-gold/10">
				<MailCheck class="size-8 text-gold" />
			</span>
			<div>
				<h1 class="font-heading text-2xl font-semibold">Periksa Email Anda</h1>
				<p class="mx-auto mt-2 max-w-md text-sm text-white/65">
					Jika <b class="text-white">{email.trim()}</b> terdaftar, tautan atur ulang kata sandi telah
					dikirim. Tautan hanya berlaku 30 menit dan sekali pakai.
				</p>
			</div>
		</div>
		<div class="mt-8 flex justify-center">
			<Button
				href="/login"
				class="h-11 bg-gold px-6 font-medium text-gold-foreground hover:bg-gold/90"
			>
				<ArrowLeft /> Kembali ke halaman masuk
			</Button>
		</div>
		<p class="mt-5 text-center text-sm text-white/55">
			Tidak menerima email?
			<button
				type="button"
				class="font-medium text-gold hover:underline"
				onclick={() => (terkirim = false)}
			>
				Kirim ulang
			</button>
		</p>
	</LayarAuthPenuh>
{:else}
	<LayarAuthPenuh label="Lupa kata sandi" {goyang}>
		<form class="grid gap-5" onsubmit={kirim} novalidate>
			<!-- Kepala: ikon + judul + keterangan (selaras dengan langkah pendaftaran). -->
			<div class="flex items-center gap-4">
				<span class="grid size-12 shrink-0 place-items-center rounded-full bg-gold/12 text-gold">
					<KeyRound class="size-6" />
				</span>
				<div class="min-w-0">
					<h1 class="font-heading text-[1.6rem] leading-tight font-semibold tracking-normal">
						Lupa Kata Sandi
					</h1>
					<p class="mt-0.5 text-sm text-white/55">
						Masukkan email dinas Anda, kami kirimkan tautan untuk membuat kata sandi baru
					</p>
				</div>
			</div>

			<FieldAuth
				id="email"
				label="Email Dinas"
				ikon={Mail}
				type="email"
				inputmode="email"
				autocomplete="email"
				spellcheck={false}
				placeholder="nama@satuan.mil.id"
				bind:value={email}
				bind:ref={refEmail}
				galat={disentuh ? galat : null}
				onblur={() => (disentuh ||= !!email)}
				oninput={() => (galatServer = null)}
			/>

			{#if galatServer}
				<p
					class="flex items-center gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200"
					role="alert"
				>
					<CircleAlert class="size-4 shrink-0" />{galatServer}
				</p>
			{/if}

			<div class="mt-3 flex items-center justify-between gap-4">
				<a
					href="/login"
					class="group/mundur flex w-fit items-center gap-2 text-sm text-white/60 transition-colors hover:text-white"
				>
					<ArrowLeft class="size-4 transition-transform group-hover/mundur:-translate-x-0.5" /> Kembali
				</a>
				<Button
					type="submit"
					aria-disabled={memuat}
					class="group/lanjut h-11 min-w-[150px] border border-gold/40 bg-gold px-6 text-[15px] font-medium text-gold-foreground hover:bg-gold/90"
				>
					{#if memuat}<LoaderCircle class="animate-spin" /> Mengirim…
					{:else}Kirim Tautan
						<ArrowRight class="transition-transform group-hover/lanjut:translate-x-0.5" />{/if}
				</Button>
			</div>
		</form>
	</LayarAuthPenuh>
{/if}
