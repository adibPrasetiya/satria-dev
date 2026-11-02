#!/usr/bin/env bash
# =============================================================================
# instal.sh — Bootstrap server dev SATYA sekali-jalan (Ubuntu/Debian, apt).
#
# Pasang & konfigurasikan SEMUA: Node 20, Python 3.13, MySQL, Nginx, PM2,
# OWASP ZAP (daemon LOKAL — worker tidak lagi akses ZAP via internet),
# clone repo, isi .env (rahasia dibangkitkan otomatis), build, lalu start.
#
# Jalankan DI SERVER sebagai user deploy (punya sudo):
#   curl -fsSL https://raw.githubusercontent.com/adibPrasetiya/satria-dev/dev/deploy/instal.sh -o instal.sh
#   chmod +x instal.sh && ./instal.sh
#
# Idempoten: aman diulang. File .env & rahasia TIDAK ditimpa bila sudah ada
# (supaya WORKER_TOKEN backend == worker tetap konsisten).
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/adibPrasetiya/satria-dev.git"
BRANCH="dev"
APP_DIR="${APP_DIR:-$HOME/satya}"
PUBLIC_HOST="${PUBLIC_HOST:-$(curl -fsSL https://api.ipify.org 2>/dev/null || echo localhost)}"
ZAP_VERSION="2.15.0"
ZAP_DIR="$HOME/ZAP_${ZAP_VERSION}"

log() { echo -e "\n\033[1;32m==> $*\033[0m"; }

# --- 0. Prasyarat sistem -----------------------------------------------------
log "Update apt & paket dasar"
sudo apt-get update -y
sudo apt-get install -y curl git unzip ca-certificates gnupg build-essential \
  software-properties-common default-jre nginx mysql-server

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
CORS_ORIGIN=http://${PUBLIC_HOST}
APP_URL=http://${PUBLIC_HOST}
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
# ZAP LOKAL di server ini (tidak lagi via internet)
ZAP_BASE_URL=http://127.0.0.1:8080
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
  ZAP_API_KEY="$(grep -E '^ZAP_API_KEY=' worker/.env | cut -d= -f2-)"
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

# --- 9. Nginx (sajikan frontend/build + proxy /api → backend) ---------------
log "Konfigurasi Nginx"
sudo tee /etc/nginx/sites-available/satya >/dev/null <<NGINX
server {
    listen 80 default_server;
    server_name _;
    root ${APP_DIR}/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location / {
        try_files \$uri \$uri/ /index.html;   # SPA fallback (adapter-static)
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/satya /etc/nginx/sites-enabled/satya
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# --- 10. Selesai ------------------------------------------------------------
log "SELESAI"
cat <<DONE

  Frontend : http://${PUBLIC_HOST}/
  API      : http://${PUBLIC_HOST}/api/v1
  PM2      : pm2 ls   (satya-backend, satya-worker, satya-zap)

  Langkah manual tersisa:
   1. Buat admin pertama:   cd ${APP_DIR}/backend && npm run admin:create
   2. (opsional) isi RESEND_API_KEY / GEMINI_API_KEY di backend/.env & worker/.env,
      lalu: pm2 reload ecosystem.config.cjs --update-env
   3. Deploy berikutnya cukup merge PR ke 'dev' → GitHub Actions jalan otomatis.
DONE
