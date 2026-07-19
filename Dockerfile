FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/backend

# Collect static files at build time
RUN SECRET_KEY=build-time-placeholder DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --no-input && daphne -b 0.0.0.0 -p ${PORT:-8000} ecommerce.asgi:application"]
