-- 08: індекси та оптимізація (рівень 3)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Індекси на зовнішніх ключах (PostgreSQL не створює їх автоматично)
CREATE INDEX idx_products_category   ON products(category_id);
CREATE INDEX idx_products_supplier   ON products(supplier_id);
CREATE INDEX idx_orders_employee     ON orders(employee_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);   -- order_id покриває UNIQUE(order_id, product_id)
CREATE INDEX idx_customers_region    ON customers(region_id);
CREATE INDEX idx_employees_reports   ON employees(reports_to);

-- Складений індекс: історія замовлень клієнта від нових до старих
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date DESC);
-- Частковий індекс: лише активні замовлення (невелика частка таблиці)
CREATE INDEX idx_orders_active ON orders(order_date) WHERE order_status IN ('pending', 'processing');
-- Частковий індекс для звіту про низькі залишки
CREATE INDEX idx_products_low_stock ON products(units_in_stock) WHERE NOT discontinued;
CREATE INDEX idx_products_price ON products(unit_price);
-- Пошук ILIKE '%текст%' по назві/імені (trigram GIN)
CREATE INDEX idx_products_name_trgm  ON products  USING gin (product_name gin_trgm_ops);
CREATE INDEX idx_customers_name_trgm ON customers USING gin (contact_name gin_trgm_ops);
-- Журнал дій
CREATE INDEX idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX idx_activity_record  ON activity_log(table_name, record_id);
CREATE INDEX idx_price_history_product ON product_price_history(product_id, changed_at DESC);
-- Примітка: окремий індекс по customers.email не потрібен - UNIQUE вже створює індекс.
