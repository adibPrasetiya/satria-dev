// `npm run komponen:backfill` — bentuk ulang komponen bersumber 'formulir' dari field teknologi semua aplikasi
// (termasuk yang terarsip). Idempoten: komponen formulir lama diganti; komponen manual & hasil recon tidak disentuh.
import { db } from '../db/index.js';
import { applications } from '../db/schema.js';
import { komponenService } from '../features/komponen/komponen.service.js';

export async function backfillKomponen() {
  const rows = await db
    .select({
      id: applications.id,
      frontend: applications.techFrontend,
      backend: applications.techBackend,
      database: applications.techDatabase,
      server: applications.techServer,
    })
    .from(applications);

  let total = 0;
  for (const { id, ...teknologi } of rows) total += await komponenService.sinkronFormulir(id, teknologi);
  console.log(`Komponen formulir dibentuk ulang: ${total} komponen dari ${rows.length} aplikasi`);
}
