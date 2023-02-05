#!/bin/bash

# Script to update the database
# The script creates a file db_backup.bck that stores the generated dump
# The script is designed to have generous sleep times to not break on slower servers

# NB: IF YOU TRY STARTING THE WRONG MAJOR VERSION CONTAINER AT FIRST THE SCRIPT WILL CURRENTLY FAIL LEADING TO DATA LOSS

if [ -f /.dockerenv ]; then
  echo "This script cannot be run inside a docker container.";
  exit 1;
fi

version=$1
config_file=${2:-$USER.env}

if [ -z "$version" ]; then
  echo "Please provide the desired PostgreSQL version as the first argument"
  exit 1
fi

# Set config file
if [ ! -f "$config_file" ]; then
  echo "Config file $config_file not found"
  exit 1
fi

# Check if the required environment variables are set
if [ -z "$DATE_POSTGRESQL_VERSION" ] || [ -z "$DATE_DB_PORT" ] || [ -z "$DATE_DB_PASSWORD" ]; then
  echo "Error: Required environment variables are not set"
  exit 1
fi

# Make sure website is stopped
docker compose down && sleep 15 && docker-compose up db -d

# Wait for db to start
sleep 15

# Dump database to host file system
# TODO Imlement a check that the container is actually running
docker-compose exec -T db pg_dump -U postgres postgres > ./db_backup.bck

# TODO Check for errors from the previous command
# Stop container and remove volumes
docker-compose down --volumes && sleep 15

# Update the PostgreSQL image version in the env file
DATE_POSTGRESQL_VERSION=$version
sed -i "s/DATE_POSTGRESQL_VERSION=.*/DATE_POSTGRESQL_VERSION=${DATE_POSTGRESQL_VERSION}/" "$config_file"

# Stat the container with the new version
docker-compose up db -d && sleep 15

# Restore the database dump to new container
docker-compose exec -T db psql -U postgres -d postgres < ./db_backup.bck

# Stop container
docker-compose down
