<script lang="ts">
	import type { PersiapanAuth } from '#lib/types.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import Field from '#lib/components/Field.svelte';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';

	let { p = $bindable() }: { p: PersiapanAuth } = $props();
</script>

<label class="flex items-start justify-between gap-3 rounded-md border border-critical/30 bg-critical/5 p-4">
	<span class="flex items-start gap-2">
		<ShieldAlert class="mt-0.5 size-4 shrink-0 text-critical" />
		<span>
			<span class="block text-sm font-medium">Izinkan uji penguncian akun</span>
			<span class="text-xs text-muted-foreground">Akun uji cadangan bisa terkunci sementara. Pastikan akun itu tidak dipakai pengguna nyata.</span>
		</span>
	</span>
	<Switch bind:checked={p.intrusif.izinkan_penguncian} />
</label>
{#if p.intrusif.izinkan_penguncian}
	<div class="grid items-start gap-4 sm:grid-cols-2">
		<Field label="Boleh diuji mulai" id="intrusif-mulai" info="Uji berisiko hanya dijalankan dalam rentang waktu ini.">
			<Input id="intrusif-mulai" class="h-9" type="datetime-local" bind:value={p.intrusif.jendela_mulai} />
		</Field>
		<Field label="Sampai dengan" id="intrusif-selesai">
			<Input id="intrusif-selesai" class="h-9" type="datetime-local" bind:value={p.intrusif.jendela_selesai} />
		</Field>
	</div>
{/if}
