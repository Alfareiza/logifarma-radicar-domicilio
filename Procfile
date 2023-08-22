release: python manage.py migrate --noinput;
release: python manage.py migrate --database=users --noinput;
web: gunicorn core.wsgi --log-file -
