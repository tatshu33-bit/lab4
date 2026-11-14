"""Підключення до PostgreSQL. Параметри беруться зі змінних середовища (є значення за замовчуванням)."""
import os
import psycopg2


class Database:
    def __init__(self):
        self.params = dict(
            dbname=os.getenv("DB_NAME", "technomart"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "password"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
        )
        self.conn = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(**self.params)
            print("✅ Успішне підключення до бази даних")
            return True
        except psycopg2.Error as e:
            print(f"❌ Помилка підключення: {e}")
            return False

    def close(self):
        if self.conn:
            self.conn.close()
            print("З'єднання закрито")

    def query(self, sql, params=None):
        """SELECT -> список кортежів та назви стовпців. Завжди параметризований запит (захист від SQL-ін'єкцій)."""
        with self.conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                self.conn.commit()
                return rows, cols
            except psycopg2.Error as e:
                self.conn.rollback()
                print(f"❌ Помилка БД: {(e.diag.message_primary or str(e)).strip()}")
                return [], []

    def execute(self, sql, params=None):
        """INSERT/UPDATE/DELETE/CALL. Повертає (True, перший_рядок|None) або (False, None)."""
        with self.conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                row = cur.fetchone() if cur.description else None
                self.conn.commit()
                return True, row
            except psycopg2.Error as e:
                self.conn.rollback()
                print(f"❌ Помилка БД: {(e.diag.message_primary or str(e)).strip()}")
                return False, None
