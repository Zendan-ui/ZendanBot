#!/usr/bin/env bash
# ============================================
#  ZendanBOT v2.0 - Installer
#  Light, robust, polling mode (no domain/webhook needed)
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

log()  { printf "${GREEN}[✓]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()  { printf "${RED}[✗]${NC} %s\n" "$*" >&2; }
info() { printf "${BLUE}[i]${NC} %s\n" "$*"; }
sep()  { printf "${CYAN}──────────────────────────────────────────────${NC}\n"; }
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

# ---------- wait for apt lock ----------
wait_apt() {
    local i=0
    while fuser /var/lib/dpkg/lock-frontend &>/dev/null; do
        i=$((i + 1))
        if [[ $i -gt 30 ]]; then
            warn "Waited 30s for apt lock, forcing..."
            kill $(fuser /var/lib/dpkg/lock-frontend 2>/dev/null) 2>/dev/null || true
            rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock 2>/dev/null || true
            sleep 2
            break
        fi
        info "Waiting for apt lock... ($i/30)"
        sleep 2
    done
}

# ---------- install system packages ----------
install_packages() {
    local os
    os=$(detect_os)
    info "OS: $os"

    case "$os" in
        ubuntu|debian|linuxmint|pop)
            wait_apt
            apt-get update -qq
            apt-get install -y \
                python3 python3-pip python3-dev \
                python3-venv python3.11-venv python3.12-venv python3.13-venv \
                git curl wget sqlite3 libffi-dev libssl-dev \
                software-properties-common 2>/dev/null || \
            apt-get install -y \
                python3 python3-pip python3-dev python3-venv \
                git curl wget sqlite3 libffi-dev libssl-dev \
                software-properties-common
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
        arch|manjaro)
            pacman -Sy --noconfirm python python-pip git curl wget sqlite base-devel 2>/dev/null || true
            ;;
        *)
            warn "Unknown distro — trying apt..."
            wait_apt
            apt-get update -qq
            apt-get install -y python3 python3-pip python3-venv git curl wget sqlite3 || true
            ;;
    esac
    log "System packages done."
}

# ---------- find python 3.10+ ----------
# IMPORTANT: Only echo the python command to stdout. All messages to stderr.
find_python() {
    local cmd ver major minor
    for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" -c 'import sys; print(sys.version_info.major, sys.version_info.minor)' 2>/dev/null) || continue
            major=$(echo "$ver" | awk '{print $1}')
            minor=$(echo "$ver" | awk '{print $2}')
            if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
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
        wait_apt
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt-get update -qq
        apt-get install -y python3.12 python3.12-venv python3.12-dev 2>/dev/null || \
        apt-get install -y python3.11 python3.11-venv python3.11-dev 2>/dev/null || true
        py=$(find_python)
        if [[ -n "$py" ]]; then
            log "Python installed." >&2
            echo "$py"
            return 0
        fi
    fi
    die "Install Python 3.10+ manually and re-run."
}

# ---------- clone / update ----------
get_code() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing installation..."
        cd "$INSTALL_DIR" || die "Cannot cd to $INSTALL_DIR"
        git pull || warn "Git pull failed — using local files."
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
    local ver
    ver=$("$py" -c 'import sys; v=sys.version_info; print(f"{v.major}.{v.minor}")' 2>/dev/null || echo "")

    info "Python $ver — creating virtual environment..."
    rm -rf "${INSTALL_DIR}/venv" 2>/dev/null || true

    # Try 1: normal venv
    if "$py" -m venv "${INSTALL_DIR}/venv" 2>&1; then
        source "${INSTALL_DIR}/venv/bin/activate" || die "Failed to activate venv."
        log "Virtual environment created."
        install_pip_deps
        return 0
    fi

    # Try 2: install version-specific venv package
    warn "venv failed — installing python${ver}-venv..."
    wait_apt
    apt-get install -y "python${ver}-venv" "python${ver}-dev" 2>&1
    rm -rf "${INSTALL_DIR}/venv" 2>/dev/null || true
    if "$py" -m venv "${INSTALL_DIR}/venv" 2>&1; then
        source "${INSTALL_DIR}/venv/bin/activate" || die "Failed to activate venv."
        log "Virtual environment created (after installing python${ver}-venv)."
        install_pip_deps
        return 0
    fi

    # Try 3: --without-pip + get-pip.py
    warn "Trying --without-pip workaround..."
    rm -rf "${INSTALL_DIR}/venv" 2>/dev/null || true
    "$py" -m venv --without-pip "${INSTALL_DIR}/venv" || die "Cannot create venv at all."
    source "${INSTALL_DIR}/venv/bin/activate" || die "Failed to activate venv."

    info "Downloading pip via get-pip.py..."
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py || die "Cannot download get-pip.py."
    python /tmp/get-pip.py 2>&1 | tail -3
    rm -f /tmp/get-pip.py
    log "pip bootstrapped."
    install_pip_deps
}

install_pip_deps() {
    pip install --upgrade pip setuptools wheel --quiet 2>/dev/null
    info "Installing Python packages (may take a few minutes)..."
    pip install -r requirements.txt || die "pip install failed."
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

    if [[ -f .env.example ]]; then
        cp .env.example .env
    else
        touch .env
    fi

    echo ""
    sep
    printf "${BOLD}${CYAN}  ⚙  Configuration${NC}\n"
    sep
    echo ""

    local bot_token admin_id bot_user
    while :; do
        read -rp "  Bot Token (from @BotFather): " bot_token
        if [[ "$bot_token" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then
            break
        else
            err "Invalid token format. Expected: 1234567:AAH-xxxxxxxxxxxx"
        fi
    done

    while :; do
        read -rp "  Admin Telegram ID (from @userinfobot): " admin_id
        if [[ "$admin_id" =~ ^[0-9]+$ ]]; then
            break
        else
            err "ADMIN_ID must be numeric."
        fi
    done

    read -rp "  Bot Username (e.g. zendanbot): " bot_user
    bot_user="${bot_user:-zendanbot}"

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
DATABASE_URL=${db_url}
SECRET_KEY=${secret}
DEBUG=false
DOMAIN=
WEBHOOK_URL=
EOF

    chmod 600 .env
    log ".env written."

    read -rp "  Review .env? [y/N]: " ans
    [[ "${ans,,}" == "y" ]] && ${EDITOR:-nano} .env
}

# ---------- verify token ----------
verify_token() {
    info "Testing Telegram connectivity..."
    local token resp uname
    token=$(grep -E '^BOT_TOKEN=' "${INSTALL_DIR}/.env" | cut -d= -f2-)

    resp=$(curl -s --max-time 15 "https://api.telegram.org/bot${token}/getMe" || true)
    if echo "$resp" | grep -q '"ok":true'; then
        uname=$(echo "$resp" | grep -oE '"username":"[^"]+"' | head -1 | cut -d'"' -f4)
        log "Bot reachable: @${uname}"
        return 0
    fi

    warn "Telegram API unreachable. Response:"
    echo "$resp" | head -c 300
    echo ""
    warn "If the server has an Iran IP, Telegram is blocked. Use a non-Iran VPS."
    return 1
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
EnvironmentFile=${INSTALL_DIR}/.env
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

# ---------- test ----------
run_test() {
    info "Testing imports..."
    cd "$INSTALL_DIR" || return
    source "${INSTALL_DIR}/venv/bin/activate" || return

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
    ('app.panels.hiddify', 'HiddifyPanel'),
    ('app.panels.alireza', 'AlirezaPanel'),
    ('app.panels.wireguard', 'WGDashboardPanel'),
    ('app.panels.marzneshin', 'MarzneshinPanel'),
    ('app.panels.eylan', 'EylanPanel'),
    ('app.panels.ibsng', 'IBSngPanel'),
    ('app.payments.card', 'process_card_receipt'),
    ('app.payments.nowpayment', 'NowPayment'),
    ('app.payments.zarinpal', 'ZarinpalPayment'),
    ('app.payments.aqayepardakht', 'AqayePardakht'),
    ('app.payments.tron', 'TronPayment'),
    ('app.payments.stars', 'TelegramStars'),
    ('app.payments.plisio', 'PlisioPayment'),
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
    print(f'  OK   {m}')
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
    printf "${BOLD}${CYAN}  🛡️  ZendanBOT Installed${NC}\n"
    sep
    echo ""
    echo "  📂 Directory:  ${INSTALL_DIR}"
    echo "  ⚙️  Config:     ${INSTALL_DIR}/.env"
    echo "  🗃️  Database:   ${INSTALL_DIR}/zendanbot.db"
    echo "  📋 Logs:       journalctl -u ${SERVICE_NAME} -f"
    echo "  📡 Mode:       Long polling (no domain/webhook)"
    echo ""
    printf "  ${BOLD}Commands:${NC}\n"
    echo "    sudo systemctl start   ${SERVICE_NAME}"
    echo "    sudo systemctl stop    ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo systemctl status  ${SERVICE_NAME}"
    echo ""
    printf "  ${BOLD}Telegram:${NC}  /start  /panel\n"
    echo ""
    printf "  ${BOLD}Panels:${NC}  Marzban X-UI S-UI Hiddify Remnawave Pasargad\n"
    echo "           Marzneshin Mikrotik Eylan WGDashboard IBSng Alireza"
    echo ""
    sep
}

# ==================== MAIN ====================
echo ""
sep
printf "${BOLD}${CYAN}  🛡️  ZendanBOT v2.0 Installer${NC}\n"
sep
echo ""

# Root check
if [[ "$(id -u)" -ne 0 ]]; then
    warn "Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

install_packages
PY=$(ensure_python)   # only stdout = python command, all messages go to stderr
get_code
setup_venv "$PY"
setup_env
verify_token || warn "Continuing anyway. Fix .env later and run: systemctl restart ${SERVICE_NAME}"
setup_systemd
setup_backup
run_test

echo ""
read -rp "Start the bot now? [Y/n]: " start_ans
if [[ "${start_ans,,}" != "n" ]]; then
    start_bot
fi

print_summary
