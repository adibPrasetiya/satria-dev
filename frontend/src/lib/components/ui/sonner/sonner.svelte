<script lang="ts">
	// Toast bergaya taktis SATYA: kartu gelap + strip & ikon berwarna per jenis (gaya di layout.css, .satya-toast).
	import { Toaster as Sonner, type ToasterProps as SonnerProps } from "svelte-sonner";
	import Loader2Icon from '@lucide/svelte/icons/loader-2';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import OctagonXIcon from '@lucide/svelte/icons/octagon-x';
	import InfoIcon from '@lucide/svelte/icons/info';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';

	let { ...restProps }: SonnerProps = $props();
</script>

<!-- Kartu selalu gelap (senada header & sidebar), di mode terang maupun gelap. -->
<Sonner
	theme="dark"
	class="toaster group"
	closeButton
	toastOptions={{
		unstyled: true,
		classes: {
			toast: "satya-toast",
			icon: "satya-toast-ikon",
			content: "satya-toast-isi",
			title: "satya-toast-judul",
			description: "satya-toast-ket",
			closeButton: "satya-toast-tutup",
		},
	}}
	{...restProps}
>
	{#snippet loadingIcon()}
		<Loader2Icon class="size-[18px] animate-spin" />
	{/snippet}
	{#snippet successIcon()}
		<CircleCheckIcon class="size-[18px]" />
	{/snippet}
	{#snippet errorIcon()}
		<OctagonXIcon class="size-[18px]" />
	{/snippet}
	{#snippet infoIcon()}
		<InfoIcon class="size-[18px]" />
	{/snippet}
	{#snippet warningIcon()}
		<TriangleAlertIcon class="size-[18px]" />
	{/snippet}
</Sonner>
