<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.js';
	import type { KerentananAset } from '#lib/types.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let {
		target = $bindable(null),
		status,
		ondiubah
	}: {
		target: KerentananAset | null;
		status: 'ditangani' | 'dikecualikan';
		ondiubah: (k: KerentananAset) => void;
	} = $props();

	let catatan = $state('');
	let sibuk = $state(false);
	let galat = $state<string | null>(null);

	const JUDUL = { ditangani: 'Tandai sudah ditangani', dikecualikan: 'Kecualikan kerentanan' } as const;
	const PETUNJUK = {
		ditangani: 'Mis. "nginx diperbarui ke 1.26.2 pada 14/11", atau "tambalan backport USN-6000-1 terpasang".',
		dikecualikan: 'Mis. "modul HTTP/2 tidak diaktifkan", atau "hanya dapat diakses dari jaringan internal".'
	} as const;

	$effect(() => {
		if (target) {
			catatan = '';
			galat = null;
		}
	});

	async function simpan(e: SubmitEvent) {
		e.preventDefault();
		if (!target) return;
		if (catatan.trim().length < 5) {
			galat = 'Catatan minimal 5 karakter.';
			return;
		}
		sibuk = true;
		try {
			const hasil = await api.ubahStatusKerentanan(target.id, { status, catatan: catatan.trim() });
			toast.success(status === 'ditangani' ? `${target.cve.id} ditandai ditangani` : `${target.cve.id} dikecualikan`);
			ondiubah(hasil);
			target = null;
		} catch (err) {
			galat = err instanceof Error ? err.message : 'Gagal menyimpan status';
		} finally {
			sibuk = false;
		}
	}
</script>

<Dialog.Root open={!!target} onOpenChange={(o) => !o && !sibuk && (target = null)}>
	<Dialog.Content>
		{#if target}
			<form onsubmit={simpan} class="grid gap-4">
				<Dialog.Header>
					<Dialog.Title>{JUDUL[status]}</Dialog.Title>
					<Dialog.Description>
						{target.cve.id} · {target.komponen.nama}{target.komponen.versi ? ` ${target.komponen.versi}` : ''} · {target.aplikasi.nama}
					</Dialog.Description>
				</Dialog.Header>
				<div class="grid gap-1.5">
					<label for="catatan-kerentanan" class="text-sm font-medium">Catatan <span class="text-critical">*</span></label>
					<Textarea id="catatan-kerentanan" bind:value={catatan} rows={3} maxlength={1000} placeholder={PETUNJUK[status]} aria-invalid={!!galat} />
					{#if galat}<p class="text-xs text-critical" role="alert">{galat}</p>{/if}
					<p class="text-xs text-muted-foreground">
						Status ini tidak akan ditimpa pencocokan otomatis. Bisa dibuka kembali kapan saja.
					</p>
				</div>
				<Dialog.Footer>
					<Button type="button" variant="outline" disabled={sibuk} onclick={() => (target = null)}>Batal</Button>
					<Button type="submit" disabled={sibuk}>
						{#if sibuk}<LoaderCircle class="animate-spin" />{/if}
						Simpan
					</Button>
				</Dialog.Footer>
			</form>
		{/if}
	</Dialog.Content>
</Dialog.Root>
