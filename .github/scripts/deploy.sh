#!/usr/bin/env bash
# Deploy Domicilios on the VPS. Piped to the server via: ssh ... 'bash -s' < deploy.sh
# Expected env: APP_DIR, SERVICE (optional; defaults below).

set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/Projects/domicilios}"
SERVICE="${SERVICE:-gunicorn-domicilios}"

cd "$APP_DIR"

PREV_SHA="$(git rev-parse HEAD)"
echo "$PREV_SHA" > .deploy_prev_sha

echo "==> Previous SHA: $PREV_SHA"
echo "==> Fetching origin/main..."
git fetch --prune origin main
git reset --hard origin/main
# Do NOT run git clean: .env, credential JSON, pickles, and staticfiles/ are untracked and must survive.

NEW_SHA="$(git rev-parse HEAD)"
echo "==> Deployed SHA: $NEW_SHA"

if ! git diff --quiet "$PREV_SHA" "$NEW_SHA" -- requirements.txt; then
  echo "==> requirements.txt changed; installing dependencies..."
  .venv/bin/pip install -r requirements.txt
else
  echo "==> requirements.txt unchanged; skipping pip install"
fi

if git diff --name-only "$PREV_SHA" "$NEW_SHA" | grep -qE '(^|/)migrations/.*\.py$'; then
  echo 1 > .deploy_migrations_changed
  echo "==> Migration files changed in this deploy"
else
  echo 0 > .deploy_migrations_changed
  echo "==> No migration files changed"
fi

echo "==> Running migrate..."
.venv/bin/python manage.py migrate --noinput

echo "==> Running collectstatic..."
.venv/bin/python manage.py collectstatic --noinput

echo "==> Reloading $SERVICE..."
sudo systemctl daemon-reload
sudo systemctl reload "$SERVICE"

if ! systemctl is-active --quiet "$SERVICE"; then
  echo "ERROR: $SERVICE is not active after reload" >&2
  systemctl status "$SERVICE" --no-pager || true
  exit 1
fi

echo "==> Deploy complete: $NEW_SHA"
echo "DEPLOY_PREV_SHA=$PREV_SHA"
echo "DEPLOY_NEW_SHA=$NEW_SHA"
echo "DEPLOY_MIGRATIONS_CHANGED=$(cat .deploy_migrations_changed)"
