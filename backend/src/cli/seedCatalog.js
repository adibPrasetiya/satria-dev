import { readFileSync } from 'node:fs';
import path from 'node:path';
import { count } from 'drizzle-orm';
import { load } from 'js-yaml';
import { db } from '../db/index.js';
import { catalogControls, catalogFunctions, catalogMeta, catalogMethods, catalogTestPoints } from '../db/schema.js';

const DEFAULT_SOURCE = path.resolve(process.cwd(), '../controls/bssn_web.yaml');

/**
 * Mengisi katalog kontrol dari YAML (`npm run catalog:seed [path]`). Hanya berjalan bila katalog masih kosong,
 * agar perubahan yang dibuat admin lewat aplikasi tidak tertimpa.
 */
export async function seedCatalog(source = process.argv[3] ?? DEFAULT_SOURCE) {
  const [{ total }] = await db.select({ total: count() }).from(catalogFunctions);
  if (total > 0) {
    console.error('Katalog sudah terisi; seed dibatalkan agar perubahan admin tidak tertimpa.');
    process.exitCode = 1;
    return;
  }

  const yaml = load(readFileSync(source, 'utf8'));
  const defaults = yaml.default_metode ?? {};
  let controlCount = 0;
  let methodCount = 0;

  await db.transaction(async (tx) => {
    await tx.insert(catalogMeta).values({
      schemaVersion: yaml.schema_version ?? 1,
      regulation: yaml.sumber.peraturan,
      section: yaml.sumber.bagian,
      notes: yaml.sumber.catatan ?? [],
    });
    await tx.insert(catalogTestPoints).values(yaml.titik_uji.map((t, i) => ({ code: t.id, name: t.nama, sort: i })));

    for (const [fi, fungsi] of yaml.fungsi_keamanan.entries()) {
      const [fn] = await tx.insert(catalogFunctions).values({ code: fungsi.id, number: fungsi.nomor, name: fungsi.nama, sort: fi });
      for (const [ki, kontrol] of fungsi.kontrol.entries()) {
        const [ctl] = await tx.insert(catalogControls).values({
          code: kontrol.id,
          functionId: fn.insertId,
          refNumber: String(kontrol.nomor_referensi),
          description: kontrol.uraian,
          verifiability: kontrol.verifiabilitas,
          defaultSeverity: kontrol.severity_default,
          aggregation: kontrol.agregasi ?? 'semua_lulus',
          refs: kontrol.referensi_pendukung ?? [],
          parameters: kontrol.parameter ?? null,
          sort: ki,
        });
        controlCount++;
        const methods = kontrol.metode_pengujian.map((raw, mi) => {
          // Nilai bawaan metode cukup ditulis sekali di YAML (default_metode).
          const m = { ...defaults, ...raw };
          return {
            code: m.id,
            controlId: ctl.insertId,
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
          };
        });
        await tx.insert(catalogMethods).values(methods);
        methodCount += methods.length;
      }
    }
  });

  console.log(
    `Katalog terisi dari ${source}: ${yaml.fungsi_keamanan.length} fungsi, ${controlCount} kontrol, ${methodCount} metode, ` +
      `${yaml.titik_uji.length} titik uji.`,
  );
}
