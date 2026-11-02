#!/usr/bin/env bash
# =============================================================================
# instal.sh — Bootstrap server dev SATYA sekali-jalan (Ubuntu/Debian, apt).
#
# Setup frontend + backend + worker: Node 20, Python 3.13, MySQL, PM2,
# clone repo, isi .env (rahasia dibangkitkan otomatis), build, lalu start via PM2.
# ZAP TIDAK dipasang skrip ini — worker memakai ZAP yang SUDAH ADA di server
# (atur ZAP_BASE_URL / ZAP_API_KEY; default ZAP_BASE_URL=http://127.0.0.1:8080).
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
# ZAP eksternal (sudah ada di server). Worker memakainya; skrip tak memasang ZAP.
ZAP_BASE_URL="${ZAP_BASE_URL:-http://127.0.0.1:8080}"
ZAP_API_KEY="${ZAP_API_KEY:-}"

log() { echo -e "\n\033[1;32m==> $*\033[0m"; }

# --- 0. Prasyarat sistem -----------------------------------------------------
log "Update apt & paket dasar"
sudo apt-get update -y
sudo apt-get install -y curl git unzip ca-certificates gnupg build-essential \
  software-properties-common mysql-server

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
WORKER_ENGINES=custom,discovery,zap,playwright
POLL_INTERVAL=2
# ZAP yang sudah ada di server (eksternal; isi ZAP_API_KEY sesuai daemon Anda)
ZAP_BASE_URL=${ZAP_BASE_URL}
ZAP_API_KEY=${ZAP_API_KEY}
ZAP_TIMEOUT_SPIDER=120
ZAP_TIMEOUT_ASCAN=300
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_NAV_TIMEOUT_MS=15000
PLAYWRIGHT_BROWSER=chromium
AI_PROVIDER=none
AI_REDAKSI=true
AI_BAHASA=id
ENV
  echo "   .env dibuat. Edit manual bila perlu Resend/AI (RESEND_API_KEY, GEMINI_API_KEY, dst)."
else
  log ".env sudah ada — dipertahankan (rahasia tidak diubah)"
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
log "Start backend + worker via PM2"
pm2 reload ecosystem.config.cjs --update-env || pm2 start ecosystem.config.cjs
pm2 save

log "Aktifkan PM2 saat boot"
sudo env PATH="$PATH:$(dirname "$(command -v node)")" "$(command -v pm2)" startup systemd -u "$USER" --hp "$HOME" || true
pm2 save

# --- 9. Selesai -------------------------------------------------------------
log "SELESAI (frontend+backend+worker siap; Nginx diatur sendiri)"
cat <<DONE

  Proses PM2 : pm2 ls   (satya-backend, satya-worker)
  Backend    : http://127.0.0.1:3000   (arahkan reverse proxy: /api/ -> sini)
  Frontend   : ${APP_DIR}/frontend/build   (file statis SPA; arahkan reverse proxy: / -> sini,
               fallback ke /index.html untuk adapter-static)
  ZAP        : ${ZAP_BASE_URL}   (eksternal; set ZAP_API_KEY di worker/.env sesuai daemon Anda)

  Langkah manual tersisa:
   1. Konfigurasi reverse proxy (Nginx) Anda ke dua lokasi di atas + TLS domain.
   2. Buat admin pertama:   cd ${APP_DIR}/backend && npm run admin:create
   3. (opsional) isi RESEND_API_KEY / GEMINI_API_KEY di backend/.env & worker/.env,
      lalu: pm2 reload ecosystem.config.cjs --update-env
   4. Deploy berikutnya cukup merge PR ke 'dev' → GitHub Actions jalan otomatis.
DONE
