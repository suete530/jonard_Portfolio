#!/usr/bin/env bash
#
# setup.sh — One-time provisioning para sa Oracle Cloud (Ubuntu) VPS.
#
# Gamitin (mula sa project folder sa server):
#     sudo bash deploy/setup.sh
#
# Opsyonal na env vars bago patakbuhin:
#     DOMAIN=1.2.3.4.sslip.io   sudo bash deploy/setup.sh
#
# Ginagawa nito:
#   1. Nag-i-install ng Python, MySQL, Redis, Nginx
#   2. Gumagawa ng database + DB user
#   3. Gumagawa ng system user + /opt/portfolio (kinokopya ang code)
#   4. Nagse-setup ng virtualenv + dependencies
#   5. Gumagawa ng .env (random SECRET_KEY at DB password)
#   6. Nagse-setup ng systemd service + nginx reverse proxy
#   7. Binubuksan ang firewall ports 80/443 (ufw + iptables ng Oracle)
#
set -euo pipefail

APP_NAME="portfolio"
APP_USER="portfolio"
APP_DIR="/opt/${APP_NAME}"
DOMAIN="${DOMAIN:-_}"                 # hal. 1.2.3.4.sslip.io o iyong domain
DB_NAME="${DB_NAME:-portfolio_db}"
DB_USER="${DB_USER:-portfolio}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [[ $EUID -ne 0 ]]; then
  echo "Patakbuhin gamit ang sudo: sudo bash deploy/setup.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -z "$DB_PASSWORD" ]]; then
  DB_PASSWORD="$(openssl rand -hex 16)"
  echo ">> Gumawa ng random DB password."
fi

echo ">> [1/8] Pag-install ng system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-dev python3-pip \
  build-essential libjpeg-dev zlib1g-dev \
  mysql-server redis-server nginx git rsync ufw openssl

echo ">> [2/8] Pagsisimula ng MySQL at Redis..."
systemctl enable --now mysql
systemctl enable --now redis-server

echo ">> [3/8] Paggawa ng database at DB user..."
mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo ">> [4/8] Paggawa ng system user at app folder..."
id -u "$APP_USER" >/dev/null 2>&1 || \
  useradd --system --create-home --shell /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    --exclude '.env' --exclude 'instance' --exclude '.pytest_cache' \
    "$SRC_DIR"/ "$APP_DIR"/
fi
mkdir -p "$APP_DIR/static/uploads"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo ">> [5/8] Paggawa ng virtualenv at pag-install ng dependencies..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo ">> [6/8] Pagse-setup ng .env..."
if [[ ! -f "$APP_DIR/.env" ]]; then
  SECRET_KEY="$(openssl rand -hex 32)"
  cat > "$APP_DIR/.env" <<ENV
SECRET_KEY=${SECRET_KEY}
FLASK_ENV=production
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=${DB_NAME}
RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379

# Email notification (contact form) — punan para gumana
SMTP_USER=
SMTP_PASSWORD=
MAIL_TO=

# AI assistant (opsyonal)
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
ENV
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo ">> Ginawa ang $APP_DIR/.env — i-edit ito para sa SMTP/AI."
else
  echo ">> Existing na ang $APP_DIR/.env — hinahayaan (hindi ginagalaw)."
fi

echo ">> [7/8] Pagse-setup ng systemd service..."
sed "s|__APP_DIR__|$APP_DIR|g; s|__APP_USER__|$APP_USER|g" \
  "$APP_DIR/deploy/portfolio.service" > "/etc/systemd/system/${APP_NAME}.service"
systemctl daemon-reload
systemctl enable --now "${APP_NAME}"

echo ">> [8/8] Pagse-setup ng nginx + firewall..."
sed "s|__DOMAIN__|${DOMAIN}|g; s|__APP_DIR__|$APP_DIR|g" \
  "$APP_DIR/deploy/nginx.conf" > "/etc/nginx/sites-available/${APP_NAME}"
ln -sf "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# UFW (host firewall)
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

# Ang Oracle Ubuntu images ay may sariling iptables na humaharang sa 80/443.
if command -v iptables >/dev/null 2>&1; then
  iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
  iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
  mkdir -p /etc/iptables
  iptables-save > /etc/iptables/rules.v4 || true
fi

IP_ADDR="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo "======================================================"
echo " TAPOS! Naka-deploy na ang app."
echo " DB name : ${DB_NAME}"
echo " DB user : ${DB_USER}"
echo " DB pass : ${DB_PASSWORD}   <-- ITAGO ITO"
echo ""
echo " Susunod:"
echo "   1) I-edit ang $APP_DIR/.env (SMTP/AI kung gusto)"
echo "   2) Gumawa ng admin account:"
echo "      sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/seed_admin.py"
echo "   3) Buksan sa browser:  http://${IP_ADDR}/"
echo "======================================================"
