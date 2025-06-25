#!/usr/bin/env bash
set -e
# Create the database if it does not exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
   DO \$\$
   BEGIN
      IF NOT EXISTS (
         SELECT FROM pg_database WHERE datname = '$POSTGRES_DB'
      ) THEN
         CREATE DATABASE "$POSTGRES_DB";
      END IF;
   END
   \$\$;
EOSQL

cd /app
# Run Alembic migrations
PYTHONPATH=/app python3 -m alembic upgrade head

# Load test data
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
   DO \$\$
   BEGIN
      UPDATE repository SET public_key = '-----BEGIN PUBLIC KEY-----
      MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA+oe91ueJ6cNJsEILa+4S
      KFtj5SMgJh9orJ0OxuewNfw59svhzvLCCK+buSgoO5gh+HS1bNRmob14lAiI/9z5
      oNFxwMHC76o6V2Rr4fXqh28Zl/SDF81uuvTcfSGUS/DLn9+83YMizIh6zPLxG/rr
      qFNQ1wYvJlHCMgZQ8NGheKsPwRGhjqynHr6YxlxO8RcfRQZLg8ScexVRQo5bAB0y
      jFSSBq7/uB7BD7Qt9+hr0YJeZNjVvvSTB97YQIDTIXhi0jfvyFcV4dZ3zkXyi7tw
      G47QP9YdiC7jJFtZZ2bpeYxhtYrl8dA7EXJvpGRU8+LEaqgwHK9hitFciDCMq7kf
      2QIDAQAB
      -----END PUBLIC KEY-----' WHERE id = 1;

      -- TOKEN is mhd_1781097016_1d81aa35-4896-44bc-8dee-a0198e88b2a8

      INSERT INTO api_token (id, repository_id, name, description, token_hash, expiration_datetime, created_at, status)
      VALUES (1, 1, 'test_token', 'test token description', '6707c01b35e754eb3e7a634e019df831b3e2a2ce0ab845ac6d46351c37d2b3dc', NOW() + INTERVAL '1 year', NOW(), 1);

   END
   \$\$;

EOSQL
