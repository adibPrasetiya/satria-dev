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

echo "==> Backend: install dependensi + migrasi DB"
( cd backend && npm ci && npm run db:migrate )

echo "==> Frontend: install + build statis (hasil di frontend/build, disajikan Nginx)"
( cd frontend && npm ci && npm run build )

echo "==> Worker: siapkan venv + dependensi"
cd worker
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv            # server HARUS punya Python 3.13 (greenlet/playwright)
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
