release: python manage.py migrate --noinput
release: python manage.py collectstatic --noinput;
web: gunicorn core.wsgi --log-file -
