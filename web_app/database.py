"""Робота з PostgreSQL у Flask: одне з'єднання на запит, параметризовані запити, дружні повідомлення про помилки."""
import os
import psycopg2
import psycopg2.extras
from flask import g

PARAMS = dict(
    dbname=os.getenv("DB_NAME", "technomart"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "password"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
)


class DBError(Exception):
    """Помилка БД з повідомленням, зрозумілим користувачу."""


def get_conn():
    if "db" not in g:
        g.db = psycopg2.connect(**PARAMS, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db


def close_conn(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _friendly(e: psycopg2.Error) -> str:
    code = e.pgcode or ""
    if code == "23505":
        return "Запис із такими унікальними даними (email, назва тощо) вже існує."
    if code == "23503":
        return "Операцію неможливо виконати: існують пов'язані записи (або вказано неіснуючий зв'язок)."
    if code == "23514":
        return "Введені значення порушують обмеження цілісності (діапазон, статус, дати)."
    if code == "23502":
        return "Не заповнено обов'язкове поле."
    if code in ("22P02", "22003", "22007"):
        return "Некоректний формат даних."
    return (e.diag.message_primary or "Помилка бази даних").strip()  # RAISE EXCEPTION з процедур/тригерів


def fetch(sql, params=None, one=False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            res = cur.fetchone() if one else cur.fetchall()
        conn.commit()
        return res
    except psycopg2.Error as e:
        conn.rollback()
        raise DBError(_friendly(e)) from e


def run(sql, params=None, user_id=None, returning=True):
    """Виконує зміну даних. user_id передається в тригери аудиту через app.user_id (в межах транзакції)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id or ""),))
            cur.execute(sql, params)
            row = cur.fetchone() if (returning and cur.description) else None
        conn.commit()
        return row
    except psycopg2.Error as e:
        conn.rollback()
        raise DBError(_friendly(e)) from e
