// Klien sumber intel kerentanan (HTTP keluar). Satu tempat untuk URL, batas laju, dan percobaan ulang.
// Proxy: fetch bawaan Node memakai HTTPS_PROXY bila NODE_USE_ENV_PROXY=1 (lihat .env.example).
import { env } from '../../config/env.js';
import { logger } from '../../utils/logger.js';

const NVD_URL = 'https://services.nvd.nist.gov/rest/json/cves/2.0';
const KEV_URL = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json';
const EPSS_URL = 'https://api.first.org/data/v1/epss';
const OSV_URL = 'https://api.osv.dev/v1';

const USER_AGENT = 'SATRIA-intel-kerentanan/1.0';
// Halaman besar (2000) sering dijawab 503 oleh NVD untuk produk berriwayat panjang (mis. MySQL).
const NVD_PER_HALAMAN = 1000;
// Batas NVD: 50 req/30 dtk dengan kunci, 5 req/30 dtk tanpa kunci (diberi jeda aman).
const jedaNvd = () => (env.cve.nvdApiKey ? 800 : 6500);
// Rentang tanggal lastMod NVD maksimal 120 hari per request.
export const NVD_MAKS_HARI = 120;

const tidur = (ms) => new Promise((r) => setTimeout(r, ms));

/** fetch JSON dengan timeout & percobaan ulang untuk 429/5xx/galat jaringan. */
export async function ambilJson(url, { method = 'GET', headers = {}, body, percobaan = 5, timeoutMs = 60_000 } = {}) {
  let galat;
  for (let i = 0; i < percobaan; i++) {
    try {
      const res = await fetch(url, {
        method,
        headers: { 'User-Agent': USER_AGENT, Accept: 'application/json', ...headers, ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (res.ok) return await res.json();
      galat = new Error(`${new URL(url).host} menjawab HTTP ${res.status}`);
      if (res.status !== 429 && res.status < 500) throw galat;
    } catch (error) {
      galat = error;
      if (/HTTP 4(?!29)/.test(error.message)) throw error;
    }
    if (i < percobaan - 1) await tidur(3000 * 2 ** i);
  }
  throw galat;
}

// Format tanggal NVD: ISO-8601 dengan offset eksplisit.
const isoNvd = (d) => d.toISOString().replace('Z', '+00:00');

/**
 * Iterasi halaman NVD untuk `params` (mis. { virtualMatchString } atau { lastModStartDate, lastModEndDate }).
 * Menghasilkan array `vulnerabilities` per halaman.
 */
export async function* halamanNvd(params) {
  const headers = env.cve.nvdApiKey ? { apiKey: env.cve.nvdApiKey } : {};
  let mulai = 0;
  for (;;) {
    const q = new URLSearchParams({ ...params, resultsPerPage: String(NVD_PER_HALAMAN), startIndex: String(mulai) });
    const data = await ambilJson(`${NVD_URL}?${q}`, { headers, timeoutMs: 120_000 });
    yield data.vulnerabilities ?? [];
    mulai += data.resultsPerPage ?? NVD_PER_HALAMAN;
    if (!data.totalResults || mulai >= data.totalResults) return;
    await tidur(jedaNvd());
  }
}

/** Semua CVE untuk satu produk CPE (mis. "cpe:2.3:a:f5:nginx"). */
export const nvdPerProduk = (bagian, vendor, produk) =>
  halamanNvd({ virtualMatchString: `cpe:2.3:${bagian}:${vendor}:${produk}`, noRejected: '' });

/** CVE yang berubah dalam jendela waktu (≤ 120 hari). */
export const nvdBerubah = (dari, sampai) =>
  halamanNvd({ lastModStartDate: isoNvd(dari), lastModEndDate: isoNvd(sampai) });

export async function jedaAntarPermintaanNvd() {
  await tidur(jedaNvd());
}

/** Katalog CISA KEV → [{ cveId, dateAdded, dueDate, knownRansomwareCampaignUse }]. */
export async function ambilKev() {
  const data = await ambilJson(KEV_URL, { timeoutMs: 120_000 });
  return data.vulnerabilities ?? [];
}

/** Skor EPSS untuk ≤ 100 CVE per panggilan → [{ cve, epss, percentile }]. */
export async function ambilEpss(ids) {
  const hasil = [];
  for (let i = 0; i < ids.length; i += 100) {
    const potongan = ids.slice(i, i + 100);
    const data = await ambilJson(`${EPSS_URL}?cve=${potongan.join(',')}&limit=100`);
    hasil.push(...(data.data ?? []));
    await tidur(300);
  }
  return hasil;
}

/** OSV querybatch: purl berversi → daftar ID advisory per purl (urutan sama dengan input). */
export async function osvQueryBatch(purls) {
  const hasil = [];
  for (let i = 0; i < purls.length; i += 500) {
    const potongan = purls.slice(i, i + 500);
    const data = await ambilJson(`${OSV_URL}/querybatch`, {
      method: 'POST',
      body: { queries: potongan.map((purl) => ({ package: { purl } })) },
    });
    for (const r of data.results ?? []) hasil.push((r.vulns ?? []).map((v) => v.id));
  }
  return hasil;
}

/** Detail satu advisory OSV. */
export async function osvVuln(id) {
  return ambilJson(`${OSV_URL}/vulns/${encodeURIComponent(id)}`);
}

export const logIntel = (pesan, data) => logger.info(`[intel CVE] ${pesan}`, data);
