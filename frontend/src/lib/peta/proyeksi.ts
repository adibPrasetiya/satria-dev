// Proyeksi Mercator ke kotak peta (sama persis dengan scripts/build-peta.mjs — ubah keduanya bersamaan).
import peta from '#lib/data/peta-indonesia.json';

export const PETA = peta as {
	sumber: string;
	batas: { lngMin: number; lngMax: number; latMin: number; latMax: number };
	lebar: number;
	tinggi: number;
	provinsi: { kode: string; iso: string; d: string }[];
};

/**
 * Data batas wilayah masih 34 provinsi (sebelum pemekaran Papua 2022). Provinsi baru digambar memakai
 * bentuk provinsi induknya: Papua Selatan/Tengah/Pegunungan → Papua, Papua Barat Daya → Papua Barat.
 */
const BENTUK_INDUK: Record<string, string> = { '93': '91', '94': '91', '95': '91', '96': '92' };
export const kodeBentuk = (kode: string) => BENTUK_INDUK[kode] ?? kode;

const rad = (d: number) => (d * Math.PI) / 180;
const mercY = (lat: number) => (Math.log(Math.tan(Math.PI / 4 + rad(lat) / 2)) * 180) / Math.PI;
const K = PETA.lebar / (PETA.batas.lngMax - PETA.batas.lngMin);
const ATAS = mercY(PETA.batas.latMax);

/** [lng, lat] → koordinat kotak peta (0..lebar, 0..tinggi). */
export function proyeksi(lng: number, lat: number): [number, number] {
	return [(lng - PETA.batas.lngMin) * K, (ATAS - mercY(lat)) * K];
}

/**
 * Kilometer per satuan kotak di garis lintang tertentu (Mercator membesar ke arah kutub;
 * Indonesia dekat khatulistiwa sehingga selisihnya kecil). 1° bujur di khatulistiwa ≈ 111,32 km.
 */
export function kmPerSatuan(lat = 0): number {
	return (111.32 * Math.cos(rad(lat))) / K;
}
