"""
Django settings for core project.

Generated by 'django-admin startproject' using Django 4.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""
import logging
from functools import partial
from os.path import join
from pathlib import Path

import pyrebase
from decouple import config
from dj_database_url import parse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

CSRF_TRUSTED_ORIGINS = ["https://*.sa.ngrok.io", "https://*.ngrok.io"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", cast=bool)

ALLOWED_HOSTS = ['domicilios.logifarma.com.co',
                 'radicatudomicilio.herokuapp.com',
                 '*']

LOGIN_URL = '/login/'

LOGIN_REDIRECT_URL = '/inicio/'

LOGOUT_REDIRECT_URL = '/login/'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'core.apps.home.backends.FireBase'
]

# Application definition
INSTALLED_APPS = [
    'core.apps.base',
    'core.apps.home',
    'core.apps.api',
    'core.apps.tasks',
    'formtools',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'drf_spectacular',
]

MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'staticfiles'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.csrf',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'TIMEOUT': 60
    }
}

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

default_db_url = 'sqlite:///' + join(BASE_DIR, 'db.sqlite3')
parse_database = partial(parse, conn_max_age=600)
DATABASES = {
    'default': config('DATABASE_URL', default=default_db_url,
                      cast=parse_database),
    'server': {
        'ENGINE': 'mssql',
        'NAME': config('MSSQL_NAME'),
        'HOST': config('MSSQL_HOST'),
        'USER': config('MSSQL_USER'),
        'PASSWORD': config('MSSQL_PASSWORD'),
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'es-co'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Admins | Error Reporting https://docs.djangoproject.com/en/4.1/howto/error-reporting/
ADMINS = [('Alfonso AG', 'alfareiza@gmail.com')]

# Email Configuration

EMAIL_BACKEND = config('EMAIL_BACKEND')
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT')
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_USE_SSL = config('EMAIL_USE_SSL')

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'tmp'

# STATICFILES_DIRS = [BASE_DIR / "build/static", BASE_DIR / "build"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# logger = logging.getLogger('django')
# logging.basicConfig(format='%(asctime)s - %(message)s')

# create logger
logger = logging.getLogger("logging_tryout2")
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                              "[%d/%b/%Y %H:%M:%S]")

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

# Firebase configuration
# https://github.com/nhorvath/Pyrebase4

FIREBASE_CONFIG = {
    'apiKey': config('FBASE_APIKEY'),
    'authDomain': config('FBASE_AUTHDOMAIN'),
    'databaseURL': config('FBASE_DATABASEURL'),
    'projectId': config('FBASE_PROJECTID'),
    'storageBucket': config('FBASE_STORAGEBUCKET'),
    'messagingSenderId': config('FBASE_MESSAGINGSENDERID')
}
FIREBASE = pyrebase.initialize_app(FIREBASE_CONFIG)
FIREBASE_DB = FIREBASE.database()

REST_FRAMEWORK = {
    # YOUR SETTINGS
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'API Domicilios Logifarma',
    'SWAGGER_UI_FAVICON_HREF': 'http://domicilios.logifarma.com.co/static/img/ICONO-AZUL.png',
    'VERSION': '1.0.0',
    "SWAGGER_UI_SETTINGS": {
        'supportedSubmitMethods': ['']
    },
}

# settings.py

# Use the default database-backed session engine
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Set SESSION_COOKIE_SECURE to True if using HTTPS
SESSION_COOKIE_SECURE = True
