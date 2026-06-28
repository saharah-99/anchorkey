# Contributing to anchorkey

Thanks for your interest. This project values **readable, auditable identity logic** over
cleverness: a contribution that a non-specialist can follow is worth more than one that shaves
a fraction of a percent of accuracy behind an opaque model.

## Ground rules

- **No runtime dependencies in the core library.** Keep `src/anchorkey/` pure standard library.
  Test/figure extras belong in the `dev` / `figures` optional groups in `pyproject.toml`.
- **Comment for a non-Python reader.** Explain *what* and *why*, not just *how*.
- **Every behaviour gets a test.** New matching rules need example tests; anything touching
  `normalize` must keep the idempotency property test (`tests/test_normalize.py`) green.
- **Be conservative about merging identities.** A false merge (collision) is worse than a
  missed one (fragmentation): it silently averages two real things together. When in doubt,
  don't merge.

## Getting set up

```bash
pip install -e ".[dev]"
pytest
```

## Proposing a change

1. Open an issue describing the drift case or matching gap, ideally with a real example string.
2. Add a failing test that captures it.
3. Make it pass with the smallest, clearest change.
4. Open a pull request linking the issue.
