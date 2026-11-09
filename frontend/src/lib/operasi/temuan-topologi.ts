// Integrasi topologi (graf Recon & Discovery) dengan hasil pengujian: tiap temuan (metode FAILED)
// dipetakan ke endpoint / halaman yang diuji — dari request nyata worker pada peristiwa uji di log —
// lalu node tersebut ditandai. Temuan tanpa URL spesifik (mis. header global) ditempel ke node target.
// Murni (tanpa I/O).
import { originDari, templatPath, type Graf, type NodeGraf } from '#lib/penemuan/graf.js';
import type { Uji } from '#lib/pengujian/uji.js';
import type { Severity } from '#lib/types.js';
import { URUTAN_SEVERITY } from '#lib/catalog.js';
import type { BarisMetode } from './ringkas.js';

export interface TemuanNode {
	id: string;
	nama: string;
	severity: Severity;
}

/** Segmen parameter apa pun ({id}, {cutiId}, :id) → {id} agar sebanding dengan templatPath(url). */
const normal = (path: string) =>
	path
		.split('?')[0]
		.split('/')
		.map((s) => (/^\{.*\}$|^:\w+$/.test(s) ? '{id}' : s))
		.join('/')
		.replace(/\/+$/, '') || '/';

function cariNode(graf: Graf, url: string, metode?: string): NodeGraf | undefined {
	const tmpl = normal(templatPath(url));
	const origin = originDari(url);
	const ep = graf.nodes.filter(
		(n) =>
			n.jenis === 'endpoint' &&
			n.endpoint &&
			normal(n.endpoint.path_template) === tmpl &&
			(!origin || !n.endpoint.origin || n.endpoint.origin === origin)
	);
	const pasMetode = metode
		? ep.find((n) => n.endpoint!.metode_http?.toUpperCase() === metode.toUpperCase())
		: undefined;
	return (
		pasMetode ?? ep[0] ?? graf.nodes.find((n) => n.jenis === 'halaman' && normal(n.label) === tmpl)
	);
}

/** nodeId → daftar temuan (terurut severity) pada node tersebut. */
export function petaTemuanTopologi(
	graf: Graf,
	uji: Uji,
	temuan: BarisMetode[]
): Map<string, TemuanNode[]> {
	const peta = new Map<string, TemuanNode[]>();
	const situs = graf.nodes.find((n) => n.jenis === 'situs');
	const tambah = (nodeId: string, t: TemuanNode) => {
		const daftar = peta.get(nodeId) ?? [];
		if (!daftar.some((x) => x.id === t.id)) daftar.push(t);
		peta.set(nodeId, daftar);
	};
	for (const b of temuan) {
		const t: TemuanNode = { id: b.id, nama: b.nama, severity: b.severity };
		let tertaut = false;
		for (const k of uji.per.get(b.id)?.ketukan ?? []) {
			if (k.tipe !== 'request' || !k.req.url) continue;
			const n = cariNode(graf, k.req.url, k.req.metode_http);
			if (n) {
				tambah(n.id, t);
				tertaut = true;
			}
		}
		if (!tertaut && situs) tambah(situs.id, t);
	}
	for (const daftar of peta.values()) {
		daftar.sort(
			(a, b) => URUTAN_SEVERITY.indexOf(a.severity) - URUTAN_SEVERITY.indexOf(b.severity)
		);
	}
	return peta;
}

/** Salinan graf dengan field `temuan` pada node yang terkena temuan. */
export function tandaiGraf(graf: Graf, peta: Map<string, TemuanNode[]>): Graf {
	if (!peta.size) return graf;
	return {
		...graf,
		nodes: graf.nodes.map((n) => (peta.has(n.id) ? { ...n, temuan: peta.get(n.id) } : n))
	};
}
