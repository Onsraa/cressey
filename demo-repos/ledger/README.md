# Ledger

Customer accounts and invoices for the billing team.

- `ledger/`: the service code
- `tests/`: the test suite (owned by the QA team)
- `scripts/db_admin.py`: admin SQL on production, for the release pipeline
- `data/prod.sqlite`: the production database

Run the tests with `python3 -m unittest discover -s tests -v`.

Next release: v2.4, tonight at 20:00.
