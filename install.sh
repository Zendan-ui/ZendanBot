#!/usr/bin/env bash
# ============================================
#  ZendanBOT v2.0 - Installer
#  Tested: Ubuntu 20/22/24, Debian 11/12,
#          CentOS 8/9, Rocky 8/9, AlmaLinux 9
# ============================================

INSTALL_DIR="/opt/ZendanBot"
REPO_URL="https://github.com/Zendan-ui/ZendanBot.git"
SERVICE_NAME="zendanbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
BACKUP_SCRIPT="${INSTALL_DIR}/backup.sh"

# Colors
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
sep()  { echo -e "${CYAN}──────────────────────────────────────────────${NC}"; }
die()  { err "$@"; exit 1; }

# ---------- detect OS ----------
detect_os() {
    if [[ -f /etc/os-release ]]; then
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

    case "$os" in
        ubuntu|debian|linuxmint|pop)
            apt-get update -qq 2>/dev/null || true
            # Install python3 and common version-specific venv packages
            apt-get install -y python3 python3-pip python3-venv python3-dev \
                python3.11-venv python3.12-venv python3.13-venv \
                git curl wget sqlite3 libffi-dev libssl-dev \
                software-properties-common 2>/dev/null || true
            ;;
        centos|rhel|rocky|almalinux)
            dnf install -y python3 python3-pip python3-devel git curl wget \
                sqlite libffi-devel openssl-devel 2>/dev/null || \
            yum install -y python3 python3-pip python3-devel git curl wget \
                sqlite libffi-devel openssl-devel 2>/dev/null || true
            ;;
        fedora)
            dnf install -y python3 python3-pip python3-devel git curl wget \
                sqlite libffi-devel openssl-devel 2>/dev/null || true
            ;;
        *)
            warn "Unknown distro — trying apt..."
            apt-get update -qq 2>/dev/null || true
            apt-get install -y python3 python3-pip python3-venv git curl wget sqlite3 2>/dev/null || true
            ;;
    esac
    log "System packages done."
}

# ---------- python ----------
find_python() {
    for cmd in python3.12 python3.11 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || continue
            local major=${ver%%.*}
            local minor=${ver#*.}
            if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    echo ""
}

ensure_python() {
    local py
    py=$(find_python)
    if [[ -n "$py" ]]; then
        log "Python: $($py --version 2>&1)" >&2
        echo "$py"
        return 0
    fi

    warn "Python 3.10+ not found — installing..." >&2
    local os
    os=$(detect_os)
    if [[ "$os" == "ubuntu" || "$os" == "debian" ]]; then
        apt-get install -y software-properties-common 2>/dev/null || true
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt-get update -qq 2>/dev/null || true
        apt-get install -y python3.12 python3.12-venv python3.12-dev 2>/dev/null || true
        if command -v python3.12 &>/dev/null; then
            log "Python 3.12 installed." >&2
            echo "python3.12"
            return 0
        fi
    fi
    die "Install Python 3.10+ manually and re-run."
}

# ---------- clone / update ----------
get_code() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull 2>/dev/null || warn "Git pull failed — using local files."
    else
        info "Cloning repository..."
        rm -rf "$INSTALL_DIR" 2>/dev/null || true
        git clone "$REPO_URL" "$INSTALL_DIR" || die "Git clone failed. Check internet."
    fi
    cd "$INSTALL_DIR" || die "Cannot cd to $INSTALL_DIR"
    log "Code ready at ${INSTALL_DIR}"
}

# ---------- venv ----------
setup_venv() {
    local py="$1"
    info "Creating virtual environment..."
    rm -rf venv 2>/dev/null || true

    # Try creating venv; if it fails, install the matching -venv package
    if ! "$py" -m venv venv 2>/dev/null; then
        warn "venv creation failed — installing missing package..."
        local ver
        ver=$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
        if [[ -n "$ver" ]]; then
            local os
            os=$(detect_os)
            case "$os" in
                ubuntu|debian|linuxmint|pop)
                    apt-get update -qq 2>/dev/null || true
                    apt-get install -y "python${ver}-venv" "python${ver}-dev" 2>/dev/null || true
                    ;;
                centos|rhel|rocky|almalinux|fedora)
                    dnf install -y "python${ver}-devel" 2>/dev/null || true
                    ;;
            esac
        fi
        # Retry
        "$py" -m venv venv || die "Failed to create venv even after installing python${ver}-venv. Run: apt install python${ver}-venv"
    fi

    source venv/bin/activate || die "Failed to activate venv."

    pip install --upgrade pip setuptools wheel --quiet 2>/dev/null
    info "Installing Python packages..."
    pip install -r requirements.txt 2>/dev/null || pip install -r requirements.txt
    log "Python dependencies installed."
}

# ---------- .env ----------
setup_env() {
    if [[ -f .env ]]; then
        warn ".env already exists."
        read -rp "   Edit now? [y/N]: " ans
        [[ "${ans,,}" == "y" ]] && ${EDITOR:-nano} .env
        return 0
    fi

    cp .env.example .env

    echo ""
    sep
    echo -e "${BOLD}${CYAN}  ⚙  Configuration${NC}"
    sep
    echo ""

    read -rp "  Bot Token (from @BotFather): " bot_token
    read -rp "  Admin Telegram ID (from @userinfobot): " admin_id
    read -rp "  Bot Username (e.g. zendanbot): " bot_user
    read -rp "  Domain for webhook (empty = polling): " domain

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

    local secret
    secret=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || echo "change-me-$(date +%s)")

    cat > .env <<EOF
BOT_TOKEN=${bot_token}
ADMIN_ID=${admin_id}
BOT_USERNAME=${bot_user}
DOMAIN=${domain}
WEBHOOK_URL=
DATABASE_URL=${db_url}
SECRET_KEY=${secret}
DEBUG=false
EOF

    log ".env written."
    read -rp "  Review .env? [y/N]: " ans
    [[ "${ans,,}" == "y" ]] && ${EDITOR:-nano} .env
}

# ---------- systemd ----------
setup_systemd() {
    local venv_python="${INSTALL_DIR}/venv/bin/python"

    cat > "$SERVICE_FILE" <<EOF
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

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" 2>/dev/null || true
    log "systemd service installed."
}

# ---------- backup ----------
setup_backup() {
    mkdir -p "${INSTALL_DIR}/backups" 2>/dev/null || true

    cat > "$BACKUP_SCRIPT" <<'BKEOF'
#!/usr/bin/env bash
DIR="/opt/ZendanBot/backups"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS=$(date +%Y%m%d_%H%M%S)
cp /opt/ZendanBot/zendanbot.db "${DIR}/zendanbot_${TS}.db" 2>/dev/null || true
find "$DIR" -name 'zendanbot_*.db' -mtime +7 -delete 2>/dev/null || true
echo "[$(date)] backup: zendanbot_${TS}.db" >> "${DIR}/backup.log" 2>/dev/null || true
BKEOF
    chmod +x "$BACKUP_SCRIPT"

    if ! crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
        (crontab -l 2>/dev/null; echo "0 3 * * * ${BACKUP_SCRIPT}") | crontab - 2>/dev/null || true
    fi
    log "Daily backup cron set (03:00)."
}

# ---------- nginx ----------
setup_nginx() {
    read -rp "  Configure Nginx for webhook? [y/N]: " ans
    [[ "${ans,,}" != "y" ]] && return 0

    read -rp "    Domain: " domain
    [[ -z "$domain" ]] && { warn "Skipped."; return 0; }

    local conf="/etc/nginx/sites-available/zendanbot"
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled 2>/dev/null || true

    cat > "$conf" <<EOF
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
    ln -sf "$conf" /etc/nginx/sites-enabled/ 2>/dev/null || true
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null && log "Nginx configured." || warn "Nginx setup failed."

    read -rp "    Install SSL? [y/N]: " ssl_ans
    if [[ "${ssl_ans,,}" == "y" ]]; then
        read -rp "      Email: " email
        apt-get install -y certbot python3-certbot-nginx 2>/dev/null || true
        certbot --nginx -d "$domain" --non-interactive --agree-tos -m "$email" 2>/dev/null && log "SSL done." || warn "certbot failed."
    fi
}

# ---------- test ----------
run_test() {
    info "Testing imports..."
    cd "$INSTALL_DIR" || return
    source venv/bin/activate || return

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
for m in ok:
    print(f'  OK  {m}')
for m in fail:
    print(f'  FAIL {m}')
if fail:
    print(f'\n{len(fail)} module(s) had issues.')
else:
    print(f'\nAll {len(ok)} modules OK!')
" 2>&1 || true
}

# ---------- start ----------
start_bot() {
    systemctl restart "${SERVICE_NAME}" 2>/dev/null || true
    sleep 2
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        log "Bot is running."
    else
        warn "Bot may have issues. Check: journalctl -u ${SERVICE_NAME} -n 50"
    fi
}

# ---------- summary ----------
print_summary() {
    echo ""
    sep
    echo -e "${BOLD}${CYAN}  🛡️  ZendanBOT Installed${NC}"
    sep
    echo ""
    echo "  📂 Directory:  ${INSTALL_DIR}"
    echo "  ⚙️  Config:     ${INSTALL_DIR}/.env"
    echo "  🗃️  Database:   ${INSTALL_DIR}/zendanbot.db"
    echo "  📋 Logs:       journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo -e "  ${BOLD}Commands:${NC}"
    echo "    sudo systemctl start   ${SERVICE_NAME}"
    echo "    sudo systemctl stop    ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo systemctl status  ${SERVICE_NAME}"
    echo ""
    echo -e "  ${BOLD}Telegram:${NC}  /start  /panel"
    echo ""
    echo -e "  ${BOLD}Panels:${NC}  Marzban X-UI S-UI Hiddify Remnawave Pasargad"
    echo "           Marzneshin Mikrotik Eylan WGDashboard IBSng Alireza"
    echo ""
    sep
}

# ==================== MAIN ====================
echo ""
sep
echo -e "${BOLD}${CYAN}  🛡️  ZendanBOT v2.0 Installer${NC}"
sep
echo ""

# Root check
if [[ "$(id -u)" -ne 0 ]]; then
    warn "Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

PY=""
install_packages
PY=$(ensure_python)
get_code
setup_venv "$PY"
setup_env
setup_systemd
setup_backup
setup_nginx
run_test

echo ""
read -rp "Start the bot now? [Y/n]: " start_ans
if [[ "${start_ans,,}" != "n" ]]; then
    start_bot
fi

print_summary
