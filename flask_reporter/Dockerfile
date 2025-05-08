FROM python:3.9-alpine
RUN apk add --no-cache tzdata build-base libffi-dev openssl-dev
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python", "app.py"]