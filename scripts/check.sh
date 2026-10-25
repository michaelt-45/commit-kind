#!/usr/bin/env bash
# Quality gate: runs every step, prints PASS/FAIL per step, exits 1 if any failed.
# Exit codes: 0 all passed, 1 a step failed, 2 usage error, 3 refused recursive run.
# Written for bash 3.2 (macOS): no arrays, no mapfile, no associative arrays.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
PY="${PYTHON:-python3}"
FAILED=""

run_step() {
    local name="$1"
    shift
    echo "==> $name"
    if "$@"; then
        echo "PASS $name"
    else
        echo "FAIL $name (exit $?)"
        FAILED="$FAILED $name"
    fi
}

finish() {
    if [ -z "$FAILED" ]; then
        echo "check passed"
        exit 0
    fi
    echo "check failed:$FAILED"
    exit 1
}

if [ "$#" -gt 1 ]; then
    echo "usage: scripts/check.sh [--selftest-pass | --selftest-fail]" >&2
    exit 2
fi

case "${1:-}" in
    "")
        if [ -n "${COMMIT_KIND_CHECK_RUNNING:-}" ]; then
            echo "refusing recursive check.sh run (COMMIT_KIND_CHECK_RUNNING is set; unset it)" >&2
            exit 3
        fi
        export COMMIT_KIND_CHECK_RUNNING=1
        run_step ruff-check "$PY" -m ruff check src tests
        run_step ruff-format "$PY" -m ruff format --check src tests
        run_step mypy "$PY" -m mypy --strict src tests
        run_step pytest "$PY" -m pytest -q
        # >>> EVAL STEP (added in B3) >>>
        # run_step eval "$PY" -m commit_kind eval
        # <<< EVAL STEP <<<
        finish
        ;;
    --selftest-pass)
        run_step selftest-ok true
        run_step selftest-ok true
        finish
        ;;
    --selftest-fail)
        run_step before-failure true
        run_step injected-failure false
        run_step after-failure true
        finish
        ;;
    *)
        echo "usage: scripts/check.sh [--selftest-pass | --selftest-fail]" >&2
        exit 2
        ;;
esac
