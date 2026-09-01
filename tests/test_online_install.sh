#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai-review-online-test.XXXXXX")
trap 'rm -rf "$TEST_ROOT"' EXIT HUP INT TERM

PATH="$SCRIPT_DIR/tests/fixtures:$PATH" \
AI_REVIEW_TEST_SOURCE="$SCRIPT_DIR" \
AI_REVIEW_EXPECT_AUTH=1 \
AI_REVIEW_REF=main \
GITHUB_TOKEN=github_pat_test_123 \
"$SCRIPT_DIR/install-online.sh" \
    --install-dir "$TEST_ROOT/data files" \
    --bin-dir "$TEST_ROOT/bin files" >/dev/null

test -x "$TEST_ROOT/bin files/ai-review"
test -f "$TEST_ROOT/bin files/ai-review-data/prompts/review.md"
"$TEST_ROOT/bin files/ai-review" --version | grep 'ai-review 1.1.0' >/dev/null

PATH="$SCRIPT_DIR/tests/fixtures:$PATH" \
AI_REVIEW_TEST_SOURCE="$SCRIPT_DIR" \
AI_REVIEW_REF=main \
GITHUB_TOKEN= \
GH_TOKEN= \
"$SCRIPT_DIR/install-online.sh" \
    --install-dir "$TEST_ROOT/public data" \
    --bin-dir "$TEST_ROOT/public bin" >/dev/null
test -x "$TEST_ROOT/public bin/ai-review"

if AI_REVIEW_REF='../unsafe' "$SCRIPT_DIR/install-online.sh" >/dev/null 2>&1; then
    printf '%s\n' "Unsafe ref was unexpectedly accepted" >&2
    exit 1
fi

if GITHUB_TOKEN='invalid token' "$SCRIPT_DIR/install-online.sh" >/dev/null 2>&1; then
    printf '%s\n' "Unsafe token characters were unexpectedly accepted" >&2
    exit 1
fi

printf '%s\n' "Online installer test passed"
