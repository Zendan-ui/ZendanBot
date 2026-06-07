#!/usr/bin/env bash
# =====================================================================
#  ZendanBot installer — long-polling, no domain/SSL/webhook needed.
#  Usage:
#     wget https://raw.githubusercontent.com/Zendan-ui/ZendanBot/main/setup.sh
#     sudo bash setup.sh
# =====================================================================
set -euo pipefail

INSTALL_DIR="/opt/ZendanBot"
REPO_URL="https://github.com/Zendan-ui/ZendanBot.git"
SERVICE_NAME="zendanbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { printf "${GREEN}[✓]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
die()  { printf "${RED}[✗]${NC} %s\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "لطفاً با sudo اجرا کنید."

log "نصب پیش‌نیازها..."
if command -v apt-get &>/dev/null; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip git
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip git
else
    die "سیستم‌عامل پشتیبانی نمی‌شود (فقط Debian/Ubuntu/CentOS)."
fi

log "دریافت سورس..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" pull --ff-only
else
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

log "ساخت محیط مجازی و نصب وابستگی‌ها..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

# ---------- گرفتن اطلاعات ----------
if [[ ! -f .env ]]; then
    echo
    read -rp "BOT_TOKEN (از @BotFather): " BOT_TOKEN
    read -rp "ADMIN_ID (آیدی عددی ادمین): " ADMIN_ID
    read -rp "BOT_USERNAME (بدون @): " BOT_USERNAME
    cat > .env <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
BOT_USERNAME=${BOT_USERNAME}
DATABASE_URL=sqlite+aiosqlite:///${INSTALL_DIR}/zendanbot.db
DEBUG=false
EOF
    log ".env ساخته شد."
else
    warn ".env از قبل وجود دارد؛ بدون تغییر باقی ماند."
fi

# ---------- بررسی توکن ----------
log "بررسی توکن..."
TOKEN=$(grep -E '^BOT_TOKEN=' .env | cut -d= -f2-)
if curl -fsS "https://api.telegram.org/bot${TOKEN}/getMe" | grep -q '"ok":true'; then
    log "توکن معتبر است."
else
    warn "نتوانستم توکن را تایید کنم. ادامه می‌دهم؛ در صورت اشکال .env را بررسی کنید."
fi

# ---------- systemd ----------
log "ساخت سرویس systemd..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ZendanBot Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo
log "نصب کامل شد! 🎉"
echo "وضعیت سرویس:   systemctl status ${SERVICE_NAME}"
echo "مشاهده لاگ:     journalctl -u ${SERVICE_NAME} -f"
echo "حالا در تلگرام به ربات /start بدهید و سپس /panel برای پنل مدیریت."
