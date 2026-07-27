#!/usr/bin/env bash
# Roll back Domicilios on the VPS to the SHA recorded by deploy.sh.
# Piped to the server via: ssh ... 'bash -s' < rollback.sh
# Expected env: APP_DIR, SERVICE (optional; defaults below).

set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/Projects/domicilios}"
SERVICE="${SERVICE:-gunicorn-domicilios}"

cd "$APP_DIR"

if [[ ! -f .deploy_prev_sha ]]; then
  echo "ERROR: .deploy_prev_sha not found; cannot roll back" >&2
  exit 1
fi

PREV_SHA="$(cat .deploy_prev_sha)"
FAILED_SHA="$(git rev-parse HEAD)"

echo "==> Rolling back from $FAILED_SHA to $PREV_SHA"

git reset --hard "$PREV_SHA"

if ! git diff --quiet "$FAILED_SHA" "$PREV_SHA" -- requirements.txt; then
  echo "==> requirements.txt differs from failed revision; reinstalling..."
  .venv/bin/pip install -r requirements.txt
else
  echo "==> requirements.txt unchanged vs failed revision; skipping pip install"
fi

echo "==> Running collectstatic..."
.venv/bin/python manage.py collectstatic --noinput

echo "==> Reloading $SERVICE..."
sudo systemctl daemon-reload
sudo systemctl reload "$SERVICE"

if ! systemctl is-active --quiet "$SERVICE"; then
  echo "ERROR: $SERVICE is not active after rollback reload" >&2
  systemctl status "$SERVICE" --no-pager || true
  exit 1
fi

echo "==> Rollback complete: now at $(git rev-parse HEAD)"
