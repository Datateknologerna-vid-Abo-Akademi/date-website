#!/bin/sh
set -Eeuo pipefail

echo "WARNING! This will restore your project to an intial state"
read -p "Are you sure? y/n " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

source ../example.env
COMPOSE_PATH="../docker-compose.yml"
DB_NAME=date-website-db-1 # Name of your database container

# Shut down any currently running containers
docker-compose down

# Delete all existing migration files
find ../ -path "*/migrations/*.py" -not -name "__init__.py" -delete

# Start the database container
docker-compose -f $COMPOSE_PATH build
docker-compose -f $COMPOSE_PATH up -d db

sleep 2

# Connect to a temporary database to delete and recreate the postgres database
docker exec $DB_NAME psql -U postgres -c "CREATE DATABASE temp;"
docker exec $DB_NAME psql -U postgres -d temp -c "DROP DATABASE postgres;"
docker exec $DB_NAME psql -U postgres -d temp -c "CREATE DATABASE postgres;"
docker exec $DB_NAME psql -U postgres -c "DROP DATABASE temp;"

echo "Database cleared."
echo "Deleting migration files"

# Run migrations on fresh database and load fixture data
docker-compose -f $COMPOSE_PATH run web python /code/manage.py makemigrations
docker-compose -f $COMPOSE_PATH run web python /code/manage.py migrate
docker-compose -f $COMPOSE_PATH run web python /code/manage.py loaddata initialdata.json
docker-compose down

sleep 2

# (optional) start website
# docker-compose up -d

echo "All migrations and data cleared, initial website data loaded."
