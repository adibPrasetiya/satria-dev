# SATYA — Worker Pengujian (AUTH + SESS)

Worker Python yang menjalankan metode uji **fungsi keamanan Autentikasi (AUTH 1.1–1.7)** dan
**Manajemen Sesi (SESS 2.1–2.7)**
terhadap aplikasi target yang berjalan, lalu mengembalikan `HasilMetode` yang formatnya
sama persis dengan tipe di `frontend/src/lib/types.ts`.

Ini worker **pertama**; arsitektur penuh (antrean task, endpoint `/internal` backend,
check kontrol lain) ada di rencana. Lihat juga `controls/bssn_web.yaml` fungsi `AUTH`.

## Mengapa Python

`sslyze` (TLS) native Python, klien HTTP `httpx`, Playwright setara, dan worker berjalan
sebagai proses terpisah dari API Express sehingga beban/crash scan tidak mengganggu API.
Kontrak worker ↔ backend berbasis HTTP/JSON, jadi bahasa tidak mengikat.

## Granularitas worker

Bukan 1 worker per metode, bukan 1 worker per fungsi keamanan. Satuannya:

| Satuan | Isi |
|---|---|
| **check** (kode) | satu kelas per `check_id` katalog, didaftarkan di `registry.py` |
| **scan** (job) | satu permintaan scan, dipecah menjadi task per metode |
| **pool** (skala) | dipisah per `engine`/profil (`custom` ringan vs `playwright` berat) |

Fungsi keamanan hanya jadi **folder** (`checks/auth/`), bukan batas layanan.

## Metode yang ditangani (fungsi Autentikasi, engine custom)

| Metode | check_id | Titik uji | Butuh login | Catatan |
|---|---|---|---|---|
| AUTH-1.1-T01 | `auth.login_required` | area_terautentikasi | — | area terbatas ditolak tanpa auth (401/403/redirect) |
| AUTH-1.1-T02 | `auth.password_field_masked` | login_page | — | input sandi type=password (parse HTML; SPA → tak dapat diverifikasi) |
| AUTH-1.2-T01 | `auth.server_side_validation` | login | — | kredensial acak ditolak server (4xx) |
| AUTH-1.2-T02 | `auth.password_policy.server_side` | registrasi | — | sandi lemah ditolak |
| AUTH-1.3-T01 | `auth.password_policy.min_length` | registrasi | — | sandi di bawah panjang minimum ditolak |
| AUTH-1.3-T02 | `auth.password_policy.complexity` | registrasi | — | sandi tanpa kombinasi ditolak |
| AUTH-1.3-T04 | `auth.password_policy.min_length+complexity` | ubah_password | ✔ | login → ubah sandi jadi lemah → ditolak |
| AUTH-1.4-T01 | `auth.lockout_threshold` | login | ✔ (penguncian) | **intrusif**: N+1 login gagal → 423/429/CAPTCHA/penundaan |
| AUTH-1.5-T01 | `auth.reset.no_user_enumeration` | reset_password | — | respons akun ada vs tidak ada identik |
| AUTH-1.6-T01 | `auth.password_not_echoed` | area_terautentikasi | ✔ | sandi tak muncul di profil |
| AUTH-1.7-T01 | `auth.login_over_https` | login | — | halaman+endpoint login HTTPS |
| AUTH-1.7-T02 | `tls.http_redirect` | login | — | akses HTTP → 301/308 ke HTTPS |

Metode engine **playwright** (1.3-T03, 1.5-T02) kini ditangani worker (lihat bagian *Engine
`playwright`*; reset butuh Resend). Metode **manual** (1.3-T05, 1.5-T03, 1.6-T02) tetap
diserahkan asesor → `tidak_dapat_diverifikasi` / menunggu tinjauan.

**Prinsip uji** (black-box, sisi server): bentuk permintaan yang melanggar kontrol dan kirim
langsung ke endpoint (melewati JavaScript klien). Server yang menegakkan kontrol menolak →
`lulus`; bila melanggar diterima → `gagal`. Check ber-login memakai `sesi.login` (cookie atau
token Bearer dari respons). Kredensial akun uji tak pernah masuk bukti/log (redaksi).

Status hasil: `lulus` | `gagal` | `tidak_berlaku` | `tidak_dapat_diverifikasi`.

## Metode yang ditangani (fungsi Manajemen Sesi, engine custom)

Memakai ulang data persiapan Autentikasi (titik uji `login`, akun uji `utama`) — tanpa form baru.
Endpoint probe sesi = titik uji `area_terautentikasi`; arahkan ke endpoint **API** yang 401 tanpa
token & 200 dengan token (mis. `/api/v1/auth/me`), bukan halaman SPA.

| Metode | check_id | Andal? | Catatan |
|---|---|---|---|
| SESS-2.1-T01 | `session.token_issued` | ✔ | login → ada artefak sesi (token di body / `Set-Cookie`) |
| SESS-2.2-T01 | `session.framework_fingerprint` | ✔ | token/cookie cocok pola kerangka dikenal (JWT 3-segmen, nama cookie umum) |
| SESS-2.3-T01 | `session.token_entropy` | ✔ | `jumlah_sampel` login → token unik, entropi ≥ `entropi_minimum_bit`, tak berurutan; token **JWT** → `tidak_dapat_diverifikasi` (entropi session-ID tak berlaku untuk token stateless) |
| SESS-2.5-T01 | `session.rotation_on_login` | ✔ | dua login (jeda >1 dtk) → token berbeda |
| SESS-2.5-T02 | `session.reject_unknown_id` | ✔ | token palsu ke `area_terautentikasi` → 401 |
| SESS-2.6-T01 | `session.cookie_flags` | ✔ | cookie sesi ber-Secure/HttpOnly/SameSite; sesi berbasis token → `tidak_dapat_diverifikasi` |
| SESS-2.4-T01 | `session.logout_invalidates` | asesor | semantik logout token/refresh app-spesifik; butuh titik uji `logout` (kosong → `tidak_berlaku`) |
| SESS-2.4-T02 | `session.idle_timeout` | asesor | batas idle ~30 menit tak dapat ditunggu worker |
| SESS-2.7-T01 | `session.concurrent_sessions` | asesor | bergantung kebijakan sesi ganda aplikasi |

Metode **zap** (2.6-T02) dan **manual** (2.2-T02, 2.7-T02) diserahkan asesor. Check SESS uji entropi
melakukan ~30 login, jadi relatif lambat terhadap target dengan bcrypt.

## Engine `zap` — pemindaian OWASP ZAP

Memetakan temuan ZAP ke metode katalog berengine `zap` (`checks/zap_scan.py` + `zap_client.py`).
Satu scan per target (spider + passive, plus active scan untuk metode intrusif) dipakai ulang oleh
semua check zap pada target yang sama (cache per-proses).

- **Pasif (profil aman)**: `tls.mixed_content`, `session.token_not_in_url`, `access.csrf_token`,
  `deps.vulnerable_js_libraries`, `api.sensitive_in_uri`, `conf.directory_listing`.
- **Aktif (profil intrusif)**: `zap.active.xss_policy`, `zap.active.sqli_policy`,
  `zap.active.injection_policy`, `zap.active.code_injection_policy`. Hanya disemai bila ada
  izin/persetujuan (gerbang intrusif di `applicability.js`).

Tiap check memfilter alert ZAP berdasarkan `pluginId`/CWE dan ambang risiko lalu menilai lulus/gagal.
Bila ZAP tak terjangkau target (0 URL ter-crawl) atau belum dikonfigurasi, hasilnya
`tidak_dapat_diverifikasi` — tidak menghakimi tanpa bukti.

Konfigurasi (env): `ZAP_BASE_URL` (mis. `https://zap.satria.pro` saat dev, `http://127.0.0.1:8080`
saat satu server), `ZAP_API_KEY` (kunci daemon ZAP — **berbeda dari `WORKER_TOKEN`**),
`ZAP_TIMEOUT_SPIDER`, `ZAP_TIMEOUT_ASCAN`. Jalankan worker dengan `zap` di `WORKER_ENGINES`.
Backend menyemai metode zap hanya bila engine `zap` didukung (`ENGINE_DIDUKUNG`); pastikan ada
worker zap yang berjalan agar task tidak menggantung.

## Engine `playwright` — browser nyata (library in-proses)

Berbeda dari ZAP (daemon REST) dan nuclei (biner CLI), **Playwright adalah library Python** yang
dipakai worker **in-proses** (`playwright_driver.py` + `checks/playwright_scan.py`). Tak ada daemon;
cukup venv Python 3.13 dan unduh browser sekali: `python -m playwright install chromium` (server
Linux tambah `python -m playwright install-deps`). Tanpa Playwright/browser, check playwright →
`tidak_dapat_diverifikasi` dan fallback (di bawah) non-aktif — tidak menghakimi.

Metode katalog ber-`engine: playwright`:

| Metode | check_id | Titik uji | Catatan |
|---|---|---|---|
| MALC-9.2-T02 | `deps.unknown_third_party_scripts` | global | skrip dari domain luar allowlist (`parameter.domain_diizinkan`/`domain_ditandai`) |
| MALC-9.3-T02 | `privacy.permission_prompts` | global | izin perangkat (kamera/mikrofon/geolokasi/notifikasi) diminta saat load |
| DATA-7.2-T02 | `data.browser_storage` | area_terautentikasi | login browser → localStorage/sessionStorage tak memuat sandi/data dikecualikan |
| AUTH-1.3-T03 | `auth.password_policy.min_length+complexity` | reset_password | kebijakan sandi ditegakkan saat reset (butuh Resend) |
| AUTH-1.5-T02 | `auth.reset.token_single_use_expiry` | reset_password | token reset sekali pakai (butuh Resend; kedaluwarsa tak diuji — di luar jendela worker) |

Navigasi global (skrip + izin) di-cache per target (satu muat untuk dua check), seperti cache ZAP.

**Otomasi reset (Resend inbound).** AUTH-1.3-T03 & AUTH-1.5-T02 menuntut pengguna baru didaftarkan
dan email reset diterima. Worker mendaftar pengguna uji beremail `@RESEND_INBOUND_DOMAIN`, memicu
"lupa sandi", lalu mengambil email lewat REST inbound Resend (`GET /emails/receiving`) untuk
mengekstrak tautan/token (`email_reset.py`). Tanpa `RESEND_API_KEY` + `RESEND_INBOUND_DOMAIN` (atau
tanpa titik uji `registrasi`), kedua metode → `menunggu_tinjauan`. Simpan `RESEND_API_KEY` via
vault/secret, jangan commit.

**Fallback browser untuk check AUTH/SESS yang ada.** Saat login httpx gagal (form digerakkan JS/SPA),
`sesi.login`/`login_ambil` otomatis mencoba `playwright_driver.login_browser` lalu menyuntik
cookie/token ke klien httpx — memperbaiki `session.*` (token_issued, framework_fingerprint,
token_entropy, rotation_on_login, cookie_flags), `auth.password_not_echoed`, ubah sandi, dan
lockout. `auth.password_field_masked` me-render SPA untuk menemukan `input[type=password]` nyata, dan
`auth.login_required` memeriksa pengalihan ke login di browser. Semua fallback lazy & opsional.

Konfigurasi (env): `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_NAV_TIMEOUT_MS`, `PLAYWRIGHT_BROWSER`,
`RESEND_API_KEY`, `RESEND_INBOUND_DOMAIN`. Jalankan worker dengan `playwright` di `WORKER_ENGINES`;
backend menyemai metode playwright hanya bila engine itu didukung (`ENGINE_DIDUKUNG`) — pastikan ada
worker playwright berjalan agar task tak menggantung.

## Mode eksploratif — fase penemuan (engine `discovery`)

Selain mode **terarah** (pengguna mengisi data persiapan), ada mode **eksploratif**: backend hanya
diberi URL aplikasi, lalu menyemai satu task `discovery`. Worker (engine `discovery`) menjalankan
`discovery.temukan(base_url)`:

1. **Crawl** dalam-host (`satya_worker/discovery.py`) — hanya GET, batas `MAKS_HALAMAN`/`MAKS_KEDALAMAN`, tanpa kirim form.
2. **Klasifikasi** form & tautan → titik uji (`login`, `registrasi`, `reset_password`, `ubah_password`,
   `unggah_file`, `area_terautentikasi`, dst.) dengan nama field diambil dari HTML.
   `login_page` (HALAMAN login frontend, GET HTML) dipisahkan dari `login` (endpoint AKSI, POST):
   form/tautan login merekam `login_page` dari URL halamannya, dan bila hanya endpoint API `login`
   yang terdeteksi (mis. SPA via OpenAPI), `login_page` **diinferensi** (`/login`, `/masuk`, … → root)
   agar check field-sandi & HTTPS memeriksa frontend, bukan endpoint API.
3. **Probe** jalur dokumentasi API umum (OpenAPI/Swagger).

Penemuan berjalan berlapis dan **mengirim log bertahap ke UI** (via `kirim_log` → SSE): apa yang
dicari, ditemukan, dan hasilnya. Lapisannya: (1) OpenAPI, (2) crawl HTML statis, (3a) **penemuan
browser (Playwright)** — kini bisa **terautentikasi** bila ada akun uji, (3b) **pengayaan ZAP**,
(4) **katana** (enumerasi endpoint mendalam), (5) **inventaris endpoint terpadu + pemetaan field +
alur proses bisnis**, dan (6) **enrichment AI** (opsional).

### Penemuan terautentikasi + MFA/TOTP

Bila `ScanContext` membawa akun uji (`scan_targets.accounts.utama`/`penguncian`, dialirkan juga ke
fase penemuan), worker **login lebih dulu** lalu menjelajah area terproteksi untuk menemukan endpoint
di balik autentikasi. Bila akun menyertakan `totp_secret` (base32), worker membangkitkan kode OTP
sendiri (`satya_worker/mfa.py`, `pyotp`) dan menyelesaikan langkah MFA — pada form httpx (fallback ke
browser saat MFA diminta) maupun login browser (`playwright_driver.login_browser` mengisi field OTP
lalu submit lagi). Tanpa `pyotp`/secret, langkah MFA dilewati dengan anggun.

### Inventaris endpoint + field + alur bisnis

`endpoint_map.py` menyatukan endpoint dari semua sumber (OpenAPI, form HTML, XHR/fetch browser,
katana, ZAP), dideduplikasi per `METODE + path_template` (segmen id → `{id}`), lengkap dengan
**field request** (query/body/path/header, tipe, wajib), status terlihat, sumber, dan inferensi
`butuh_autentikasi`. Hasil di `ringkasan.endpoints_lengkap` (+ `jumlah_endpoint_unik`). `flow_map.py`
menyusun **alur proses bisnis** kandidat (`ringkasan.flows`): alur autentikasi, CRUD per sumber daya,
dan alur teramati dari urutan navigasi/XHR browser. `test_points`/`forms` lama **tidak berubah** (seed
fase-2 tetap kompatibel).

### katana (opsional)

`katana_client.py` membungkus biner **katana** (projectdiscovery) via subprocess untuk enumerasi
endpoint mendalam termasuk yang tertanam di berkas JS, dengan scope dikunci ke FQDN target dan crawl
terautentikasi via cookie sesi (diambil dari login browser). Bukan paket pip — pasang terpisah:
`go install github.com/projectdiscovery/katana/cmd/katana@latest`, lalu set `KATANA_BIN` bila tak di
PATH. Tanpa biner (atau `KATANA_ENABLE=0`), tahap ini dilewati.

### Enrichment AI (opsional)

`satya_worker/ai/` memperkaya inventaris: deskripsi endpoint, semantik/sensitivitas field, dan narasi
alur bisnis (`ringkasan.ai`). Provider: **Gemini** (`google-genai`, utama) dan **Anthropic**
(`anthropic`, fallback) — keduanya diimpor lazy. **AI tidak pernah memutuskan lulus/gagal.** Nilai
field sensitif disamarkan sebelum dikirim (`AI_REDAKSI`, default aktif). Konfigurasi: `AI_PROVIDER`
(`gemini`|`anthropic`|`none`; kosong = auto), `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`AI_API_KEY`,
`AI_MODEL`, `AI_BAHASA`. Tanpa kunci/paket, enrichment dilewati dan hasil deterministik tetap utuh.

**(3a) Penemuan browser — `discovery_browser.py` (tak bergantung OpenAPI).** Untuk SPA (HTML awal
kosong), me-render aplikasi di Chromium, mengunjungi rute frontend umum + tautan router internal
(`/login`, `/register`, `/forgot-password`, dst.), membaca **form/input yang DIRENDER** (termasuk SPA
tanpa `<form>`: input `type=password` → `login_page`), dan **menyadap lalu lintas XHR/fetch** untuk
membangun **inventaris endpoint API sebenarnya** (`ringkasan.endpoints`, dipakai uji fungsi lain mis.
validasi input). Non-destruktif: hanya navigasi GET + baca DOM + amati jaringan (form tak disubmit);
endpoint aksi (POST login/registrasi) didapat dari `action` form atau XHR/fetch terpantau. Best-effort
— tanpa Playwright/Chromium, lapisan ini dilewati.

**(3b) Pengayaan ZAP** (`_enrich_zap`) — bila ZAP terkonfigurasi, menjalankan spider + ajax spider,
mengklasifikasi titik uji tambahan dari URL hasil ZAP (keyakinan sedang), mencatat temuan pasif awal
(header hilang, banner server, dll.) ke ringkasan, dan menitipkan alert ke cache engine `zap` agar
check zap pasif tidak mem-spider ulang. Semua best-effort: kegagalan ZAP tidak menggagalkan penemuan.

**Sumber paling akurat: OpenAPI/Swagger.** Untuk aplikasi SPA + API (HTML awal kosong, crawl tak
menemukan apa-apa), penemuan mengutamakan spesifikasi OpenAPI (`discovery_openapi.py`):
`cari_spec()` menemukan URL spec dari base_url (konvensi `/openapi.json`, `/api/v1/docs/…`, dll.,
termasuk membaca `url:` dari `swagger-ui-init.js` seperti Swagger UI modern); `muat_spec()`
mem-parse JSON (stdlib) atau YAML (`ruamel.yaml`, pure-Python, aman di 3.15); `dari_openapi()`
memetakan tiap `path` → titik uji (login/registrasi/ubah_password/logout/area_terautentikasi/…)
dengan URL absolut dan template form (nama field, resolve `$ref`). Bila base_url punya OpenAPI,
titik uji terisi `keyakinan: tinggi` tanpa perlu crawl. Hint eksplisit bisa diisi via
`scan_targets.options.openapi_url`.

Hasil dikirim ke `POST /internal/scans/:id/discovery`; backend menyimpannya ke `scan_targets`
(tiap titik diberi `sumber: "otomatis"` + `keyakinan`), **tanpa menimpa data manual**, lalu menyemai
task fase pengujian (AUTH + SESS). Setelah itu check yang sama seperti mode terarah berjalan.

Jalankan satu worker untuk keduanya: `WORKER_ENGINES=custom,discovery` (default).

## Menjalankan

```sh
cd worker
py -3.13 -m venv .venv          # Python 3.13 (Playwright/greenlet belum ada wheel utk 3.15)
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium   # unduh browser (engine playwright + fallback)
cp .env.example .env            # isi BACKEND_URL & WORKER_TOKEN (sama dengan backend)

# Mode LOOP (bawaan) — tersambung ke backend:
.venv/Scripts/python -m satya_worker.main

# Mode CONTEXT — uji lokal tanpa backend (cetak HasilMetode ke stdout):
.venv/Scripts/python -m satya_worker.main --context contoh.context.json
```

**Mode loop** mem-poll `POST {BACKEND_URL}/internal/tasks/claim`; untuk tiap task yang
diklaim, worker menjalankan check lalu mengirim hasil ke `POST /internal/tasks/{id}/result`
(header `X-Worker-Token`). Worker **tidak pernah menyentuh MySQL** — seluruh antrean lewat HTTP.
Ctrl+C menghentikan worker secara rapi. Konfigurasi lewat env (lihat `.env.example`):
`BACKEND_URL`, `WORKER_TOKEN`, `WORKER_ID`, `WORKER_ENGINES`, `POLL_INTERVAL`.

**Mode context** (`contoh.context.json`) adalah bentuk `ScanContext` + daftar `metode` untuk
uji cepat tanpa backend: URL dasar, pemetaan titik uji, template form, akun uji.

## Uji

```sh
.venv/Scripts/python -m pytest
```

Tiap check diuji terhadap **target palsu** (`tests/target_palsu.py`) versi `aman`
(menolak sandi lemah → harus `lulus`) dan `rentan` (menerima → harus `gagal`), plus
kasus titik uji tak tersedia, akun uji kosong, check tak dikenal, dan penyamaran sandi.

Coba manual dengan target palsu:

```sh
.venv/Scripts/python -m tests.target_palsu --mode rentan --port 8081
# di terminal lain:
.venv/Scripts/python -m satya_worker.main --context contoh.context.json
```

## Keamanan worker

- **Ruang lingkup**: hanya mengirim request ke host aset (`http_client.KlienScan`).
- **Penyamaran**: kata sandi/token/cookie/authorization diganti `[disamarkan]` pada bukti
  sebelum keluar dari worker.
- **Intrusif**: metode profil intrusif (bukan di 1.3) hanya dijalankan bila izin backend
  menyetujui; di luar jendela → `tidak_dapat_diverifikasi`.

## Struktur

```
worker/
├── satya_worker/
│   ├── models.py          # ScanContext, MetodeSpec, HasilMetode, Bukti (↔ types.ts)
│   ├── http_client.py     # klien httpx: scope guard + rekam bukti + penyamaran
│   ├── registry.py        # @check("<check_id>")
│   ├── runner.py          # cari check → jalankan; tak dikenal → tidak_dapat_diverifikasi
│   ├── backend_client.py  # klien /internal: claim / result / log / discovery (mode loop)
│   ├── discovery.py       # fase penemuan: orkestrasi OpenAPI+HTML+browser+ZAP+katana+inventaris+flow+AI
│   ├── discovery_openapi.py # parse spec OpenAPI → titik uji + form + field detail (endpoint_fields)
│   ├── discovery_browser.py # penemuan SPA via Playwright: login terautentikasi + sadap XHR/fetch lengkap
│   ├── endpoint_map.py    # inventaris endpoint terpadu + pemetaan field + inferensi butuh_autentikasi
│   ├── flow_map.py        # alur proses bisnis kandidat (auth, CRUD, teramati)
│   ├── katana_client.py   # pembungkus biner katana (subprocess, opsional) — enumerasi endpoint mendalam
│   ├── mfa.py             # kode TOTP (MFA) dari totp_secret (pyotp, lazy)
│   ├── ai/               # enrichment AI (opsional): Gemini (utama) + Anthropic (fallback) + redaksi
│   ├── zap_client.py      # klien REST OWASP ZAP (spider/ajax/active/alerts)
│   ├── playwright_driver.py # browser in-proses: instrumentasi skrip/izin, login_browser (+MFA), submit_reset
│   ├── email_reset.py     # klien Resend inbound: terima email reset → ekstrak token/link
│   ├── main.py            # loop (klaim dari backend) atau --context (uji lokal)
│   └── checks/
│       ├── password_policy.py   # AUTH-1.3 T01/T02/T04 (+ check AUTH lain per modul)
│       ├── manajemen_sesi.py    # SESS 2.1–2.7
│       ├── zap_scan.py          # engine zap: alert ZAP → metode katalog
│       └── playwright_scan.py   # engine playwright: skrip/izin/storage + reset (Resend)
├── tests/
│   ├── target_palsu.py    # app target aman|rentan (token opak/JWT, cookie sesi opsional)
│   ├── test_auth_checks.py
│   ├── test_sesi_checks.py
│   ├── test_discovery.py
│   ├── test_discovery_openapi.py
│   ├── test_zap.py
│   ├── test_playwright.py
│   └── test_loop.py
├── contoh.context.json
├── requirements.txt
└── .env.example
```

## Menambah check berikutnya

Buat kelas dengan `engine` + metode `run(ctx, metode) -> HasilMetode`, beri dekorator
`@check("<check_id>")`, dan impor modulnya di `checks/__init__.py`. Tak perlu menyentuh
runner/queue.
