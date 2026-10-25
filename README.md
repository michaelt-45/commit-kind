# commit-kind

A small Python CLI and library that classifies git commit messages by type (`feat`, `fix`, `docs`,
`refactor`, `test`, `chore`) with a transparent, rule-based classifier. Every prediction names the
rule that produced it.

## Status

Milestone 1 is in progress. The CLI is not usable yet beyond `--version`.

## Requirements

Python >= 3.10. Development tools (ruff, mypy, pytest) come from the `dev` extra.

## Quality gate

```
./scripts/check.sh
```

Runs ruff, ruff format, mypy (strict) and pytest, and exits non-zero if any step fails. Set
`PYTHON=` to choose the interpreter.

## Try it

```
PYTHONPATH=src python3 -m commit_kind --version
```

## License

MIT, see `LICENSE`.
