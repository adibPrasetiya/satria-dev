#!/usr/bin/env bash
# Deploy SATYA ke server dev. Dijalankan DI SERVER, dialirkan via SSH dari GitHub Actions:
#   ssh user@host "APP_DIR='/srv/satya' bash -s" < deploy/deploy-dev.sh
#
# Idempoten & aman diulang. File .env dan worker/.venv TER-IGNORE git,
# jadi `git reset --hard` tidak menghapusnya.
set -euo pipefail

APP_DIR="${APP_DIR:?APP_DIR belum diset (set lewat perintah SSH)}"
cd "$APP_DIR"

echo "==> Sinkron kode ke origin/dev"
git fetch --all --prune
git checkout dev
git reset --hard origin/dev

echo "==> Backend: install dependensi + migrasi DB + sinkron katalog"
# catalog:sync idempoten — menyisipkan butir katalog baru (mis. metode SESS baru) & memperbarui
# definisinya dari YAML tanpa menyentuh is_active atau butir non-YAML. Aman diulang tiap deploy.
# satuan:seed idempoten — menambah hierarki satuan TNI yang belum ada & mengisi kolom lokasi yang masih
# kosong; tidak menimpa isian admin dan tidak menghapus satuan.
( cd backend && npm ci && npm run db:migrate && npm run catalog:sync && npm run satuan:seed )

# Rekonsiliasi backend/.env: AI penyusun laporan memakai konfigurasi AI yang sama dengan worker.
# Variabel yang belum ada di backend/.env disalin dari worker/.env (nilai yang sudah diisi tidak ditimpa).
if [ -f backend/.env ] && [ -f worker/.env ]; then
  for var in AI_PROVIDER GEMINI_API_KEY ANTHROPIC_API_KEY AI_API_KEY AI_MODEL; do
    if ! grep -q "^${var}=" backend/.env && grep -q "^${var}=" worker/.env; then
      grep "^${var}=" worker/.env | tail -1 >> backend/.env
      echo "==> backend/.env: tambah ${var} dari worker/.env"
    fi
  done
fi

echo "==> Frontend: install + build statis (hasil di frontend/build, disajikan Nginx)"
( cd frontend && npm ci && npm run build )

echo "==> Worker: siapkan venv + dependensi"
cd worker
# Rekonsiliasi .env: pastikan engine fungsi baru (sslyze=COMM, nuclei=APIS) aktif.
# .env ter-ignore git & tak ditimpa deploy, jadi server lama perlu penambahan ini sekali.
# Idempoten: hanya menambah bila baris ada & belum memuat engine tersebut.
if [ -f .env ] && grep -q '^WORKER_ENGINES=' .env; then
  for eng in sslyze nuclei; do
    if ! grep -q "^WORKER_ENGINES=.*${eng}" .env; then
      sed -i "s/^\(WORKER_ENGINES=.*\)$/\1,${eng}/" .env
      echo "==> worker/.env: tambah engine '${eng}' ke WORKER_ENGINES"
    fi
  done
fi

# IP publik worker untuk keterangan blokir di UI ("minta whitelist IP …"). Dideteksi dari tabel
# routing (tanpa layanan eksternal) dan hanya diisi bila bukan alamat privat/NAT. Idempoten.
if [ -f .env ] && ! grep -q '^WORKER_IP_PUBLIK=.\+' .env; then
  IP_SRC=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')
  if [ -n "$IP_SRC" ] && ! echo "$IP_SRC" | grep -Eq '^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)'; then
    sed -i '/^WORKER_IP_PUBLIK=$/d' .env
    echo "WORKER_IP_PUBLIK=$IP_SRC" >> .env
    echo "==> worker/.env: set WORKER_IP_PUBLIK=$IP_SRC"
  fi
fi

# Biner nuclei (APIS-12.2-T02): unduh rilis precompiled sekali (tanpa Go). Idempoten.
# Tanpa biner, check exposure.api_docs_debug tetap jalan sebagai tidak_dapat_diverifikasi.
NUCLEI_VER="3.11.1"
NUCLEI_DST="$HOME/.local/bin/nuclei"
if [ ! -x "$NUCLEI_DST" ] && ! command -v nuclei >/dev/null 2>&1; then
  echo "==> Memasang biner nuclei v${NUCLEI_VER}"
  mkdir -p "$HOME/.local/bin" /tmp/satya-nuclei
  if curl -fsSL "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VER}/nuclei_${NUCLEI_VER}_linux_amd64.zip" -o /tmp/satya-nuclei/n.zip; then
    unzip -o -q /tmp/satya-nuclei/n.zip -d /tmp/satya-nuclei \
      && mv -f /tmp/satya-nuclei/nuclei "$NUCLEI_DST" && chmod +x "$NUCLEI_DST" \
      && "$NUCLEI_DST" -update-templates -silent 2>/dev/null || true
  fi
  rm -rf /tmp/satya-nuclei
fi
# Arahkan worker ke biner nuclei bila di ~/.local/bin (mungkin di luar PATH proses PM2).
if [ -x "$NUCLEI_DST" ] && [ -f .env ] && ! grep -q '^NUCLEI_BIN=' .env; then
  echo "NUCLEI_BIN=$NUCLEI_DST" >> .env
  echo "==> worker/.env: set NUCLEI_BIN=$NUCLEI_DST"
fi

# Biner ffuf (pengaya recon INPV: penemuan nama parameter query & path; biner precompiled, tanpa Go).
# Tanpa biner, tahap ffuf dilewati (recon tetap jalan). ffuf BUKAN engine → tak masuk WORKER_ENGINES.
FFUF_VER="2.3.0"
FFUF_DST="$HOME/.local/bin/ffuf"
if [ ! -x "$FFUF_DST" ] && ! command -v ffuf >/dev/null 2>&1; then
  echo "==> Memasang biner ffuf v${FFUF_VER}"
  mkdir -p "$HOME/.local/bin" /tmp/satya-ffuf
  if curl -fsSL "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VER}/ffuf_${FFUF_VER}_linux_amd64.tar.gz" -o /tmp/satya-ffuf/f.tgz; then
    tar -xzf /tmp/satya-ffuf/f.tgz -C /tmp/satya-ffuf ffuf \
      && mv -f /tmp/satya-ffuf/ffuf "$FFUF_DST" && chmod +x "$FFUF_DST"
  fi
  rm -rf /tmp/satya-ffuf
fi
# Arahkan worker ke biner ffuf bila di ~/.local/bin (mungkin di luar PATH proses PM2).
if [ -x "$FFUF_DST" ] && [ -f .env ] && ! grep -q '^FFUF_BIN=' .env; then
  echo "FFUF_BIN=$FFUF_DST" >> .env
  echo "==> worker/.env: set FFUF_BIN=$FFUF_DST"
fi

# Wordlist ffuf (SecLists): nama parameter & path. Disimpan DI LUAR repo (git reset tak menyentuhnya).
# Idempoten: unduh hanya bila belum ada. Tanpa wordlist param → pakai daftar internal; tanpa wordlist
# path → penemuan path dilewati.
WLDIR="$HOME/.local/share/satya/wordlists"
SL="https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content"
mkdir -p "$WLDIR"
[ -s "$WLDIR/parameter-names.txt" ] || curl -fsSL "$SL/burp-parameter-names.txt" -o "$WLDIR/parameter-names.txt" || true
[ -s "$WLDIR/paths-common.txt" ] || curl -fsSL "$SL/common.txt" -o "$WLDIR/paths-common.txt" || true
if [ -s "$WLDIR/parameter-names.txt" ] && [ -f .env ] && ! grep -q '^FFUF_WORDLIST_PARAM=' .env; then
  echo "FFUF_WORDLIST_PARAM=$WLDIR/parameter-names.txt" >> .env
  echo "==> worker/.env: set FFUF_WORDLIST_PARAM"
fi
if [ -s "$WLDIR/paths-common.txt" ] && [ -f .env ] && ! grep -q '^FFUF_WORDLIST_PATH=' .env; then
  echo "FFUF_WORDLIST_PATH=$WLDIR/paths-common.txt" >> .env
  echo "==> worker/.env: set FFUF_WORDLIST_PATH"
fi

if [ ! -x .venv/bin/python ]; then
  # Worker butuh Python 3.13 (greenlet/playwright). Pakai python3.13 bila ada.
  { command -v python3.13 >/dev/null && python3.13 -m venv .venv; } || python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
# Browser Playwright (chromium) hanya diunduh sekali bila belum ada.
# Dependensi SISTEM playwright (apt) dipasang manual sekali saat bootstrap server:
#   sudo .venv/bin/python -m playwright install-deps
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
  .venv/bin/python -m playwright install chromium || true
fi
cd ..

echo "==> Restart backend + worker via PM2"
pm2 reload ecosystem.config.cjs --update-env
pm2 save

echo "==> Deploy selesai: $(git rev-parse --short HEAD) @ dev"
