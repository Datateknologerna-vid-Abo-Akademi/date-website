#!/bin/sh
set -Eeuo pipefail

echo "WARNING! This will restore your project to an intial state"
read -p "Are you sure? " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

COMPOSE_PATH="../docker-compose.yml"
DB_NAME=tempDB

source ../example.env
find . -path "../*/migrations/*.py" -not -name "__init__.py" -delete
docker-compose -f $COMPOSE_PATH build
docker-compose -f $COMPOSE_PATH run -d --name $DB_NAME db 
docker exec $DB_NAME psql -U postgres << EOF
CREATE DATABASE temp;
CONNECT DATABASE temp;
DROP DATABASE postgres;
CREATE DATABASE postgres;
CONNECT DATABASE postgres;
DROP DATABASE temp;
EOF

echo "Database cleared."
echo "Deleting migration files"

docker-compose -f $COMPOSE_PATH run web python /code/manage.py makemigrations
docker-compose -f $COMPOSE_PATH run web python /code/manage.py migrate
docker-compose -f $COMPOSE_PATH run web python /code/manage.py loaddata initialdata.json
docker-compose down

sleep 2

docker-compose up -d

echo "All migrations and data cleared, initial website data loaded."
