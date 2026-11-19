#!/bin/zsh
# Read-only query helper for the retrospective studies.
# usage: RETRO_DB_ENV=/path/to/env ./db_query.sh "<sql>"
#   env file holds DB_HOST, DB_PORT, DB_NAME, DB_USER (or DB_USERNAME), DB_PASSWORD; it is never committed.
#
# Safeguards (all three apply; the first is the real guarantee):
# 1. Prerequisite: the DB account in RETRO_DB_ENV must be a read-only role (SELECT only). Do not use a role that can write.
# 2. The query runs inside BEGIN TRANSACTION READ ONLY ... ROLLBACK, with default_transaction_read_only=on.
# 3. Statements that could leave the read-only transaction or change data are refused before connecting.
# Session settings: standard_conforming_strings=on (backslash is not an escape), statement timeout TMO (default 120000 ms),
# timezone Asia/Seoul. -q keeps command tags out of the output.
set -euo pipefail
if [[ -z "${RETRO_DB_ENV:-}" || ! -f "$RETRO_DB_ENV" ]]; then
  echo "RETRO_DB_ENV must point to a local env file (see retrospective_study/.env.example)" >&2
  exit 1
fi
if [[ $# -ne 1 || -z "$1" ]]; then
  echo "usage: RETRO_DB_ENV=... $0 \"<sql>\"" >&2
  exit 1
fi
SQL="$1"
# Statement check (sql_guard.py): one read statement only; only '...' literals and -- comments are accepted
# (block comments, E''/U&'' strings, dollar quoting and "identifiers" are refused); COPY only TO STDOUT;
# no transaction-control or write keyword or risky function outside literals.
print -r -- "$SQL" | python3 -I "${0:A:h}/sql_guard.py" || exit 2
set -a; source "$RETRO_DB_ENV"; set +a
export PGPASSWORD="$DB_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on -c standard_conforming_strings=on -c statement_timeout=${TMO:-120000} -c timezone=Asia/Seoul"
exec psql -h "$DB_HOST" -p "$DB_PORT" -U "${DB_USER:-$DB_USERNAME}" -d "$DB_NAME" -X -q -P pager=off -v ON_ERROR_STOP=1 \
  -c "BEGIN TRANSACTION READ ONLY" -c "$SQL" -c "ROLLBACK"
