#!/bin/sh

set -e

echo "Running database migration"
alembic upgrade head

echo "Starting server............"

exec "$@"