#!/bin/bash
# Creates the metabase metadata database if it doesn't already exist.
# Runs automatically on first docker compose up (empty volume).
# Safe to re-run manually on existing installs — idempotent.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
  SELECT 'CREATE DATABASE metabase'
  WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'metabase'
  )\gexec
EOSQL
