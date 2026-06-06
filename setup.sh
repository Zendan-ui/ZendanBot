#!/usr/bin/env bash
# ZendanBot installer
# Polling mode, no webhook, no domain required.
# Supported: Ubuntu 20/22/24, Debian 11/12, CentOS/Rocky/Alma 8/9, Fedora, Arch.
#
# Usage:
#   sudo bash setup.sh

set -u

# -------- colors --------
B='\033[1m'; R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'

log()  { echo -e "${G}[ok]${N} $*"; }
warn() { echo -e "${Y}[!]${N} $*"; }
err()  { echo -e "${R}[x]${N} $*" >&2; }
info() { echo -e "${C}[*]${N} $*"; }
sep()  { echo "------------------------------------------------"; }
die()  { err "$@"; exit 1; }

# -------- constants --------
INSTALL_DIR="${INSTALL_DIR:-/opt/ZendanBot}"
REPO_URL="${REPO_URL:-https://github.com/Zendan-ui/ZendanBot.git}"
SERVICE_NAME="zendanbot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PY_MIN_MAJOR=3
PY_MIN_MINOR=10

# -------- helpers --------
require_root() {
    [[ $EUID -eq 0 ]] || die "Run as root: sudo bash setup.sh"
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "${ID:-unknown}"
    else
        echo "unknown"
    fi
}

install_system_packages() {
    local os; os=$(detect_os)
    info "OS: $os"

    case "$os" in
        ubuntu|debian|linuxmint|pop|raspbian)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq
            apt-get install -y -qq \
                python3 python3-pip python3-venv python3-dev \
                git curl wget ca-certificates \
                build-essential libffi-dev libssl-dev sqlite3 \
                || die "package install failed"
            ;;
        centos|rhel|rocky|almalinux|ol)
            yum install -y epel-release 2>/dev/null || true
            (yum install -y python3 python3-pip python3-devel \
                git curl wget gcc gcc-c++ make \
                libffi-devel openssl-devel sqlite \
             || dnf install -y python3 python3-pip python3-devel \
                git curl wget gcc gcc-c++ make \
                libffi-devel openssl-devel sqlite) \
                || die "package install failed"
            ;;
        fedora)
            dnf install -y python3 python3-pip python3-devel \
                git curl wget gcc gcc-c++ make \
                libffi-devel openssl-devel sqlite \
                || die "package install failed"
            ;;
        arch|manjaro)
            pacman -Sy --noconfirm python python-pip git curl wget base-devel sqlite \
                || die "package install failed"
            ;;
        *)
            warn "Unknown OS. Continuing; ensure python3 and git are installed."
            ;;
    esac
    log "system packages installed"
}

check_python() {
    command -v python3 >/dev/null || die "python3 not found"
    local v major minor
    v=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major=${v%.*}; minor=${v#*.}
    info "python: $v"
    if (( major < PY_MIN_MAJOR )) || { (( major == PY_MIN_MAJOR )) && (( minor < PY_MIN_MINOR )); }; then
        die "python ${PY_MIN_MAJOR}.${PY_MIN_MINOR}+ required (found $v)"
    fi
}

clone_repo() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "updating existing repo"
        git -C "$INSTALL_DIR" fetch --quiet --all
        git -C "$INSTALL_DIR" reset --hard origin/HEAD 2>/dev/null \
            || git -C "$INSTALL_DIR" pull --rebase --quiet \
            || warn "git pull failed; continuing with local files"
    elif [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
        warn "$INSTALL_DIR exists and is not a git repo; using files in place"
    else
        info "cloning $REPO_URL"
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || die "git clone failed"
    fi
    log "source ready at $INSTALL_DIR"
}

setup_venv() {
    cd "$INSTALL_DIR" || die "cd $INSTALL_DIR failed"
    [[ -d venv ]] || python3 -m venv venv || die "venv creation failed"
    # shellcheck disable=SC1091
    source venv/bin/activate
    pip install -q -U pip setuptools wheel
    info "installing python dependencies"
    pip install -q -r requirements.txt || die "pip install failed"
    deactivate
    log "virtualenv ready"
}

read_config() {
    sep
    echo -e "${B}Configuration${N}"
    sep

    local cur_token="" cur_admin="" cur_user=""
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cur_token=$(grep -E '^BOT_TOKEN='   "$INSTALL_DIR/.env" | cut -d= -f2- || true)
        cur_admin=$(grep -E '^ADMIN_ID='    "$INSTALL_DIR/.env" | cut -d= -f2- || true)
        cur_user=$( grep -E '^BOT_USERNAME=' "$INSTALL_DIR/.env" | cut -d= -f2- || true)
        info "existing .env detected; press Enter to keep current value"
    fi

    local bot_token admin_id bot_user
    while :; do
        read -rp "Bot Token (from @BotFather) [${cur_token}]: " bot_token
        bot_token=${bot_token:-$cur_token}
        if [[ "$bot_token" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then break
        else err "invalid token format (expected 1234567:AAH-...)"
        fi
    done

    while :; do
        read -rp "Admin Telegram ID (numeric, from @userinfobot) [${cur_admin}]: " admin_id
        admin_id=${admin_id:-$cur_admin}
        if [[ "$admin_id" =~ ^[0-9]+$ ]]; then break
        else err "ADMIN_ID must be numeric"
        fi
    done

    read -rp "Bot Username (without @) [${cur_user:-zendanbot}]: " bot_user
    bot_user=${bot_user:-${cur_user:-zendanbot}}

    local secret
    secret=$(openssl rand -hex 32 2>/dev/null \
             || python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null \
             || echo "change-me-$(date +%s)")

    cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=${bot_token}
ADMIN_ID=${admin_id}
BOT_USERNAME=${bot_user}
DATABASE_URL=sqlite+aiosqlite:///./zendanbot.db
DEBUG=false
SECRET_KEY=${secret}
DOMAIN=
WEBHOOK_URL=
EOF

    chmod 600 "$INSTALL_DIR/.env"
    log ".env written"
}

verify_token() {
    info "testing Telegram connectivity"
    local token resp uname
    token=$(grep -E '^BOT_TOKEN=' "$INSTALL_DIR/.env" | cut -d= -f2-)
    resp=$(curl -s --max-time 15 "https://api.telegram.org/bot${token}/getMe" || true)

    if echo "$resp" | grep -q '"ok":true'; then
        uname=$(echo "$resp" | grep -oE '"username":"[^"]+"' | head -1 | cut -d'"' -f4)
        log "bot reachable: @${uname}"
        return 0
    fi

    warn "Telegram API unreachable. Response:"
    echo "$resp" | head -c 300
    echo
    warn "If the server has an Iran IP, Telegram is blocked. Use a non-Iran VPS."
    return 1
}

setup_systemd() {
    info "creating systemd service"

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ZendanBot Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now "${SERVICE_NAME}" 2>/dev/null
    sleep 3

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log "service ${SERVICE_NAME} is running"
    else
        warn "service failed to start, recent logs:"
        journalctl -u "${SERVICE_NAME}" -n 30 --no-pager
    fi
}

print_summary() {
    sep
    echo -e "${B}${G}Installation complete${N}"
    sep
    echo "  path:    ${INSTALL_DIR}"
    echo "  service: ${SERVICE_NAME}"
    echo "  mode:    long polling"
    echo
    echo "Commands:"
    echo "  systemctl status   ${SERVICE_NAME}"
    echo "  systemctl restart  ${SERVICE_NAME}"
    echo "  systemctl stop     ${SERVICE_NAME}"
    echo "  journalctl -u ${SERVICE_NAME} -f"
    echo "  nano ${INSTALL_DIR}/.env"
    echo
    echo "Now open Telegram and send /start to your bot."
    sep
}

main() {
    require_root
    install_system_packages
    check_python
    clone_repo
    setup_venv
    read_config
    verify_token || warn "starting the service anyway; fix .env later and run: systemctl restart ${SERVICE_NAME}"
    setup_systemd
    print_summary
}

main "$@"
