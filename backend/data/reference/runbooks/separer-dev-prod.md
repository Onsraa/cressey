# Separating development and production

Owner: Platform team.

1. Agents and developers work on a copy of the staging database, never on production.
2. No production key may be found in an agent's workspace.
3. Access to production goes through a request approved by a human and limited in time.
4. Backups are stored on a volume separate from the database they protect.
5. Restoring a backup is tested every week and its result is recorded.
