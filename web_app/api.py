"""REST API для інтеграції з іншими системами. Автентифікація: заголовок X-API-Key."""
import os
from functools import wraps
from flask import Blueprint, jsonify, request
from database import DBError, fetch, run
import charts

api = Blueprint("api", __name__, url_prefix="/api")
API_KEY = os.getenv("API_KEY", "technomart-demo-key")   # у продакшені задається змінною середовища


def require_api_key(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if request.headers.get("X-API-Key") != API_KEY:
            return jsonify(success=False, error="Невірний або відсутній X-API-Key"), 401
        return f(*a, **kw)
    return wrapper


@api.errorhandler(DBError)
def db_error(e):
    return jsonify(success=False, error=str(e)), 400


@api.get("/products")
@require_api_key
def products():
    q = request.args.get("q", "")
    page = max(request.args.get("page", 1, type=int), 1)
    size = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    rows = fetch("""SELECT p.product_id AS id, p.product_name AS name, c.category_name AS category,
                           p.unit_price AS price, p.units_in_stock AS stock, p.discontinued
                    FROM products p JOIN categories c ON c.category_id = p.category_id
                    WHERE p.product_name ILIKE %s ORDER BY p.product_id LIMIT %s OFFSET %s""",
                 (f"%{q}%", size, (page - 1) * size))
    return jsonify(success=True, page=page, count=len(rows), data=rows)


@api.get("/products/<int:pid>")
@require_api_key
def product(pid):
    row = fetch("SELECT * FROM products WHERE product_id=%s", (pid,), one=True)
    return (jsonify(success=True, data=row) if row else (jsonify(success=False, error="Товар не знайдено"), 404))


@api.post("/products")
@require_api_key
def create_product():
    d = request.get_json(silent=True) or {}
    missing = [k for k in ("product_name", "category_id", "unit_price") if k not in d]
    if missing:
        return jsonify(success=False, error=f"Відсутні поля: {', '.join(missing)}"), 400
    row = run("""INSERT INTO products (product_name, category_id, supplier_id, unit_price, units_in_stock)
                 VALUES (%s,%s,%s,%s,%s) RETURNING product_id""",
              (d["product_name"], d["category_id"], d.get("supplier_id"), d["unit_price"], d.get("units_in_stock", 0)))
    return jsonify(success=True, product_id=row["product_id"]), 201


@api.put("/products/<int:pid>")
@require_api_key
def update_product(pid):
    d = request.get_json(silent=True) or {}
    row = run("""UPDATE products SET unit_price = COALESCE(%s, unit_price), units_in_stock = COALESCE(%s, units_in_stock)
                 WHERE product_id=%s RETURNING product_id""", (d.get("unit_price"), d.get("units_in_stock"), pid))
    return (jsonify(success=True) if row else (jsonify(success=False, error="Товар не знайдено"), 404))


@api.delete("/products/<int:pid>")
@require_api_key
def delete_product(pid):
    row = run("DELETE FROM products WHERE product_id=%s RETURNING product_id", (pid,))
    return (jsonify(success=True) if row else (jsonify(success=False, error="Товар не знайдено"), 404))


@api.get("/orders")
@require_api_key
def orders():
    status = request.args.get("status")
    rows = fetch("""SELECT order_id AS id, order_date, order_status AS status, customer_name, grand_total
                    FROM order_details WHERE (%s IS NULL OR order_status=%s) ORDER BY order_id DESC LIMIT 100""",
                 (status, status))
    return jsonify(success=True, count=len(rows), data=rows)


@api.get("/orders/<int:oid>")
@require_api_key
def order(oid):
    head = fetch("SELECT * FROM order_details WHERE order_id=%s", (oid,), one=True)
    if not head:
        return jsonify(success=False, error="Замовлення не знайдено"), 404
    items = fetch("""SELECT p.product_name, oi.quantity, oi.unit_price, oi.discount FROM order_items oi
                     JOIN products p ON p.product_id=oi.product_id WHERE oi.order_id=%s""", (oid,))
    return jsonify(success=True, data={**head, "items": items})


@api.post("/orders")
@require_api_key
def create_order():
    import json
    d = request.get_json(silent=True) or {}
    if not d.get("customer_id") or not d.get("items"):
        return jsonify(success=False, error="Потрібні customer_id та items"), 400
    row = run("SELECT create_order(%s,%s,%s,%s,%s::jsonb) AS id",
              (d["customer_id"], d.get("employee_id"), d.get("ship_via", "Нова Пошта"), d.get("freight", 0),
               json.dumps(d["items"])))
    return jsonify(success=True, order_id=row["id"]), 201


@api.get("/stats")
@require_api_key
def stats():
    return jsonify(success=True, data=charts.dashboard_stats())
