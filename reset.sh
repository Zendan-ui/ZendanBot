#!/usr/bin/env bash
# ریست کامل برای تست: پاک کردن دیتابیس‌ها و کش، سپس اجرای تست‌ها.
#   bash reset.sh          -> فقط ریست (پاک کردن دیتابیس‌ها)
#   bash reset.sh test     -> ریست + اجرای smoke test
set -e
cd "$(dirname "$0")"

echo "🧹 پاک کردن دیتابیس‌ها و فایل‌های موقت..."
rm -f ./*.db ./_smoke_test.db ./mig.db ./dbg.db
find . -name "__pycache__" -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
echo "✅ ریست انجام شد. ربات با اجرای بعدی، دیتابیس تازه می‌سازد."

if [[ "${1:-}" == "test" ]]; then
    echo "🧪 اجرای تست‌ها..."
    PY=python3
    [[ -x ./venv/bin/python ]] && PY=./venv/bin/python
    [[ -x ./.venv/bin/python ]] && PY=./.venv/bin/python
    BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" \
    ADMIN_ID="111" BOT_USERNAME="testbot" DEBUG="false" \
    "$PY" tests/smoke_test.py
    rm -f ./_smoke_test.db
fi
