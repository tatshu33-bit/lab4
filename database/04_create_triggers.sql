-- 04: тригери (рівень 2). Створюються ПІСЛЯ завантаження тестових даних,
-- щоб історичні позиції не змінювали залишки на складі.

-- Тригер 1: автоматичне ведення залишків при зміні позицій замовлення
CREATE OR REPLACE FUNCTION fn_order_items_stock() RETURNS TRIGGER AS $$
DECLARE v_stock INT; v_status VARCHAR;
BEGIN
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        -- у разі UPDATE спочатку повертаємо старе
        IF TG_OP = 'UPDATE' THEN
            UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
        END IF;
        SELECT units_in_stock INTO v_stock FROM products WHERE product_id = NEW.product_id FOR UPDATE;
        IF v_stock < NEW.quantity THEN
            RAISE EXCEPTION 'Недостатньо товару (ID %) на складі: є %, потрібно %',
                NEW.product_id, v_stock, NEW.quantity;
        END IF;
        UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id;
        RETURN NEW;
    ELSE
        SELECT order_status INTO v_status FROM orders WHERE order_id = OLD.order_id;
        IF v_status IS DISTINCT FROM 'cancelled' THEN      -- скасоване вже повернуло товар
            UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
        END IF;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_items_stock
AFTER INSERT OR UPDATE OF quantity, product_id OR DELETE ON order_items
FOR EACH ROW EXECUTE FUNCTION fn_order_items_stock();

-- Тригер 2: контроль переходів статусів замовлення + автоматична дата відправки
CREATE OR REPLACE FUNCTION fn_orders_status_guard() RETURNS TRIGGER AS $$
DECLARE
    rank_old INT; rank_new INT;
BEGIN
    IF NEW.order_status = OLD.order_status THEN RETURN NEW; END IF;

    IF OLD.order_status IN ('delivered', 'cancelled') THEN
        RAISE EXCEPTION 'Статус "%" є кінцевим, змінити його неможливо', OLD.order_status;
    END IF;
    IF NEW.order_status = 'cancelled' THEN
        IF OLD.order_status NOT IN ('pending', 'processing') THEN
            RAISE EXCEPTION 'Відправлене замовлення скасувати не можна';
        END IF;
        RETURN NEW;
    END IF;

    rank_old := array_position(ARRAY['pending','processing','shipped','delivered'], OLD.order_status);
    rank_new := array_position(ARRAY['pending','processing','shipped','delivered'], NEW.order_status);
    IF rank_new < rank_old THEN
        RAISE EXCEPTION 'Неможливо повернути статус з "%" на "%"', OLD.order_status, NEW.order_status;
    END IF;

    IF NEW.order_status IN ('shipped', 'delivered') AND NEW.shipped_date IS NULL THEN
        NEW.shipped_date := GREATEST(CURRENT_DATE, NEW.order_date);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_status_guard
BEFORE UPDATE OF order_status ON orders
FOR EACH ROW EXECUTE FUNCTION fn_orders_status_guard();

-- Тригер 3: повернення товару на склад при скасуванні замовлення
CREATE OR REPLACE FUNCTION fn_orders_cancel_restock() RETURNS TRIGGER AS $$
BEGIN
    UPDATE products p
    SET units_in_stock = p.units_in_stock + oi.quantity
    FROM order_items oi
    WHERE oi.order_id = NEW.order_id AND p.product_id = oi.product_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_cancel_restock
AFTER UPDATE OF order_status ON orders
FOR EACH ROW WHEN (NEW.order_status = 'cancelled' AND OLD.order_status <> 'cancelled')
EXECUTE FUNCTION fn_orders_cancel_restock();

-- Тригер 4: аудит зміни цін
CREATE OR REPLACE FUNCTION fn_products_price_audit() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO product_price_history (product_id, old_price, new_price)
    VALUES (NEW.product_id, OLD.unit_price, NEW.unit_price);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_products_price_audit
AFTER UPDATE OF unit_price ON products
FOR EACH ROW WHEN (OLD.unit_price IS DISTINCT FROM NEW.unit_price)
EXECUTE FUNCTION fn_products_price_audit();
