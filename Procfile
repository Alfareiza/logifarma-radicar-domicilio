release: python manage.py migrate --noinput;
release: python manage.py migrate --database=server --noinput;
web: gunicorn core.wsgi --log-file -
