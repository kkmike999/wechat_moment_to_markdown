#!/bin/sh

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
URL_FILE=""
OUTPUT_DIR="$SCRIPT_DIR/temp"
PYTHON_EXE=""
TOTAL=0
SUCCESS=0
FAILED=0

usage() {
    resolve_default_url_file >/dev/null 2>&1 || true
    echo "Usage:"
    echo "  $(basename "$0") [url_file] [output_dir]"
    echo
    echo "Default:"
    echo "  url_file   = ${URL_FILE:-<not found>}"
    echo "  output_dir = $OUTPUT_DIR"
}

resolve_default_url_file() {
    set -- "$SCRIPT_DIR"/temp/550*_urls.txt
    if [ "$1" = "$SCRIPT_DIR/temp/550*_urls.txt" ]; then
        echo "No default URL list matched $SCRIPT_DIR/temp/550*_urls.txt." >&2
        return 1
    fi

    if [ "$#" -gt 1 ]; then
        echo "Multiple default URL lists matched $SCRIPT_DIR/temp/550*_urls.txt." >&2
        echo "Pass the desired file path as the first argument." >&2
        return 1
    fi

    URL_FILE=$1
    return 0
}

resolve_python() {
    if command -v python >/dev/null 2>&1; then
        PYTHON_EXE=python
        return 0
    fi

    if command -v py >/dev/null 2>&1; then
        PYTHON_EXE=py
        return 0
    fi

    echo "Python was not found. Make sure 'python' or 'py' is available in PATH." >&2
    return 1
}

download_one() {
    url=$1
    if [ -z "$url" ]; then
        return 0
    fi

    TOTAL=$((TOTAL + 1))
    echo "[$TOTAL] Fetching: $url"
    "$PYTHON_EXE" "$SCRIPT_DIR/download_wechat_article.py" "$url" --output-dir "$OUTPUT_DIR"
    status=$?
    if [ "$status" -ne 0 ]; then
        FAILED=$((FAILED + 1))
        echo "[FAILED] $url"
        echo
        return 0
    fi

    SUCCESS=$((SUCCESS + 1))
    echo "[OK] $url"
    echo
    return 0
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
esac

if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
    URL_FILE=$1
else
    resolve_default_url_file || exit 1
fi

if [ $# -ge 2 ] && [ -n "${2:-}" ]; then
    OUTPUT_DIR=$2
fi

if [ ! -f "$URL_FILE" ]; then
    echo "URL list not found: $URL_FILE" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/download_wechat_article.py" ]; then
    echo "Script not found: $SCRIPT_DIR/download_wechat_article.py" >&2
    exit 1
fi

resolve_python || exit 1
mkdir -p "$OUTPUT_DIR"

echo "URL file: $URL_FILE"
echo "Output dir: $OUTPUT_DIR"
echo "Python: $PYTHON_EXE"
echo

while IFS= read -r url || [ -n "$url" ]; do
    download_one "$url"
done < "$URL_FILE"

echo
echo "Done. Total: $TOTAL, success: $SUCCESS, failed: $FAILED"
[ "$FAILED" -eq 0 ]
