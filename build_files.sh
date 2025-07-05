#!/bin/bash

# build.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting Vercel Build Script ---"

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt using python3.12..."
# Explicitly use python3.12 to run pip to ensure the correct version is used.
python3.12 -m pip install --disable-pip-version-check --target . --upgrade setuptools
python3.12 -m pip install --disable-pip-version-check --target . --upgrade -r requirements.txt

# Run Django migrations
echo "Running Django migrations..."
python3.12 manage.py makemigrations
python3.12 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
# The --clear flag removes existing static files before collecting new ones.
python3.12 manage.py collectstatic --noinput --clear

echo "--- Vercel Build Script Finished Successfully ---"
