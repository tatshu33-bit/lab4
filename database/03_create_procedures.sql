-- 03: збережені процедури та функції (рівень 2)

-- Процедура 1: створення замовлення з кількома позиціями (атомарно)
-- p_items: [{"product_id":1,"quantity":2,"discount":0.05}, ...]
CREATE OR REPLACE FUNCTION create_order(
    p_customer_id INT,
    p_employee_id INT,
    p_ship_via    VARCHAR,
    p_freight     DECIMAL,
    p_items       JSONB
) RETURNS INT AS $$
DECLARE
    v_cust     customers%ROWTYPE;
    v_order_id INT;
    v_item     JSONB;
    v_prod     products%ROWTYPE;
    v_qty      INT;
    v_disc     DECIMAL(4,2);
BEGIN
    SELECT * INTO v_cust FROM customers WHERE customer_id = p_customer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Клієнта з ID % не існує', p_customer_id USING ERRCODE = 'P0002';
    END IF;
    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'Замовлення має містити хоча б одну позицію';
    END IF;

    INSERT INTO orders (customer_id, employee_id, order_date, required_date, ship_via, freight,
                        ship_name, ship_address, ship_city, ship_region_id, ship_postal_code, order_status)
    VALUES (p_customer_id, p_employee_id, CURRENT_DATE, CURRENT_DATE + 4, p_ship_via, COALESCE(p_freight, 0),
            COALESCE(v_cust.company_name, v_cust.contact_name), v_cust.address, v_cust.city,
            v_cust.region_id, v_cust.postal_code, 'pending')
    RETURNING order_id INTO v_order_id;

    FOR v_item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
        v_qty  := (v_item->>'quantity')::INT;
        v_disc := COALESCE((v_item->>'discount')::DECIMAL, 0);

        SELECT * INTO v_prod FROM products
        WHERE product_id = (v_item->>'product_id')::INT FOR UPDATE;   -- блокування рядка товару

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Товару з ID % не існує', v_item->>'product_id';
        END IF;
        IF v_prod.discontinued THEN
            RAISE EXCEPTION 'Товар "%" знято з продажу', v_prod.product_name;
        END IF;
        IF v_prod.units_in_stock < v_qty THEN
            RAISE EXCEPTION 'Недостатньо товару "%" на складі: є %, потрібно %',
                v_prod.product_name, v_prod.units_in_stock, v_qty;
        END IF;

        INSERT INTO order_items (order_id, product_id, unit_price, quantity, discount)
        VALUES (v_order_id, v_prod.product_id, v_prod.unit_price, v_qty, v_disc);
        -- залишок на складі зменшує тригер trg_order_items_stock
    END LOOP;

    RETURN v_order_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'Один товар не можна додати до замовлення двічі';
    WHEN check_violation THEN
        RAISE EXCEPTION 'Некоректна кількість або знижка у позиції замовлення';
END;
$$ LANGUAGE plpgsql;

-- Процедура 2: зміна цін усієї категорії на відсоток (історія пишеться тригером)
CREATE OR REPLACE FUNCTION change_category_prices(p_category_id INT, p_percent DECIMAL)
RETURNS INT AS $$
DECLARE v_count INT;
BEGIN
    IF p_percent < -90 OR p_percent > 100 THEN
        RAISE EXCEPTION 'Відсоток зміни ціни має бути в межах від -90 до 100';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM categories WHERE category_id = p_category_id) THEN
        RAISE EXCEPTION 'Категорії з ID % не існує', p_category_id;
    END IF;
    UPDATE products
    SET unit_price = ROUND(unit_price * (1 + p_percent / 100), 2)
    WHERE category_id = p_category_id AND NOT discontinued;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Процедура 3: зведений звіт по клієнту
CREATE OR REPLACE FUNCTION customer_report(p_customer_id INT)
RETURNS TABLE(orders_count BIGINT, total_spent NUMERIC, avg_order NUMERIC,
              first_order DATE, last_order DATE, favorite_category TEXT) AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = p_customer_id) THEN
        RAISE EXCEPTION 'Клієнта з ID % не існує', p_customer_id;
    END IF;
    RETURN QUERY
    WITH t AS (
        SELECT o.order_id, o.order_date,
               SUM(oi.unit_price * oi.quantity * (1 - oi.discount)) AS amount
        FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.customer_id = p_customer_id AND o.order_status <> 'cancelled'
        GROUP BY o.order_id, o.order_date
    ), fav AS (
        SELECT c.category_name
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p ON p.product_id = oi.product_id
        JOIN categories c ON c.category_id = p.category_id
        WHERE o.customer_id = p_customer_id AND o.order_status <> 'cancelled'
        GROUP BY c.category_name
        ORDER BY SUM(oi.quantity) DESC, c.category_name LIMIT 1
    )
    SELECT COUNT(*), COALESCE(ROUND(SUM(t.amount),2),0), COALESCE(ROUND(AVG(t.amount),2),0),
           MIN(t.order_date), MAX(t.order_date), (SELECT category_name FROM fav)::TEXT
    FROM t;
END;
$$ LANGUAGE plpgsql;

-- Процедура 4 (CREATE PROCEDURE): скасування замовлення; склад повертає тригер
CREATE OR REPLACE PROCEDURE cancel_order(p_order_id INT)
LANGUAGE plpgsql AS $$
DECLARE v_status VARCHAR;
BEGIN
    SELECT order_status INTO v_status FROM orders WHERE order_id = p_order_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Замовлення % не знайдено', p_order_id;
    END IF;
    IF v_status NOT IN ('pending', 'processing') THEN
        RAISE EXCEPTION 'Замовлення % у статусі "%" скасувати не можна', p_order_id, v_status;
    END IF;
    UPDATE orders SET order_status = 'cancelled' WHERE order_id = p_order_id;
END;
$$;

-- Процедура 5: видалення замовлення (лише pending/cancelled)
CREATE OR REPLACE FUNCTION delete_order(p_order_id INT) RETURNS VOID AS $$
DECLARE v_status VARCHAR;
BEGIN
    SELECT order_status INTO v_status FROM orders WHERE order_id = p_order_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Замовлення % не знайдено', p_order_id;
    END IF;
    IF v_status NOT IN ('pending', 'cancelled') THEN
        RAISE EXCEPTION 'Видалити можна лише замовлення зі статусом pending або cancelled (зараз: %)', v_status;
    END IF;
    DELETE FROM order_items WHERE order_id = p_order_id;  -- тригер поверне товар на склад
    DELETE FROM orders WHERE order_id = p_order_id;
END;
$$ LANGUAGE plpgsql;
