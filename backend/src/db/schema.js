import { sql } from 'drizzle-orm';
import {
  bigint,
  boolean,
  char,
  datetime,
  decimal,
  foreignKey,
  index,
  json,
  mysqlEnum,
  mysqlTable,
  smallint,
  text,
  varchar,
} from 'drizzle-orm/mysql-core';
import { ROLES } from '../config/app.js';
import { JENIS_SATUAN } from '../config/satuan.js';

/** Status kepegawaian pendaftar: militer (NRP) atau PNS (NIP 18 digit). */
export const EMPLOYMENT_STATUSES = ['TNI', 'PNS'];

const id = () => bigint('id', { mode: 'number', unsigned: true }).autoincrement().primaryKey();
const userId = () =>
  bigint('user_id', { mode: 'number', unsigned: true })
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' });
const createdAt = () => datetime('created_at').notNull().default(sql`CURRENT_TIMESTAMP`);
const updatedAt = () =>
  datetime('updated_at')
    .notNull()
    .default(sql`CURRENT_TIMESTAMP`)
    .$onUpdate(() => new Date());

// Daftar satuan/instansi resmi; pendaftar memilih dari sini (bukan teks bebas).
// Hierarkis: tiap satuan boleh punya induk (mis. Mabes TNI → Kodam Jaya → Kodim 0501); akar = parent_id NULL.
// Alamat & koordinat dipakai peta sebaran sistem informasi per daerah di dasbor.
export const units = mysqlTable(
  'units',
  {
    id: id(),
    parentId: bigint('parent_id', { mode: 'number', unsigned: true }),
    name: varchar('name', { length: 120 }).notNull().unique(),
    type: mysqlEnum('type', JENIS_SATUAN).notNull().default('SATUAN'),
    address: varchar('address', { length: 255 }),
    city: varchar('city', { length: 100 }),
    provinceCode: char('province_code', { length: 2 }),
    latitude: decimal('latitude', { precision: 9, scale: 6 }),
    longitude: decimal('longitude', { precision: 9, scale: 6 }),
    // Satuan nonaktif tidak muncul di pilihan pendaftaran, tetapi akun yang sudah merujuknya tetap sah.
    isActive: boolean('is_active').notNull().default(true),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [
    foreignKey({ name: 'units_parent_id_units_id_fk', columns: [table.parentId], foreignColumns: [table.id] }).onDelete(
      'restrict',
    ),
    index('units_parent_id_idx').on(table.parentId),
    index('units_province_code_idx').on(table.provinceCode),
  ],
);

export const users = mysqlTable(
  'users',
  {
    id: id(),
    name: varchar('name', { length: 100 }).notNull(),
    // Status kepegawaian (TNI/PNS) & pangkat/golongan. Nullable: akun lama (sebelum kolom ini ada)
    // menyimpan pangkat di dalam `name`.
    employmentStatus: mysqlEnum('status_kepegawaian', EMPLOYMENT_STATUSES),
    rank: varchar('pangkat', { length: 60 }),
    // NRP (militer) / NIP (PNS).
    nrp: varchar('nrp', { length: 20 }).notNull().unique(),
    unitId: bigint('unit_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => units.id, { onDelete: 'restrict' }),
    email: varchar('email', { length: 160 }).notNull().unique(),
    passwordHash: varchar('password_hash', { length: 255 }).notNull(),
    role: mysqlEnum('role', ROLES).notNull().default('pemilik'),
    // Akun hasil pendaftaran mandiri baru bisa dipakai setelah email diverifikasi lewat tautan, atau
    // diverifikasi manual oleh admin (`verifiedBy` null = terverifikasi lewat email).
    isVerified: boolean('is_verified').notNull().default(false),
    verifiedAt: datetime('verified_at'),
    verifiedBy: bigint('verified_by', { mode: 'number', unsigned: true }).references(() => users.id, { onDelete: 'set null' }),
    isActive: boolean('is_active').notNull().default(true),
    // Penguncian setelah login gagal berturut-turut (kontrol BSSN 1.4).
    failedLoginCount: smallint('failed_login_count', { unsigned: true }).notNull().default(0),
    lockedUntil: datetime('locked_until'),
    passwordChangedAt: datetime('password_changed_at'),
    lastLoginAt: datetime('last_login_at'),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [index('users_unit_id_idx').on(table.unitId)],
);

export const refreshTokens = mysqlTable(
  'refresh_tokens',
  {
    id: id(),
    userId: userId(),
    tokenHash: char('token_hash', { length: 64 }).notNull().unique(),
    expiresAt: datetime('expires_at').notNull(),
    revokedAt: datetime('revoked_at'),
    // Hanya token berstatus 'rotated' yang dipakai ulang dianggap pencurian.
    revokedReason: mysqlEnum('revoked_reason', ['rotated', 'logout', 'password_change', 'deactivated', 'reuse', 'role_change']),
    userAgent: varchar('user_agent', { length: 255 }),
    ip: varchar('ip', { length: 45 }),
    createdAt: createdAt(),
  },
  (table) => [index('refresh_tokens_user_id_idx').on(table.userId)],
);

// Token tautan "lupa kata sandi": hanya hash yang disimpan, sekali pakai, dan berbatas waktu (kontrol BSSN 1.5).
export const passwordResetTokens = mysqlTable(
  'password_reset_tokens',
  {
    id: id(),
    userId: userId(),
    tokenHash: char('token_hash', { length: 64 }).notNull().unique(),
    expiresAt: datetime('expires_at').notNull(),
    usedAt: datetime('used_at'),
    createdAt: createdAt(),
  },
  (table) => [index('password_reset_tokens_user_id_idx').on(table.userId)],
);

// Token tautan verifikasi email pendaftaran: hanya hash yang disimpan, sekali pakai, dan berbatas waktu.
export const emailVerificationTokens = mysqlTable(
  'email_verification_tokens',
  {
    id: id(),
    userId: userId(),
    tokenHash: char('token_hash', { length: 64 }).notNull().unique(),
    expiresAt: datetime('expires_at').notNull(),
    usedAt: datetime('used_at'),
    createdAt: createdAt(),
  },
  (table) => [index('email_verification_tokens_user_id_idx').on(table.userId)],
);

export const ENVIRONMENTS = ['produksi', 'staging', 'pengembangan'];
export const DATA_CLASSIFICATIONS = ['biasa', 'terbatas', 'rahasia'];

// Aset aplikasi yang akan dinilai: hanya informasi dasar. Persiapan pengujian (verifikasi kepemilikan, titik uji,
// akun uji, izin intrusif) disimpan terpisah per pengujian.
export const applications = mysqlTable(
  'applications',
  {
    id: id(),
    name: varchar('name', { length: 150 }).notNull(),
    description: text('description'),
    unitId: bigint('unit_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => units.id, { onDelete: 'restrict' }),
    // Pendaftar; akun yang dihapus tidak menghapus asetnya.
    ownerId: bigint('owner_id', { mode: 'number', unsigned: true }).references(() => users.id, { onDelete: 'set null' }),
    picName: varchar('pic_name', { length: 100 }).notNull(),
    picContact: varchar('pic_contact', { length: 100 }).notNull(),
    // Satu URL dasar = satu aset, agar aplikasi yang sama tidak terdaftar dua kali.
    baseUrl: varchar('base_url', { length: 255 }).notNull().unique(),
    environment: mysqlEnum('environment', ENVIRONMENTS).notNull(),
    dataClassification: mysqlEnum('data_classification', DATA_CLASSIFICATIONS).notNull(),
    techFrontend: varchar('tech_frontend', { length: 100 }),
    techBackend: varchar('tech_backend', { length: 100 }),
    techDatabase: varchar('tech_database', { length: 100 }),
    techServer: varchar('tech_server', { length: 100 }),
    // Diarsipkan (pengganti hapus): disembunyikan dari daftar & tak bisa diuji, riwayat scan tetap utuh.
    archivedAt: datetime('archived_at'),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [index('applications_unit_id_idx').on(table.unitId)],
);

// ---------------------------------------------------------------------------
// Katalog kontrol BSSN (awal diisi dari controls/bssn_web.yaml lewat `npm run catalog:seed`, lalu dikelola admin).
// Butir tidak pernah dihapus, hanya dinonaktifkan, agar hasil pengujian lama tetap bisa dibaca.

export const SEVERITIES = ['kritis', 'tinggi', 'sedang', 'rendah', 'info'];
export const VERIFIABILITIES = ['otomatis', 'sebagian', 'manual'];
export const AGGREGATIONS = ['semua_lulus', 'minimal_satu'];
export const METHOD_KINDS = ['otomatis', 'semi_otomatis', 'manual'];
// 'discovery' = fase penemuan mode eksploratif (crawl + klasifikasi titik uji); bukan metode katalog.
export const ENGINES = ['custom', 'zap', 'nuclei', 'sslyze', 'playwright', 'manual', 'discovery'];
export const PROFILES = ['aman', 'intrusif'];
// Mode pengujian: 'terarah' (pengguna mengisi data persiapan) | 'eksploratif' (hanya URL → penemuan otomatis).
export const SCAN_MODES = ['terarah', 'eksploratif'];
// Pendekatan uji: 'greybox' (memakai akun uji terbatas) | 'blackbox' (tanpa pengetahuan/akses internal,
// akun uji tersimpan tidak dipakai sama sekali).
export const SCAN_APPROACHES = ['greybox', 'blackbox'];
export const EVIDENCE_TYPES = ['request_response', 'screenshot', 'dokumen'];

export const catalogMeta = mysqlTable('catalog_meta', {
  id: id(),
  schemaVersion: smallint('schema_version', { unsigned: true }).notNull(),
  regulation: varchar('regulation', { length: 255 }).notNull(),
  section: varchar('section', { length: 255 }).notNull(),
  notes: json('notes').$type(),
  createdAt: createdAt(),
});

export const catalogTestPoints = mysqlTable('catalog_test_points', {
  id: id(),
  code: varchar('code', { length: 40 }).notNull().unique(),
  name: varchar('name', { length: 150 }).notNull(),
  sort: smallint('sort', { unsigned: true }).notNull().default(0),
});

export const catalogFunctions = mysqlTable('catalog_functions', {
  id: id(),
  code: varchar('code', { length: 20 }).notNull().unique(),
  number: smallint('number', { unsigned: true }).notNull(),
  name: varchar('name', { length: 150 }).notNull(),
  sort: smallint('sort', { unsigned: true }).notNull().default(0),
});

export const catalogControls = mysqlTable(
  'catalog_controls',
  {
    id: id(),
    code: varchar('code', { length: 40 }).notNull().unique(),
    functionId: bigint('function_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => catalogFunctions.id, { onDelete: 'restrict' }),
    refNumber: varchar('ref_number', { length: 20 }).notNull(),
    description: text('description').notNull(),
    verifiability: mysqlEnum('verifiability', VERIFIABILITIES).notNull(),
    defaultSeverity: mysqlEnum('default_severity', SEVERITIES).notNull(),
    aggregation: mysqlEnum('aggregation', AGGREGATIONS).notNull().default('semua_lulus'),
    refs: json('refs').$type(),
    parameters: json('parameters').$type(),
    isActive: boolean('is_active').notNull().default(true),
    sort: smallint('sort', { unsigned: true }).notNull().default(0),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [index('catalog_controls_function_id_idx').on(table.functionId)],
);

export const catalogMethods = mysqlTable(
  'catalog_methods',
  {
    id: id(),
    code: varchar('code', { length: 50 }).notNull().unique(),
    controlId: bigint('control_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => catalogControls.id, { onDelete: 'restrict' }),
    name: varchar('name', { length: 255 }).notNull(),
    testPoint: varchar('test_point', { length: 40 }).notNull(),
    checkId: varchar('check_id', { length: 120 }).notNull(),
    kind: mysqlEnum('kind', METHOD_KINDS).notNull(),
    engine: mysqlEnum('engine', ENGINES).notNull(),
    profile: mysqlEnum('profile', PROFILES).notNull(),
    requiresAuth: boolean('requires_auth').notNull().default(false),
    evidence: json('evidence').$type(),
    passCriteria: text('pass_criteria').notNull(),
    sideEffect: text('side_effect'),
    parameters: json('parameters').$type(),
    severity: mysqlEnum('severity', SEVERITIES).notNull(),
    isActive: boolean('is_active').notNull().default(true),
    sort: smallint('sort', { unsigned: true }).notNull().default(0),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [index('catalog_methods_control_id_idx').on(table.controlId)],
);

// ---------------------------------------------------------------------------
// Pengujian (scan): orkestrasi di backend, eksekusi di worker (lihat worker/).
// Worker mengambil task lewat HTTP claim (/internal/tasks/claim) dan melapor hasil;
// worker tidak pernah menyentuh tabel ini langsung.

export const SCAN_STATUSES = ['antre', 'berjalan', 'selesai', 'dibatalkan'];
export const TASK_STATUSES = ['antre', 'berjalan', 'selesai'];
export const LOG_LEVELS = ['info', 'peringatan', 'galat'];
export const VERDICTS = ['laik', 'laik_bersyarat', 'tidak_laik'];
// Status penyusunan laporan AI: belum diminta, sedang disusun (auto saat selesai), siap, atau gagal.
export const LAPORAN_STATUSES = ['belum', 'proses', 'siap', 'gagal'];

// Persiapan pengujian per aplikasi: pemetaan titik uji -> URL nyata & template form.
// Dipakai worker untuk tahu endpoint mana yang diuji dan nama field form-nya.
// Akun uji (kredensial) ditunda; metode yang butuh_autentikasi -> tidak_dapat_diverifikasi.
export const scanTargets = mysqlTable('scan_targets', {
  id: id(),
  applicationId: bigint('application_id', { mode: 'number', unsigned: true })
    .notNull()
    .unique()
    .references(() => applications.id, { onDelete: 'cascade' }),
  // { registrasi: { tersedia, url, metode_http }, ... }
  testPoints: json('test_points').$type(),
  // { registrasi: { field_dasar, field_sandi, field_unik, tipe_body, status_sukses }, login: {...}, ... }
  forms: json('forms').$type(),
  // Kredensial akun uji: { utama: { username, password }, penguncian: { username, password } }.
  // CATATAN: untuk produksi harus dienkripsi (saat ini plaintext untuk dev).
  accounts: json('accounts').$type(),
  // Opsi uji: { izinkan_penguncian, jendela_mulai, jendela_selesai, panjang_minimum, wajib }.
  options: json('options').$type(),
  // Ringkasan fase penemuan (mode eksploratif): { halaman, endpoint_api, titik_ditemukan, ... }.
  discovery: json('discovery').$type(),
  updatedAt: updatedAt(),
});

export const scans = mysqlTable(
  'scans',
  {
    id: id(),
    applicationId: bigint('application_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => applications.id, { onDelete: 'cascade' }),
    profile: mysqlEnum('profile', PROFILES).notNull().default('aman'),
    mode: mysqlEnum('mode', SCAN_MODES).notNull().default('terarah'),
    approach: mysqlEnum('approach', SCAN_APPROACHES).notNull().default('greybox'),
    // Scan yang hasil Recon & Discovery-nya dipakai ulang oleh scan ini (tanpa menyalin data recon).
    // NULL = scan menjalankan penemuannya sendiri, atau tanpa penemuan (mode terarah).
    reconScanId: bigint('recon_scan_id', { mode: 'number', unsigned: true }),
    status: mysqlEnum('status', SCAN_STATUSES).notNull().default('berjalan'),
    startedAt: datetime('started_at').notNull().default(sql`CURRENT_TIMESTAMP`),
    finishedAt: datetime('finished_at'),
    // Putusan kelaikan & skor kepatuhan (0–100) dihitung saat scan selesai (lihat scans/verdict.js),
    // agar daftar aplikasi bisa disaring/diurutkan di DB. NULL = belum dihitung / scan belum selesai.
    verdict: mysqlEnum('verdict', VERDICTS),
    score: smallint('score', { unsigned: true }),
    // Jumlah temuan (metode GAGAL) per severity metode; info tidak dihitung (sama dengan laporan).
    findingsCritical: smallint('findings_critical', { unsigned: true }),
    findingsHigh: smallint('findings_high', { unsigned: true }),
    findingsMedium: smallint('findings_medium', { unsigned: true }),
    findingsLow: smallint('findings_low', { unsigned: true }),
    // Laporan hasil generate AI (ringkasan eksekutif + rekomendasi). Hanya disimpan untuk scan SELESAI
    // terakhir sebuah aplikasi; laporan riwayat lama selalu di-generate ulang & tidak disimpan.
    aiAnalysis: json('ai_analysis').$type(),
    // Status penyusunan laporan: diisi 'proses' saat auto-generate dimulai (scan selesai), lalu
    // 'siap' (ai_analysis terisi) atau 'gagal'. Dasar tombol Lihat/Generate di UI (salah satu saja).
    laporanStatus: mysqlEnum('laporan_status', LAPORAN_STATUSES).notNull().default('belum'),
  },
  (table) => [
    index('scans_application_id_idx').on(table.applicationId),
    index('scans_application_status_idx').on(table.applicationId, table.status),
  ],
);

// Satu baris per metode pengujian dalam satu scan. Metode manual/tidak-berlaku
// langsung berstatus 'selesai' dengan result terisi (tak pernah diklaim worker).
export const scanTasks = mysqlTable(
  'scan_tasks',
  {
    id: id(),
    scanId: bigint('scan_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => scans.id, { onDelete: 'cascade' }),
    methodCode: varchar('method_code', { length: 50 }).notNull(),
    checkId: varchar('check_id', { length: 120 }).notNull(),
    engine: mysqlEnum('engine', ENGINES).notNull(),
    status: mysqlEnum('status', TASK_STATUSES).notNull().default('antre'),
    attempts: smallint('attempts', { unsigned: true }).notNull().default(0),
    lockedBy: varchar('locked_by', { length: 100 }),
    lockedAt: datetime('locked_at'),
    // HasilMetode (lihat frontend/src/lib/types.ts) saat task selesai.
    result: json('result').$type(),
    durationMs: bigint('duration_ms', { mode: 'number', unsigned: true }),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (table) => [
    index('scan_tasks_scan_id_idx').on(table.scanId),
    index('scan_tasks_status_engine_idx').on(table.status, table.engine),
  ],
);

export const scanLogs = mysqlTable(
  'scan_logs',
  {
    id: id(),
    scanId: bigint('scan_id', { mode: 'number', unsigned: true })
      .notNull()
      .references(() => scans.id, { onDelete: 'cascade' }),
    level: mysqlEnum('level', LOG_LEVELS).notNull().default('info'),
    message: varchar('message', { length: 500 }).notNull(),
    // Peristiwa terstruktur opsional (visualisasi penemuan): { v, jenis, ... }.
    data: json('data').$type(),
    createdAt: createdAt(),
  },
  (table) => [index('scan_logs_scan_id_idx').on(table.scanId)],
);

export const WORKER_STATUSES = ['siaga', 'sibuk', 'berhenti'];

// Registry worker pengujian: diperbarui heartbeat & klaim task. Worker dianggap aktif bila
// `terakhirTerlihat` masih dalam WORKER_HEARTBEAT_TIMEOUT_MS — dasar status di UI & penjaga mulai scan.
export const workers = mysqlTable('workers', {
  id: varchar('id', { length: 100 }).primaryKey(),
  engines: json('engines').$type().notNull(),
  status: mysqlEnum('status', WORKER_STATUSES).notNull().default('siaga'),
  taskId: bigint('task_id', { mode: 'number', unsigned: true }),
  scanId: bigint('scan_id', { mode: 'number', unsigned: true }),
  tahap: varchar('tahap', { length: 120 }),
  versi: varchar('versi', { length: 40 }),
  host: varchar('host', { length: 120 }),
  mulaiPada: datetime('mulai_pada').notNull().default(sql`CURRENT_TIMESTAMP`),
  terakhirTerlihat: datetime('terakhir_terlihat').notNull().default(sql`CURRENT_TIMESTAMP`),
});
