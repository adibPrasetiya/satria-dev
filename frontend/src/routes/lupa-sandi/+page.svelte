<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { galatEmail as cekEmail } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import AuthShell from '#lib/components/AuthShell.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import Mail from '@lucide/svelte/icons/mail';
	import MailCheck from '@lucide/svelte/icons/mail-check';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';

	let email = $state('');
	let disentuh = $state(false);
	let memuat = $state(false);
	let terkirim = $state(false);
	let refEmail = $state<HTMLInputElement | null>(null);

	const galat = $derived(cekEmail(email));

	$effect(() => {
		if (refEmail && matchMedia('(pointer: fine)').matches) refEmail.focus();
	});

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		if (galat) {
			disentuh = true;
			refEmail?.focus();
			return;
		}
		memuat = true;
		try {
			await api.lupaSandi(email.trim());
			terkirim = true;
		} finally {
			memuat = false;
		}
	}
</script>

<svelte:head><title>Lupa kata sandi — SATYA</title></svelte:head>

{#if terkirim}
	<AuthShell judul="Periksa email Anda" keterangan="Ikuti tautan di email untuk membuat kata sandi baru.">
		<div class="flex flex-col items-center gap-4 rounded-md border border-success/30 bg-success/10 p-5 text-center">
			<MailCheck class="size-8 text-[#9fe08a]" />
			<p class="text-sm text-white/75">
				Jika <b class="text-white">{email}</b> terdaftar, tautan atur ulang telah dikirim. Tautan hanya berlaku
				30 menit dan sekali pakai.
			</p>
		</div>
		<Button href="/login" class="mt-6 h-11 w-full bg-gold font-heading tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
			<ArrowLeft /> Kembali ke halaman masuk
		</Button>
		<p class="mt-4 text-center text-sm text-white/60">
			Tidak menerima email?
			<button type="button" class="font-medium text-gold hover:underline" onclick={() => (terkirim = false)}>Kirim ulang</button>
		</p>
	</AuthShell>
{:else}
	<AuthShell judul="Lupa kata sandi" keterangan="Masukkan email dinas Anda. Kami kirimkan tautan untuk mengatur ulang kata sandi.">
		<form class="grid gap-3" onsubmit={kirim} novalidate>
			<FieldAuth
				id="email"
				label="Email dinas"
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
			/>
			<Button type="submit" aria-disabled={memuat} class="mt-1 h-11 bg-gold font-heading text-[15px] tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
				{#if memuat}<LoaderCircle class="animate-spin" /> Mengirim…{:else}Kirim tautan{/if}
			</Button>
		</form>

		<p class="mt-6 text-center text-sm text-white/60">
			<a href="/login" class="inline-flex items-center gap-1 font-medium text-gold hover:underline">
				<ArrowLeft class="size-3.5" /> Kembali ke halaman masuk
			</a>
		</p>
	</AuthShell>
{/if}
