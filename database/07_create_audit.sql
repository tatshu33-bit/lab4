-- 07: логування всіх операцій з даними (рівень 3)
-- Вебзастосунок перед змінами виконує set_config('app.user_id', ..., true) - тригер бере user_id звідти.
CREATE TABLE activity_log (
    log_id     BIGSERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    username   VARCHAR(50),
    action     VARCHAR(20) NOT NULL,          -- INSERT / UPDATE / DELETE / LOGIN / EXPORT ...
    table_name VARCHAR(50),
    record_id  INTEGER,
    details    JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION log_activity(p_user_id INT, p_action VARCHAR, p_table VARCHAR,
                                        p_record_id INT, p_details JSONB DEFAULT NULL) RETURNS VOID AS $$
    INSERT INTO activity_log (user_id, username, action, table_name, record_id, details)
    VALUES (p_user_id, (SELECT username FROM users WHERE user_id = p_user_id), p_action, p_table, p_record_id, p_details);
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION fn_audit_row() RETURNS TRIGGER AS $$
DECLARE
    v_pk TEXT := TG_ARGV[0];
    v_uid INT := NULLIF(current_setting('app.user_id', true), '')::INT;
    v_details JSONB; v_rec JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_rec := to_jsonb(NEW); v_details := v_rec;
    ELSIF TG_OP = 'DELETE' THEN
        v_rec := to_jsonb(OLD); v_details := v_rec;
    ELSE
        v_rec := to_jsonb(NEW);
        SELECT jsonb_object_agg(n.key, jsonb_build_object('old', o.value, 'new', n.value))
          INTO v_details
        FROM jsonb_each(v_rec) n JOIN jsonb_each(to_jsonb(OLD)) o ON o.key = n.key
        WHERE n.value IS DISTINCT FROM o.value AND n.key <> 'units_in_stock';  -- залишки змінюються автоматично
        IF v_details IS NULL THEN RETURN NEW; END IF;
    END IF;
    PERFORM log_activity(v_uid, TG_OP::VARCHAR, TG_TABLE_NAME::VARCHAR, (v_rec->>v_pk)::INT, v_details);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_products    AFTER INSERT OR UPDATE OR DELETE ON products    FOR EACH ROW EXECUTE FUNCTION fn_audit_row('product_id');
CREATE TRIGGER trg_audit_customers   AFTER INSERT OR UPDATE OR DELETE ON customers   FOR EACH ROW EXECUTE FUNCTION fn_audit_row('customer_id');
CREATE TRIGGER trg_audit_orders      AFTER INSERT OR UPDATE OR DELETE ON orders      FOR EACH ROW EXECUTE FUNCTION fn_audit_row('order_id');
CREATE TRIGGER trg_audit_order_items AFTER INSERT OR UPDATE OR DELETE ON order_items FOR EACH ROW EXECUTE FUNCTION fn_audit_row('order_item_id');
