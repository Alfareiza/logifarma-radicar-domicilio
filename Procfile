release: python manage.py migrate --noinput && python manage.py migrate --database=server --noinput;
web: gunicorn core.wsgi --log-file -
