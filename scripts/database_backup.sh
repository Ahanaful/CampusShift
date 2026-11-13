#!/usr/bin/env bash
# Run as campusshift with the deployment environment loaded. No password arguments.
set -euo pipefail
umask 077
action=${1:?backup or restore required}
file=${2:?backup path required}
export PGHOST=${PGHOST:?Set database host}
export PGUSER=${PGUSER:?Set database user}
export PGDATABASE=${PGDATABASE:?Set database name}
export PGPASSFILE=${PGPASSFILE:-/etc/campusshift/pgpass}
export PGSSLMODE=${PGSSLMODE:-verify-full}
export PGSSLROOTCERT=${PGSSLROOTCERT:-/etc/campusshift/rds-ca.pem}
if [[ $action == backup ]]; then
    [[ ! -e $file && ! -L $file ]] || { echo 'Refusing to overwrite an existing backup or symbolic link' >&2; exit 1; }
    pg_dump --format=custom --no-owner --no-acl --file="$file"
    pg_restore --list "$file" >/dev/null
    echo 'Backup created. Copy it to approved protected storage outside this instance.'
elif [[ $action == restore ]]; then
    [[ ${3:-} == --approve-empty-target-restore ]] || { echo 'Explicit restore approval flag required' >&2; exit 1; }
    [[ $(psql -X -A -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'") == 0 ]] || { echo 'Restore target must be empty; existing data was preserved' >&2; exit 1; }
    pg_restore --single-transaction --exit-on-error --no-owner --no-acl --dbname="$PGDATABASE" "$file"
else
    echo 'Unknown action' >&2; exit 1
fi
