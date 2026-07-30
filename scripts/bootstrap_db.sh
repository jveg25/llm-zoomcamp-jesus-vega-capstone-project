#!/usr/bin/env bash
# One-time (idempotent) database bootstrap. Run after `docker compose up -d`.
# Safe to re-run: each step checks whether it's already done.
set -euo pipefail
cd "$(dirname "$0")/.."
PW="${POSTGRES_PASSWORD:-postgres}"

echo "1/3 schema (papers, chunks, profiles, ...)"
if docker exec pi-db psql -U postgres -tAc "SELECT to_regclass('public.papers')" | grep -q papers; then
    echo "     already present, skipping"
else
    docker exec -i pi-db psql -U postgres < migrations/init.sql
    echo "     created"
fi

echo "2/3 auth admin password (supabase_auth_admin, so GoTrue can connect)"
docker exec pi-db psql -U supabase_admin -d postgres \
    -c "ALTER USER supabase_auth_admin WITH PASSWORD '${PW}';"

echo "3/3 auth FK + signup trigger (needs the auth service to have booted once)"
if docker exec pi-db psql -U postgres -tAc "SELECT to_regclass('auth.users')" | grep -q users; then
    if docker exec pi-db psql -U postgres -tAc \
        "SELECT tgname FROM pg_trigger WHERE tgname='on_auth_user_created'" | grep -q on_auth_user_created; then
        echo "     already present, skipping"
    else
        docker exec -i pi-db psql -U supabase_admin -d postgres < migrations/002_auth.sql
        echo "     created"
    fi
else
    echo "     auth.users missing — 'docker compose up -d auth', wait, then re-run this script"
fi

echo
echo "Done. Promote your first admin once you've signed up in the UI:"
echo "  docker exec pi-db psql -U postgres -c \"UPDATE profiles SET role='admin' WHERE email='you@example.com';\""
