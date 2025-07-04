#!/bin/bash

# build.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting Vercel Build Script ---"

# Navigate to the project root (assuming build.sh is in the same directory as manage.py)
# If your manage.py is in a subdirectory, adjust this.
# For example, if manage.py is in 'myproject/core', you might need 'cd myproject'
# For this setup, we assume manage.py is in the root where vercel.json is.

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt using python3.11..."
# Explicitly use python3.11 to run pip to ensure the correct version is used.
python3.11 -m pip install --disable-pip-version-check --target . --upgrade -r /vercel/path0/requirements.txt

# Run Django migrations
echo "Running Django migrations..."
python3.11 manage.py makemigrations
python3.11 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
# The --clear flag removes existing static files before collecting new ones.
python3.11 manage.py collectstatic --noinput --clear

echo "--- Vercel Build Script Finished Successfully ---"

