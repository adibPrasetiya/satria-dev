<script lang="ts">
	// Profil akun yang sedang masuk (tampilan saja; data dari sesi login).
	import { auth, inisialNama, LABEL_PERAN } from '#lib/stores/auth.svelte.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import DialogGantiSandi from '#lib/components/DialogGantiSandi.svelte';
	import IdCard from '@lucide/svelte/icons/id-card';
	import Mail from '@lucide/svelte/icons/mail';
	import Building from '@lucide/svelte/icons/building-2';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import BadgeCheck from '@lucide/svelte/icons/badge-check';
	import KeyRound from '@lucide/svelte/icons/key-round';

	const p = $derived(auth.pengguna);
	let gantiSandi = $state(false);

	const data = $derived(
		p
			? [
					{ label: 'NRP / NIP', nilai: p.nrp ?? '—', ikon: IdCard },
					{ label: 'Email dinas', nilai: p.email, ikon: Mail },
					{ label: 'Satuan / instansi', nilai: p.satuan, ikon: Building },
					{ label: 'Peran', nilai: LABEL_PERAN[p.peran], ikon: ShieldCheck },
					{ label: 'Status akun', nilai: p.aktif ? 'Aktif · terverifikasi' : 'Nonaktif', ikon: BadgeCheck }
				]
			: []
	);
</script>

<svelte:head><title>Profil — SATRIA</title></svelte:head>

<PageHeader label="Akun" judul="Profil" />

{#if p}
	<div class="sudut-taktis max-w-3xl overflow-hidden rounded-lg border bg-card">
		<!-- Pita identitas berlatar loreng. -->
		<div class="bg-loreng flex flex-col gap-4 border-b-2 border-gold/70 px-6 py-6 text-white sm:flex-row sm:items-center">
			<span
				class="grid size-20 shrink-0 place-items-center rounded-sm border-2 border-gold/80 bg-black/45 font-heading text-2xl font-semibold tracking-wider text-gold shadow-[0_8px_24px_rgb(0_0_0/0.4)]"
			>
				{inisialNama(p.nama)}
			</span>
			<div class="min-w-0 flex-1">
				<p class="text-xl font-semibold break-words">{p.nama}</p>
				<p class="mt-1 font-heading text-[11px] tracking-[0.2em] text-gold uppercase">{LABEL_PERAN[p.peran]}</p>
				<p class="mt-1 truncate text-sm text-white/70">{p.satuan}</p>
			</div>
			<Button
				variant="outline"
				class="border-gold/50 bg-black/30 text-white hover:bg-black/50 hover:text-white"
				onclick={() => (gantiSandi = true)}
			>
				<KeyRound /> Ganti Password
			</Button>
		</div>

		<dl class="grid divide-y sm:grid-cols-2 sm:divide-y-0">
			{#each data as d (d.label)}
				<div class="flex items-start gap-3 px-6 py-4 sm:border-b sm:odd:border-r">
					<d.ikon class="mt-0.5 size-4 shrink-0 text-gold" />
					<div class="min-w-0">
						<dt class="label-stensil text-[10px]">{d.label}</dt>
						<dd class="mt-0.5 text-sm break-words">{d.nilai}</dd>
					</div>
				</div>
			{/each}
		</dl>
	</div>
{/if}

<DialogGantiSandi bind:open={gantiSandi} />
