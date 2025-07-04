#!/bin/bash

echo "Building project packages..."

# Install Python dependencies (redundant if Vercel auto-installs, but safe to include)
# pip install -r requirements.txt

# Run database migrations
# Use --noinput to prevent prompts during automated deployment
# You might need to specify the python version explicitly, e.g., python3.11
python manage.py migrate --noinput

# Collect static files
# Use --noinput to prevent prompts
# Use --clear to remove existing static files before collecting new ones (good for fresh deployments)
python manage.py collectstatic --noinput --clear

echo "Build process complete."