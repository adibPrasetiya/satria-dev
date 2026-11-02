# SATYA — Frontend

Antarmuka Sistem Asesmen Kelaikan Keamanan Aplikasi (Peraturan BSSN No. 4 Tahun 2021).
SvelteKit 3 (SPA, adapter-static) · Svelte 5 · Tailwind 4 · shadcn-svelte · tema Army (loreng).

## Menjalankan

```sh
npm install
npm run dev        # http://localhost:5173 — otomatis membangun katalog dari ../controls/bssn_web.yaml
npm run check      # pemeriksaan tipe
npm run build      # keluaran statis di build/
```

Mode demo aktif secara bawaan (`VITE_USE_MOCK=true` di `.env`): data tiruan disimpan di localStorage,
scan disimulasikan. Masuk dengan email contoh berikut (kata sandi bebas di mode demo):

| Peran | Email |
|---|---|
| Pemilik aplikasi | rina.w@contoh.mil.id |
| Asesor | budi.s@contoh.mil.id |
| Administrator | admin@contoh.mil.id |
| Pendaftar (belum diverifikasi — coba verifikasi lewat Admin → Pengguna) | bagas.w@contoh.mil.id |
Set `VITE_USE_MOCK=false` untuk memakai backend Express (`../backend`); `/api` di-proxy ke `http://localhost:3000`.
Saat ini backend baru menangani autentikasi & verifikasi pengguna; fitur lain tetap memakai mock
(lihat `src/lib/api/client.ts` dan `API_CONTRACT.md`).

## Struktur
- `scripts/build-catalog.mjs` — YAML katalog → `src/lib/data/catalog.json`
- `scripts/build-login-assets.mjs` — foto root → `static/login/latar.webp` + potongan prajurit beralpha (`npm run login-assets`)
- `scripts/build-loreng.mjs` — membangkitkan pola loreng `static/loreng.svg`
- `src/lib/catalog.ts` — penerapan metode, agregasi kontrol, putusan kelaikan
- `src/lib/api/` — kontrak (`types.ts`), mock, dan klien HTTP
- `src/routes/` — login, dasbor, aplikasi (daftar/registrasi/detail), scan, laporan, asesor, katalog, admin

Catatan: import `#lib/...` wajib memakai ekstensi (`#lib/types.js`); `node scripts/fix-imports.mjs` merapikannya.
