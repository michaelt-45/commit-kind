# B5 — Summary (rework 1)

- Commit: b3cd3c177df12c2cbfaf9304b7a66bf735f16d9e on loop/B5 (not pushed, not merged)
- S1: tests/test_classify_cli.py:68-75. The `run("-c", code) if False else subprocess.run(...)` expression is replaced with a plain `r = subprocess.run(...)` with the same arguments.
- S2: tests/test_cli.py:21 and tests/test_eval.py:219. PYTHONPATH is now `os.pathsep.join(["src", "tests"])`. `import os` was already present in both files.
- ./scripts/check.sh: check passed. 5 PASS lines (ruff-check, ruff-format, mypy, pytest, eval). pytest: 128 passed. The eval passed, and all negative controls failed as expected.
