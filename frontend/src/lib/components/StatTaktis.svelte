<script lang="ts">
	import type { Component } from 'svelte';
	import { cn } from '#lib/utils.js';

	let {
		label,
		nilai,
		ket,
		ikon: Ikon,
		nada = 'default',
		href
	}: {
		label: string;
		nilai: string | number;
		ket?: string;
		ikon?: Component<{ class?: string }>;
		nada?: 'default' | 'success' | 'warning' | 'critical' | 'gold';
		href?: string;
	} = $props();

	const warna = {
		default: 'text-foreground',
		success: 'text-success',
		warning: 'text-warning-foreground',
		critical: 'text-critical',
		gold: 'text-gold'
	};
	const garis = {
		default: 'bg-primary',
		success: 'bg-success',
		warning: 'bg-warning',
		critical: 'bg-critical',
		gold: 'bg-gold'
	};
</script>

<svelte:element
	this={href ? 'a' : 'div'}
	{href}
	class={cn(
		'sudut-taktis relative overflow-hidden border bg-card p-4 shadow-sm',
		href && 'transition hover:border-primary/50 hover:shadow-md'
	)}
>
	<span class={cn('absolute inset-y-0 left-0 w-1', garis[nada])}></span>
	<div class="flex items-start justify-between gap-2">
		<p class="font-heading text-[11px] tracking-[0.16em] text-muted-foreground uppercase">{label}</p>
		{#if Ikon}<Ikon class="size-4 text-muted-foreground" />{/if}
	</div>
	<p class={cn('mt-1 font-stencil text-3xl', warna[nada])}>{nilai}</p>
	{#if ket}<p class="mt-0.5 text-xs text-muted-foreground">{ket}</p>{/if}
</svelte:element>
