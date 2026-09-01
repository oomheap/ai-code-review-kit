#!/bin/sh
set -eu

REPOSITORY="oomheap/ai-code-review-kit"
REF=${AI_REVIEW_REF:-main}
TEMP_DIR=""

case "$REF" in
    ""|*[!A-Za-z0-9._-]*)
        printf 'Invalid AI_REVIEW_REF: %s\n' "$REF" >&2
        exit 2
        ;;
esac

command -v curl >/dev/null 2>&1 || {
    printf '%s\n' "curl is required for the online installer." >&2
    exit 1
}

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ai-review-online.XXXXXX")
cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT HUP INT TERM

RAW_BASE="https://raw.githubusercontent.com/$REPOSITORY/$REF"

fetch() {
    relative_path=$1
    destination="$TEMP_DIR/$relative_path"
    mkdir -p "$(dirname -- "$destination")"
    curl -fsSL --proto '=https' --tlsv1.2 \
        "$RAW_BASE/$relative_path" >"$destination"
    [ -s "$destination" ] || {
        printf 'Downloaded an empty file: %s\n' "$relative_path" >&2
        exit 1
    }
}

for payload in \
    install.sh \
    src/ai_review.py \
    prompts/review.md \
    config/default.json
do
    fetch "$payload"
done

sh -n "$TEMP_DIR/install.sh"
printf 'Installing ai-review from GitHub ref %s...\n' "$REF"
sh "$TEMP_DIR/install.sh" "$@"
