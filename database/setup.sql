-- Hardcore Fashion Store — PostgreSQL Setup
-- Run this script in pgAdmin or psql before running Django migrations

CREATE DATABASE hardcore_fashion;

\c hardcore_fashion;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgAdmin connection settings:
-- Host: localhost
-- Port: 5432
-- Database: hardcore_fashion
-- Username: postgres

-- ── Least-privilege application user ─────────────────────────────────────────
-- Run as the postgres superuser AFTER the database is created.
-- Replace <strong_password> with a real secret (store it in .env as DB_PASSWORD).

CREATE USER hardcore_app WITH PASSWORD '<strong_password>';

-- Grant connect + schema usage
GRANT CONNECT ON DATABASE hardcore_fashion TO hardcore_app;
GRANT USAGE ON SCHEMA public TO hardcore_app;

-- DML only — no DDL (no CREATE/DROP/ALTER)
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO hardcore_app;

-- Allow sequences (needed for auto-increment PKs)
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO hardcore_app;

-- Apply the same grants to any future tables created by migrations
-- (run migrations as the superuser, not as hardcore_app)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hardcore_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO hardcore_app;

-- Explicitly deny DDL by ensuring hardcore_app is NOT a superuser
-- and does NOT own the schema (already the case with the commands above).
-- Verify with:
--   SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = 'hardcore_app';
-- All three should be 'f' (false).
