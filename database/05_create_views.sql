-- 05: представлення (рівень 2)
-- Підсумки замовлень обчислюються один раз, щоб уникнути множення рядків при JOIN з order_items
CREATE OR REPLACE VIEW order_totals AS
SELECT o.order_id, o.customer_id, o.employee_id, o.order_date, o.order_status, o.freight,
       COALESCE(SUM(oi.quantity), 0)                                           AS items_qty,
       COALESCE(ROUND(SUM(oi.unit_price * oi.quantity * (1 - oi.discount)), 2), 0) AS items_total
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.order_id;

CREATE OR REPLACE VIEW customer_orders_summary AS
SELECT c.customer_id, c.contact_name, c.company_name, c.customer_type, c.city, r.region_name,
       COUNT(ot.order_id)                    AS total_orders,
       COALESCE(SUM(ot.items_total), 0)      AS total_amount,
       MAX(ot.order_date)                    AS last_order_date
FROM customers c
LEFT JOIN regions r ON r.region_id = c.region_id
LEFT JOIN order_totals ot ON ot.customer_id = c.customer_id AND ot.order_status <> 'cancelled'
GROUP BY c.customer_id, c.contact_name, c.company_name, c.customer_type, c.city, r.region_name;

CREATE OR REPLACE VIEW product_sales_summary AS
SELECT p.product_id, p.product_name, c.category_name, s.company_name AS supplier_name,
       p.unit_price, p.units_in_stock,
       COALESCE(x.total_sold, 0)    AS total_sold,
       COALESCE(x.total_revenue, 0) AS total_revenue,
       COALESCE(x.order_count, 0)   AS order_count
FROM products p
LEFT JOIN categories c ON c.category_id = p.category_id
LEFT JOIN suppliers  s ON s.supplier_id = p.supplier_id
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS total_sold,
           ROUND(SUM(oi.unit_price * oi.quantity * (1 - oi.discount)), 2) AS total_revenue,
           COUNT(DISTINCT oi.order_id) AS order_count
    FROM order_items oi JOIN orders o ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY oi.product_id
) x ON x.product_id = p.product_id;

CREATE OR REPLACE VIEW monthly_sales_report AS
SELECT TO_CHAR(order_date, 'YYYY-MM')       AS year_month,
       COUNT(*)                             AS orders_count,
       COUNT(DISTINCT customer_id)          AS unique_customers,
       SUM(items_qty)::BIGINT              AS total_items,
       SUM(items_total)                     AS total_revenue,
       ROUND(AVG(items_total), 2)           AS avg_order_value
FROM order_totals
WHERE order_status = 'delivered'
GROUP BY TO_CHAR(order_date, 'YYYY-MM')
ORDER BY year_month;

CREATE OR REPLACE VIEW employee_performance AS
SELECT e.employee_id, e.first_name || ' ' || e.last_name AS full_name, e.title, e.city,
       COUNT(ot.order_id)                    AS orders_handled,
       COALESCE(SUM(ot.items_total), 0)      AS sales_amount,
       COALESCE(ROUND(AVG(ot.items_total), 2), 0) AS avg_order_value
FROM employees e
LEFT JOIN order_totals ot ON ot.employee_id = e.employee_id AND ot.order_status <> 'cancelled'
GROUP BY e.employee_id, e.first_name, e.last_name, e.title, e.city;

CREATE OR REPLACE VIEW low_stock_products AS
SELECT p.product_id, p.product_name, c.category_name, p.units_in_stock, p.reorder_level, p.units_on_order,
       s.company_name AS supplier_name, s.phone AS supplier_phone
FROM products p
JOIN categories c ON c.category_id = p.category_id
LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
WHERE NOT p.discontinued AND p.units_in_stock <= p.reorder_level + 2;

-- Детальний список замовлень для вебзастосунку
CREATE OR REPLACE VIEW order_details AS
SELECT ot.order_id, ot.order_date, ot.order_status, ot.items_qty, ot.freight, ot.items_total,
       ot.items_total + ot.freight AS grand_total,
       c.customer_id, COALESCE(c.company_name, c.contact_name) AS customer_name,
       e.first_name || ' ' || e.last_name AS employee_name
FROM order_totals ot
JOIN customers c ON c.customer_id = ot.customer_id
LEFT JOIN employees e ON e.employee_id = ot.employee_id;
