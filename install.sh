#!/usr/bin/env bash
set -euo pipefail

# ============================================
#  ZendanBOT v2.0 - Installer
#  Tested: Ubuntu 20/22/24, Debian 11/12,
#          CentOS 8/9, Rocky 8/9, AlmaLinux 9
# ============================================

# ---------- constants ----------
INSTALL_DIR="/opt/ZendanBot"
REPO_URL="https://github.com/Zendan-ui/ZendanBot.git"
SERVICE_NAME="zendanbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
BACKUP_SCRIPT="${INSTALL_DIR}/backup.sh"
LOG_FILE="/tmp/zendanbot_install.log"

# ---------- helpers ----------
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
info() { echo -e "${BLUE}[i]${NC} $*"; }

separator() {
    echo -e "${CYAN}──────────────────────────────────────────────${NC}"
}

die() { err "$@"; exit 1; }

# ---------- detect OS ----------
detect_os() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        echo "$ID"
    elif command -v dnf &>/dev/null; then
        echo "centos"
    else
        echo "unknown"
    fi
}

# ---------- install system packages ----------
install_packages() {
    local os
    os=$(detect_os)
    info "OS: $os"

    local pkgs=(python3 python3-pip python3-venv git curl wget sqlite3)

    case "$os" in
        ubuntu|debian|linuxmint|pop)
            sudo apt-get update -qq
            sudo apt-get install -y -qq "${pkgs[@]}" python3-dev libffi-dev libssl-dev 2>/dev/null
            ;;
        centos|rhel|rocky|almalinux)
            sudo dnf install -y "${pkgs[@]}" python3-devel libffi-devel openssl-devel 2>/dev/null \
                || sudo yum install -y "${pkgs[@]}" python3-devel libffi-devel openssl-devel 2>/dev/null
            ;;
        fedora)
            sudo dnf install -y "${pkgs[@]}" python3-devel libffi-devel openssl-devel
            ;;
        *)
            warn "Unknown distro — trying apt..."
            sudo apt-get update -qq 2>/dev/null || true
            sudo apt-get install -y -qq "${pkgs[@]}" 2>/dev/null || true
            ;;
    esac
    log "System packages installed."
}

# ---------- python check ----------
find_python() {
    local candidates=(python3.12 python3.11 python3 python)
    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            local major minor
            major=${ver%%.*}
            minor=${ver#*.}
            if (( major >= 3 && minor >= 10 )); then
                echo "$cmd"
                return
            fi
        fi
    done
    echo ""
}

ensure_python() {
    local py
    py=$(find_python)
    if [[ -n "$py" ]]; then
        log "Python OK: $($py --version 2>&1)"
        echo "$py"
        return
    fi

    warn "Python 3.10+ not found — installing deadsnakes PPA..."
    local os
    os=$(detect_os)
    if [[ "$os" == "ubuntu" || "$os" == "debian" ]]; then
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        sudo apt-get update -qq
        sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
        log "Python 3.12 installed."
        echo "python3.12"
    else
        die "Install Python 3.10+ manually and re-run."
    fi
}

# ---------- clone / update ----------
get_code() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull --ff-only || warn "Git pull failed — continuing with local files."
    else
        info "Cloning repository..."
        sudo rm -rf "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"
    log "Code ready at ${INSTALL_DIR}"
}

# ---------- venv + pip ----------
setup_venv() {
    local py="$1"
    info "Creating virtual environment..."
    rm -rf venv
    "$py" -m venv venv
    # shellcheck disable=SC1091
    source venv/bin/activate

    pip install --upgrade pip setuptools wheel --quiet
    pip install -r requirements.txt --quiet 2>/dev/null \
        || pip install -r requirements.txt

    log "Python dependencies installed."
}

# ---------- .env ----------
setup_env() {
    if [[ -f .env ]]; then
        warn ".env already exists."
        read -rp "   Edit it now? [y/N]: " ans
        [[ "${ans,,}" == "y" ]] && ${EDITOR:-nano} .env
        return
    fi

    cp .env.example .env

    echo ""
    separator
    echo -e "${BOLD}${CYAN}  ⚙  Configuration${NC}"
    separator
    echo ""

    read -rp "  Bot Token (from @BotFather): " bot_token
    read -rp "  Admin Telegram ID (from @userinfobot): " admin_id
    read -rp "  Bot Username (e.g. zendanbot): " bot_user
    read -rp "  Domain for webhook (leave empty for polling): " domain

    local db_url="sqlite+aiosqlite:///./zendanbot.db"
    read -rp "  Use PostgreSQL? [y/N]: " use_pg
    if [[ "${use_pg,,}" == "y" ]]; then
        read -rp "    PG host [localhost]: " pg_host
        read -rp "    PG port [5432]: " pg_port
        read -rp "    PG user: " pg_user
        read -rp "    PG password: " pg_pass
        read -rp "    PG database [zendanbot]: " pg_db
        pg_host="${pg_host:-localhost}"
        pg_port="${pg_port:-5432}"
        pg_db="${pg_db:-zendanbot}"
        db_url="postgresql+asyncpg://${pg_user}:${pg_pass}@${pg_host}:${pg_port}/${pg_db}"
    fi

    # Generate random secret
    local secret
    secret=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')

    # Write .env
    cat > .env <<ENVFILE
BOT_TOKEN=${bot_token}
ADMIN_ID=${admin_id}
BOT_USERNAME=${bot_user}
DOMAIN=${domain}
WEBHOOK_URL=
DATABASE_URL=${db_url}
SECRET_KEY=${secret}
DEBUG=false
ENVFILE

    log ".env written."
    read -rp "  Review / edit .env? [y/N]: " ans
    [[ "${ans,,}" == "y" ]] && ${EDITOR:-nano} .env
}

# ---------- systemd ----------
setup_systemd() {
    local venv_python="${INSTALL_DIR}/venv/bin/python"

    sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=ZendanBOT - VPN Sales Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${venv_python} main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}" 2>/dev/null

    log "systemd service installed and enabled."
}

# ---------- backup cron ----------
setup_backup_cron() {
    cat > "$BACKUP_SCRIPT" <<'BKEOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="/opt/ZendanBot/backups"
mkdir -p "$DIR"
TS=$(date +%Y%m%d_%H%M%S)
cp /opt/ZendanBot/zendanbot.db "${DIR}/zendanbot_${TS}.db" 2>/dev/null || true
find "$DIR" -name 'zendanbot_*.db' -mtime +7 -delete 2>/dev/null || true
echo "[$(date)] backup done: zendanbot_${TS}.db" >> "${DIR}/backup.log"
BKEOF
    chmod +x "$BACKUP_SCRIPT"

    # Install cron only if not already present
    if ! crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
        (crontab -l 2>/dev/null; echo "0 3 * * * ${BACKUP_SCRIPT}") | crontab -
    fi
    log "Daily backup cron set (03:00)."
}

# ---------- nginx + SSL ----------
setup_nginx() {
    read -rp "  Configure Nginx reverse-proxy for webhook? [y/N]: " ans
    [[ "${ans,,}" != "y" ]] && return

    read -rp "    Domain: " domain
    [[ -z "$domain" ]] && { warn "Skipped."; return; }

    local conf="/etc/nginx/sites-available/zendanbot"
    sudo tee "$conf" >/dev/null <<EOF
server {
    listen 80;
    server_name ${domain};

    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    sudo ln -sf "$conf" /etc/nginx/sites-enabled/ 2>/dev/null || true
    sudo nginx -t && sudo systemctl reload nginx
    log "Nginx configured for ${domain}"

    read -rp "    Install SSL (Let's Encrypt)? [y/N]: " ssl_ans
    if [[ "${ssl_ans,,}" == "y" ]]; then
        read -rp "      Email for certbot: " email
        sudo apt-get install -y certbot python3-certbot-nginx 2>/dev/null || true
        sudo certbot --nginx -d "$domain" --non-interactive --agree-tos -m "$email" 2>/dev/null \
            && log "SSL installed." \
            || warn "certbot failed — run manually."
    fi
}

# ---------- quick import test ----------
run_test() {
    info "Testing imports..."
    cd "$INSTALL_DIR"
    source venv/bin/activate

    python3 -c "
import sys; sys.path.insert(0, '.')
ok, fail = [], []
mods = [
    ('app.config', 'settings'),
    ('app.database', 'init_db'),
    ('app.security', 'sanitize_text'),
    ('app.models', 'User'),
    ('app.bot.keyboards', 'main_menu'),
    ('app.topics', 'get_topic_id'),
    ('app.panels.marzban', 'MarzbanAPI'),
    ('app.panels.remnawave', 'RemnawavePanel'),
    ('app.panels.pasargad', 'PasargadPanel'),
    ('app.panels.sui', 'SUIPanel'),
    ('app.panels.mikrotik', 'MikrotikPanel'),
    ('app.payments.card', 'process_card_receipt'),
    ('app.utils.qr_generator', 'generate_professional_qr'),
]
for mod, attr in mods:
    try:
        m = __import__(mod, fromlist=[attr])
        getattr(m, attr)
        ok.append(mod)
    except Exception as e:
        fail.append(f'{mod}: {e}')

print()
for m in ok:
    print(f'  ✅ {m}')
for m in fail:
    print(f'  ❌ {m}')
print()
if fail:
    print(f'⚠  {len(fail)} module(s) had issues.')
else:
    print(f'🎉 All {len(ok)} modules OK!')
" 2>&1 || true
}

# ---------- start ----------
start_bot() {
    sudo systemctl restart "${SERVICE_NAME}"
    sleep 2
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        log "Bot is running."
    else
        err "Bot failed to start. Check: journalctl -u ${SERVICE_NAME} -n 50"
    fi
}

# ---------- print summary ----------
print_summary() {
    echo ""
    separator
    echo -e "${BOLD}${CYAN}  🛡️  ZendanBOT Installed Successfully${NC}"
    separator
    echo ""
    echo "  📂  Directory:  ${INSTALL_DIR}"
    echo "  ⚙️  Config:     ${INSTALL_DIR}/.env"
    echo "  🗃️  Database:   ${INSTALL_DIR}/zendanbot.db"
    echo "  📋  Logs:       journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo -e "  ${BOLD}Commands:${NC}"
    echo "    start    sudo systemctl start   ${SERVICE_NAME}"
    echo "    stop     sudo systemctl stop    ${SERVICE_NAME}"
    echo "    restart  sudo systemctl restart ${SERVICE_NAME}"
    echo "    status   sudo systemctl status  ${SERVICE_NAME}"
    echo "    logs     journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo -e "  ${BOLD}Telegram:${NC}"
    echo "    /start   → main menu"
    echo "    /panel   → admin panel"
    echo ""
    echo -e "  ${BOLD}Panels supported:${NC}  Marzban • X-UI • S-UI • Hiddify • Remnawave"
    echo "  ${BOLD}              ${NC}  Pasargad • Marzneshin • Mikrotik • Eylan"
    echo "  ${BOLD}              ${NC}  WGDashboard • IBSng • Alireza"
    echo ""
    separator
}

# ==================== MAIN ====================
main() {
    echo ""
    separator
    echo -e "${BOLD}${CYAN}  🛡️  ZendanBOT v2.0 Installer${NC}"
    separator
    echo ""

    # Must be run as root or with sudo
    if [[ "$(id -u)" -ne 0 ]]; then
        # Re-run with sudo
        warn "Re-running with sudo..."
        exec sudo bash "$0" "$@"
    fi

    local PY

    install_packages
    PY=$(ensure_python)
    get_code
    setup_venv "$PY"
    setup_env
    setup_systemd
    setup_backup_cron
    setup_nginx
    run_test

    echo ""
    read -rp "Start the bot now? [Y/n]: " start_ans
    if [[ "${start_ans,,}" != "n" ]]; then
        start_bot
    fi

    print_summary
}

main "$@"
