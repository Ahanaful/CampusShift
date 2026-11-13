#!/usr/bin/env bash
# Run on the new AL2023 server: sudo bash scripts/deploy_backend.sh ARCHIVE RELEASE_ID
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root on the deployment host.' >&2; exit 1; }
archive=$(realpath "${1:?release archive required}")
release=${2:?release ID required}
[[ $release =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid release ID' >&2; exit 1; }
target="/opt/campusshift/releases/$release"
[[ ! -e $target ]] || { echo 'Release already exists; choose a new ID. No files changed.' >&2; exit 1; }
test -s /etc/campusshift/application.env
test -s /etc/campusshift/nginx.conf
test -s /etc/campusshift/tls/fullchain.pem
test -s /etc/campusshift/tls/privkey.pem
install -d -m 0755 "$target"
# Reject archive entries that escape this release directory or create symlinks.
python3.11 - "$archive" "$target" <<'PY'
from pathlib import Path
import sys, tarfile
target = Path(sys.argv[2]).resolve()
with tarfile.open(sys.argv[1]) as archive:
    for entry in archive.getmembers():
        if entry.issym() or entry.islnk() or not (entry.isfile() or entry.isdir()):
            raise SystemExit('Unsafe archive member type')
        if not (target / entry.name).resolve().is_relative_to(target):
            raise SystemExit('Archive member escapes release directory')
    archive.extractall(target, filter='data')
PY
python3.11 -m venv "$target/.venv"
"$target/.venv/bin/python" -m pip install -r "$target/backend/requirements.txt"
"$target/.venv/bin/python" -m pip install "$target"
chmod -R go-w "$target"
install -d -o root -g campusshift -m 0750 /var/log/campusshift
[[ ! -L /var/log/campusshift/application.log ]] || { echo 'Refusing symbolic link for application log' >&2; exit 1; }
touch /var/log/campusshift/application.log
chown root:campusshift /var/log/campusshift/application.log
chmod 0640 /var/log/campusshift/application.log
install -m 0644 "$target/infrastructure/runtime/logrotate.conf" /etc/logrotate.d/campusshift
# Additive upgrade only. On failure the existing current release keeps serving.
cd "$target/backend"
set -a
source /etc/campusshift/application.env
set +a
sudo --preserve-env=APP_ENV,DATABASE_URL,JWT_SECRET,CORS_ORIGINS,PGPASSFILE -u campusshift "$target/.venv/bin/python" -m alembic upgrade head
sudo --preserve-env=APP_ENV,DATABASE_URL,JWT_SECRET,CORS_ORIGINS,PGPASSFILE -u campusshift "$target/.venv/bin/python" -m alembic check
install -m 0644 /etc/campusshift/nginx.conf /etc/nginx/conf.d/campusshift.conf
nginx -t
install -m 0644 "$target/infrastructure/runtime/campusshift.service" /etc/systemd/system/campusshift.service
ln -s "$target" /opt/campusshift/current.next
mv -Tf /opt/campusshift/current.next /opt/campusshift/current
systemctl daemon-reload
systemctl enable --now campusshift.service
systemctl restart campusshift.service
systemctl enable --now nginx
systemctl reload nginx
for attempt in {1..15}; do
    if curl --fail --silent http://127.0.0.1:8000/api/ready >/dev/null; then
        echo 'Backend ready locally. Verify origin TLS and public CloudFront workflows next.'
        exit 0
    fi
    sleep 2
done
echo 'Readiness failed; inspect journalctl and application.log. No automatic schema downgrade.' >&2
exit 1
