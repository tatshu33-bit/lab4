"""Консольний застосунок «ТехноМарт»: CRUD для товарів, клієнтів і замовлень + звіти."""
import json
from database import Database


# ---------- допоміжні функції ----------
def print_table(rows, cols, widths=None):
    if not rows:
        print("   (даних немає)")
        return
    widths = widths or [min(max(len(str(c)), *(len(str(r[i])) for r in rows)), 38) for i, c in enumerate(cols)]
    line = "-" * (sum(widths) + 2 * len(widths))
    print(line)
    print("  ".join(f"{str(c):<{w}}" for c, w in zip(cols, widths)))
    print(line)
    for r in rows:
        print("  ".join(f"{str(v if v is not None else '')[:w]:<{w}}" for v, w in zip(r, widths)))
    print(line)


def ask(prompt, cast=str, required=True, default=None):
    """Запитує значення, повторює ввід при помилці."""
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw:
            if default is not None:
                return default
            if not required:
                return None
            print("  Поле обов'язкове.")
            continue
        try:
            return cast(raw)
        except ValueError:
            print("  Некоректне значення, спробуйте ще раз.")


# ---------- ТОВАРИ ----------
def list_products(db, search=None):
    sql = """SELECT p.product_id, p.product_name, c.category_name, p.unit_price, p.units_in_stock
             FROM products p JOIN categories c USING (category_id)
             WHERE (%(s)s IS NULL OR p.product_name ILIKE %(like)s)
             ORDER BY p.product_id"""
    rows, cols = db.query(sql, {"s": search, "like": f"%{search}%"})
    print_table(rows, ["ID", "Назва", "Категорія", "Ціна", "Склад"], [4, 40, 28, 10, 6])


def add_product(db):
    rows, _ = db.query("SELECT category_id, category_name FROM categories ORDER BY 1")
    print_table(rows, ["ID", "Категорія"])
    name = ask("Назва")
    cat = ask("ID категорії", int)
    rows, _ = db.query("SELECT supplier_id, company_name FROM suppliers ORDER BY 1")
    print_table(rows, ["ID", "Постачальник"])
    sup = ask("ID постачальника", int)
    price = ask("Ціна, грн", float)
    stock = ask("Кількість на складі", int, default=0)
    ok, row = db.execute(
        """INSERT INTO products (product_name, category_id, supplier_id, unit_price, units_in_stock)
           VALUES (%s,%s,%s,%s,%s) RETURNING product_id""", (name, cat, sup, price, stock))
    if ok:
        print(f"✅ Товар додано, ID = {row[0]}")


def update_product(db):
    list_products(db)
    pid = ask("ID товару для зміни", int)
    price = ask("Нова ціна (Enter - без змін)", float, required=False)
    stock = ask("Новий залишок (Enter - без змін)", int, required=False)
    ok, row = db.execute(
        """UPDATE products SET unit_price = COALESCE(%s, unit_price), units_in_stock = COALESCE(%s, units_in_stock)
           WHERE product_id = %s RETURNING product_id""", (price, stock, pid))
    print("✅ Оновлено" if ok and row else "⚠️  Товар не знайдено" if ok else "")


def delete_product(db):
    list_products(db)
    pid = ask("ID товару для видалення", int)
    if input("Підтвердьте видалення (так/ні): ").lower() != "так":
        return
    ok, row = db.execute("DELETE FROM products WHERE product_id=%s RETURNING product_id", (pid,))
    print("✅ Видалено" if ok and row else "⚠️  Товар не знайдено" if ok else "")


# ---------- КЛІЄНТИ ----------
def list_customers(db):
    rows, _ = db.query("""SELECT customer_id, COALESCE(company_name, contact_name), customer_type, city, email,
                                 total_orders, ROUND(total_amount, 2) FROM customer_orders_summary ORDER BY 1""")
    print_table(rows, ["ID", "Клієнт", "Тип", "Місто", "Email", "Замовл.", "Сума"], [4, 30, 11, 10, 30, 7, 12])


def add_customer(db):
    ctype = ask("Тип (individual/company)", str, default="individual")
    company = ask("Назва компанії", required=(ctype == "company")) if ctype == "company" else None
    name = ask("Контактна особа (ПІБ)")
    city = ask("Місто", required=False)
    email = ask("Email", required=False)
    phone = ask("Телефон", required=False)
    ok, row = db.execute(
        """INSERT INTO customers (customer_type, company_name, contact_name, city, email, phone)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING customer_id""", (ctype, company, name, city, email, phone))
    if ok:
        print(f"✅ Клієнта додано, ID = {row[0]}")


def update_customer(db):
    list_customers(db)
    cid = ask("ID клієнта", int)
    phone = ask("Новий телефон (Enter - без змін)", required=False)
    city = ask("Нове місто (Enter - без змін)", required=False)
    ok, row = db.execute(
        """UPDATE customers SET phone = COALESCE(%s, phone), city = COALESCE(%s, city)
           WHERE customer_id=%s RETURNING customer_id""", (phone, city, cid))
    print("✅ Оновлено" if ok and row else "⚠️  Клієнта не знайдено" if ok else "")


def delete_customer(db):
    list_customers(db)
    cid = ask("ID клієнта для видалення", int)
    if input("Підтвердьте (так/ні): ").lower() != "так":
        return
    ok, row = db.execute("DELETE FROM customers WHERE customer_id=%s RETURNING customer_id", (cid,))
    print("✅ Видалено" if ok and row else "⚠️  Клієнта не знайдено" if ok else "")


# ---------- ЗАМОВЛЕННЯ ----------
def list_orders(db):
    rows, _ = db.query("""SELECT order_id, order_date, customer_name, employee_name, order_status, grand_total
                          FROM order_details ORDER BY order_id DESC LIMIT 30""")
    print_table(rows, ["ID", "Дата", "Клієнт", "Менеджер", "Статус", "Разом, грн"], [4, 10, 28, 20, 10, 12])


def show_order(db):
    oid = ask("ID замовлення", int)
    rows, _ = db.query("""SELECT p.product_name, oi.quantity, oi.unit_price, oi.discount,
                                 ROUND(oi.quantity*oi.unit_price*(1-oi.discount),2)
                          FROM order_items oi JOIN products p USING (product_id) WHERE oi.order_id=%s""", (oid,))
    print_table(rows, ["Товар", "К-сть", "Ціна", "Знижка", "Сума"], [40, 6, 10, 7, 12])


def create_order(db):
    list_customers(db)
    cust = ask("ID клієнта", int)
    emp = ask("ID менеджера", int, default=2)
    via = ask("Доставка", str, default="Нова Пошта")
    items = []
    list_products(db)
    print("Додавайте позиції (порожній ID - завершити)")
    while True:
        pid = ask("  ID товару", int, required=False)
        if pid is None:
            break
        qty = ask("  Кількість", int, default=1)
        disc = ask("  Знижка (0..1)", float, default=0)
        items.append({"product_id": pid, "quantity": qty, "discount": disc})
    ok, row = db.execute("SELECT create_order(%s,%s,%s,%s,%s::jsonb)", (cust, emp, via, 150, json.dumps(items)))
    if ok:
        print(f"✅ Замовлення створено, ID = {row[0]}")


def change_status(db):
    oid = ask("ID замовлення", int)
    st = ask("Новий статус (processing/shipped/delivered)", str)
    ok, row = db.execute("UPDATE orders SET order_status=%s WHERE order_id=%s RETURNING order_id", (st, oid))
    print("✅ Статус змінено" if ok and row else "⚠️  Замовлення не знайдено" if ok else "")


def cancel_order(db):
    oid = ask("ID замовлення для скасування", int)
    ok, _ = db.execute("CALL cancel_order(%s)", (oid,))
    print("✅ Замовлення скасовано, товар повернуто на склад" if ok else "")


# ---------- ЗВІТИ ----------
def reports(db):
    print("1. Місячні продажі  2. Ефективність менеджерів  3. Низькі залишки  4. Звіт по клієнту  5. ТОП товарів")
    ch = input("Оберіть звіт: ")
    if ch == "1":
        rows, cols = db.query("SELECT * FROM monthly_sales_report"); print_table(rows, cols)
    elif ch == "2":
        rows, cols = db.query("SELECT full_name, title, orders_handled, sales_amount FROM employee_performance ORDER BY 4 DESC")
        print_table(rows, ["Менеджер", "Посада", "Замовл.", "Продажі"])
    elif ch == "3":
        rows, cols = db.query("SELECT product_name, units_in_stock, reorder_level, supplier_name FROM low_stock_products")
        print_table(rows, ["Товар", "Склад", "Мін.", "Постачальник"])
    elif ch == "4":
        cid = ask("ID клієнта", int)
        rows, cols = db.query("SELECT * FROM customer_report(%s)", (cid,)); print_table(rows, cols)
    elif ch == "5":
        rows, cols = db.query("SELECT product_name, total_sold, total_revenue FROM product_sales_summary ORDER BY total_revenue DESC LIMIT 5")
        print_table(rows, ["Товар", "Продано", "Виручка"])


MENU = """
================ ТЕХНОМАРТ ================
 ТОВАРИ                  КЛІЄНТИ               ЗАМОВЛЕННЯ
 1. Список               5. Список             9.  Список
 2. Пошук                6. Додати             10. Деталі замовлення
 3. Додати / змінити     7. Змінити            11. Створити
 4. Видалити             8. Видалити           12. Змінити статус / 13. Скасувати
 14. Звіти                                     0.  Вихід
==========================================="""


def main():
    db = Database()
    if not db.connect():
        return
    actions = {
        "1": list_products, "2": lambda d: list_products(d, ask("Пошук")),
        "3": lambda d: (add_product(d) if input("a - додати, u - змінити: ") == "a" else update_product(d)),
        "4": delete_product, "5": list_customers, "6": add_customer, "7": update_customer,
        "8": delete_customer, "9": list_orders, "10": show_order, "11": create_order,
        "12": change_status, "13": cancel_order, "14": reports,
    }
    try:
        while True:
            print(MENU)
            ch = input("Ваш вибір: ").strip()
            if ch == "0":
                break
            action = actions.get(ch)
            if action:
                action(db)
            else:
                print("❌ Невірна опція")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
