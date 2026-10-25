# Contributing

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest && mkdocs build --strict
```

CI runs exactly those commands (tests on Python 3.11–3.13). A PR merges when they pass.

- After changing a config model, run `python scripts/gen_reference.py`. A test fails if the reference is stale.
- `python scripts/gen_examples.py` regenerates `examples/scenarios/` (logistics needs network for OSRM).
- Release: bump `version` in `pyproject.toml`, add a CHANGELOG entry, then tag `vX.Y.Z`. The tag must match the version.

- Keep the runtime offline: network and LLM calls belong only in compile-time code.
- Every opt-in feature is switched on in one place, the scenario config.
- Fail fast on bad input; no silent fallbacks.
- New behaviour comes with a test.
