#!/usr/bin/env bash
# =============================================================================
# instal.sh — Bootstrap server dev SATYA sekali-jalan (Ubuntu/Debian, apt).
#
# Setup frontend + backend + worker: Node 20, Python 3.13, MySQL, PM2,
# OWASP ZAP (daemon LOKAL — worker tidak lagi akses ZAP via internet),
# clone repo, isi .env (rahasia dibangkitkan otomatis), build, lalu start via PM2.
#
# CATATAN: skrip ini TIDAK memasang/mengatur Nginx. Reverse proxy & TLS
# Anda konfigurasi sendiri — arahkan ke:
#   /      -> ${APP_DIR}/frontend/build   (file statis, SPA)
#   /api/  -> http://127.0.0.1:3000       (backend)
#
# Jalankan DI SERVER sebagai user deploy (punya sudo). Set DOMAIN agar tautan
# reset kata sandi & CORS memakai domain publik Anda:
#   curl -fsSL https://raw.githubusercontent.com/adibPrasetiya/satria-dev/dev/deploy/instal.sh -o instal.sh
#   chmod +x instal.sh && DOMAIN=dev.domain-anda.id ./instal.sh
#
# Idempoten: aman diulang. File .env & rahasia TIDAK ditimpa bila sudah ada
# (supaya WORKER_TOKEN backend == worker tetap konsisten).
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/adibPrasetiya/satria-dev.git"
BRANCH="dev"
APP_DIR="${APP_DIR:-$HOME/satya}"
PUBLIC_HOST="${PUBLIC_HOST:-$(curl -fsSL https://api.ipify.org 2>/dev/null || echo localhost)}"
# URL publik untuk CORS & tautan reset email. Set DOMAIN=... untuk pakai domain + HTTPS.
DOMAIN="${DOMAIN:-}"
if [ -n "$DOMAIN" ]; then BASE_URL="https://${DOMAIN}"; else BASE_URL="http://${PUBLIC_HOST}"; fi
ZAP_VERSION="2.15.0"
ZAP_DIR="$HOME/ZAP_${ZAP_VERSION}"

log() { echo -e "\n\033[1;32m==> $*\033[0m"; }

# --- 0. Prasyarat sistem -----------------------------------------------------
log "Update apt & paket dasar"
sudo apt-get update -y
sudo apt-get install -y curl git unzip ca-certificates gnupg build-essential \
  software-properties-common default-jre mysql-server

# --- 1. Node.js 20 (NodeSource) ---------------------------------------------
if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" -lt 20 ]; then
  log "Pasang Node.js 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# --- 2. Python 3.13 (deadsnakes) --------------------------------------------
if ! command -v python3.13 >/dev/null; then
  log "Pasang Python 3.13"
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -y
  sudo apt-get install -y python3.13 python3.13-venv python3.13-dev
fi

# --- 3. PM2 global ----------------------------------------------------------
command -v pm2 >/dev/null || { log "Pasang PM2"; sudo npm install -g pm2; }

# --- 4. OWASP ZAP (daemon LOKAL) --------------------------------------------
if [ ! -x "$ZAP_DIR/zap.sh" ]; then
  log "Unduh OWASP ZAP $ZAP_VERSION"
  curl -fsSL "https://github.com/zaproxy/zaproxy/releases/download/v${ZAP_VERSION}/ZAP_${ZAP_VERSION}_Crossplatform.zip" -o /tmp/zap.zip
  unzip -q -o /tmp/zap.zip -d "$HOME"
  rm -f /tmp/zap.zip
fi

# --- 4b. nuclei (engine Keamanan API APIS-12.2-T02; biner precompiled, tanpa Go) ------
NUCLEI_VERSION="3.11.1"
NUCLEI_BIN_PATH="$HOME/.local/bin/nuclei"
if [ ! -x "$NUCLEI_BIN_PATH" ] && ! command -v nuclei >/dev/null 2>&1; then
  log "Unduh biner nuclei $NUCLEI_VERSION"
  mkdir -p "$HOME/.local/bin" /tmp/satya-nuclei
  if curl -fsSL "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_amd64.zip" -o /tmp/satya-nuclei/n.zip; then
    unzip -q -o /tmp/satya-nuclei/n.zip -d /tmp/satya-nuclei \
      && mv -f /tmp/satya-nuclei/nuclei "$NUCLEI_BIN_PATH" && chmod +x "$NUCLEI_BIN_PATH" \
      && "$NUCLEI_BIN_PATH" -update-templates -silent 2>/dev/null || true
  fi
  rm -rf /tmp/satya-nuclei
fi

# --- 5. Clone / update repo -------------------------------------------------
if [ ! -d "$APP_DIR/.git" ]; then
  log "Clone repo ke $APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  log "Repo sudah ada, sinkron ke origin/$BRANCH"
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi
cd "$APP_DIR"

# --- 6. Rahasia & .env (hanya saat pertama; jangan timpa) -------------------
gen() { node -e "console.log(require('crypto').randomBytes($1).toString('base64url'))"; }

if [ ! -f backend/.env ]; then
  log "Bangkitkan rahasia & tulis .env (pertama kali)"
  JWT_SECRET="$(gen 48)"
  WORKER_TOKEN="$(gen 24)"
  DB_PASS="$(gen 18)"
  ZAP_API_KEY="$(gen 16)"

  # MySQL: buat database + user (fresh mysql pakai socket auth → sudo mysql)
  sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS satya CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'satya'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER 'satya'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON satya.* TO 'satya'@'localhost';
FLUSH PRIVILEGES;
SQL

  cat > backend/.env <<ENV
NODE_ENV=production
PORT=3000
DATABASE_URL=mysql://satya:${DB_PASS}@localhost:3306/satya
JWT_ACCESS_SECRET=${JWT_SECRET}
JWT_ACCESS_EXPIRES_IN=15m
REFRESH_TOKEN_TTL_DAYS=7
CORS_ORIGIN=${BASE_URL}
APP_URL=${BASE_URL}
PASSWORD_RESET_TTL_MINUTES=30
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
RESEND_API_KEY=
MAIL_FROM="SATYA <onboarding@resend.dev>"
WORKER_TOKEN=${WORKER_TOKEN}
WORKER_TASK_TIMEOUT_MS=120000
LOG_TO_FILE=true
LOG_DIR=logs
LOG_LEVEL=
ENV

  cat > frontend/.env <<ENV
VITE_USE_MOCK=false
VITE_API_BASE=/api/v1
ENV

  cat > worker/.env <<ENV
BACKEND_URL=http://127.0.0.1:3000/api/v1
WORKER_TOKEN=${WORKER_TOKEN}
WORKER_ID=worker-1
WORKER_ENGINES=custom,discovery,zap,playwright,sslyze,nuclei
POLL_INTERVAL=2
# ZAP LOKAL di server ini (tidak lagi via internet)
ZAP_BASE_URL=http://127.0.0.1:8080
ZAP_API_KEY=${ZAP_API_KEY}
ZAP_TIMEOUT_SPIDER=120
ZAP_TIMEOUT_ASCAN=300
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_NAV_TIMEOUT_MS=15000
PLAYWRIGHT_BROWSER=chromium
# sslyze (engine Keamanan Komunikasi COMM-8.3/8.4): handshake TLS read-only, paket in-proses.
SSLYZE_ENABLE=
SSLYZE_PORT=443
SSLYZE_TIMEOUT=10
# nuclei (engine Keamanan API APIS-12.2-T02): biner precompiled dipasang di ~/.local/bin (lihat #4b).
NUCLEI_BIN=${NUCLEI_BIN_PATH}
NUCLEI_ENABLE=
NUCLEI_TIMEOUT=90
NUCLEI_TAGS=exposure,swagger,api,config,misconfig,debug
NUCLEI_SEVERITY=low,medium,high,critical
NUCLEI_RATE=50
NUCLEI_CONCURRENCY=25
AI_PROVIDER=none
AI_REDAKSI=true
AI_BAHASA=id
# Penajam AI untuk COMM (klasifikasi penerbit->PSrE & adjudikasi host). Aktif hanya bila AI_PROVIDER != none.
AI_COMM=hemat
# Penajam AI untuk APIS (klasifikasi endpoint publik & adjudikasi paparan). Aktif hanya bila AI_PROVIDER != none.
AI_APIS=hemat
# Penajam AI untuk ERRL (kebocoran error & paparan log). Aktif hanya bila AI_PROVIDER != none.
AI_ERRL=hemat
ENV
  echo "   .env dibuat. Edit manual bila perlu Resend/AI (RESEND_API_KEY, GEMINI_API_KEY, dst)."
else
  log ".env sudah ada — dipertahankan (rahasia tidak diubah)"
  ZAP_API_KEY="$(grep -E '^ZAP_API_KEY=' worker/.env | cut -d= -f2-)"
  # Rekonsiliasi: pastikan engine fungsi baru (sslyze/nuclei) ada tanpa menyentuh rahasia lain.
  if grep -q '^WORKER_ENGINES=' worker/.env; then
    for eng in sslyze nuclei; do
      if ! grep -q "^WORKER_ENGINES=.*${eng}" worker/.env; then
        sed -i "s/^\(WORKER_ENGINES=.*\)$/\1,${eng}/" worker/.env
        echo "   WORKER_ENGINES diperbarui: tambah '${eng}'."
      fi
    done
  fi
  # Arahkan ke biner nuclei bila terpasang & belum tercatat.
  if [ -x "$NUCLEI_BIN_PATH" ] && ! grep -q '^NUCLEI_BIN=' worker/.env; then
    echo "NUCLEI_BIN=${NUCLEI_BIN_PATH}" >> worker/.env
    echo "   worker/.env: set NUCLEI_BIN=${NUCLEI_BIN_PATH}."
  fi
fi

# --- 7. Install & build tiap komponen ---------------------------------------
log "Backend: install + migrasi DB"
( cd backend && npm ci && npm run db:migrate )

log "Frontend: install + build statis"
( cd frontend && npm ci && npm run build )

log "Worker: venv Python 3.13 + dependensi + browser Playwright"
cd worker
[ -x .venv/bin/python ] || python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
sudo .venv/bin/python -m playwright install-deps
.venv/bin/python -m playwright install chromium
cd ..

# --- 8. Start proses via PM2 -------------------------------------------------
log "Start ZAP (daemon lokal) via PM2"
pm2 describe satya-zap >/dev/null 2>&1 || \
  pm2 start "$ZAP_DIR/zap.sh" --name satya-zap -- \
    -daemon -host 127.0.0.1 -port 8080 \
    -config api.key="$ZAP_API_KEY" \
    -config api.addrs.addr.name=127.0.0.1 -config api.addrs.addr.regex=false

log "Start backend + worker via PM2"
pm2 reload ecosystem.config.cjs --update-env || pm2 start ecosystem.config.cjs
pm2 save

log "Aktifkan PM2 saat boot"
sudo env PATH="$PATH:$(dirname "$(command -v node)")" "$(command -v pm2)" startup systemd -u "$USER" --hp "$HOME" || true
pm2 save

# --- 9. Selesai -------------------------------------------------------------
log "SELESAI (frontend+backend+worker siap; Nginx diatur sendiri)"
cat <<DONE

  Proses PM2 : pm2 ls   (satya-backend, satya-worker, satya-zap)
  Backend    : http://127.0.0.1:3000   (arahkan reverse proxy: /api/ -> sini)
  Frontend   : ${APP_DIR}/frontend/build   (file statis SPA; arahkan reverse proxy: / -> sini,
               fallback ke /index.html untuk adapter-static)
  ZAP lokal  : http://127.0.0.1:8080

  Langkah manual tersisa:
   1. Konfigurasi reverse proxy (Nginx) Anda ke dua lokasi di atas + TLS domain.
   2. Buat admin pertama:   cd ${APP_DIR}/backend && npm run admin:create
   3. (opsional) isi RESEND_API_KEY / GEMINI_API_KEY di backend/.env & worker/.env,
      lalu: pm2 reload ecosystem.config.cjs --update-env
   4. Deploy berikutnya cukup merge PR ke 'dev' → GitHub Actions jalan otomatis.
DONE
