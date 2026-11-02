import 'dotenv/config';
import mysql from 'mysql2/promise';
import { errorMessage } from '../utils/errorMessage.js';

// drizzle-kit tidak membuat database, jadi buat dulu database dari DATABASE_URL bila belum ada.
// Sengaja hanya membaca DATABASE_URL (seperti drizzle.config.js), bukan seluruh validasi env aplikasi.
async function createDatabase() {
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL belum diisi di .env');
  const url = new URL(process.env.DATABASE_URL);
  const database = decodeURIComponent(url.pathname.slice(1));
  if (!/^\w+$/.test(database)) {
    throw new Error(`Nama database "${database}" tidak valid (hanya huruf, angka, underscore)`);
  }

  url.pathname = '/';
  const connection = await mysql.createConnection({ uri: url.toString() });
  try {
    await connection.query(
      `CREATE DATABASE IF NOT EXISTS \`${database}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`,
    );
    console.log(`Database ${database} siap`);
  } finally {
    await connection.end();
  }
}

createDatabase().catch((error) => {
  console.error(errorMessage(error));
  process.exitCode = 1;
});
