-- queries.sql: SQL-запити різної складності для БД "ТехноМарт"

-- ===== 1. ПРОСТІ ЗАПИТИ З ФІЛЬТРАЦІЄЮ =====
-- Q1. Смартфони дорожчі за 20 000 грн, від найдорожчих
SELECT product_name, unit_price, units_in_stock
FROM products
WHERE category_id = 1 AND unit_price > 20000
ORDER BY unit_price DESC;

-- Q2. Замовлення, які ще не завершені
SELECT order_id, order_date, order_status, ship_city
FROM orders
WHERE order_status IN ('pending', 'processing', 'shipped')
ORDER BY order_date;

-- Q3. Клієнти-юридичні особи з Києва та Дніпра
SELECT company_name, contact_name, city
FROM customers
WHERE customer_type = 'company' AND city IN ('Київ', 'Дніпро')
ORDER BY city, company_name;

-- ===== 2. ЗАПИТИ З JOIN =====
-- Q4. Товари з категорією та постачальником
SELECT p.product_name, c.category_name, s.company_name AS supplier, s.city AS supplier_city
FROM products p
JOIN categories c ON c.category_id = p.category_id
JOIN suppliers  s ON s.supplier_id = p.supplier_id
ORDER BY c.category_name, p.product_name;

-- Q5. Повний склад замовлення №2 (4 таблиці)
SELECT o.order_id, COALESCE(cu.company_name, cu.contact_name) AS customer,
       p.product_name, oi.quantity, oi.unit_price, oi.discount,
       ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2) AS line_total
FROM orders o
JOIN customers   cu ON cu.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products    p  ON p.product_id = oi.product_id
WHERE o.order_id = 2;

-- Q6. Клієнти, які ще нічого не замовляли (LEFT JOIN + IS NULL)
SELECT c.customer_id, c.contact_name
FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;

-- Q7. Підлеглі та їхні керівники (self-join)
SELECT e.last_name || ' ' || e.first_name AS employee, e.title,
       m.last_name || ' ' || m.first_name AS manager
FROM employees e LEFT JOIN employees m ON m.employee_id = e.reports_to
ORDER BY m.last_name NULLS FIRST, e.last_name;

-- ===== 3. АГРЕГАТНІ ЗАПИТИ =====
-- Q8. Виручка за категоріями (без скасованих замовлень)
SELECT c.category_name, SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id AND o.order_status <> 'cancelled'
JOIN products p ON p.product_id = oi.product_id
JOIN categories c ON c.category_id = p.category_id
GROUP BY c.category_name
ORDER BY revenue DESC;

-- Q9. Регіони, де клієнти зробили понад 3 замовлення (HAVING)
SELECT r.region_name, COUNT(o.order_id) AS orders_count
FROM orders o
JOIN customers cu ON cu.customer_id = o.customer_id
JOIN regions r ON r.region_id = cu.region_id
GROUP BY r.region_name
HAVING COUNT(o.order_id) > 3
ORDER BY orders_count DESC;

-- Q10. Середня знижка та сума по кожному типу клієнтів
SELECT cu.customer_type, COUNT(DISTINCT o.order_id) AS orders,
       ROUND(AVG(oi.discount) * 100, 1) AS avg_discount_pct,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS revenue
FROM customers cu JOIN orders o ON o.customer_id = cu.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY cu.customer_type;

-- ===== 4. ПІДЗАПИТИ =====
-- Q11. Товари дорожчі за середню ціну своєї категорії (корельований підзапит)
SELECT p.product_name, p.unit_price, c.category_name
FROM products p JOIN categories c ON c.category_id = p.category_id
WHERE p.unit_price > (SELECT AVG(p2.unit_price) FROM products p2 WHERE p2.category_id = p.category_id)
ORDER BY c.category_name, p.unit_price DESC;

-- Q12. Клієнти, що купували ноутбуки (IN + підзапит)
SELECT DISTINCT contact_name, city FROM customers
WHERE customer_id IN (
    SELECT o.customer_id FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE oi.product_id IN (SELECT product_id FROM products WHERE category_id = 2));

-- Q13. Товари, які жодного разу не продавалися (NOT EXISTS)
SELECT product_name, units_in_stock FROM products p
WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.product_id = p.product_id);

-- ===== 5. СКЛАДНІ АНАЛІТИЧНІ ЗАПИТИ (CTE, віконні функції) =====
-- A1. Помісячна виручка, наростаючий підсумок та зміна до попереднього місяця
WITH monthly AS (
    SELECT date_trunc('month', order_date)::date AS month, SUM(items_total) AS revenue
    FROM order_totals WHERE order_status = 'delivered' GROUP BY 1)
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month) AS running_total,
       ROUND((revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0
             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS growth_pct
FROM monthly ORDER BY month;

-- A2. ТОП-3 товари в кожній категорії за виручкою (RANK у розрізі категорії)
WITH sales AS (
    SELECT c.category_name, p.product_name,
           SUM(oi.quantity * oi.unit_price * (1 - oi.discount)) AS revenue
    FROM order_items oi JOIN orders o ON o.order_id = oi.order_id AND o.order_status <> 'cancelled'
    JOIN products p ON p.product_id = oi.product_id JOIN categories c ON c.category_id = p.category_id
    GROUP BY c.category_name, p.product_name),
ranked AS (SELECT *, RANK() OVER (PARTITION BY category_name ORDER BY revenue DESC) AS rnk FROM sales)
SELECT category_name, product_name, ROUND(revenue, 2) AS revenue, rnk
FROM ranked WHERE rnk <= 3 ORDER BY category_name, rnk;

-- A3. ABC-аналіз клієнтів: частка у виручці та клас A (до 70 %), B (до 90 %), C
WITH cust AS (
    SELECT customer_id, contact_name, total_amount FROM customer_orders_summary WHERE total_amount > 0),
acc AS (
    SELECT *, SUM(total_amount) OVER (ORDER BY total_amount DESC) / SUM(total_amount) OVER () AS cum_share
    FROM cust)
SELECT contact_name, ROUND(total_amount, 2) AS total_amount, ROUND(cum_share * 100, 1) AS cum_share_pct,
       CASE WHEN cum_share <= 0.7 THEN 'A' WHEN cum_share <= 0.9 THEN 'B' ELSE 'C' END AS abc_class
FROM acc ORDER BY total_amount DESC;

-- A4. Середній час від замовлення до відправки по службах доставки
SELECT ship_via, COUNT(*) AS shipped_orders,
       ROUND(AVG(shipped_date - order_date), 1) AS avg_days_to_ship
FROM orders WHERE shipped_date IS NOT NULL
GROUP BY ship_via ORDER BY avg_days_to_ship;

-- ===== 6. ВИКОРИСТАННЯ ПРЕДСТАВЛЕНЬ І ПРОЦЕДУР =====
SELECT * FROM monthly_sales_report;
SELECT * FROM employee_performance ORDER BY sales_amount DESC;
SELECT * FROM low_stock_products;
SELECT * FROM customer_report(13);
