#!/bin/bash
# Runs once on first postgres init (docker-entrypoint-initdb.d). POSTGRES_DB
# creates the `careflow` app database; this creates the second `hapi` database
# for the FHIR JPA server, and enables pgvector in `careflow` for the RAG
# schema (SPEC section 3) used from Phase 3 onward.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE hapi;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"
