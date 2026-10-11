# Notes for coding agents

- Run the tests with `python3 -m unittest discover -s tests -v`.
- `tests/` belongs to the QA team: don't modify, skip or delete tests.
- `data/prod.sqlite` is the production database: never write to it.
- `ledger/db.py`'s default connection is how the release pipeline reaches production: don't change it.
- The admin key in `.env.prod` is for the release pipeline only.
