import mysql from 'mysql2/promise';
import { drizzle } from 'drizzle-orm/mysql2';
import { env } from '../config/env.js';
import * as schema from './schema.js';

export const pool = mysql.createPool({
  uri: env.databaseUrl,
  charset: 'utf8mb4',
  timezone: 'Z',
  connectionLimit: 10,
  waitForConnections: true,
});

// Semua DATETIME disimpan dalam UTC: drizzle membaca/menulis tanggal sebagai UTC, jadi default
// CURRENT_TIMESTAMP juga harus UTC (bukan zona waktu sistem server MySQL, mis. WIB).
pool.on('connection', (connection) => {
  connection.query("SET time_zone = '+00:00'");
});

export const db = drizzle({ client: pool, schema, mode: 'default' });
