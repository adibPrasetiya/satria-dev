import path from 'node:path';
import { migrate } from 'drizzle-orm/mysql2/migrator';
import { db } from './index.js';

/** Jalankan migrasi dari folder `drizzle/` di folder kerja aplikasi (tanpa drizzle-kit, aman setelah dibundel). */
export async function runMigrations(migrationsFolder = path.resolve(process.cwd(), 'drizzle')) {
  await migrate(db, { migrationsFolder });
}
