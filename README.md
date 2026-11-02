# SATYA

**Sistem Asesmen Kelaikan Keamanan Aplikasi** — platform untuk menilai kelaikan keamanan aplikasi
berbasis web terhadap **Peraturan BSSN No. 4 Tahun 2021** (Standar Teknis Keamanan Aplikasi Berbasis Web).

Pemilik aplikasi mendaftarkan aplikasinya, sistem menjalankan pemindaian (scan) per kontrol BSSN,
asesor meninjau hasil dan bukti, lalu laporan beserta putusan kelaikan diterbitkan.

## Struktur Repositori

```
satya/
├── backend/    API Express 5 + MySQL (Drizzle ORM) — autentikasi & manajemen pengguna
├── frontend/   SvelteKit (SPA) + Svelte 5 + Tailwind 4 + shadcn-svelte, tema Army
└── controls/   Katalog kontrol BSSN
    ├── bssn_web.yaml   katalog terstruktur: fungsi keamanan → kontrol → metode pengujian
    └── raw.text        uraian kontrol yang disalin dari peraturan
```

Detail tiap bagian:
- [`backend/README.md`](backend/README.md) — instalasi, alur akun, penerapan keamanan, daftar endpoint
- [`frontend/README.md`](frontend/README.md) — mode demo, akun contoh, struktur kode
- [`frontend/API_CONTRACT.md`](frontend/API_CONTRACT.md) — kontrak API frontend ↔ backend

## Peran Pengguna

| Peran | Kemampuan |
|---|---|
| Pemilik aplikasi | Mendaftarkan aplikasi, menjalankan scan, melihat laporan |
| Asesor | Meninjau antrean hasil scan, menilai kontrol manual, memberi putusan |
| Administrator | Memverifikasi pendaftar, mengatur peran & status akun, konfigurasi AI |

Akun baru berstatus *belum terverifikasi* sampai disetujui administrator.

## Persyaratan

- Node.js **≥ 20.6**
- MySQL (hanya bila memakai backend; mode demo frontend tidak membutuhkannya)

## Mulai Cepat

### Opsi A — Mode demo (frontend saja)

```sh
cd frontend
npm install
npm run dev          # http://localhost:5173
```

`VITE_USE_MOCK=true` (bawaan) membuat data tiruan tersimpan di localStorage dan scan disimulasikan.
Akun contoh ada di [`frontend/README.md`](frontend/README.md).

### Opsi B — Dengan backend

```sh
# Terminal 1 — backend
cd backend
npm install
cp .env.example .env     # isi DATABASE_URL & JWT_ACCESS_SECRET
npm run db:create        # buat database bila belum ada
npm run db:migrate       # jalankan migrasi
npm run admin:create     # buat administrator pertama
npm run dev              # http://localhost:3000

# Terminal 2 — frontend
cd frontend
npm install
# set VITE_USE_MOCK=false di frontend/.env
npm run dev              # http://localhost:5173 (meneruskan /api ke port 3000)
```

## Katalog Kontrol

`controls/bssn_web.yaml` adalah sumber tunggal kontrol yang dinilai. Setiap kontrol memiliki satu
atau lebih metode pengujian dengan atribut seperti `verifiabilitas` (otomatis/sebagian/manual),
`engine` (custom, ZAP, Nuclei, SSLyze, Playwright, manual), `profil` (aman/intrusif), dan `severity`.
Pengujian berprofil *intrusif* hanya dijalankan pada target yang berizin.

Frontend mengubah YAML ini menjadi `src/lib/data/catalog.json` secara otomatis saat `npm run dev`
atau `npm run build` (bisa juga manual dengan `npm run catalog`).

## Status Pengembangan

| Bagian | Status |
|---|---|
| Autentikasi (daftar, masuk, lupa/atur ulang sandi, refresh token) | ✅ backend |
| Verifikasi & manajemen pengguna oleh admin | ✅ backend |
| Registrasi aplikasi, scan, tinjauan asesor, laporan, katalog, pengaturan AI | 🟡 antarmuka selesai, masih memakai mock |

Endpoint yang belum tersedia di backend tercantum di [`frontend/API_CONTRACT.md`](frontend/API_CONTRACT.md).

## Pengujian

```sh
cd backend && npm test       # unit test (tanpa database)
cd frontend && npm run check # pemeriksaan tipe Svelte/TypeScript
```
