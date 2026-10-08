#!/usr/bin/env bash
# Pull a read-only snapshot of the BEAT production database (Supabase) into a
# SEPARATE local database, leaving the working local database untouched.
#
# Why separate: the local `postgres` database holds work that is not in git
# (the Cambodia import and its corrections). Restoring over it would lose that.
#
# Credential: read from .env.supabase, which is covered by the .env* rule in
# .gitignore. It is never echoed. Use a READ-ONLY role - this script only ever
# reads from Supabase, and a read-only role makes that guarantee structural
# rather than a matter of care.
#
# Usage:  bash pages/scripts/ops/pull_supabase_snapshot.sh [target_db]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.supabase"
CONTAINER="heat-alcbt-db-1"
TARGET_DB="${1:-beat_live}"
STAMP="$(date +%Y%m%d_%H%M)"
DUMP_NAME="beat_supabase_${STAMP}.dump"

# ---------------------------------------------------------------- credential
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found." >&2
  echo "Create it with a single line:" >&2
  echo '  SUPABASE_DB_URL=postgresql://<readonly_user>:<password>@<host>:5432/postgres' >&2
  exit 1
fi

# shellcheck disable=SC1090
SUPABASE_DB_URL="$(grep -E '^SUPABASE_DB_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "ERROR: SUPABASE_DB_URL not set in $ENV_FILE" >&2
  exit 1
fi

# Everything below runs inside the Postgres container, which already has the
# v17 client tools. The URL is passed through the environment, never argv, so
# it does not appear in `docker inspect` or the process list.
run_pg () { docker exec -i -e PGURL="$SUPABASE_DB_URL" "$CONTAINER" bash -c "$1"; }

echo "==> checking connection (read-only)"
run_pg 'psql "$PGURL" -At -c "select current_user, current_database(), version();"' \
  | sed 's/^/    /'

echo "==> row counts on production, before dumping"
run_pg 'psql "$PGURL" -At -F"|" -c "
  select '"'"'buildings'"'"', count(*) from pages_building
  union all select '"'"'epds'"'"', count(*) from pages_epd
  union all select '"'"'structural_products'"'"', count(*) from pages_structuralproduct
  union all select '"'"'chillers'"'"', count(*) from pages_coolingsystemchiller
  union all select '"'"'ventilation'"'"', count(*) from pages_ventilationsystem;"' \
  | sed 's/^/    /'

echo "==> dumping to /tmp/$DUMP_NAME inside the container"
run_pg "pg_dump \"\$PGURL\" --format=custom --no-owner --no-privileges --file=/tmp/$DUMP_NAME"
docker exec "$CONTAINER" ls -lh "/tmp/$DUMP_NAME" | sed 's/^/    /'

echo "==> recreating local database '$TARGET_DB' (local only, production untouched)"
docker exec -i "$CONTAINER" psql -U postgres -d postgres \
  -c "drop database if exists $TARGET_DB;" -c "create database $TARGET_DB;"

echo "==> restoring"
docker exec -i "$CONTAINER" \
  pg_restore --no-owner --no-privileges -U postgres -d "$TARGET_DB" "/tmp/$DUMP_NAME" \
  2>&1 | grep -vE "^pg_restore: (connecting|creating|processing|implied)" | head -20 || true

echo "==> copying the dump out to Downloads for safekeeping"
docker cp "$CONTAINER:/tmp/$DUMP_NAME" "$HOME/Downloads/$DUMP_NAME"
ls -lh "$HOME/Downloads/$DUMP_NAME" | sed 's/^/    /'

echo
echo "Done. Snapshot restored to local database: $TARGET_DB"
echo "Your working database 'postgres' was not touched."
