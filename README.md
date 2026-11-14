# ЛР №4. Реляційна БД інтернет-магазину «ТехноМарт» (PostgreSQL + Python)

Рівні: **1** (БД + консольний CRUD) · **2** (процедури, тригери, представлення, Flask) · **3** (ролі, журнал, PDF/Excel, графіки, API, бекап, індекси).

## Швидкий старт
```bash
docker compose up -d                 # PostgreSQL 17 + pgAdmin; SQL з ./database виконується автоматично
docker compose logs -f postgres      # дочекайтесь "database system is ready to accept connections"
```
> Скрипти з `database/` виконуються **лише при першому створенні тому**. Щоб перестворити БД з нуля: `docker compose down -v && docker compose up -d`.

**Консольний застосунок**
```bash
cd console_app && pip install -r requirements.txt && python main.py
```
**Вебзастосунок** → http://127.0.0.1:5000
```bash
cd web_app && pip install -r requirements.txt && python app.py
```
Демо-акаунти: `admin/admin123` (усе) · `manager/manager123` (CRUD) · `viewer/viewer123` (перегляд). Нові користувачі реєструються з роллю `viewer`.

Параметри підключення (змінні середовища, за замовчуванням збігаються з `docker-compose.yml`):
`DB_HOST=localhost DB_PORT=5432 DB_NAME=technomart DB_USER=postgres DB_PASSWORD=password`, а також `SECRET_KEY`, `API_KEY`.

pgAdmin: http://localhost:5050 (admin@admin.com / admin), сервер `postgres`, порт 5432.

## Структура
```
database/   01_create_tables · 02_insert_data · 03_create_procedures · 04_create_triggers
            05_create_views · 06_create_users · 07_create_audit · 08_create_indexes · queries.sql
console_app/  main.py, database.py          web_app/  app.py, api.py, reports.py, charts.py, backup.py, templates/, static/
docs/       conceptual_model.png (+er.dot) · logical_schema.md · report.md
scripts/    backup.sh, restore.sh
```

## REST API (заголовок `X-API-Key: technomart-demo-key`)
| Метод | URL | Опис |
|---|---|---|
| GET | `/api/products?q=&page=&per_page=` | список товарів |
| GET/PUT/DELETE | `/api/products/<id>` | товар / зміна ціни й залишку / видалення |
| POST | `/api/products` | створення товару |
| GET | `/api/orders?status=` · `/api/orders/<id>` | замовлення |
| POST | `/api/orders` | `{"customer_id":1,"items":[{"product_id":21,"quantity":2,"discount":0.05}]}` |
| GET | `/api/stats` | дані для графіків |

```bash
curl -H "X-API-Key: technomart-demo-key" "http://127.0.0.1:5000/api/products?q=iphone"
```

## Резервне копіювання
Вебінтерфейс (admin → «Бекап») або `./scripts/backup.sh`. Відновлення: `./scripts/restore.sh backups/<файл>.sql`.

## Безпека
Параметризовані запити (захист від SQL-ін'єкцій), bcrypt-хеші паролів (`pgcrypto`), CSRF-токени у всіх POST-формах, перевірка ролей на сервері, whitelist для полів сортування, Jinja-автоекранування. **Перед реальним використанням змініть** демо-паролі, `SECRET_KEY`, `API_KEY` і пароль PostgreSQL.
