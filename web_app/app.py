"""ТехноМарт: вебзастосунок (Flask). Ролі: viewer < manager < admin."""
import json
import os
import re
import secrets
from decimal import Decimal
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session,
                   url_for, Response)
from flask.json.provider import DefaultJSONProvider

import backup
import charts
import reports
from api import api
from database import DBError, close_conn, fetch, run

ROLE_RANK = {"viewer": 1, "manager": 2, "admin": 3}
PER_PAGE = 12
ORDER_FLOW = {"pending": ["processing"], "processing": ["shipped"], "shipped": ["delivered"]}


class Provider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        return float(o) if isinstance(o, Decimal) else DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = Provider(app)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
app.teardown_appcontext(close_conn)
app.register_blueprint(api)


# ---------------- безпека: CSRF, ролі ----------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method == "POST" and not request.path.startswith("/api/"):
        if not secrets.compare_digest(request.form.get("_csrf", ""), session.get("_csrf", "x")):
            abort(400, "Недійсний CSRF-токен")


@app.before_request
def load_user():
    g.user = session.get("user")


def login_required(role="viewer"):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if ROLE_RANK[g.user["role"]] < ROLE_RANK[role]:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, msg="Недостатньо прав для цієї дії"), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, msg="Сторінку не знайдено"), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, msg=getattr(e, "description", "Некоректний запит")), 400


def uid():
    return g.user["user_id"] if g.user else None


# ---------------- валідація ----------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


def clean(form, key):
    v = (form.get(key) or "").strip()
    return v or None


def to_num(v, cast, name, errors, minimum=None, maximum=None, required=True):
    if v in (None, ""):
        if required:
            errors.append(f"Поле «{name}» обов'язкове")
        return None
    try:
        n = cast(v)
    except (ValueError, ArithmeticError):
        errors.append(f"Поле «{name}» має бути числом")
        return None
    if (minimum is not None and n < minimum) or (maximum is not None and n > maximum):
        errors.append(f"«{name}»: допустимий діапазон {minimum}…{maximum}")
        return None
    return n


def validate_product(f):
    e = []
    name = clean(f, "product_name")
    if not name or len(name) < 2 or len(name) > 100:
        e.append("Назва товару: від 2 до 100 символів")
    d = dict(
        product_name=name,
        category_id=to_num(f.get("category_id"), int, "Категорія", e, 1),
        supplier_id=to_num(f.get("supplier_id"), int, "Постачальник", e, 1, required=False),
        unit_price=to_num(f.get("unit_price"), Decimal, "Ціна", e, 0, 10_000_000),
        units_in_stock=to_num(f.get("units_in_stock", "0"), int, "Залишок", e, 0, 1_000_000),
        units_on_order=to_num(f.get("units_on_order", "0") or "0", int, "Замовлено", e, 0, 1_000_000),
        reorder_level=to_num(f.get("reorder_level", "0") or "0", int, "Мін. залишок", e, 0, 1_000_000),
        discontinued=f.get("discontinued") == "on",
        description=clean(f, "description"),
    )
    return d, e


def validate_customer(f):
    e = []
    d = {k: clean(f, k) for k in ("company_name", "contact_name", "contact_title", "address", "city",
                                   "postal_code", "phone", "email")}
    d["customer_type"] = f.get("customer_type", "individual")
    d["region_id"] = to_num(f.get("region_id"), int, "Регіон", e, 1, required=False)
    if d["customer_type"] not in ("individual", "company"):
        e.append("Некоректний тип клієнта")
    if not d["contact_name"] or len(d["contact_name"]) < 3:
        e.append("ПІБ контактної особи: мінімум 3 символи")
    if d["customer_type"] == "company" and not d["company_name"]:
        e.append("Для юридичної особи потрібна назва компанії")
    if d["email"] and not EMAIL_RE.match(d["email"]):
        e.append("Некоректний email")
    if d["phone"] and not PHONE_RE.match(d["phone"]):
        e.append("Некоректний телефон (7-20 цифр, можна +, пробіли, дужки)")
    if d["postal_code"] and not re.fullmatch(r"\d{5}", d["postal_code"]):
        e.append("Поштовий індекс — 5 цифр")
    if d["customer_type"] == "individual":
        d["company_name"] = None
    return d, e


def show_errors(errors):
    for m in errors:
        flash(m, "error")


# ---------------- допоміжне: сортування, пагінація ----------------
def paginate(total):
    page = max(request.args.get("page", 1, type=int), 1)
    pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return min(page, pages), pages


def sort_args(allowed, default):
    col = request.args.get("sort", default)
    col = col if col in allowed else default
    direction = "DESC" if request.args.get("dir") == "desc" else "ASC"
    return col, direction


@app.template_global()
def qs(**over):
    """Поточні GET-параметри з підміною (для посилань сортування/пагінації)."""
    args = {k: v for k, v in request.args.items() if k != "page"}
    args.update({k: v for k, v in over.items() if v is not None})
    return url_for(request.endpoint, **(request.view_args or {}), **args)


# ---------------- автентифікація ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = fetch("SELECT * FROM authenticate_user(%s,%s)",
                  (request.form.get("username", "").strip(), request.form.get("password", "")), one=True)
        if u:
            session.clear()
            session["user"] = dict(u)
            run("SELECT log_activity(%s,'LOGIN','users',%s,NULL)", (u["user_id"], u["user_id"]), user_id=u["user_id"])
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Невірне ім'я користувача або пароль", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f, errors = request.form, []
        username, email, pw = f.get("username", "").strip(), f.get("email", "").strip(), f.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
            errors.append("Ім'я користувача: 3-30 символів (латиниця, цифри, _)")
        if not EMAIL_RE.match(email):
            errors.append("Некоректний email")
        if len(pw) < 6:
            errors.append("Пароль: мінімум 6 символів")
        if pw != f.get("password2"):
            errors.append("Паролі не співпадають")
        if not errors:
            try:
                run("SELECT register_user(%s,%s,%s,'viewer')", (username, pw, email))
                flash("Реєстрація успішна. Увійдіть у систему (роль: viewer).", "success")
                return redirect(url_for("login"))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
    return render_template("register.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- дашборд ----------------
@app.route("/")
@login_required()
def dashboard():
    return render_template("dashboard.html", k=charts.kpis(),
                           low=fetch("SELECT * FROM low_stock_products ORDER BY units_in_stock LIMIT 5"))


@app.route("/stats")
@login_required()
def stats():
    return jsonify(charts.dashboard_stats())


# ---------------- товари ----------------
PRODUCT_SORT = {"id": "p.product_id", "name": "p.product_name", "price": "p.unit_price",
                "stock": "p.units_in_stock", "category": "c.category_name"}


def product_filters():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", type=int)
    pmin = request.args.get("pmin", type=float)
    pmax = request.args.get("pmax", type=float)
    only_low = request.args.get("low") == "1"
    where = """(%(q)s = '' OR p.product_name ILIKE %(like)s) AND (%(cat)s IS NULL OR p.category_id = %(cat)s)
               AND (%(pmin)s IS NULL OR p.unit_price >= %(pmin)s) AND (%(pmax)s IS NULL OR p.unit_price <= %(pmax)s)
               AND (NOT %(low)s OR p.units_in_stock <= p.reorder_level)"""
    params = dict(q=q, like=f"%{q}%", cat=cat, pmin=pmin, pmax=pmax, low=only_low)
    return where, params


@app.route("/products")
@login_required()
def products():
    where, params = product_filters()
    total = fetch(f"SELECT COUNT(*) AS n FROM products p WHERE {where}", params, one=True)["n"]
    page, pages = paginate(total)
    col, direction = sort_args(PRODUCT_SORT, "id")
    rows = fetch(f"""SELECT p.product_id, p.product_name, c.category_name, s.company_name AS supplier, p.unit_price,
                            p.units_in_stock, p.reorder_level, p.discontinued
                     FROM products p JOIN categories c ON c.category_id = p.category_id
                     LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
                     WHERE {where} ORDER BY {PRODUCT_SORT[col]} {direction}, p.product_id
                     LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}""", params)
    cats = fetch("SELECT category_id, category_name FROM categories ORDER BY 2")
    return render_template("products.html", rows=rows, cats=cats, page=page, pages=pages, total=total,
                           sort=col, dir=direction.lower())


def product_form_data():
    return dict(cats=fetch("SELECT category_id, category_name FROM categories ORDER BY 2"),
                sups=fetch("SELECT supplier_id, company_name FROM suppliers ORDER BY 2"))


@app.route("/products/new", methods=["GET", "POST"])
@login_required("manager")
def product_new():
    if request.method == "POST":
        d, errors = validate_product(request.form)
        if not errors:
            try:
                row = run("""INSERT INTO products (product_name, category_id, supplier_id, unit_price, units_in_stock,
                             units_on_order, reorder_level, discontinued, description)
                             VALUES (%(product_name)s,%(category_id)s,%(supplier_id)s,%(unit_price)s,%(units_in_stock)s,
                             %(units_on_order)s,%(reorder_level)s,%(discontinued)s,%(description)s) RETURNING product_id""",
                          d, uid())
                flash(f"Товар додано (ID {row['product_id']})", "success")
                return redirect(url_for("products"))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
        return render_template("product_form.html", p=request.form, mode="new", **product_form_data())
    return render_template("product_form.html", p={}, mode="new", **product_form_data())


@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required("manager")
def product_edit(pid):
    if request.method == "POST":
        d, errors = validate_product(request.form)
        if not errors:
            try:
                run("""UPDATE products SET product_name=%(product_name)s, category_id=%(category_id)s,
                       supplier_id=%(supplier_id)s, unit_price=%(unit_price)s, units_in_stock=%(units_in_stock)s,
                       units_on_order=%(units_on_order)s, reorder_level=%(reorder_level)s,
                       discontinued=%(discontinued)s, description=%(description)s
                       WHERE product_id=%(id)s""", {**d, "id": pid}, uid(), returning=False)
                flash("Товар оновлено", "success")
                return redirect(url_for("products"))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
        return render_template("product_form.html", p=request.form, mode="edit", pid=pid, **product_form_data())
    p = fetch("SELECT * FROM products WHERE product_id=%s", (pid,), one=True) or abort(404)
    hist = fetch("SELECT * FROM product_price_history WHERE product_id=%s ORDER BY changed_at DESC LIMIT 5", (pid,))
    return render_template("product_form.html", p=p, mode="edit", pid=pid, hist=hist, **product_form_data())


@app.post("/products/<int:pid>/delete")
@login_required("manager")
def product_delete(pid):
    try:
        run("DELETE FROM products WHERE product_id=%s", (pid,), uid(), returning=False)
        flash("Товар видалено", "success")
    except DBError as e:
        flash(f"Не вдалося видалити: {e} Позначте товар як знятий з продажу.", "error")
    return redirect(url_for("products"))


# ---------------- клієнти ----------------
CUSTOMER_SORT = {"id": "customer_id", "name": "contact_name", "city": "city", "orders": "total_orders",
                 "amount": "total_amount"}


@app.route("/customers")
@login_required()
def customers():
    q, ctype, city = request.args.get("q", "").strip(), request.args.get("type", ""), request.args.get("city", "")
    where = """(%(q)s = '' OR contact_name ILIKE %(like)s OR COALESCE(company_name,'') ILIKE %(like)s)
               AND (%(t)s = '' OR customer_type = %(t)s) AND (%(city)s = '' OR city = %(city)s)"""
    params = dict(q=q, like=f"%{q}%", t=ctype, city=city)
    total = fetch(f"SELECT COUNT(*) AS n FROM customer_orders_summary WHERE {where}", params, one=True)["n"]
    page, pages = paginate(total)
    col, direction = sort_args(CUSTOMER_SORT, "id")
    rows = fetch(f"""SELECT * FROM customer_orders_summary WHERE {where}
                     ORDER BY {CUSTOMER_SORT[col]} {direction}, customer_id
                     LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}""", params)
    cities = [r["city"] for r in fetch("SELECT DISTINCT city FROM customers WHERE city IS NOT NULL ORDER BY 1")]
    return render_template("customers.html", rows=rows, cities=cities, page=page, pages=pages, total=total,
                           sort=col, dir=direction.lower())


def regions():
    return fetch("SELECT region_id, region_name FROM regions ORDER BY 2")


@app.route("/customers/new", methods=["GET", "POST"])
@login_required("manager")
def customer_new():
    if request.method == "POST":
        d, errors = validate_customer(request.form)
        if not errors:
            try:
                run("""INSERT INTO customers (customer_type, company_name, contact_name, contact_title, address, city,
                       region_id, postal_code, phone, email)
                       VALUES (%(customer_type)s,%(company_name)s,%(contact_name)s,%(contact_title)s,%(address)s,%(city)s,
                       %(region_id)s,%(postal_code)s,%(phone)s,%(email)s)""", d, uid(), returning=False)
                flash("Клієнта додано", "success")
                return redirect(url_for("customers"))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
        return render_template("customer_form.html", c=request.form, mode="new", regions=regions())
    return render_template("customer_form.html", c={}, mode="new", regions=regions())


@app.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
@login_required("manager")
def customer_edit(cid):
    if request.method == "POST":
        d, errors = validate_customer(request.form)
        if not errors:
            try:
                run("""UPDATE customers SET customer_type=%(customer_type)s, company_name=%(company_name)s,
                       contact_name=%(contact_name)s, contact_title=%(contact_title)s, address=%(address)s, city=%(city)s,
                       region_id=%(region_id)s, postal_code=%(postal_code)s, phone=%(phone)s, email=%(email)s
                       WHERE customer_id=%(id)s""", {**d, "id": cid}, uid(), returning=False)
                flash("Клієнта оновлено", "success")
                return redirect(url_for("customers"))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
        return render_template("customer_form.html", c=request.form, mode="edit", cid=cid, regions=regions())
    c = fetch("SELECT * FROM customers WHERE customer_id=%s", (cid,), one=True) or abort(404)
    rep = fetch("SELECT * FROM customer_report(%s)", (cid,), one=True)
    return render_template("customer_form.html", c=c, mode="edit", cid=cid, regions=regions(), rep=rep)


@app.post("/customers/<int:cid>/delete")
@login_required("manager")
def customer_delete(cid):
    try:
        run("DELETE FROM customers WHERE customer_id=%s", (cid,), uid(), returning=False)
        flash("Клієнта видалено", "success")
    except DBError as e:
        flash(f"Не вдалося видалити: {e}", "error")
    return redirect(url_for("customers"))


# ---------------- замовлення ----------------
ORDER_SORT = {"id": "order_id", "date": "order_date", "total": "grand_total", "customer": "customer_name"}


@app.route("/orders")
@login_required()
def orders():
    q, st = request.args.get("q", "").strip(), request.args.get("status", "")
    dfrom, dto = request.args.get("from") or None, request.args.get("to") or None
    where = """(%(q)s = '' OR customer_name ILIKE %(like)s) AND (%(st)s = '' OR order_status = %(st)s)
               AND (%(df)s::date IS NULL OR order_date >= %(df)s::date) AND (%(dt)s::date IS NULL OR order_date <= %(dt)s::date)"""
    params = dict(q=q, like=f"%{q}%", st=st, df=dfrom, dt=dto)
    try:
        total = fetch(f"SELECT COUNT(*) AS n FROM order_details WHERE {where}", params, one=True)["n"]
        page, pages = paginate(total)
        col, direction = sort_args(ORDER_SORT, "id")
        rows = fetch(f"""SELECT * FROM order_details WHERE {where} ORDER BY {ORDER_SORT[col]} {direction}, order_id DESC
                         LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}""", params)
    except DBError:
        flash("Некоректний фільтр дат", "error")
        rows, total, page, pages, col, direction = [], 0, 1, 1, "id", "DESC"
    return render_template("orders.html", rows=rows, page=page, pages=pages, total=total, sort=col, dir=direction.lower())


@app.route("/orders/new", methods=["GET", "POST"])
@login_required("manager")
def order_new():
    if request.method == "POST":
        f, errors, items = request.form, [], []
        for pid, qty, disc in zip(f.getlist("product_id"), f.getlist("quantity"), f.getlist("discount")):
            if not pid:
                continue
            items.append({"product_id": to_num(pid, int, "Товар", errors, 1),
                          "quantity": to_num(qty, int, "Кількість", errors, 1, 1000),
                          "discount": (to_num(disc or "0", Decimal, "Знижка", errors, 0, 100) or 0) / 100})
        cust = to_num(f.get("customer_id"), int, "Клієнт", errors, 1)
        emp = to_num(f.get("employee_id"), int, "Менеджер", errors, 1, required=False)
        freight = to_num(f.get("freight") or "0", Decimal, "Доставка", errors, 0, 100000)
        if not items:
            errors.append("Додайте хоча б одну позицію")
        if not errors:
            try:
                row = run("SELECT create_order(%s,%s,%s,%s,%s::jsonb) AS id",
                          (cust, emp, f.get("ship_via") or "Нова Пошта", freight, json.dumps(items, default=float)), uid())
                flash(f"Замовлення №{row['id']} створено", "success")
                return redirect(url_for("order_detail", oid=row["id"]))
            except DBError as e:
                errors.append(str(e))
        show_errors(errors)
    return render_template(
        "order_new.html",
        customers=fetch("SELECT customer_id, COALESCE(company_name, contact_name) AS name FROM customers ORDER BY 2"),
        employees=fetch("SELECT employee_id, first_name || ' ' || last_name AS name FROM employees WHERE title ILIKE '%продаж%' ORDER BY 2"),
        products=fetch("SELECT product_id, product_name, unit_price, units_in_stock FROM products WHERE NOT discontinued ORDER BY 2"))


@app.route("/orders/<int:oid>")
@login_required()
def order_detail(oid):
    o = fetch("SELECT * FROM order_details WHERE order_id=%s", (oid,), one=True) or abort(404)
    full = fetch("SELECT * FROM orders WHERE order_id=%s", (oid,), one=True)
    items = fetch("""SELECT p.product_name, oi.quantity, oi.unit_price, oi.discount,
                            ROUND(oi.quantity*oi.unit_price*(1-oi.discount),2) AS line_total
                     FROM order_items oi JOIN products p ON p.product_id=oi.product_id WHERE oi.order_id=%s""", (oid,))
    return render_template("order_detail.html", o=o, full=full, items=items,
                           next_status=ORDER_FLOW.get(o["order_status"], []),
                           can_cancel=o["order_status"] in ("pending", "processing"),
                           can_delete=o["order_status"] in ("pending", "cancelled"))


@app.post("/orders/<int:oid>/status")
@login_required("manager")
def order_status(oid):
    new = request.form.get("status", "")
    try:
        if new == "cancelled":
            run("CALL cancel_order(%s)", (oid,), uid(), returning=False)
            flash("Замовлення скасовано, товар повернуто на склад", "success")
        elif new in ("processing", "shipped", "delivered"):
            run("UPDATE orders SET order_status=%s WHERE order_id=%s", (new, oid), uid(), returning=False)
            flash(f"Статус змінено на «{new}»", "success")
        else:
            flash("Невідомий статус", "error")
    except DBError as e:
        flash(str(e), "error")
    return redirect(url_for("order_detail", oid=oid))


@app.post("/orders/<int:oid>/delete")
@login_required("manager")
def order_delete(oid):
    try:
        run("SELECT delete_order(%s)", (oid,), uid(), returning=False)
        flash("Замовлення видалено", "success")
        return redirect(url_for("orders"))
    except DBError as e:
        flash(str(e), "error")
        return redirect(url_for("order_detail", oid=oid))


# ---------------- звіти PDF / Excel ----------------
def report_data(kind):
    if kind == "products":
        rows = fetch("""SELECT p.product_id, p.product_name, c.category_name, p.unit_price, p.units_in_stock
                        FROM products p JOIN categories c USING (category_id) ORDER BY c.category_name, p.product_name""")
        data = [list(r.values()) for r in rows]
        return ("Каталог товарів", ["ID", "Назва", "Категорія", "Ціна, грн", "Склад"], data, [40, 330, 200, 90, 60],
                {"Позицій": len(rows), "Вартість залишків, грн": sum(r["unit_price"] * r["units_in_stock"] for r in rows)})
    if kind == "sales":
        rows = fetch("SELECT * FROM monthly_sales_report")
        return ("Продажі за місяцями", ["Місяць", "Замовлень", "Клієнтів", "Одиниць", "Виручка, грн", "Сер. чек, грн"],
                [list(r.values()) for r in rows], None, {"Виручка всього, грн": sum(r["total_revenue"] for r in rows)})
    if kind == "employees":
        rows = fetch("SELECT full_name, title, city, orders_handled, sales_amount, avg_order_value "
                     "FROM employee_performance ORDER BY sales_amount DESC")
        return ("Ефективність співробітників", ["Співробітник", "Посада", "Місто", "Замовлень", "Продажі, грн", "Сер. чек, грн"],
                [list(r.values()) for r in rows], None, None)
    if kind == "orders":
        rows = fetch("""SELECT order_id, order_date, customer_name, employee_name, order_status, grand_total
                        FROM order_details ORDER BY order_id DESC""")
        return ("Замовлення", ["№", "Дата", "Клієнт", "Менеджер", "Статус", "Сума, грн"], [list(r.values()) for r in rows],
                None, {"Замовлень": len(rows), "Разом, грн": sum(r["grand_total"] for r in rows)})
    abort(404)


@app.route("/reports")
@login_required()
def reports_page():
    return render_template("reports.html")


@app.route("/reports/<kind>.<fmt>")
@login_required()
def report(kind, fmt):
    title, headers, rows, widths, summary = report_data(kind)
    run("SELECT log_activity(%s,'EXPORT','report',NULL,%s::jsonb)", (uid(), json.dumps({"kind": kind, "format": fmt})), uid())
    if fmt == "pdf":
        return Response(reports.make_pdf(title, headers, rows, summary, widths), mimetype="application/pdf",
                        headers={"Content-Disposition": f"inline; filename={kind}.pdf"})
    if fmt == "xlsx":
        return Response(reports.make_xlsx(title, headers, rows),
                        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename={kind}.xlsx"})
    abort(404)


# ---------------- адміністрування ----------------
@app.route("/admin/log")
@login_required("admin")
def activity_log():
    tbl, act = request.args.get("table", ""), request.args.get("action", "")
    where = "(%(t)s = '' OR table_name = %(t)s) AND (%(a)s = '' OR action = %(a)s)"
    params = dict(t=tbl, a=act)
    total = fetch(f"SELECT COUNT(*) AS n FROM activity_log WHERE {where}", params, one=True)["n"]
    page, pages = paginate(total)
    rows = fetch(f"""SELECT * FROM activity_log WHERE {where} ORDER BY log_id DESC
                     LIMIT {PER_PAGE * 2} OFFSET {(page - 1) * PER_PAGE * 2}""", params)
    return render_template("log.html", rows=rows, page=page, pages=max((total + PER_PAGE * 2 - 1) // (PER_PAGE * 2), 1), total=total)


@app.route("/admin/users", methods=["GET", "POST"])
@login_required("admin")
def users():
    if request.method == "POST":
        try:
            role = request.form.get("role")
            if role not in ROLE_RANK:
                raise DBError("Некоректна роль")
            if int(request.form["user_id"]) == uid():
                raise DBError("Не можна змінювати власну роль")
            run("UPDATE users SET role=%s, is_active=%s WHERE user_id=%s",
                (role, request.form.get("is_active") == "on", request.form["user_id"]), uid(), returning=False)
            flash("Користувача оновлено", "success")
        except (DBError, ValueError) as e:
            flash(str(e), "error")
        return redirect(url_for("users"))
    return render_template("users.html", rows=fetch("SELECT user_id, username, email, role, is_active, created_at FROM users ORDER BY 1"))


@app.route("/admin/backup", methods=["GET", "POST"])
@login_required("admin")
def backup_page():
    if request.method == "POST":
        try:
            path = backup.make_backup()
            run("SELECT log_activity(%s,'BACKUP','database',NULL,%s::jsonb)", (uid(), json.dumps({"file": os.path.basename(path)})), uid())
            flash(f"Резервну копію створено: {os.path.basename(path)}", "success")
        except Exception as e:  # noqa: BLE001
            flash(f"Помилка резервного копіювання: {e}", "error")
        return redirect(url_for("backup_page"))
    return render_template("backup.html", files=backup.list_backups())


@app.route("/admin/backup/<name>")
@login_required("admin")
def backup_download(name):
    if not re.fullmatch(r"technomart_\d{8}_\d{6}\.sql", name):   # захист від path traversal
        abort(404)
    path = os.path.join(backup.BACKUP_DIR, name)
    return send_file(path, as_attachment=True) if os.path.exists(path) else abort(404)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1", host="127.0.0.1", port=5000)
