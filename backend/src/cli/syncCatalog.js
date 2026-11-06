import { readFileSync } from 'node:fs';
import path from 'node:path';
import { count } from 'drizzle-orm';
import { load } from 'js-yaml';
import { db } from '../db/index.js';
import { catalogControls, catalogFunctions, catalogMeta, catalogMethods, catalogTestPoints } from '../db/schema.js';

const DEFAULT_SOURCE = path.resolve(process.cwd(), '../controls/bssn_web.yaml');

/**
 * Sinkron katalog kontrol dari YAML secara IDEMPOTEN (`npm run catalog:sync [path]`).
 *
 * Beda dari `seedCatalog` (sekali, hanya bila kosong): sync aman dijalankan tiap deploy —
 * menyisipkan butir baru (fungsi/kontrol/metode/titik uji berdasarkan `code` unik) dan
 * memperbarui definisi butir yang sudah ada dari YAML. Yang TIDAK pernah disentuh:
 *   - `is_active` (status aktif/nonaktif yang dikelola admin; butir tak pernah dihapus),
 *   - baris yang tak ada di YAML (tak dihapus).
 * Jadi penambahan metode (mis. SESS-2.x baru) langsung aktif di server tanpa menimpa
 * keputusan admin menonaktifkan butir.
 *
 * `CATALOG_DRY_RUN=1` → hanya parse YAML & cetak ringkasan, tak menyentuh DB.
 */
export async function syncCatalog(source = process.argv[3] ?? DEFAULT_SOURCE) {
  const yaml = load(readFileSync(source, 'utf8'));
  const defaults = yaml.default_metode ?? {};

  // --- Bangun baris dari YAML (murni; tanpa DB) agar bisa diuji/dry-run. ---
  const testPoints = yaml.titik_uji.map((t, i) => ({ code: t.id, name: t.nama, sort: i }));
  const functions = yaml.fungsi_keamanan.map((f, i) => ({ code: f.id, number: f.nomor, name: f.nama, sort: i }));
  const controls = [];
  const methods = [];
  for (const fungsi of yaml.fungsi_keamanan) {
    for (const [ki, kontrol] of fungsi.kontrol.entries()) {
      controls.push({
        code: kontrol.id,
        functionCode: fungsi.id,
        refNumber: String(kontrol.nomor_referensi),
        description: kontrol.uraian,
        verifiability: kontrol.verifiabilitas,
        defaultSeverity: kontrol.severity_default,
        aggregation: kontrol.agregasi ?? 'semua_lulus',
        refs: kontrol.referensi_pendukung ?? [],
        parameters: kontrol.parameter ?? null,
        sort: ki,
      });
      for (const [mi, raw] of kontrol.metode_pengujian.entries()) {
        const m = { ...defaults, ...raw };
        methods.push({
          code: m.id,
          controlCode: kontrol.id,
          name: m.nama,
          testPoint: m.titik_uji,
          checkId: m.check_id,
          kind: m.jenis,
          engine: m.engine,
          profile: m.profil,
          requiresAuth: Boolean(m.butuh_autentikasi),
          evidence: m.bukti ?? [],
          passCriteria: m.kriteria_lulus,
          sideEffect: m.efek_samping ?? null,
          parameters: m.parameter ?? null,
          severity: m.severity ?? kontrol.severity_default,
          sort: mi,
        });
      }
    }
  }

  const ringkas = `${functions.length} fungsi, ${controls.length} kontrol, ${methods.length} metode, ${testPoints.length} titik uji`;
  if (process.env.CATALOG_DRY_RUN) {
    console.log(`[dry-run] Katalog dari ${source}: ${ringkas}. Tidak menyentuh DB.`);
    return { functions, controls, methods, testPoints };
  }

  await db.transaction(async (tx) => {
    // Meta singleton: isi bila kosong, selain itu perbarui.
    const metaVals = {
      schemaVersion: yaml.schema_version ?? 1,
      regulation: yaml.sumber.peraturan,
      section: yaml.sumber.bagian,
      notes: yaml.sumber.catatan ?? [],
    };
    const [{ total: metaTotal }] = await tx.select({ total: count() }).from(catalogMeta);
    if (metaTotal === 0) await tx.insert(catalogMeta).values(metaVals);
    else await tx.update(catalogMeta).set({ schemaVersion: metaVals.schemaVersion, regulation: metaVals.regulation, section: metaVals.section, notes: metaVals.notes });

    for (const t of testPoints) {
      await tx.insert(catalogTestPoints).values(t).onDuplicateKeyUpdate({ set: { name: t.name, sort: t.sort } });
    }
    for (const f of functions) {
      await tx.insert(catalogFunctions).values(f).onDuplicateKeyUpdate({ set: { number: f.number, name: f.name, sort: f.sort } });
    }

    const fnRows = await tx.select({ id: catalogFunctions.id, code: catalogFunctions.code }).from(catalogFunctions);
    const fnId = new Map(fnRows.map((r) => [r.code, r.id]));
    for (const c of controls) {
      const row = {
        code: c.code, functionId: fnId.get(c.functionCode), refNumber: c.refNumber, description: c.description,
        verifiability: c.verifiability, defaultSeverity: c.defaultSeverity, aggregation: c.aggregation,
        refs: c.refs, parameters: c.parameters, sort: c.sort,
      };
      const { code, ...upd } = row; // `is_active` sengaja tak disertakan → keputusan admin terjaga
      await tx.insert(catalogControls).values(row).onDuplicateKeyUpdate({ set: upd });
    }

    const ctlRows = await tx.select({ id: catalogControls.id, code: catalogControls.code }).from(catalogControls);
    const ctlId = new Map(ctlRows.map((r) => [r.code, r.id]));
    for (const m of methods) {
      const row = {
        code: m.code, controlId: ctlId.get(m.controlCode), name: m.name, testPoint: m.testPoint, checkId: m.checkId,
        kind: m.kind, engine: m.engine, profile: m.profile, requiresAuth: m.requiresAuth, evidence: m.evidence,
        passCriteria: m.passCriteria, sideEffect: m.sideEffect, parameters: m.parameters, severity: m.severity, sort: m.sort,
      };
      const { code, ...upd } = row; // `is_active` tak disertakan
      await tx.insert(catalogMethods).values(row).onDuplicateKeyUpdate({ set: upd });
    }
  });

  console.log(`Katalog tersinkron dari ${source}: ${ringkas}. (butir baru disisipkan, definisi diperbarui; is_active & butir non-YAML tak disentuh.)`);
}
