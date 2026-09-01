#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=${AI_REVIEW_INSTALL_DIR:-${XDG_DATA_HOME:-"$HOME/.local/share"}/ai-code-review}
BIN_DIR=${AI_REVIEW_BIN_DIR:-"$HOME/.local/bin"}

usage() {
    printf '%s\n' "Usage: ./install.sh [--install-dir PATH] [--bin-dir PATH]"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --install-dir)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            INSTALL_DIR=$2
            shift 2
            ;;
        --bin-dir)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            BIN_DIR=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

command -v python3 >/dev/null 2>&1 || {
    printf '%s\n' "Python 3.9 or later is required." >&2
    exit 1
}

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' || {
    printf '%s\n' "Python 3.9 or later is required." >&2
    exit 1
}

for required in src/ai_review.py prompts/review.md config/default.json; do
    [ -f "$SCRIPT_DIR/$required" ] || {
        printf 'Installer payload is incomplete: %s\n' "$required" >&2
        exit 1
    }
done

umask 022
mkdir -p \
    "$INSTALL_DIR/src" \
    "$INSTALL_DIR/prompts" \
    "$INSTALL_DIR/config" \
    "$BIN_DIR/ai-review-data/prompts"
cp "$SCRIPT_DIR/src/ai_review.py" "$INSTALL_DIR/src/ai_review.py"
cp "$SCRIPT_DIR/prompts/review.md" "$INSTALL_DIR/prompts/review.md"
cp "$SCRIPT_DIR/config/default.json" "$INSTALL_DIR/config/default.json"
cp "$SCRIPT_DIR/src/ai_review.py" "$BIN_DIR/ai-review"
cp "$SCRIPT_DIR/prompts/review.md" "$BIN_DIR/ai-review-data/prompts/review.md"
chmod 0755 "$BIN_DIR/ai-review"

printf 'Installed ai-review %s to %s\n' "1.3.0" "$BIN_DIR/ai-review"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        printf '%s\n' "Add $BIN_DIR to PATH, then run: ai-review --doctor"
        ;;
esac
