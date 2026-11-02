# SATYA — Backend

API Express 5 + MySQL (Drizzle ORM) untuk SATYA. Struktur mengikuti kappee-lite:
`src/features/<fitur>/<fitur>.{route,controller,service,repository,validation}.js`.

Tahap ini: **autentikasi** (daftar, masuk, lupa & atur ulang kata sandi) dan **verifikasi akun oleh admin**.

## Menjalankan

```sh
npm install
cp .env.example .env        # isi DATABASE_URL & JWT_ACCESS_SECRET
npm run db:create           # buat database dari DATABASE_URL bila belum ada
npm run db:migrate          # jalankan migrasi di drizzle/
npm run admin:create        # buat administrator pertama (langsung terverifikasi)
npm run catalog:seed        # isi katalog kontrol dari ../controls/bssn_web.yaml (sekali, saat katalog kosong)
npm run dev                 # http://localhost:3000
npm test                    # unit test (tanpa database)
```

Frontend: set `VITE_USE_MOCK=false` di `frontend/.env`; Vite meneruskan `/api` ke port 3000.

## Alur akun
1. Pengguna **mendaftar** (`POST /api/v1/auth/register`) dengan memilih satuan dari daftar (`GET /api/v1/units`)
   → akun `pemilik`, `is_verified = false`.
2. **Admin memverifikasi** (`PATCH /api/v1/users/:id/verify`, bisa sekaligus memilih peran) atau **menolak**
   (`DELETE /api/v1/users/:id`, data pendaftaran dihapus).
3. Sebelum diverifikasi, login dengan kata sandi benar ditolak `403 ACCOUNT_PENDING`.

## Keamanan (selaras kontrol yang dinilai SATYA sendiri)
| Kontrol BSSN | Penerapan |
|---|---|
| 1.2 / 1.3 | Validasi & kebijakan kata sandi di server: 8–72 karakter, huruf besar, kecil, angka, simbol |
| 1.4 | Akun dikunci `LOGIN_LOCK_MINUTES` setelah `LOGIN_MAX_ATTEMPTS` gagal (`423 ACCOUNT_LOCKED`) + rate limit per IP |
| 1.5 | Lupa kata sandi: respons selalu sama, token acak sekali pakai (hanya hash sha256 yang disimpan), kedaluwarsa `PASSWORD_RESET_TTL_MINUTES`, sesi lama dicabut setelah reset |
| 1.6 | Kata sandi di-hash bcrypt (cost 12); bcrypt tetap dijalankan untuk email tak terdaftar (anti-timing) |
| 2.x | Access token JWT 15 menit + refresh token berotasi; pemakaian ulang token lama mencabut semua sesi |
| 6.1 / 6.3 | Pesan galat generik + kode request; log audit keamanan (lihat *Logging*) dengan penyamaran kata sandi/token |

Lupa kata sandi dan `register` tidak membocorkan apakah email terdaftar. **Pengecualian yang disengaja:** stepper
pendaftaran memeriksa NRP/NIP & email lewat `POST /auth/check-availability` demi UX, sehingga keberadaan akun bisa
ditebak secara terbatas; risikonya diredam rate limit 10 pemeriksaan / 15 menit per IP (`availabilityLimiter`). Status akun (pending/nonaktif)
hanya diungkap setelah kata sandi terbukti benar.

## Daftar satuan/instansi
Satuan tidak diketik bebas: pendaftar mencari & memilih dari tabel `units` (`GET /units?search=`, maks. 50 hasil)
dan mengirim `satuan_id`. Satuan yang tidak ada atau nonaktif ditolak `400`. Data awal di `drizzle/0001_units.sql`
masih **contoh**.

Admin mengelola daftarnya di menu **Administrasi → Satuan Kerja** (`/api/v1/admin/units`): tambah, ganti nama, dan
aktif/nonaktifkan. Nama unik (tidak membedakan huruf besar; spasi ganda dirapikan). Satuan nonaktif hilang dari
pilihan pendaftaran, tetapi akun yang sudah merujuknya tetap sah; satuan tidak bisa dihapus selama dipakai akun.

## Aset aplikasi
Tabel `applications` hanya menyimpan **data dasar** aset: nama, deskripsi, satuan pemilik, PIC, URL dasar (unik),
lingkungan, klasifikasi data, dan teknologi. Persiapan pengujian (verifikasi kepemilikan, titik uji, akun uji, izin
intrusif) disimpan terpisah per pengujian (fitur pengujian, menyusul).

## Katalog kontrol
Katalog (fungsi keamanan → kontrol → metode pengujian, serta titik uji) disimpan di tabel `catalog_*`. Isi awal dari
`controls/bssn_web.yaml` lewat `npm run catalog:seed`; perintah ini **menolak berjalan bila katalog sudah terisi** agar
perubahan admin tidak tertimpa. Selanjutnya admin mengelola kontrol & metode di menu **Katalog Kontrol**: tambah, ubah,
nonaktifkan (tidak ada hapus, agar hasil pengujian lama tetap terbaca). Kode kontrol = `<FUNGSI>-<nomor>` (tetap),
kode metode = `<KONTROL>-Tnn` (dibuat otomatis). Fungsi keamanan & titik uji tidak diubah lewat aplikasi.
`parameter` kontrol/metode (nilai yang dibaca pemeriksa, mis. `batas_percobaan`) bisa diedit: nama kunci snake_case,
maks. 30 kunci, 6 tingkat, 20.000 karakter; `null`/objek kosong menghapus parameter.

## Logging
Saat ini log **hanya tampil di terminal** (`LOG_TO_FILE=false`). Set `LOG_TO_FILE=true` untuk juga menulis file JSON
harian ke `LOG_DIR` (disimpan 14 hari). Development: baris berwarna + metadata ringkas; production: JSON per baris.

- **Startup**: ringkasan konfigurasi (tanpa rahasia), cek koneksi MySQL, galat port terpakai.
- **Setiap request**: `METHOD path status durasi` + kode request (header `X-Request-Id`), IP, user, user-agent.
  Galat 4xx dicatat di level `debug` beserta detail validasinya; galat 5xx di level `error` dengan stack & body (tersamar).
- **Audit keamanan** (ditandai `[AUDIT]`, field `kategori: "audit"` dan `event`):

| Event | Kapan |
|---|---|
| `auth.daftar`, `auth.daftar.duplikat` | pendaftaran baru / email-NRP sudah terdaftar |
| `auth.cek_ketersediaan` | stepper memeriksa NRP/email (nilainya tidak dicatat) |
| `auth.login.berhasil`, `auth.login.gagal` | login; `alasan`: `sandi_salah`, `email_tidak_terdaftar`, `terkunci`, `belum_diverifikasi`, `nonaktif` |
| `auth.akun.dikunci` | batas login gagal tercapai |
| `auth.refresh.reuse` | refresh token lama dipakai ulang (indikasi pencurian), semua sesi dicabut |
| `auth.logout` | logout |
| `auth.lupa_sandi`, `auth.reset_sandi.berhasil`, `auth.reset_sandi.gagal` | alur atur ulang kata sandi |
| `auth.ganti_sandi.berhasil`, `auth.ganti_sandi.gagal` | ganti kata sandi dari menu akun (sesi lain dicabut) |
| `pengguna.verifikasi`, `pengguna.tolak`, `pengguna.status` | tindakan admin (pelaku = `userId`, sasaran = `targetUserId`) |
| `katalog.kontrol.tambah/ubah`, `katalog.metode.tambah/ubah` | admin mengubah katalog (`kode`, `kolom` yang berubah) |
| `aplikasi.daftar`, `aplikasi.ubah` | registrasi / perubahan data aset aplikasi (`kolom` yang berubah) |
| `satuan.tambah`, `satuan.ubah` | admin menambah satuan / mengganti nama (`namaLama` → `namaBaru`) / mengubah status |
| `akses.ditolak` | peran tidak cukup (403) |
| `rate_limit.terlampaui` | rate limit tercapai (`limiter`: login, daftar, cek_ketersediaan, reset_sandi) |

Kata sandi, token, header Authorization, dan API key selalu diganti `[disamarkan]` sebelum ditulis.

## Email (Resend)
Email atur ulang kata sandi dikirim lewat [Resend](https://resend.com) (`RESEND_API_KEY`, `MAIL_FROM`).
`MAIL_FROM` harus memakai domain yang sudah diverifikasi di Resend; `onboarding@resend.dev` hanya untuk uji.
Tanpa `RESEND_API_KEY` di development, isi email (termasuk tautan reset) dicatat di log server.

## Endpoint
Semua respons: `{ success, message, data }`; galat: `{ success: false, message, code?, errors? }`.

| Metode | Path | Akses |
|---|---|---|
| GET | `/api/v1/units` (daftar satuan aktif) | publik |
| POST | `/api/v1/auth/register` `{ nama, nrp, satuan_id, email, password }` | publik |
| POST | `/api/v1/auth/check-availability` `{ nrp }` atau `{ email }` → `{ tersedia }` | publik (10/15 menit per IP) |
| POST | `/api/v1/auth/login` | publik |
| POST | `/api/v1/auth/refresh` | publik |
| POST | `/api/v1/auth/forgot-password` | publik |
| POST | `/api/v1/auth/reset-password` | publik |
| GET | `/api/v1/auth/me` | login |
| POST | `/api/v1/auth/change-password` `{ passwordLama, passwordBaru }` → token baru | login (5 gagal / 15 menit per pengguna) |
| POST | `/api/v1/auth/logout` | login |
| GET | `/api/v1/users?status=pending\|verified\|inactive&search=` | admin |
| PATCH | `/api/v1/users/:id/verify` `{ peran }` | admin |
| PATCH | `/api/v1/users/:id/status` `{ aktif }` | admin |
| DELETE | `/api/v1/users/:id` (tolak pendaftaran) | admin |
| GET | `/api/v1/applications?search=&page=&limit=` (pemilik: satuannya; asesor/admin: semua) | login |
| GET | `/api/v1/applications/:id` (di luar cakupan → 404) | login |
| POST | `/api/v1/applications` (pemilik: satuan sendiri; admin boleh `satuan_id`; URL ganda → 409) | pemilik, admin |
| PATCH | `/api/v1/applications/:id` | pemilik (satuan sama), admin |
| GET | `/api/v1/catalog` (termasuk butir nonaktif, `aktif: false`) | login |
| POST | `/api/v1/catalog/functions/:kode/controls` (409 bila kode ada) | admin |
| PATCH | `/api/v1/catalog/controls/:kode` | admin |
| POST | `/api/v1/catalog/controls/:kode/methods` | admin |
| PATCH | `/api/v1/catalog/methods/:kode` | admin |
| GET | `/api/v1/admin/units?search=&status=aktif\|nonaktif&page=&limit=` | admin |
| POST | `/api/v1/admin/units` `{ nama, aktif? }` (409 bila nama sudah ada) | admin |
| PATCH | `/api/v1/admin/units/:id` `{ nama?, aktif? }` | admin |
| PUT | `/api/v1/apps/:id/scan-target` `{ test_points, forms }` (persiapan uji) | pemilik, admin |
| POST | `/api/v1/apps/:id/scans` (mulai scan; 400 bila scan-target belum diisi) | pemilik, admin |
| GET | `/api/v1/scans?app=:id` · `/api/v1/scans/:id` | login |
| GET | `/api/v1/scans/:id/events` (SSE `EventScan`) | login |
| POST | `/api/v1/scans/:id/cancel` | login (cakupan sama) |

## Pengujian (scan) & worker
Backend mengorkestrasi scan; eksekusi pengujian ada di **worker** terpisah (lihat `../worker/`).
Tahap ini worker menguji fungsi **Autentikasi (AUTH 1.1–1.7)** dan **Manajemen Sesi (SESS 2.1–2.7)**,
engine custom; metode engine playwright/zap & manual diserahkan asesor. Seed scan menyemai semua
metode fungsi `AUTH` + `SESS` (`FUNGSI` di `scans.service.js`, lewat `functionsWithControls`). SESS
memakai data persiapan Autentikasi yang sama; isi `area_terautentikasi` dengan endpoint API (mis.
`/api/v1/auth/me`).

**Dua mode** (`POST /apps/:id/scans` body `{ mode }`): `terarah` (butuh data persiapan) atau
`eksploratif` (hanya URL + `persetujuan: true`). Mode eksploratif menyemai satu task `discovery`;
worker meng-crawl aplikasi dan mengirim hasil ke `POST /internal/scans/:id/discovery`, yang mengisi
`scan_targets` otomatis (manual menang) lalu menyemai task pengujian (fase 2). Persetujuan eksploratif
mengaktifkan metode intrusif untuk scan tersebut (override di memori, tidak disimpan ke aset).

**scan_targets.accounts** menyimpan kredensial akun uji (username+password) yang diteruskan ke
worker untuk check ber-login (1.3-T04, 1.4-T01, 1.6-T01) dan `options.izinkan_penguncian`
menggerbang uji intrusif (1.4-T01). ⚠️ **Untuk produksi, kolom `accounts` harus dienkripsi**
(saat ini plaintext untuk pengembangan).

Alur: `POST /apps/:id/scans` → backend menyemai baris `scans` + `scan_tasks` dari katalog AUTH + SESS
(metode manual/tak-berlaku langsung `selesai`, sisanya `antre`) → worker **klaim task** lewat
`POST /internal/tasks/claim` (`SELECT … FOR UPDATE SKIP LOCKED`) → worker menguji target →
`POST /internal/tasks/:id/result` → backend menyimpan hasil, menyiarkan `EventScan` ke pelanggan SSE,
dan memfinalisasi scan saat semua task selesai.

- **scan_targets** (`PUT /apps/:id/scan-target`): pemetaan titik uji → URL nyata & template form per aplikasi.
  Wajib diisi sebelum scan (worker perlu tahu endpoint registrasi & nama field). Akun uji belum disimpan,
  jadi metode `butuh_autentikasi` berstatus `tidak_dapat_diverifikasi`.
- **Endpoint `/internal/*`** dilindungi header `X-Worker-Token` (= `WORKER_TOKEN`), **bukan** JWT pengguna;
  tanpa `WORKER_TOKEN` dikonfigurasi, seluruh `/internal` ditolak. Task yang dikunci worker tetapi tak
  selesai dalam `WORKER_TASK_TIMEOUT_MS` dikembalikan ke antrean.
- **Audit**: `scan.mulai`, `scan.selesai`, `scan.batal`, `scan.target.simpan`.
- Seed target SATYA untuk uji mandiri: `npm run scan-target:seed <applicationId>`.
