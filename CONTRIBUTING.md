# Contributing

Thanks for your interest in improving Library Management! This app runs on
[Frappe](https://frappeframework.com/) v15 and depends on the
[Education](https://github.com/frappe/education) app (for `Student` and `School`).

## Developer setup

You need a working [Frappe Bench](https://github.com/frappe/bench) with Frappe v15 and the
Education app installed.

```bash
# in your bench
bench get-app https://github.com/WalnutAppSuite/library_management --branch library-revamp
bench --site <your-site> install-app library_management

# enable formatting/linting hooks
cd apps/library_management
pre-commit install
```

Useful loops while developing:

```bash
bench build --app library_management        # rebuild JS/CSS assets
bench --site <your-site> migrate            # sync doctype/schema changes
bench --site <your-site> reload-doc library_management <module> <doctype>
```

## Code style

Formatting and linting are enforced by `pre-commit`:

- **Python** — `ruff` (lint) and `ruff format` (configured in `pyproject.toml`, tab indent,
  110 cols)
- **JS** — `eslint` + `prettier`

Run everything before pushing:

```bash
pre-commit run --all-files
```

## Tests

```bash
bench --site <your-site> run-tests --app library_management
```

Please add or update tests when you change behaviour in `services.py` or the doctype
controllers.

## Pull requests

1. Branch off `library-revamp`.
2. Keep changes focused; write a clear description of what and why.
3. **Sign off your commits** (`git commit -s`) — we use the
   [Developer Certificate of Origin](https://developercertificate.org/).
4. Make sure `pre-commit run --all-files` and the test suite pass.

## Reporting bugs / requesting features

Open an issue on the [tracker](https://github.com/WalnutAppSuite/library_management/issues) with
clear reproduction steps (and your Frappe/Education versions for bugs).
