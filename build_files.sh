#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting Vercel Build Script ---"

# Run Django migrations
echo "Running Django migrations..."
python3.11 manage.py makemigrations
python3.11 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
# The --clear flag removes existing static files before collecting new ones.
python3.11 manage.py collectstatic --noinput --clear

echo "--- Vercel Build Script Finished Successfully ---"