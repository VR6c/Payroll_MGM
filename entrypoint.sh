#!/bin/sh

# Wait for MySQL to be ready if USE_MYSQL is enabled
if [ "$USE_MYSQL" = "true" ] || [ "$USE_MYSQL" = "True" ]; then
    echo "Waiting for MySQL database at $DB_HOST:$DB_PORT..."
    while ! nc -z "$DB_HOST" "$DB_PORT"; do
      sleep 0.5
    done
    echo "MySQL database connected successfully."
fi

# Apply database migrations
echo "Running Django migrations..."
python manage.py migrate --noinput

exec "$@"
