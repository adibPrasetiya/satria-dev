// Normalisasi data mentah NVD API 2.0 & OSV ke baris tabel `cve` / `cve_cpe`. Tanpa I/O.

const SEVERITAS = { CRITICAL: 'kritis', HIGH: 'tinggi', MEDIUM: 'sedang', MODERATE: 'sedang', LOW: 'rendah', NONE: 'info' };

/** Severitas dari skor CVSS (skala v3/v4). */
export function severitasDariSkor(skor) {
  if (skor === null || skor === undefined) return null;
  if (skor >= 9) return 'kritis';
  if (skor >= 7) return 'tinggi';
  if (skor >= 4) return 'sedang';
  if (skor > 0) return 'rendah';
  return 'info';
}

// Tanggal NVD tanpa zona ("2021-06-01T14:15:09.000") adalah UTC.
const tanggal = (s) => {
  if (!s) return null;
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
};

/** Metrik CVSS terpilih: v3.1 → v4.0 → v3.0 → v2, utamakan penilaian 'Primary' (NVD). */
function pilihCvss(metrics = {}) {
  for (const kunci of ['cvssMetricV31', 'cvssMetricV40', 'cvssMetricV30', 'cvssMetricV2']) {
    const daftar = metrics[kunci] ?? [];
    const m = daftar.find((x) => x.type === 'Primary') ?? daftar[0];
    if (!m?.cvssData) continue;
    const skor = Number(m.cvssData.baseScore);
    const label = m.cvssData.baseSeverity ?? m.baseSeverity;
    return {
      cvssSkor: Number.isFinite(skor) ? skor : null,
      cvssVektor: m.cvssData.vectorString?.slice(0, 200) ?? null,
      severitas: SEVERITAS[label] ?? severitasDariSkor(skor),
    };
  }
  return { cvssSkor: null, cvssVektor: null, severitas: null };
}

/** Pecah kriteria CPE 2.3 ("cpe:2.3:a:f5:nginx:1.18.0:*:...") dengan memperhatikan "\:" ter-escape. */
export function uraiCpe(kriteria) {
  const bagian = String(kriteria ?? '')
    .replace(/\\:/g, '\u0000')
    .split(':')
    .map((x) => x.replace(/\u0000/g, ':').replace(/\\(.)/g, '$1'));
  if (bagian[0] !== 'cpe' || bagian[1] !== '2.3' || bagian.length < 6) return null;
  return { bagian: bagian[2], vendor: bagian[3], produk: bagian[4], versi: bagian[5] };
}

/** Semua cpeMatch `vulnerable: true` dari konfigurasi (node AND/OR diratakan — sedikit lebih longgar). */
function rentangCpe(configurations = []) {
  const hasil = [];
  const kunci = new Set();
  for (const konfigurasi of configurations) {
    for (const node of konfigurasi.nodes ?? []) {
      if (node.negate) continue;
      for (const m of node.cpeMatch ?? []) {
        if (!m.vulnerable) continue;
        const c = uraiCpe(m.criteria);
        if (!c || c.vendor === '*' || c.produk === '*') continue;
        const baris = {
          vendor: c.vendor.slice(0, 100),
          produk: c.produk.slice(0, 100),
          versi: c.versi === '*' || c.versi === '-' ? null : c.versi.slice(0, 60),
          versiMulaiIncl: m.versionStartIncluding?.slice(0, 60) ?? null,
          versiMulaiExcl: m.versionStartExcluding?.slice(0, 60) ?? null,
          versiAkhirIncl: m.versionEndIncluding?.slice(0, 60) ?? null,
          versiAkhirExcl: m.versionEndExcluding?.slice(0, 60) ?? null,
        };
        const k = JSON.stringify(baris);
        if (!kunci.has(k)) {
          kunci.add(k);
          hasil.push(baris);
        }
      }
    }
  }
  return hasil;
}

const STATUS = { Rejected: 'ditolak', Analyzed: 'dianalisis', Modified: 'dianalisis' };

/** Satu item `vulnerabilities[]` NVD API 2.0 → { cve, cpe[] }. */
export function dariNvd(item) {
  const c = item?.cve;
  if (!c?.id) return null;
  const cpe = rentangCpe(c.configurations);
  const ringkasan = (c.descriptions ?? []).find((d) => d.lang === 'en')?.value ?? c.descriptions?.[0]?.value ?? null;
  const cwe = [
    ...new Set(
      (c.weaknesses ?? []).flatMap((w) => (w.description ?? []).map((d) => d.value)).filter((v) => /^CWE-\d+$/.test(v)),
    ),
  ];
  // Status "Modified" tanpa konfigurasi CPE belum bisa dicocokkan → tetap 'menunggu'.
  let statusAnalisis = STATUS[c.vulnStatus] ?? 'menunggu';
  if (statusAnalisis === 'dianalisis' && !cpe.length) statusAnalisis = 'menunggu';
  return {
    cve: {
      id: c.id,
      ringkasan,
      dipublikasiPada: tanggal(c.published),
      diubahPada: tanggal(c.lastModified),
      ...pilihCvss(c.metrics),
      cwe,
      referensi: (c.references ?? []).slice(0, 15).map((r) => r.url),
      statusAnalisis,
      // NVD ikut membawa data KEV; sinkron KEV tetap menjadi sumber utama.
      kev: Boolean(c.cisaExploitAdd),
      kevDitambahkan: c.cisaExploitAdd ?? null,
      kevTenggat: c.cisaActionDue ?? null,
      sumber: 'nvd',
    },
    cpe,
  };
}

/** Advisory OSV (/v1/vulns/{id}) → baris `cve`; ID memakai alias CVE bila ada. */
export function dariOsv(v) {
  if (!v?.id) return null;
  const id = (v.aliases ?? []).find((a) => /^CVE-\d{4}-\d+$/.test(a)) ?? v.id;
  const vektor = (v.severity ?? []).find((s) => /^CVSS_V[34]/.test(s.type))?.score ?? null;
  const label = v.database_specific?.severity;
  return {
    id: id.slice(0, 40),
    ringkasan: (v.summary || v.details || '').slice(0, 5000) || null,
    dipublikasiPada: tanggal(v.published),
    diubahPada: tanggal(v.modified),
    cvssSkor: null,
    cvssVektor: vektor?.slice(0, 200) ?? null,
    severitas: SEVERITAS[label] ?? null,
    cwe: (v.database_specific?.cwe_ids ?? []).filter((x) => /^CWE-\d+$/.test(x)),
    referensi: (v.references ?? []).slice(0, 15).map((r) => r.url),
    statusAnalisis: v.withdrawn ? 'ditolak' : 'dianalisis',
    sumber: 'osv',
  };
}
