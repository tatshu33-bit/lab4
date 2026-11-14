#!/usr/bin/env bash
# Резервна копія БД з Docker-контейнера: ./scripts/backup.sh
set -euo pipefail
mkdir -p backups
FILE="backups/technomart_$(date +%Y%m%d_%H%M%S).sql"
docker exec technomart_db pg_dump -U postgres --no-owner --clean --if-exists technomart > "$FILE"
echo "Створено: $FILE ($(du -h "$FILE" | cut -f1))"
