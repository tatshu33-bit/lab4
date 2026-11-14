"""Резервне копіювання: pg_dump локально або всередині Docker-контейнера."""
import os
import shutil
import subprocess
from datetime import datetime
from database import PARAMS

BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(__file__), "..", "backups"))
CONTAINER = os.getenv("DB_CONTAINER", "technomart_db")


def make_backup() -> str:
    """Створює SQL-дамп і повертає шлях до файлу."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.abspath(os.path.join(BACKUP_DIR, f"technomart_{datetime.now():%Y%m%d_%H%M%S}.sql"))
    env = dict(os.environ, PGPASSWORD=PARAMS["password"])
    if shutil.which("pg_dump"):
        cmd = ["pg_dump", "-h", PARAMS["host"], "-p", str(PARAMS["port"]), "-U", PARAMS["user"],
               "--no-owner", "--clean", "--if-exists", PARAMS["dbname"]]
    elif shutil.which("docker"):
        cmd = ["docker", "exec", CONTAINER, "pg_dump", "-U", PARAMS["user"], "--no-owner", "--clean",
               "--if-exists", PARAMS["dbname"]]
    else:
        raise RuntimeError("Не знайдено ні pg_dump, ні docker. Встановіть клієнт PostgreSQL або Docker.")
    with open(path, "wb") as f:
        res = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, timeout=120)
    if res.returncode != 0:
        os.remove(path)
        raise RuntimeError(res.stderr.decode("utf-8", "ignore")[:300])
    return path


def list_backups():
    if not os.path.isdir(BACKUP_DIR):
        return []
    files = sorted((f for f in os.listdir(BACKUP_DIR) if f.endswith(".sql")), reverse=True)
    return [(f, round(os.path.getsize(os.path.join(BACKUP_DIR, f)) / 1024, 1)) for f in files]
