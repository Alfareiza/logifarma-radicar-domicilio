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
echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

# Run Django migrations
echo "Running Django migrations..."
python manage.py makemigrations
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
# The --clear flag removes existing static files before collecting new ones.
python manage.py collectstatic --noinput --clear

echo "--- Vercel Build Script Finished Successfully ---"

