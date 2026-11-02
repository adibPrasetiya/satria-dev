<script lang="ts">
	import { api } from '#lib/api/client.js';
	import type { PengaturanAi, ProviderAi } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import * as Alert from '#lib/components/ui/alert/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Field from '#lib/components/Field.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Cloud from '@lucide/svelte/icons/cloud';
	import Server from '@lucide/svelte/icons/server';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import Save from '@lucide/svelte/icons/save';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let p = $state<PengaturanAi | null>(null);
	let menyimpan = $state(false);

	$effect(() => {
		api.getPengaturanAi().then((x) => (p = x));
	});

	const PROVIDER: { v: ProviderAi; l: string; d: string; lokal: boolean; endpoint: string; model: string }[] = [
		{ v: 'anthropic', l: 'Anthropic Claude', d: 'Layanan berbayar via API', lokal: false, endpoint: 'https://api.anthropic.com', model: 'claude-sonnet-5-5' },
		{ v: 'openai_compatible', l: 'API kompatibel OpenAI', d: 'Layanan berbayar lain', lokal: false, endpoint: 'https://', model: '' },
		{ v: 'ollama', l: 'Ollama', d: 'Model lokal di server internal', lokal: true, endpoint: 'http://localhost:11434', model: 'llama3.1:8b' },
		{ v: 'vllm', l: 'vLLM', d: 'Inferensi lokal GPU', lokal: true, endpoint: 'http://localhost:8000/v1', model: '' }
	];

	const aktif = $derived(PROVIDER.find((x) => x.v === p?.provider));

	function pilih(v: ProviderAi) {
		const x = PROVIDER.find((y) => y.v === v)!;
		p!.provider = v;
		p!.endpoint = x.endpoint;
		p!.model = x.model;
	}

	async function simpan() {
		menyimpan = true;
		try {
			p = await api.simpanPengaturanAi($state.snapshot(p!));
			toast.success('Pengaturan AI disimpan');
		} finally {
			menyimpan = false;
		}
	}
</script>

<PageHeader
	label="Administrasi"
	judul="Pengaturan AI"
	deskripsi="AI membantu menjelaskan temuan dan menyusun rekomendasi. Status lulus/gagal tetap ditentukan oleh hasil uji dan asesor."
/>

{#if !p}
	<Memuat />
{:else}
	<div class="grid gap-6 lg:grid-cols-[1fr_340px]">
		<div class="grid content-start gap-5">
			<div class="grid gap-3 sm:grid-cols-2">
				{#each PROVIDER as x (x.v)}
					<button
						onclick={() => pilih(x.v)}
						class={cn(
							'sudut-taktis flex items-start gap-3 rounded-md border bg-card p-4 text-left transition',
							p.provider === x.v ? 'border-primary ring-2 ring-primary/30' : 'hover:bg-muted/50'
						)}
					>
						<span class={cn('grid size-9 shrink-0 place-items-center', x.lokal ? 'bg-success/15 text-success' : 'bg-info/12 text-info')}>
							{#if x.lokal}<Server class="size-4" />{:else}<Cloud class="size-4" />{/if}
						</span>
						<span>
							<span class="block font-heading text-sm tracking-[0.06em] uppercase">{x.l}</span>
							<span class="text-xs text-muted-foreground">{x.d}</span>
							<span class={cn('mt-1 block font-heading text-[10px] tracking-[0.15em] uppercase', x.lokal ? 'text-success' : 'text-warning-foreground')}>
								{x.lokal ? 'Data tetap di jaringan internal' : 'Data keluar jaringan'}
							</span>
						</span>
					</button>
				{/each}
			</div>

			<div class="grid gap-4 rounded-lg border bg-card p-5 sm:grid-cols-2">
				<Field label="Endpoint" id="ai-endpoint"><Input id="ai-endpoint" bind:value={p.endpoint} /></Field>
				<Field label="Model" id="ai-model"><Input id="ai-model" bind:value={p.model} /></Field>
				{#if !aktif?.lokal}
					<Field label="API key" id="ai-key" bantuan={p.api_key_terisi ? 'Sudah tersimpan. Isi untuk mengganti.' : 'Disimpan terenkripsi di backend.'}>
						<Input id="ai-key" type="password" bind:value={p.api_key} placeholder={p.api_key_terisi ? '••••••••••••' : ''} autocomplete="off" />
					</Field>
				{/if}
				<Field label="Bahasa keluaran" id="ai-bahasa">
					<NativeSelect id="ai-bahasa" bind:value={p.bahasa} opsi={[{ value: 'id', label: 'Bahasa Indonesia' }, { value: 'en', label: 'English' }]} />
				</Field>
				<label class="flex items-start gap-3 rounded-md border border-success/40 bg-success/5 p-3 sm:col-span-2">
					<Switch bind:checked={p.redaksi} class="mt-0.5" />
					<span class="text-sm">
						<span class="flex items-center gap-1.5 font-medium"><EyeOff class="size-4" /> Samarkan data sebelum dikirim ke AI</span>
						<span class="text-xs text-muted-foreground">Host, IP, URL lengkap, token, cookie, dan kredensial diganti placeholder. Wajib aktif untuk penyedia di luar jaringan.</span>
					</span>
				</label>
				{#if !p.redaksi && !aktif?.lokal}
					<Alert.Root class="border-critical/40 bg-critical/5 sm:col-span-2">
						<TriangleAlert class="text-critical" />
						<Alert.Title>Penyamaran nonaktif pada penyedia eksternal</Alert.Title>
						<Alert.Description>Detail sasaran pengujian akan keluar dari jaringan internal.</Alert.Description>
					</Alert.Root>
				{/if}
				<div class="flex justify-end sm:col-span-2">
					<Button onclick={simpan} disabled={menyimpan}><Save /> Simpan Pengaturan</Button>
				</div>
			</div>
		</div>

		<aside class="bg-loreng sudut-taktis self-start rounded-lg p-5 text-sidebar-foreground">
			<p class="label-stensil">Kebijakan Data</p>
			<ul class="mt-3 grid gap-2 text-sm text-white/85">
				<li class="flex gap-2"><span class="text-gold">▸</span>Yang dikirim: nama metode, kriteria, status, dan ringkasan temuan yang sudah disamarkan.</li>
				<li class="flex gap-2"><span class="text-gold">▸</span>Tidak pernah dikirim: kredensial akun uji, cookie/token sesi, dokumen bukti.</li>
				<li class="flex gap-2"><span class="text-gold">▸</span>Untuk operasional, gunakan model lokal (Ollama/vLLM) agar data tidak keluar jaringan.</li>
				<li class="flex gap-2"><span class="text-gold">▸</span>Setiap permintaan ke AI dicatat di log audit backend.</li>
			</ul>
		</aside>
	</div>
{/if}
