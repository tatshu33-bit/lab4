#!/usr/bin/env bash
# Відновлення: ./scripts/restore.sh backups/technomart_YYYYMMDD_HHMMSS.sql
set -euo pipefail
[ $# -eq 1 ] || { echo "Використання: $0 <файл.sql>"; exit 1; }
docker exec -i technomart_db psql -U postgres -d technomart < "$1"
echo "Відновлено з $1"
