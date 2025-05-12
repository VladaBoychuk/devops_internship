FROM python:3.9-alpine AS builder

RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev cargo postgresql-dev

WORKDIR /app_build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target=/install_root

FROM python:3.9-alpine

# tzdata - for correct work with time zones
RUN apk add --no-cache tzdata libffi openssl postgresql-libs

WORKDIR /app

COPY --from=builder /install_root /usr/local/lib/python3.9/site-packages

COPY . .

EXPOSE 5001
CMD ["python", "app.py"]