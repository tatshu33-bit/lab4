"""Дані для графіків (віддаються у JSON, малюються Chart.js на сторінці дашборду)."""
from database import fetch


def dashboard_stats():
    monthly = fetch("SELECT year_month, total_revenue FROM monthly_sales_report ORDER BY year_month")
    by_category = fetch("""
        SELECT c.category_name, ROUND(SUM(oi.quantity*oi.unit_price*(1-oi.discount)),2) AS revenue
        FROM order_items oi JOIN orders o ON o.order_id=oi.order_id AND o.order_status<>'cancelled'
        JOIN products p ON p.product_id=oi.product_id JOIN categories c ON c.category_id=p.category_id
        GROUP BY c.category_name ORDER BY revenue DESC""")
    top = fetch("SELECT product_name, total_revenue FROM product_sales_summary ORDER BY total_revenue DESC LIMIT 5")
    status = fetch("SELECT order_status, COUNT(*) AS cnt FROM orders GROUP BY order_status ORDER BY cnt DESC")
    return {
        "monthly": {"labels": [r["year_month"] for r in monthly], "values": [float(r["total_revenue"]) for r in monthly]},
        "category": {"labels": [r["category_name"] for r in by_category], "values": [float(r["revenue"]) for r in by_category]},
        "top_products": {"labels": [r["product_name"] for r in top], "values": [float(r["total_revenue"]) for r in top]},
        "status": {"labels": [r["order_status"] for r in status], "values": [r["cnt"] for r in status]},
    }


def kpis():
    return fetch("""SELECT
        (SELECT COALESCE(SUM(items_total),0) FROM order_totals WHERE order_status='delivered') AS revenue,
        (SELECT COUNT(*) FROM orders) AS orders,
        (SELECT COUNT(*) FROM customers) AS customers,
        (SELECT COUNT(*) FROM low_stock_products) AS low_stock,
        (SELECT COUNT(*) FROM orders WHERE order_status IN ('pending','processing')) AS active_orders""", one=True)
