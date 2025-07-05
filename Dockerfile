FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/src/app


RUN apt update \
 && apt install -y libpq-dev gcc curl python3-dev build-essential g++ git\
 && pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install -r requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        unixodbc-dev \
        freetds-dev \
        libodbc1 \
        odbcinst \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

EXPOSE 8000

RUN mkdir -p -v /usr/src/core/static \
 && mkdir -p -v /usr/src/core/media


ENV PYTHONPATH "/usr/src/core"

CMD ["gunicorn", "--bind", ":8000", "--workers", "4", "core.wsgi:application"]