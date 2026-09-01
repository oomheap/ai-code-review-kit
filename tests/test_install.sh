#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai-review-install.XXXXXX")
trap 'rm -rf "$TEST_ROOT"' EXIT HUP INT TERM

"$SCRIPT_DIR/install.sh" \
    --install-dir "$TEST_ROOT/data files" \
    --bin-dir "$TEST_ROOT/bin files" >/dev/null
"$SCRIPT_DIR/install.sh" \
    --install-dir "$TEST_ROOT/data files" \
    --bin-dir "$TEST_ROOT/bin files" >/dev/null

test -x "$TEST_ROOT/bin files/ai-review"
test -f "$TEST_ROOT/data files/prompts/review.md"
test -f "$TEST_ROOT/data files/config/default.json"
test -f "$TEST_ROOT/bin files/ai-review-data/prompts/review.md"
"$TEST_ROOT/bin files/ai-review" --version | grep 'ai-review 1.0.0' >/dev/null

mkdir "$TEST_ROOT/repository"
git -C "$TEST_ROOT/repository" init -q
git -C "$TEST_ROOT/repository" config user.email tests@example.invalid
git -C "$TEST_ROOT/repository" config user.name "AI Review Tests"
printf '%s\n' 'VALUE = 1' >"$TEST_ROOT/repository/example.py"
git -C "$TEST_ROOT/repository" add example.py
git -C "$TEST_ROOT/repository" commit -q -m initial
printf '%s\n' 'VALUE = 2' >"$TEST_ROOT/repository/example.py"

"$TEST_ROOT/bin files/ai-review" "$TEST_ROOT/repository" --provider prompt \
    | grep 'P0（阻断）' >/dev/null

printf '%s\n' "POSIX installer test passed"
