# Contributing

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest
```

CI runs exactly those four commands on Python 3.11–3.13; a PR merges when they pass.

- Keep the runtime offline: network and LLM calls belong only in compile-time code.
- Every opt-in feature is switched on in one place, the scenario config.
- Fail fast on bad input; no silent fallbacks.
- New behaviour comes with a test.
