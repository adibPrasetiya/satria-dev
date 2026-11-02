# Kontrak API SATYA (frontend ↔ Express)

Tipe data lengkap ada di `src/lib/types.ts`; antarmuka klien di `src/lib/api/types.ts`.
Implementasi acuan perilaku: `src/lib/api/mock/` (mode demo).

Konvensi (sama dengan `backend/`, pola kappee-lite):
- Base path `/api/v1`; JSON. Respons sukses `{ success: true, message, data }`; galat `{ success: false, message, code?, errors? }`
  (`errors` = daftar `{ field, message }` dari validasi). Klien membuka amplop ini di `src/lib/api/http.ts`.
- Sesi: access token JWT di header `Authorization: Bearer` + refresh token berotasi (`POST /auth/refresh`).
- Kata sandi akun uji dan API key AI **hanya diterima, tidak pernah dikembalikan**; respons memakai `terisi: true` / `api_key_terisi: true`.

## Sudah tersedia di backend
Detail perilaku & keamanan: `backend/README.md`.

| Metode | Path | Body | Respons |
|---|---|---|---|
| GET | `/units?search=&limit=` | — (publik) | `Satuan[]` = `{ id, nama }[]`: satuan aktif yang namanya mengandung `search`, urut nama, maks. `limit` (bawaan 20, maks. 50) |
| POST | `/auth/check-availability` | `{ nrp }` **atau** `{ email }` | `{ tersedia: boolean }`; 429 setelah 10 cek / 15 menit per IP |
| POST | `/auth/register` | `PendaftaranAkun` (`satuan_id` dari `/units`; 400 bila tidak ada di daftar) | 202 — akun pemilik, **belum terverifikasi**; respons sama walau email/NRP sudah ada |
| POST | `/auth/login` | `{ email, password }` | `{ accessToken, refreshToken, tokenType, user: Pengguna }`; 401 salah, 403 `ACCOUNT_PENDING`/`ACCOUNT_INACTIVE`, 423 `ACCOUNT_LOCKED` |
| POST | `/auth/refresh` | `{ refreshToken }` | sama seperti login |
| POST | `/auth/forgot-password` | `{ email }` | 202 — respons selalu sama; email (Resend) berisi `APP_URL/reset-sandi?token=…` |
| POST | `/auth/reset-password` | `{ token, password }` | 200; 400 bila tautan tidak valid/kedaluwarsa |
| GET | `/auth/me` | — | `Pengguna` |
| POST | `/auth/change-password` | `{ passwordLama, passwordBaru }` (login) | token baru (sesi lain dicabut); 400 bila sandi lama salah/sama; 429 setelah 5 gagal / 15 menit |
| POST | `/auth/logout` | `{ refreshToken }` | 200 |
| GET | `/users?status=&search=&page=&limit=` | — (admin) | `{ items: Pengguna[], meta }` |
| PATCH | `/users/:id/verify` | `{ peran }` (admin) | `Pengguna` |
| PATCH | `/users/:id/status` | `{ aktif }` (admin) | `Pengguna` |
| GET | `/catalog` | — | `Katalog` dari database (termasuk butir nonaktif, `aktif: false`) |
| POST | `/catalog/functions/:kode/controls` | `KontrolBaru` (admin) | `Kontrol`; 409 bila kode sudah ada |
| PATCH | `/catalog/controls/:kode` | `Partial<KontrolBaru> & { aktif? }` (admin) | `Kontrol` |
| POST | `/catalog/controls/:kode/methods` | `MetodeBaru` (admin) | `Metode` (kode `<KONTROL>-Tnn`) |
| PATCH | `/catalog/methods/:kode` | `Partial<MetodeBaru> & { aktif? }` (admin) | `Metode` |
| GET | `/applications?search=&page=&limit=` | — | `{ items, meta }` aset (data dasar); pemilik hanya satuannya |
| GET | `/applications/:id` | — | aset; 404 bila di luar cakupan |
| POST | `/applications` | `AsetBaru` (pemilik/admin) | 201 aset; 409 bila URL dasar sudah terdaftar |
| PATCH | `/applications/:id` | `Partial<AsetBaru>` (pemilik satuan sama/admin) | aset |
| GET | `/admin/units?search=&status=aktif\|nonaktif&page=&limit=` | — (admin) | `{ items: SatuanAdmin[], meta }` |
| POST | `/admin/units` | `{ nama, aktif? }` (admin) | 201 `SatuanAdmin`; 409 bila nama sudah ada |
| PATCH | `/admin/units/:id` | `{ nama?, aktif? }` (admin) | `SatuanAdmin`; 404 / 409 |
| DELETE | `/users/:id` | — (admin, hanya akun belum terverifikasi) | 200 |
| PUT | `/apps/:id/scan-target` | `{ test_points, forms }` (pemilik/admin) | `{ aplikasi_id, test_points, forms }` — persiapan uji (pemetaan titik uji → URL & template form) |
| GET | `/scans?app=:id` | — | `Scan[]` terbaru dulu (pemilik: hanya satuannya) |
| POST | `/apps/:id/scans` | — (pemilik/admin) | 201 `Scan` (status `berjalan`); 400 bila `scan-target` belum diisi |
| GET | `/scans/:id` | — | `Scan` (404 bila di luar cakupan) |
| POST | `/scans/:id/cancel` | — | `Scan` (status `dibatalkan`) |
| GET | `/scans/:id/events` | — | **SSE**, tiap `data:` berisi `EventScan` (`metode` / `log` / `status`) |

> Cakupan scan tahap ini: **hanya kontrol AUTH-1.3** (kebijakan kata sandi) yang benar-benar diuji worker.
> Metode lain pada kontrol tersebut → `tidak_berlaku` (titik uji belum dipetakan), `tidak_dapat_diverifikasi`
> (butuh akun uji / engine belum didukung), atau `menunggu_tinjauan` (manual). Lihat `worker/README.md`.

## Belum tersedia (frontend sementara memakai mock — lihat `src/lib/api/client.ts`)

| Metode | Path | Body | Respons |
|---|---|---|---|
| POST | `/apps/:id/verify-ownership` | — | `Aplikasi` (cek DNS TXT `_satya.<host>` atau `/.well-known/satya-verify.txt`) |
| POST | `/apps/:id/intrusive-permit` | `{ dokumen_nama, jendela_mulai, jendela_selesai }` | `Aplikasi` (status `menunggu`) |
| POST | `/approvals/:appId` | `{ disetujui, catatan }` — peran asesor | `Aplikasi` |
| POST | `/scans/:id/evidence` | `{ metode_id, jenis, judul, nama_file }` (+ unggah berkas) | `Scan` |
| POST | `/scans/:id/reviews` | `{ metode_id, putusan, catatan }` — peran asesor | `Scan` |
| GET | `/reviews/queue` | — | `ItemTinjauan[]` |
| POST | `/scans/:id/ai` | — | `Scan` dengan field `ai` terisi |
| GET/PUT | `/settings/ai` | `PengaturanAi` | `PengaturanAi` — peran admin |

## Aturan penting di backend
- Penerapan metode (berlaku / tidak berlaku / belum dapat diuji) mengikuti `penerapanMetode()` di `src/lib/catalog.ts`.
- Status kontrol & putusan kelaikan dihitung di frontend (`statusKontrol`, `nilaiKelaikan`) dari `Scan.hasil`; backend cukup menyimpan hasil per metode.
- Metode `profil: intrusif` hanya boleh dijalankan worker bila `izin_intrusif.status = 'disetujui'` dan waktu sekarang di dalam jendela izin.
- Sebelum dikirim ke AI: buang kredensial, cookie/token, dan samarkan host/IP/URL bila `redaksi = true`.
